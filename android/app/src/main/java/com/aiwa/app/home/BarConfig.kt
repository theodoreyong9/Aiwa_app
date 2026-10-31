package com.aiwa.app.home

import android.app.Activity
import android.graphics.Color
import com.aiwa.app.agent.AgentScreens
import com.aiwa.app.common.openUrl
import com.aiwa.client.BarEntry
import com.aiwa.client.UiConfig
import java.net.HttpURLConnection
import java.net.URL

/**
 * The bar at the bottom of the profile pages as the person's file describes it (`Profile/aiwa-ui.json` of her profile repository, written by her super agent): which keys, in which order, with which look and
 * which action. The keys the application has (Match, Chambre, Café, Zone, Mur, Widget, Rang) are named; any other action is one of the screens the super agent can open, or an https address. The file is read
 * from GitHub as it is, and what it cannot ask for is dropped (see UiConfig); without a valid file the bar keeps its own look. The widget does not read this file: it is always there.
 */
object BarConfig {
    /** The last file read, so that a new window starts with it at once. */
    @Volatile var last: List<BarEntry>? = null

    /** Reads the file in the background and calls `done` (on any thread) with the keys, or null when there is none that is valid. */
    fun load(repo: String?, sha: String?, builtinNames: Set<String>, done: (List<BarEntry>?) -> Unit) {
        if (!ProfileView.valid(repo)) { done(null); return }
        Thread {
            val text = try {
                val c = URL(ProfileView.base(repo!!, sha) + UiConfig.FILE).openConnection() as HttpURLConnection
                c.connectTimeout = 10_000; c.readTimeout = 15_000
                if (c.responseCode == 200) c.inputStream.bufferedReader().use { it.readText().take(20_000) } else null
            } catch (err: Exception) { null }
            val entries = UiConfig.parseBar(text, builtinNames + AgentScreens.TOKENS)
            last = entries
            done(entries)
        }.start()
    }

    private fun tone(name: String?, fallback: Int): Int = when (name) {
        null -> fallback
        "violet" -> ProfileBar.VIOLET; "blue" -> ProfileBar.BLUE; "gold" -> ProfileBar.GOLD; "green" -> ProfileBar.GREEN; "white" -> ProfileBar.WHITE
        else -> try { Color.parseColor(name) } catch (err: Exception) { fallback }
    }

    /** The keys to draw and their names: the file's, or (no file) the application's own, in its own order. */
    fun resolve(activity: Activity, entries: List<BarEntry>?, builtin: LinkedHashMap<String, ProfileBar.Spec>, defaults: List<String>? = null): Pair<List<ProfileBar.Spec>, List<String>> {
        if (entries == null) {
            val names = defaults?.filter { it in builtin } ?: builtin.keys.toList()
            return names.map { builtin.getValue(it) } to names
        }
        val specs = ArrayList<ProfileBar.Spec>()
        val ids = ArrayList<String>()
        for (e in entries) {
            val own = builtin[e.action]
            when {
                own != null -> { specs.add(ProfileBar.Spec(e.icon ?: own.icon, e.label ?: own.label, tone(e.tone, own.tone), own.onClick)); ids.add(e.action) }
                e.action.startsWith("url:") -> { val address = e.action.removePrefix("url:"); specs.add(ProfileBar.Spec(e.icon ?: "🔗", e.label ?: "Lien", tone(e.tone, ProfileBar.WHITE)) { openUrl(activity, address) }); ids.add("") }
                else -> { specs.add(ProfileBar.Spec(e.icon ?: "✦", e.label ?: e.action.substringAfterLast('_').replaceFirstChar { it.uppercase() }, tone(e.tone, ProfileBar.WHITE)) { AgentScreens.open(activity, e.action) }); ids.add("") }
            }
        }
        return specs to ids
    }
}
