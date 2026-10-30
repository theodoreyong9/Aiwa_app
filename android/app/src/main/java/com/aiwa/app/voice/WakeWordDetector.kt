package com.aiwa.app.voice
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.aiwa.client.WakeCustoms
import com.aiwa.client.WakeKind
import com.aiwa.client.WakeWords
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer

/**
 * Listens to the microphone for a few phrases and nothing else: the call of the super agent, « stop » and « éteins ». The speech model runs on the phone with a grammar
 * that has only those (anything else is "[unk]"), so it is cheap, and no sound leaves the phone. When the word is heard the microphone is
 * released at once and onWake is called (on this detector's thread: post it where it must run), because the dictation that follows needs
 * the microphone.
 *
 * A word of the person's own is listened for through the spellings the engine heard when it was said to the phone (WakeWords): "Aiwa" is not in the small French model's
 * vocabulary and cannot be written in the grammar, but what the engine writes when it hears it can.
 */
class WakeWordDetector(
    private val model: Model,
    /** The spellings of the words the person chose (Words), as the engine heard them; empty lists = only the words of origin. */
    private val customs: WakeCustoms = WakeCustoms(),
    /** « Seulement ma voix »: the speaker model, the owner's print and how far a voice may be from it (null = no check). */
    private val speaker: org.vosk.SpeakerModel? = null,
    private val print: DoubleArray? = null,
    private val maxDistance: Double = 0.55,
    private val onWake: (WakeKind) -> Unit,
    private val onFailure: (String) -> Unit,
    /** True while a sound or a video plays on the phone (another app). With [pauseOnMedia], the microphone is then given back and listening waits: a video is never paused by it, and its own sound is not heard as a word. */
    private val mediaPlaying: () -> Boolean = { false },
    private val pauseOnMedia: Boolean = false,
) {
    @Volatile private var running = false
    private var thread: Thread? = null

    fun start() {
        if (running) return
        running = true
        thread = Thread({ run() }, "aiwa-wake-word").also { it.start() }
    }

    /** Stops listening and waits (a moment at most) for the microphone to be given back. */
    fun stop() {
        running = false
        try { thread?.join(800) } catch (err: InterruptedException) { /* leaving */ }
    }

    /** Listens; while a media plays (and the person asked for it) the microphone is released and listening waits, a second at a time. */
    private fun run() {
        while (running) {
            if (pauseOnMedia && mediaPlaying()) {
                try { Thread.sleep(1200) } catch (err: InterruptedException) { return }
                continue
            }
            if (listenOnce()) return
        }
    }

    /** Every word of a finished result was heard with at least MIN_CONFIDENCE (a result with no word detail is not trusted). */
    private fun sure(result: JSONObject): Boolean {
        val words = result.optJSONArray("result") ?: return false
        if (words.length() == 0) return false
        for (i in 0 until words.length()) {
            val word = words.getJSONObject(i)
            if (word.optString("word") != "[unk]" && word.optDouble("conf", 0.0) < MIN_CONFIDENCE) return false
        }
        return true
    }

    private companion object {
        const val MIN_CONFIDENCE = 0.85
    }

    /** One listening, from opening the microphone to giving it back. True when it is over for good (a word heard, a failure, a stop); false when a media started playing. */
    @android.annotation.SuppressLint("MissingPermission")
    private fun listenOnce(): Boolean {
        val sampleRate = 16_000
        val minimum = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minimum <= 0) { running = false; onFailure("le micro ne donne pas de taille de tampon (code $minimum)"); return true }
        val record = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minimum, 8192))
        } catch (err: Exception) {
            running = false
            onFailure("micro refusé : ${err.message}")
            return true
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            running = false
            onFailure("le micro n'a pas pu s'ouvrir (un autre programme l'utilise ?)")
            return true
        }
        var woken: WakeKind? = null
        var interrupted = false
        var sinceCheck = 0
        try {
            Recognizer(model, sampleRate.toFloat(), WakeWords.grammar(customs.all())).use { recognizer ->
                recognizer.setWords(true)
                if (speaker != null && print != null) try { recognizer.setSpeakerModel(speaker) } catch (err: Throwable) { /* the check is then not done */ }
                record.startRecording()
                val buffer = ShortArray(2048)
                while (running) {
                    val n = record.read(buffer, 0, buffer.size)
                    if (n < 0) { onFailure("lecture du micro interrompue (code $n)"); running = false; break }
                    if (n == 0) continue
                    // about every second (8 reads of 128 ms): has a media started? then the microphone goes back and this listening ends
                    if (pauseOnMedia && ++sinceCheck >= 8) { sinceCheck = 0; if (mediaPlaying()) { interrupted = true; break } }
                    // Rigour: only a FINISHED sentence counts (a guess in the middle of a sound woke the phone for things that were not the word), and every word of it must be heard with
                    // confidence. The detector no longer improvises.
                    if (!recognizer.acceptWaveForm(buffer, n)) continue
                    val result = JSONObject(recognizer.result)
                    if (!sure(result)) continue
                    val heard = result.optString("text")
                    var kind = if (heard.isEmpty()) null else WakeWords.kind(heard, customs)
                    // Only the wake words are checked against the owner's voice: « stop », « éteins » and the others always work
                    if (kind != null && print != null && speaker != null && (kind == WakeKind.CALL || kind == WakeKind.DIRECT)) {
                        val array = result.optJSONArray("spk")
                        // no print in the result (too little voice to measure): not refused, a measure that cannot be made must not lock the owner out
                        if (array != null && array.length() >= 64) {
                            val voice = DoubleArray(array.length()) { array.optDouble(it) }
                            if (VoiceLock.distance(voice, print) > maxDistance) kind = null
                        }
                    }
                    if (kind != null) { woken = kind; running = false }
                }
            }
        } catch (err: Throwable) {
            running = false
            onFailure(err.message ?: err.javaClass.simpleName)
        } finally {
            try { record.stop() } catch (err: Exception) { /* not started */ }
            record.release()
        }
        woken?.let { onWake(it) }
        return !interrupted
    }
}
