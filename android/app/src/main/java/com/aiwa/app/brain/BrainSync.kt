package com.aiwa.app.brain

import android.content.Context
import com.aiwa.client.Verdict
import com.aiwa.client.verdict
import kotlinx.coroutines.delay
import java.util.concurrent.atomic.AtomicLong

/**
 * The one place that copies what the brain says into [Aiwa]. The widget and the windows used to disagree about the current session when each wrote its own guess: every caller now goes
 * through here. Overlapping refreshes can finish out of order; the one that STARTED last always wins, so a slow, older answer never overwrites a newer one.
 */
object BrainSync {
    private val started = AtomicLong(0)
    private var applied = 0L
    private val lock = Any()

    fun refresh() {
        val generation = started.incrementAndGet()
        val status = Aiwa.brain.status()
        if (status == null) { markDown(); return }
        val sessions = Aiwa.brain.sessions()
        synchronized(lock) {
            if (generation < applied) return
            applied = generation
            Aiwa.update { it.copy(status = status, link = Link.UP, starts = 0, missing = null, sessions = sessions.ifEmpty { it.sessions }) }
        }
    }

    // Down — unless Termux was asked to start it a moment ago (then it is "starting", for at most a minute). A brain that Termux was asked to start twice without it ever answering
    // is not slow, it is not installed: "missing" stops the restarts (only a "down" brain is restarted) and says what to do.
    private fun markDown() {
        Aiwa.update {
            when {
                it.link == Link.MISSING -> it
                it.link == Link.STARTING && System.currentTimeMillis() - it.startedAt < 60_000 -> it
                verdict(termuxInstalled = true, startsWithoutAnswer = it.starts) == Verdict.NOT_INSTALLED -> it.copy(link = Link.MISSING, missing = "install")
                else -> it.copy(link = Link.DOWN)
            }
        }
    }

    /** Waits until the brain answers (it may be starting up), or gives up. */
    suspend fun awaitUp(timeoutMs: Long): Boolean {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            if (Aiwa.brain.status() != null) { refresh(); return true }
            delay(1500)
        }
        return false
    }
}

/**
 * A widget tap does not go through the application, so the brain may simply not be running (Termux was stopped): a window then showed an empty list. This starts it (Termux RUN_COMMAND)
 * and waits for it. True when the brain answers.
 */
suspend fun ensureBrain(context: Context): Boolean {
    if (Aiwa.brain.status() != null) return true
    Aiwa.update { if (it.link == Link.MISSING) it else it.copy(link = Link.DOWN) }
    startBrainViaTermux(context)
    return BrainSync.awaitUp(30_000)
}
