package com.aiwa.client

import org.json.JSONObject

/** One key of the bar at the bottom of the profile pages, as the person's file describes it: what it does (`action`) and, if she wants, how it looks. */
data class BarEntry(val action: String, val icon: String?, val label: String?, val tone: String?)

/**
 * The look of the application written in a file of her profile repository (`Profile/aiwa-ui.json`), which her super agent rewrites the way it rewrites her page:
 * `{"v": 1, "bar": [{"action": "zone", "icon": "📍", "label": "Autour", "tone": "violet"}, {"action": "url:https://…", "label": "Film"}]}`.
 * What the file may ask for is closed: an action the application knows, or an https address. A file that cannot be read, or that leaves nothing valid, changes nothing (null): the application keeps its own look.
 */
object UiConfig {
    const val FILE = "aiwa-ui.json"
    const val MAX_KEYS = 8
    val TONES = setOf("violet", "blue", "gold", "green", "white")
    private val HEX = Regex("#[0-9A-Fa-f]{6}")

    fun parseBar(text: String?, actions: Set<String>): List<BarEntry>? {
        val root = try { JSONObject(text ?: return null) } catch (err: Exception) { return null }
        if (root.optInt("v") != 1) return null
        val list = root.optJSONArray("bar") ?: return null
        val out = ArrayList<BarEntry>()
        for (i in 0 until minOf(list.length(), MAX_KEYS * 2)) {
            val o = list.optJSONObject(i) ?: continue
            val action = o.optString("action").trim()
            val known = action in actions || (action.startsWith("url:https://") && action.length <= 220 && action.none { it.isWhitespace() || it == '"' || it == '<' || it == '>' })
            if (!known) continue
            val label = o.optString("label").trim().takeIf { it.isNotEmpty() && it.length <= 14 && it.none { c -> c.isISOControl() } }
            val icon = o.optString("icon").trim().takeIf { it.isNotEmpty() && it.length <= 8 && it.none { c -> c.isISOControl() } }
            val tone = o.optString("tone").trim().takeIf { it in TONES || HEX.matches(it) }
            out.add(BarEntry(action, icon, label, tone))
            if (out.size == MAX_KEYS) break
        }
        return out.ifEmpty { null }
    }
}
