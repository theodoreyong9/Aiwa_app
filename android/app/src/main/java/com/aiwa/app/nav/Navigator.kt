package com.aiwa.app.nav

import android.app.Activity
import java.lang.ref.WeakReference

/** A screen that can be walked through by voice: a cursor on its elements (next, previous), one level down (open) and one level up (close). Each returns what the agent says, or null when it does not apply. */
interface VoiceNav {
    fun navNext(): String?
    fun navPrev(): String?
    fun navOpen(): String?
    fun navClose(): String?
}

/**
 * The voice navigation, the same on every screen: it speaks to the screen of Aiwa that is in front (the one resumed, forgotten as soon as it is paused). A screen that is not a VoiceNav can still be closed.
 * Main thread only.
 */
object Navigator {
    private var top: WeakReference<Activity>? = null

    fun resumed(activity: Activity) { top = WeakReference(activity) }
    fun paused(activity: Activity) { if (top?.get() === activity) top = null }

    /** `cmd` is one of NavWords' commands. What to say. */
    fun run(cmd: String): String {
        val activity = top?.get() ?: return "Aiwa n'est pas à l'écran."
        val nav = activity as? VoiceNav
        if (nav == null) {
            if (cmd == "close") { activity.finish(); return "Fermé." }
            return "Il n'y a rien à parcourir ici."
        }
        return when (cmd) {
            "next" -> nav.navNext()
            "prev" -> nav.navPrev()
            "open" -> nav.navOpen()
            else -> nav.navClose()
        } ?: "Rien à faire ici."
    }
}
