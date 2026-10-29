package com.aiwa.app.brain

import android.content.Context
import com.aiwa.client.Brain
import com.aiwa.client.Status
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Bump together with BACKEND_VERSION in brain/aiwa_brain/config.py whenever the app starts to rely on a new feature of the brain. */
const val EXPECTED_BRAIN_VERSION = 216

/** Whether the brain answers: unknown (not asked yet), up, down, starting (Termux was asked to start it), or missing (it cannot be there: Termux is absent, or two starts in vain). */
enum class Link { UNKNOWN, UP, DOWN, STARTING, MISSING }

/** What the phone knows right now: the brain's own status, whether it answers, and the few things only the phone knows. */
data class Snapshot(
    val status: Status? = null,
    val link: Link = Link.UNKNOWN,
    val startedAt: Long = 0L,
    val starts: Int = 0,
    val missing: String? = null,       // "termux" / "install"
    val listening: Boolean = false,    // the permanent listening (the ear) runs
    val agentOpen: Boolean = false,    // the super agent has the microphone
    val appUpdateReady: Boolean = false,
    val sessions: List<com.aiwa.client.Session> = emptyList(),
    val fileCounts: Map<String, Int> = emptyMap(),   // productions per kind in the scope of the Files page, read now and then
    val chamberMode: String = "closed",             // what the chamber page says: closed / open / visiting
    val chamberConversing: Boolean = false,
    val chamberEar: Boolean = false,
    val chamberCreate: Boolean = false,
    val chamberCreateThem: Boolean = false,
    val chamberRoom: String? = null,
    val chamberRefusedBusy: Boolean = false,
    val chamberPartner: String? = null,
) {
    val repo: String? get() = status?.repo
    val sessionId: String? get() = status?.session
    val sessionTitle: String? get() = sessions.firstOrNull { it.id == sessionId }?.title
}

/** The one source of truth the widget, the windows and the services read. Updated by BrainSync and by the services. */
object Aiwa {
    val brain = Brain()
    private val flow = MutableStateFlow(Snapshot())
    val state: StateFlow<Snapshot> = flow

    fun update(change: (Snapshot) -> Snapshot) { flow.value = change(flow.value) }

    fun markStarting() = update { it.copy(link = Link.STARTING, startedAt = System.currentTimeMillis()) }
}

/** Makes sure the service that keeps the brain up and the widget honest is running. Every way Aiwa's process comes to life calls this. */
fun wakeAiwa(context: Context) {
    try {
        androidx.core.content.ContextCompat.startForegroundService(context, android.content.Intent(context, KeepAliveService::class.java))
    } catch (err: Exception) {
        // Refused in the background (a widget redraw with no user action): the next tap or opening does it.
    }
}
