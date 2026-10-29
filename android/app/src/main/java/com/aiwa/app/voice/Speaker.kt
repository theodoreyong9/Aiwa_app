package com.aiwa.app.voice
import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.UUID
import kotlin.coroutines.resume
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

object Speaker {
    // Cutting the voice off (the person speaks over it, see BargeIn): whatever is playing ends at once and the sentences that follow are not said.
    @Volatile private var interrupted = false
    @Volatile private var cancelCurrent: (() -> Unit)? = null

    /** The voice stops now; the sentences still to come are dropped until resetInterrupt(). Any thread. */
    fun interrupt() {
        interrupted = true
        val cancel = cancelCurrent
        if (cancel != null) android.os.Handler(android.os.Looper.getMainLooper()).post { try { cancel() } catch (err: Exception) { /* already gone */ } }
    }
    fun resetInterrupt() { interrupted = false }

    /** Says the text and returns when it has been said: true if it was, false when the phone has no French voice, no engine, or it took too long. */
    suspend fun speakAndWait(context: Context, text: String, pitch: Float = 1f): Boolean = withContext(Dispatchers.Main) {
        withTimeoutOrNull(20_000L) {
            suspendCancellableCoroutine<Boolean> { cont ->
                var engine: TextToSpeech? = null
                fun end(ok: Boolean) {
                    cancelCurrent = null
                    try { engine?.shutdown() } catch (err: Exception) { /* already gone */ }
                    if (cont.isActive) cont.resume(ok)
                }
                if (interrupted) { end(true); return@suspendCancellableCoroutine }
                cancelCurrent = { try { engine?.stop() } catch (err: Exception) { /* not started */ }; end(true) }
                engine = TextToSpeech(context.applicationContext) { status ->
                    val tts = engine
                    if (status != TextToSpeech.SUCCESS || tts == null) {
                        end(false)
                    } else {
                        val language = tts.setLanguage(Locale.FRENCH)
                        if (language == TextToSpeech.LANG_MISSING_DATA || language == TextToSpeech.LANG_NOT_SUPPORTED) {
                            end(false)
                        } else {
                            tts.setPitch(pitch)
                            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                                override fun onStart(utteranceId: String?) {}
                                override fun onDone(utteranceId: String?) { end(true) }
                                @Suppress("OVERRIDE_DEPRECATION")
                                override fun onError(utteranceId: String?) { end(false) }
                            })
                            if (tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, UUID.randomUUID().toString()) != TextToSpeech.SUCCESS) end(false)
                        }
                    }
                }
                cont.invokeOnCancellation { try { engine?.shutdown() } catch (err: Exception) { /* already gone */ } }
            }
        } ?: false
    }

    /**
     * The natural voice (Piper, made by the backend) when it is ready, the phone's own voice otherwise or on any failure: the sentence is always said.
     */
    suspend fun speakNatural(context: Context, text: String): Boolean {
        val ready = NaturalVoice.usable(context)
        if (ready) {
            val file = try {
                val wav = com.aiwa.app.brain.Aiwa.brain.say(text)
                if (wav == null) null else java.io.File.createTempFile("voice", ".wav", context.cacheDir).also { it.writeBytes(wav) }
            } catch (err: Exception) { null }
            if (file != null) {
                val played = playFile(context, file)
                file.delete()
                if (played) return true
            }
        }
        return speakAndWait(context, text)
    }

    /**
     * The same voice, sentence by sentence: every sentence is made at once (in the background) and played in order, so the first one is heard while the others are still being made.
     * The conversation uses it: the answer starts after the first sentence, not after the whole text.
     */
    suspend fun speakNaturalStreamed(context: Context, text: String): Boolean {
        val sentences = text.trim().split(Regex("(?<=[.!?…])\\s+")).filter { it.isNotBlank() }.take(6)
        if (sentences.size < 2 || !NaturalVoice.usable(context)) return speakNatural(context, text)
        return kotlinx.coroutines.coroutineScope {
            val made = sentences.map { sentence ->
                async(Dispatchers.IO) { try { com.aiwa.app.brain.Aiwa.brain.say(sentence) } catch (err: Exception) { null } }
            }
            var all = true
            for ((i, job) in made.withIndex()) {
                if (interrupted) { job.cancel(); continue }
                val wav = job.await()
                val file = if (wav == null) null else java.io.File.createTempFile("voice", ".wav", context.cacheDir).also { it.writeBytes(wav) }
                val played = if (file != null) playFile(context, file).also { file.delete() } else false
                if (!played && !speakAndWait(context, sentences[i])) all = false
            }
            all
        }
    }

    /**
     * The voice follows the text as it is written: each sentence that arrives on `incoming` starts being made at once (a natural voice) and is played in its turn, so the first
     * one is heard while Claude is still writing the others. Returns when the channel is closed and everything has been said.
     */
    suspend fun speakFlow(context: Context, incoming: kotlinx.coroutines.channels.ReceiveChannel<String>) = kotlinx.coroutines.coroutineScope {
        val natural = NaturalVoice.usable(context)
        val made = kotlinx.coroutines.channels.Channel<Pair<String, kotlinx.coroutines.Deferred<ByteArray?>>>(kotlinx.coroutines.channels.Channel.UNLIMITED)
        launch {
            for (sentence in incoming) {
                made.send(sentence to async(Dispatchers.IO) { if (natural) try { com.aiwa.app.brain.Aiwa.brain.say(sentence) } catch (err: Exception) { null } else null })
            }
            made.close()
        }
        for ((sentence, job) in made) {
            if (interrupted) { job.cancel(); continue }
            val wav = job.await()
            val file = if (wav == null) null else java.io.File.createTempFile("voice", ".wav", context.cacheDir).also { it.writeBytes(wav) }
            val played = if (file != null) playFile(context, file).also { file.delete() } else false
            if (!played) speakAndWait(context, sentence)
        }
    }

    private suspend fun playFile(context: Context, file: java.io.File): Boolean = withContext(Dispatchers.Main) {
        withTimeoutOrNull(60_000L) {
            suspendCancellableCoroutine<Boolean> { cont ->
                val player = android.media.MediaPlayer()
                fun end(ok: Boolean) {
                    cancelCurrent = null
                    try { player.release() } catch (err: Exception) { /* already gone */ }
                    if (cont.isActive) cont.resume(ok)
                }
                if (interrupted) { end(true); return@suspendCancellableCoroutine }
                cancelCurrent = { end(true) }
                try {
                    // As a call's voice, so that the microphone can cancel the echo of it (BargeIn)
                    if (BargeIn.active) player.setAudioAttributes(android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build())
                    player.setDataSource(file.absolutePath)
                    player.setOnCompletionListener { end(true) }
                    player.setOnErrorListener { _, _, _ -> end(false); true }
                    player.setOnPreparedListener { it.start() }
                    player.prepareAsync()
                } catch (err: Exception) { end(false) }
                cont.invokeOnCancellation { try { player.release() } catch (err: Exception) { /* already gone */ } }
            }
        } ?: false
    }
}
