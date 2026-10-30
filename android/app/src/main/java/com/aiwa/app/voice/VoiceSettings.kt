package com.aiwa.app.voice

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Prefs

private fun prefs(context: Context) = Prefs(context, "aiwa_listen")

/** Whether the person turned the permanent listening (the ear) on: off until she does. */
object ListenSettings {
    // OFF at each installation and each update (Android lets a microphone service start only while Aiwa is on screen: the person turns it on, with the Écoute cell of the widget, and it then stays on).
    fun enabled(context: Context): Boolean = prefs(context).bool("on_v3", false)

    /** Called when the application starts: a new version (or a first installation) closes the switch. */
    fun resetForNewVersion(context: Context) {
        val version = try { androidx.core.content.pm.PackageInfoCompat.getLongVersionCode(context.packageManager.getPackageInfo(context.packageName, 0)) } catch (err: Exception) { return }
        val p = prefs(context)
        if (p.long("listen_version", -1L) != version) { p.put("on_v3", false); p.put("listen_version", version) }
    }

    fun setEnabled(context: Context, on: Boolean) = prefs(context).put("on_v3", on)
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

/** What the super agent proposes for a session goes at once, without the read-back and the « on y va ? »: on by default for now. (Changes of settings are still read back.) */
object DirectSendSettings {
    fun enabled(context: Context): Boolean = prefs(context).bool("direct_send", true)
    fun set(context: Context, on: Boolean) = prefs(context).put("direct_send", on)
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
