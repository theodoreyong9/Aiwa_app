package com.aiwa.app.studio

import android.Manifest
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Bundle
import android.util.Base64
import android.widget.CheckBox
import androidx.activity.result.contract.ActivityResultContracts
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** « Ma voix »: twelve seconds read from a sentence on the screen; the brain keeps them (to speak the person's words in her voice in a film). Only her own voice, or that of someone who agrees. */
class VoiceSampleActivity : FloatActivity() {
    override val title = "Ma voix"
    private var sentence = ""
    private var state = "idle"      // idle | recording | sending | done
    private var note: String? = null
    private var agreed = false
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private val permission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.Main).launch {
            sentence = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.filmStatus()?.optString("sample_text") }.orEmpty()
            reload()
        }
    }

    private fun record() {
        if (androidx.core.content.ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { permission.launch(Manifest.permission.RECORD_AUDIO); return }
        state = "recording"; note = null; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val ok = recordTwelveSeconds()
            if (!ok) { state = "idle"; note = "L'enregistrement a échoué."; reload(); return@launch }
            state = "sending"; reload()
            val bytes = file?.readBytes()
            val out = if (bytes == null) null else withContext(Dispatchers.IO) { Aiwa.brain.filmVoice(Base64.encodeToString(bytes, Base64.NO_WRAP), "m4a") }
            file?.delete()
            if (out?.ok == true) state = "done" else { state = "idle"; note = out?.error ?: "fichier vide" }
            reload()
        }
    }

    private suspend fun recordTwelveSeconds(): Boolean = withContext(Dispatchers.Main) {
        try {
            val out = File(cacheDir, "voice_sample.m4a").also { file = it }
            val r = if (android.os.Build.VERSION.SDK_INT >= 31) MediaRecorder(this@VoiceSampleActivity) else @Suppress("DEPRECATION") MediaRecorder()
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioSamplingRate(44100)
            r.setAudioEncodingBitRate(128_000)
            r.setOutputFile(out.absolutePath)
            r.prepare(); r.start(); recorder = r
            delay(12_000)
            r.stop(); r.release(); recorder = null
            true
        } catch (err: Exception) {
            try { recorder?.release() } catch (e: Exception) { }
            recorder = null
            false
        }
    }

    override fun fill() {
        note("Lis cette phrase à voix haute, d'une voix naturelle, dans le calme :")
        note(sentence, Palette.GOLD)
        add(CheckBox(this).apply { text = "C'est ma voix (ou celle de quelqu'un qui est d'accord)."; setTextColor(Palette.TEXT); isChecked = agreed; setOnCheckedChangeListener { _, on -> agreed = on } })
        entry(when (state) { "recording" -> "J'écoute… (12 s)"; "sending" -> "Envoi…"; "done" -> "Voix enregistrée ✓"; else -> "Enregistrer (12 s)" }) { if (agreed && state == "idle") record() }
        this.note?.let { note(it, Palette.RED) }
    }

    override fun onDestroy() { try { recorder?.release() } catch (e: Exception) { }; super.onDestroy() }
}
