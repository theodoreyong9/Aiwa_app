package com.aiwa.app.voice
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import com.aiwa.client.isQuestion

/**
 * The listening of the super agent: normal consumption (the phone's own recognizer, not the small word detector). Each sentence heard is handed to [onHeard]; silence just starts another pass. Whoever uses it stops it before the phone speaks (the voice
 * must not be heard as a sentence) and starts a new one afterwards. Main thread only.
 */
class AgentListener(
    context: Context, private val onQuiet: () -> Unit = {}, private val quietMs: Long = QUIET_MS,
    /** How long a silence the recognizer waits before it decides the person is done (the conversation asks for less), and whether a QUESTION that stopped changing is taken as done at once. */
    private val completeSilenceMs: Long = 2000L, private val possiblySilenceMs: Long = 1500L, private val earlyQuestion: Boolean = false,
    /** The words understood so far, while the person is still speaking (to be shown as they come). */
    private val onPartial: (String) -> Unit = {},
    private val onHeard: (String) -> Unit,
) : RecognitionListener {
    private val appContext = context.applicationContext
    private val recognizer = SpeechRecognizer.createSpeechRecognizer(appContext)
    private val quiet = QuietSounds(appContext)
    private val main = Handler(Looper.getMainLooper())
    private var stopped = false
    // Nothing heard for QUIET_MS: the listening gives up (the owner goes back to the wake word); a pass that heard words restarts the count (the owner makes a new listener each time).
    private val startedAt = android.os.SystemClock.elapsedRealtime()
    // The words understood so far in this pass: when the pass ends in an error or with an empty result (the recognizer gave up after the person had spoken), they are not lost.
    private var lastPartial = ""

    init { recognizer.setRecognitionListener(this) }

    companion object { const val QUIET_MS = 10_000L; private const val EARLY_MS = 700L }

    fun start() {
        if (stopped) return
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fr-FR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            // A pause to think (« mets-toi sur le repo test … c'est bon vas-y ») must not cut the sentence in two: the recognizer waits longer before it decides the person is done.
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, completeSilenceMs)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, possiblySilenceMs)
        }
        lastPartial = ""
        quiet.on()
        try { recognizer.startListening(intent) } catch (err: Exception) { again() }
    }

    fun stop() {
        if (stopped) return
        stopped = true
        main.removeCallbacksAndMessages(null)
        try { recognizer.destroy() } catch (err: Exception) { /* already gone */ }
        quiet.off()
    }

    // A short pause before the next pass: a recognizer restarted at once answers "busy".
    private fun again() {
        if (stopped) return
        if (android.os.SystemClock.elapsedRealtime() - startedAt >= quietMs) { stop(); onQuiet(); return }
        main.postDelayed({ start() }, 300)
    }

    override fun onResults(results: Bundle) {
        if (stopped) return
        val heard = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty().trim()
        val text = heard.ifEmpty { lastPartial }
        lastPartial = ""
        if (text.isNotEmpty()) onHeard(text) else again()
    }

    override fun onError(error: Int) {
        if (stopped) return
        val text = lastPartial
        lastPartial = ""
        if (text.isNotEmpty()) onHeard(text) else again()
    }

    override fun onPartialResults(partialResults: Bundle) {
        val partial = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim()?.takeIf { it.isNotEmpty() } ?: return
        lastPartial = partial
        onPartial(partial)
        // A question whose words stopped changing for a moment is taken as said, without waiting for the recognizer's own end of speech
        if (earlyQuestion) {
            main.removeCallbacks(early)
            if (isQuestion(partial)) main.postDelayed(early, EARLY_MS)
        }
    }

    private val early = Runnable {
        if (stopped) return@Runnable
        val text = lastPartial
        lastPartial = ""
        if (text.isNotEmpty()) { stop(); onHeard(text) }
    }
    override fun onReadyForSpeech(params: Bundle?) {}
    override fun onBeginningOfSpeech() {}
    override fun onRmsChanged(rmsdB: Float) {}
    override fun onBufferReceived(buffer: ByteArray?) {}
    override fun onEndOfSpeech() {}
    override fun onEvent(eventType: Int, params: Bundle?) {}
}
