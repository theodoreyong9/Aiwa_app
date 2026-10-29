package com.aiwa.app.voice

import android.content.Context
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import kotlin.math.max
import kotlin.math.sqrt

/**
 * The person speaks over the phone's voice: while it talks, the microphone listens (as a call's microphone, with the system's echo canceller when the phone has one) and, when a voice rises
 * above the level of the echo for a quarter of a second, [onSpeech] is called (the voice stops, the listening opens). The level of the echo is measured at the start of each sentence, so
 * a phone without a canceller still works, only less well: the person has to speak louder than the voice. Nothing is recorded or kept: the sound is only measured.
 */
class BargeIn(context: Context, private val onSpeech: () -> Unit) {
    private val appContext = context.applicationContext
    @Volatile private var running = false
    private var thread: Thread? = null
    private var oldMode = AudioManager.MODE_NORMAL
    private var oldSpeaker = false

    companion object {
        /** True while one is listening: the voice is then played as a call's (so that the echo can be cancelled). */
        @Volatile var active = false
        private const val RATE = 16_000
        private const val FRAME = 320             // 20 ms
        private const val WARM_UP_FRAMES = 15     // 300 ms for the canceller to settle: nobody can interrupt before
        private const val BASELINE_FRAMES = 25    // the next 500 ms give the level of the echo
        private const val NEEDED_FRAMES = 12      // 240 ms above the level
        private const val MIN_LEVEL = 1200.0
    }

    fun start() {
        if (running) return
        val audio = appContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        oldMode = audio.mode
        oldSpeaker = audio.isSpeakerphoneOn
        val size = max(AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT), FRAME * 8)
        if (androidx.core.content.ContextCompat.checkSelfPermission(appContext, android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) return
        val record = try {
            @android.annotation.SuppressLint("MissingPermission")
            val r = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, size)
            if (r.state != AudioRecord.STATE_INITIALIZED) { r.release(); null } else r
        } catch (err: Exception) { null } ?: return
        try { if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(record.audioSessionId)?.enabled = true } catch (err: Exception) { /* none */ }
        try { if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(record.audioSessionId)?.enabled = true } catch (err: Exception) { /* none */ }
        // The voice comes out of the loudspeaker, as a call's: the canceller knows what it has to remove
        audio.mode = AudioManager.MODE_IN_COMMUNICATION
        audio.isSpeakerphoneOn = true
        active = true
        running = true
        thread = Thread {
            val buffer = ShortArray(FRAME)
            var frame = 0
            var baseline = 0.0
            var loud = 0
            try {
                record.startRecording()
                while (running) {
                    val n = record.read(buffer, 0, FRAME)
                    if (n <= 0) continue
                    var sum = 0.0
                    for (i in 0 until n) sum += buffer[i].toDouble() * buffer[i]
                    val level = sqrt(sum / n)
                    frame++
                    when {
                        frame <= WARM_UP_FRAMES -> {}
                        frame <= WARM_UP_FRAMES + BASELINE_FRAMES -> baseline = max(baseline, level)
                        else -> {
                            loud = if (level > max(baseline * 2.0, MIN_LEVEL)) loud + 1 else 0
                            if (loud >= NEEDED_FRAMES) { running = false; onSpeech() }
                        }
                    }
                }
            } catch (err: Exception) { /* the microphone went away: no interruption, that is all */ }
            finally { try { record.stop() } catch (err: Exception) { }; record.release() }
        }.also { it.isDaemon = true; it.start() }
    }

    fun stop() {
        running = false
        try { thread?.join(500) } catch (err: Exception) { }
        thread = null
        if (active) {
            active = false
            val audio = appContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            audio.mode = oldMode
            audio.isSpeakerphoneOn = oldSpeaker
        }
    }
}
