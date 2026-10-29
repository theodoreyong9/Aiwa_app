package com.aiwa.app.voice
import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aiwa.client.WakeWords
import org.json.JSONObject
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.Recognizer

/**
 * "Mon mot d'éveil": the person chooses the word that wakes the listening, any word, by SAYING it (three tries) and not by writing it. The detector's grammar only holds words of the
 * small French model ("Aiwa" is not one), so what is kept is how the engine WRITES the word it hears (WakeWords): "ail oua", "ai oua"… Those spellings are checked (not too short, not
 * a common word that would wake the phone all day), shown, and kept only once the person confirms. A test says how many tries of the word are recognised.
 *
 * The always-on listening is put aside while this window is open (one microphone, one model) and given back when it is closed.
 */
class WakeWordEnrollActivity : ComponentActivity() {
    // the word being chosen: "call" (the call of the super agent), "stop" or "off" (intent extra "slot")
    private val slot: String by lazy { intent.getStringExtra("slot") ?: "call" }
    private val main = Handler(Looper.getMainLooper())
    private var model: Model? = null
    private var wasListening = false
    private val heard = mutableListOf<String>()
    private var pending: List<String> = emptyList()
    private var tests = 0
    private var recognised = 0
    private var busy = false

    private lateinit var status: TextView
    private lateinit var name: EditText
    private lateinit var say: Button
    private lateinit var save: Button
    private lateinit var test: Button
    private lateinit var reset: Button

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) loadModel() else show("Le micro est refusé : sans lui je ne peux pas entendre ton mot.")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wasListening = ListenSettings.enabled(this)
        VoiceService.stop(this)                      // one microphone: the listening gives it up while the word is chosen
        buildScreen()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) { override fun handleOnBackPressed() { closeAndResume() } })
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) loadModel() else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun buildScreen() {
        val column = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(24), dp(20), dp(24)) }
        fun text(t: String, size: Float, bold: Boolean = false) = TextView(this).apply { text = t; textSize = size; if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD); setPadding(0, dp(6), 0, dp(6)) }
        val recognition = Words.slot(slot)
        column.addView(text("Mon mot : " + (recognition?.label ?: "réveil"), 22f, true))
        recognition?.let { column.addView(text(it.help, 14f)) }
        column.addView(text("Dis ton mot trois fois, distinctement. Le téléphone garde la façon dont il l'entend : ça marche pour n'importe quel mot, même « Aiwa ». Tout reste sur le téléphone.", 15f))
        name = EditText(this).apply { hint = "Comment l'appeler à l'écran (facultatif)"; inputType = InputType.TYPE_CLASS_TEXT; setText(Words.name(this@WakeWordEnrollActivity, slot)) }
        column.addView(name)
        status = text("Je prépare le modèle vocal…", 16f)
        column.addView(status)
        say = Button(this).apply { text = "Dire mon mot (1/3)"; isEnabled = false; setOnClickListener { sayWord() } }
        save = Button(this).apply { text = "Enregistrer ce mot"; visibility = View.GONE; setOnClickListener { saveWord() } }
        test = Button(this).apply { text = "Tester mon mot"; visibility = if (Words.variants(this@WakeWordEnrollActivity, slot).isEmpty()) View.GONE else View.VISIBLE; isEnabled = false; setOnClickListener { testWord() } }
        reset = Button(this).apply {
            val origin = recognition?.defaults?.joinToString(" / ") { "« $it »" } ?: "« mon super agent »"
            text = "Remettre $origin"
            setOnClickListener { Words.clear(this@WakeWordEnrollActivity, slot); name.setText(""); test.visibility = View.GONE; Words.changed(this@WakeWordEnrollActivity); show("C'est de nouveau $origin.") }
        }
        val pause = android.widget.CheckBox(this).apply {
            text = "Ne pas écouter pendant qu'un son ou une vidéo joue (la vidéo n'est plus mise en pause par le micro ; le mot d'éveil ne marche alors pas pendant la lecture)"
            isChecked = Words.pauseOnMedia(this@WakeWordEnrollActivity)
            setOnCheckedChangeListener { _, on -> Words.setPauseOnMedia(this@WakeWordEnrollActivity, on) }
        }
        column.addView(pause)
        val close = Button(this).apply { text = "Fermer"; setOnClickListener { closeAndResume() } }
        for (b in listOf(say, save, test, reset, close)) column.addView(b)
        setContentView(ScrollView(this).apply { addView(column) })
        val own = Words.variants(this, slot)
        if (own.isNotEmpty()) show("Mot actuel : « " + Words.name(this, slot).ifEmpty { own.first() } + " » (entendu : " + own.joinToString(" / ") + ")")
    }

    private fun show(message: String) { main.post { status.text = message } }

    private fun loadModel() {
        if (!VoskModelStore.isReady(this)) { show("Le modèle vocal n'est pas encore sur le téléphone : active d'abord « Écoute permanente » dans l'écran principal (il se télécharge une fois), puis reviens ici."); return }
        Thread({
            try {
                LibVosk.setLogLevel(LogLevel.WARNINGS)
                model = Model(VoskModelStore.dir(this).absolutePath)
                main.post { say.isEnabled = true; test.isEnabled = true; if (Words.variants(this, slot).isEmpty()) show("Prêt. Appuie sur « Dire mon mot » et parle.") }
            } catch (err: Throwable) { show("Le modèle vocal ne s'ouvre pas : ${err.message}") }
        }, "aiwa-enroll-model").start()
    }

    /** Listens for a few seconds and gives back what the engine wrote; with a grammar (the test) only the words it holds can come out. */
    @android.annotation.SuppressLint("MissingPermission")
    private fun hear(grammar: String?, seconds: Int = 4): String {
        val current = model ?: return ""
        val rate = 16_000
        val minimum = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minimum <= 0) return ""
        val record = try { AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimum, 8192)) } catch (err: Exception) { return "" }
        if (record.state != AudioRecord.STATE_INITIALIZED) { record.release(); return "" }
        var text = ""
        try {
            val recognizer = if (grammar == null) Recognizer(current, rate.toFloat()) else Recognizer(current, rate.toFloat(), grammar)
            recognizer.use {
                record.startRecording()
                val buffer = ShortArray(2048)
                val end = System.currentTimeMillis() + seconds * 1000L
                while (System.currentTimeMillis() < end) {
                    val n = record.read(buffer, 0, buffer.size)
                    if (n <= 0) continue
                    if (it.acceptWaveForm(buffer, n)) { text = JSONObject(it.result).optString("text"); if (text.isNotEmpty()) break }
                }
                if (text.isEmpty()) text = JSONObject(it.finalResult).optString("text")
            }
        } catch (err: Throwable) { show("Écoute interrompue : ${err.message}") } finally {
            try { record.stop() } catch (err: Exception) { /* not started */ }
            record.release()
        }
        return text
    }

    private fun sayWord() {
        if (busy) return
        busy = true; say.isEnabled = false
        val n = heard.size + 1
        show("Parle maintenant (essai $n sur 3)…")
        Thread({
            val text = hear(null)
            main.post {
                busy = false
                heard.add(text)
                show(if (text.isBlank()) "Essai $n : je n'ai rien entendu." else "Essai $n : j'ai entendu « $text ».")
                if (heard.size < 3) { say.text = "Dire mon mot (${heard.size + 1}/3)"; say.isEnabled = true } else decide()
            }
        }, "aiwa-enroll-say").start()
    }

    private fun decide() {
        when (val check = WakeWords.check(heard)) {
            is WakeWords.Check.Ok -> {
                pending = check.variants
                show("Entendu : " + check.variants.joinToString(" / ") { "« $it »" } + ".\nC'est ce que le téléphone écoutera. Enregistrer ?")
                save.visibility = View.VISIBLE
                say.text = "Recommencer"; say.isEnabled = true
            }
            is WakeWords.Check.Rejected -> { show(check.reason); save.visibility = View.GONE; say.text = "Recommencer"; say.isEnabled = true }
        }
        heard.clear()
    }

    private fun saveWord() {
        if (pending.isEmpty()) return
        val label = name.text.toString().trim().ifEmpty { pending.first() }
        Words.save(this, slot, label, pending)
        Words.changed(this)
        save.visibility = View.GONE; test.visibility = View.VISIBLE; tests = 0; recognised = 0
        show("C'est enregistré : « $label ». Appuie sur « Tester mon mot » et dis-le plusieurs fois pour voir s'il est bien reconnu.")
    }

    private fun testWord() {
        if (busy) return
        val variants = Words.variants(this, slot)
        if (variants.isEmpty()) return
        busy = true; test.isEnabled = false
        show("Dis ton mot…")
        Thread({
            val text = hear(WakeWords.grammar(variants))
            val ok = WakeWords.heardCustom(text, variants)
            main.post {
                busy = false; test.isEnabled = true; tests += 1; if (ok) recognised += 1
                show((if (ok) "Reconnu ✓" else if (text.isBlank()) "Rien entendu" else "Pas reconnu (entendu : « $text »)") + "\n$recognised reconnus sur $tests essais.")
            }
        }, "aiwa-enroll-test").start()
    }

    private fun closeAndResume() {
        // The listening comes back from a visible screen (Android refuses to start a microphone service from the background).
        if (wasListening && ListenSettings.enabled(this)) VoiceService.start(this)
        finish()
    }

    override fun onDestroy() {
        try { model?.close() } catch (err: Throwable) { /* already closed */ }
        super.onDestroy()
    }
}
