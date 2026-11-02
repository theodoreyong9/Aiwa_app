package com.aiwa.app.home

import android.content.Context
import com.aiwa.app.common.Prefs

/**
 * The level of trust of a visited profile, chosen by the person who looks and kept on her phone:
 *  - closed (the default): the scripts of the page run in a closed zone (no bridge to the application, no widget, no settings, no wallet, nothing sent out), and the buttons of Aiwa are drawn by the application outside of the page;
 *  - open: the page behaves like her own (its slots of buttons work and its scripts can use the widget). She gives it herself, profile by profile, and takes it back when she wants.
 */
object TrustedProfiles {
    private fun prefs(context: Context) = Prefs(context, "aiwa_trust")
    fun all(context: Context): List<String> = (prefs(context).string("open") ?: "").split(',').filter { it.isNotBlank() }
    fun isOpen(context: Context, repo: String?): Boolean = repo != null && all(context).any { it.equals(repo, ignoreCase = true) }
    fun set(context: Context, repo: String, open: Boolean) {
        val rest = all(context).filterNot { it.equals(repo, ignoreCase = true) }
        prefs(context).put("open", (if (open) rest + repo else rest).joinToString(","))
    }
}

/** The profile on the screen of the phone right now (set by the window that shows the profiles), for the buttons and the voice that act on « this profile ». */
object ScreenNow {
    @Volatile var repo: String? = null
    @Volatile var own: Boolean = false
    /** Reads the profile on the screen again (after her trust in it changed): set by the window that shows the profiles. */
    @Volatile var reload: (() -> Unit)? = null
}
