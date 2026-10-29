package com.aiwa.app.voice

import android.content.Context
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import com.aiwa.client.Reply
import com.aiwa.client.Spoken
import com.aiwa.client.WakeWords
import kotlin.coroutines.resume
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Listens for one answer to what the phone just said aloud (« j'envoie à… : … »): a confirmation, a refusal or a stop. Anything else, or silence, is taken as a new request (a second pass is
 * given once to a silence). Nothing is ever taken as confirmed by default: nothing leaves unless a word of confirmation was heard.
 */
class ConfirmListener(private val context: Context, private val onAnswer: (Reply, String) -> Unit) : RecognitionListener {
    private val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
    private val quiet = QuietSounds(context)
    private var answered = false
    private var silences = 0
    private val extra = Words.extraConfirm(context)

    init { recognizer.setRecognitionListener(this) }

    private fun release() { recognizer.destroy(); quiet.off() }

    fun start() {
        if (answered) return
        val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fr-FR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        }
        quiet.on()
        recognizer.startListening(intent)
    }

    fun cancel() {
        if (answered) return
        answered = true
        release()
    }

    private fun meaning(heard: String): Reply {
        val plain = WakeWords.plain(heard)
        if (plain.isNotEmpty() && extra.any { plain == it || plain.contains(" $it ") || plain.startsWith("$it ") || plain.endsWith(" $it") }) return Reply.CONFIRM
        return Spoken.reply(heard)
    }

    private fun answer(reply: Reply, heard: String) {
        if (answered) return
        answered = true
        release()
        onAnswer(reply, heard)
    }

    override fun onResults(results: Bundle) {
        val heard = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        if (heard.isBlank() && silences++ < 1) start() else answer(meaning(heard), heard)
    }

    override fun onPartialResults(partialResults: Bundle) {
        val heard = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        val reply = meaning(heard)
        if (reply != Reply.OTHER) answer(reply, heard)
    }

    override fun onError(error: Int) {
        if ((error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) && silences++ < 1) start() else answer(Reply.OTHER, "")
    }

    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}

/** The phone says the sentence and listens for the answer: confirmation, refusal, stop, or something else (what was said comes with it). Main thread. */
suspend fun askAloud(context: Context, sentence: String, speak: suspend (String) -> Boolean = { Speaker.speakNatural(context, it) }): Pair<Reply, String> {
    if (!speak(sentence)) return Reply.OTHER to ""
    delay(400)   // the end of the voice must not be heard as the answer
    return suspendCancellableCoroutine { cont ->
        val confirm = ConfirmListener(context) { reply, heard -> if (cont.isActive) cont.resume(reply to heard) }
        cont.invokeOnCancellation { confirm.cancel() }
        confirm.start()
    }
}

/**
 * The beeps Android's recognizer plays when it starts and stops listening (and again at each restart of a pass): muted while a listener is
 * alive, then given back. Only the streams that were not muted already are touched, and only if the system allows it (a refusal changes nothing).
 * Nothing is spoken while a listener runs, so the voice (Speaker) is never cut. Music playing on the phone is silent for those seconds.
 */
class QuietSounds(context: Context) {
    private val audio = context.applicationContext.getSystemService(Context.AUDIO_SERVICE) as android.media.AudioManager
    private val muted = mutableListOf<Int>()
    private var held = false

    fun on() {
        if (held) return
        held = true
        for (stream in listOf(android.media.AudioManager.STREAM_NOTIFICATION, android.media.AudioManager.STREAM_SYSTEM, android.media.AudioManager.STREAM_MUSIC)) {
            try {
                if (!audio.isStreamMute(stream)) {
                    audio.adjustStreamVolume(stream, android.media.AudioManager.ADJUST_MUTE, 0)
                    muted.add(stream)
                }
            } catch (err: Exception) { /* not allowed here (Do Not Disturb): that stream keeps its sound */ }
        }
    }

    fun off() {
        if (!held) return
        held = false
        val streams = muted.toList()
        muted.clear()
        // A moment later: the closing beep comes right after the recognizer is destroyed
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            for (stream in streams) try { audio.adjustStreamVolume(stream, android.media.AudioManager.ADJUST_UNMUTE, 0) } catch (err: Exception) { }
        }, 600)
    }
}
