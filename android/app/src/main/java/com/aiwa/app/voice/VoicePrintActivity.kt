package com.aiwa.app.voice

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.SpeakerModel

/**
 * « Ma voix » — « Seulement ma voix »: the owner reads a few sentences (about twelve seconds); the speaker model of Vosk makes a print of each stretch of voice and the mean of them is kept on the
 * phone (VoiceLock). The speaker model (about 13 MB) is downloaded the first time. The permanent listening is put aside while this window records (one microphone).
 */
class VoicePrintActivity : FloatActivity() {
    override val title = "Ma voix"
    private var state = "idle"
    private var note: String? = null
    private lateinit var status: TextView
    private val permission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun fill() {
        note("Le réveil ne répondra qu'à ta voix. Lis à voix haute, normalement, dans le calme, pendant douze secondes. Rien n'est enregistré : seule une empreinte de ta voix reste sur le téléphone.")
        note("« Bonjour, c'est moi. Je dis mon mot de réveil, puis je donne une demande, comme je le fais d'habitude. Je parle d'une voix claire, ni trop près ni trop loin du micro. »", Palette.TEXT)
        val saved = VoiceLock.print(applicationContext) != null
        status = note(
            when (state) {
                "downloading" -> "Je télécharge le modèle de voix (environ 13 Mo)…"
                "recording" -> "J'écoute… lis la phrase."
                "computing" -> "Je calcule l'empreinte…"
                "done" -> "Voix enregistrée ✓ « Seulement ma voix » est actif."
                else -> if (saved) "Une empreinte est déjà gardée : tu peux la refaire." else "Pas encore d'empreinte."
            }, Palette.GOLD,
        )
        note?.let { note(it, Palette.RED) }
        if (state == "idle" || state == "done") {
            entry(if (saved) "Refaire mon empreinte" else "Enregistrer ma voix (12 s)") { start() }
            if (saved) entry("Oublier mon empreinte", "le réveil répond de nouveau à toutes les voix") {
                VoiceLock.clear(applicationContext); VoiceService.reload(applicationContext); state = "idle"; reload()
            }
            entry("Fermer") { finish() }
        }
    }

    private fun start() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { permission.launch(Manifest.permission.RECORD_AUDIO); return }
        note = null
        CoroutineScope(Dispatchers.Main).launch {
            if (!SpeakerModelStore.isReady(applicationContext)) {
                set("downloading")
                val failure = withContext(Dispatchers.IO) { SpeakerModelStore.download(applicationContext) { } }
                if (failure != null) { note = "Le modèle de voix n'a pas pu être installé : $failure"; set("idle"); return@launch }
            }
            if (!VoskModelStore.isReady(applicationContext)) {
                set("downloading")
                val failure = withContext(Dispatchers.IO) { VoskModelStore.download(applicationContext) { } }
                if (failure != null) { note = "Le modèle vocal n'a pas pu être installé : $failure"; set("idle"); return@launch }
            }
            val ear = ListenSettings.enabled(applicationContext)
            VoiceService.stop(applicationContext)              // one microphone: the listening gives it up while the voice is recorded
            set("recording")
            val print = withContext(Dispatchers.IO) { recordPrint() }
            if (ear) VoiceService.start(applicationContext)
            if (print == null) { note = "Je n'ai pas assez entendu ta voix. Réessaie plus près, dans le calme."; set("idle"); return@launch }
            VoiceLock.savePrint(applicationContext, print)
            VoiceLock.setEnabled(applicationContext, true)
            VoiceService.reload(applicationContext)
            set("done")
        }
    }

    private fun set(next: String) { state = next; reload() }

    /** Twelve seconds of the owner's voice → the mean print, or null when too little voice was measured. Blocking. */
    private fun recordPrint(): DoubleArray? {
        val rate = 16_000
        val size = maxOf(AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT), 8192)
        val record = try {
            @android.annotation.SuppressLint("MissingPermission")
            val r = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, size)
            if (r.state != AudioRecord.STATE_INITIALIZED) { r.release(); null } else r
        } catch (err: Exception) { null } ?: return null
        val prints = mutableListOf<DoubleArray>()
        try {
            LibVosk.setLogLevel(LogLevel.WARNINGS)
            Model(VoskModelStore.dir(applicationContext).absolutePath).use { model ->
                SpeakerModel(SpeakerModelStore.dir(applicationContext).absolutePath).use { spk ->
                    Recognizer(model, rate.toFloat()).use { recognizer ->
                        recognizer.setSpeakerModel(spk)
                        fun collect(json: String) {
                            val j = JSONObject(json)
                            val a = j.optJSONArray("spk") ?: return
                            if (a.length() >= 64 && j.optInt("spk_frames", 0) >= 60) prints.add(DoubleArray(a.length()) { a.optDouble(it) })
                        }
                        record.startRecording()
                        val buffer = ShortArray(2048)
                        val end = System.currentTimeMillis() + 12_000
                        while (System.currentTimeMillis() < end) {
                            val n = record.read(buffer, 0, buffer.size)
                            if (n <= 0) continue
                            if (recognizer.acceptWaveForm(buffer, n)) collect(recognizer.result)
                        }
                        collect(recognizer.finalResult)
                    }
                }
            }
        } catch (err: Throwable) {
            return null
        } finally {
            try { record.stop() } catch (err: Exception) { }
            record.release()
        }
        return if (prints.size >= 1) VoiceLock.average(prints) else null
    }
}
