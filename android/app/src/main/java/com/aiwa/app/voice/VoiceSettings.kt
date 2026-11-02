package com.aiwa.app.voice

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Prefs

private fun prefs(context: Context) = Prefs(context, "aiwa_listen")

/** Whether the person turned the permanent listening (the ear) on: off until she does. */
object ListenSettings {
    // ON by default (the settings hold the switch; the ear of the widget is gone). The microphone service can only be started while Aiwa is on screen: it starts each time the home opens, and the
    // person's own choice (the switch in the settings, the old Écoute toggle) is kept across updates.
    fun enabled(context: Context): Boolean = prefs(context).bool("on_v4", true)

    /** Kept for the application's start: the switch is no longer closed by an update. */
    fun resetForNewVersion(context: Context) {}

    fun setEnabled(context: Context, on: Boolean) = prefs(context).put("on_v4", on)
}

/** « Voix naturelle »: on by default; off, the phone's own voice speaks. Installed by default in the background (see the brain); only the switch is the person's. */
object NaturalVoice {
    fun enabled(context: Context): Boolean = prefs(context).bool("natural_voice", true)
    fun setEnabled(context: Context, on: Boolean) = prefs(context).put("natural_voice", on)

    /** Is the natural voice usable right now (switched on and installed)? */
    fun usable(context: Context): Boolean = enabled(context) && Aiwa.state.value.status?.voice == "ready"
}

/** « Création à la volée »: the super agent in a fluid conversation while the person builds: what is said goes to the agent, its orders leave without a read-back, the progress is told. Off by default. */
object LiveSettings {
    fun enabled(context: Context): Boolean = prefs(context).bool("live", false)
    fun set(context: Context, on: Boolean) = prefs(context).put("live", on)
}

/** « C'est prêt », said aloud when a new production arrives: on by default. */
object ReadySettings {
    fun enabled(context: Context): Boolean = prefs(context).bool("say_ready", true)
    fun set(context: Context, on: Boolean) = prefs(context).put("say_ready", on)
}

/** « Chambre ouverte écran éteint »: the chamber stays open (a service holds the connection) while the screen is off. */
object ChamberSettings {
    fun awake(context: Context): Boolean = prefs(context).bool("chamber_awake", true)
    fun setAwake(context: Context, on: Boolean) = prefs(context).put("chamber_awake", on)
}
