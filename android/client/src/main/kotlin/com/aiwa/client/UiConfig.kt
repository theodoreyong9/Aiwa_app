package com.aiwa.client

import org.json.JSONObject

/** One key of the bar at the bottom of the profile pages, as the person's file describes it: what it does (`action`) and, if she wants, how it looks. */
data class BarEntry(val action: String, val icon: String?, val label: String?, val tone: String?)

/**
 * The look of the application written in a file of HER OWN profile repository (`Profile/aiwa-ui.json`), which her super agent rewrites the way it rewrites her page:
 * `{"bar": [{"action": "zone", "icon": "📍", "label": "Autour", "tone": "violet"}, {"action": "url:https://…", "label": "Film"}]}`.
 * It is her own content: no limit of keys, of words or of colours is put on it. A file that cannot be read, or that has no key at all, changes nothing (null): the application keeps its own look, and deleting the file brings it back.
 */
object UiConfig {
    const val FILE = "aiwa-ui.json"

    fun parseBar(text: String?, actions: Set<String>): List<BarEntry>? {
        val root = try { JSONObject(text ?: return null) } catch (err: Exception) { return null }
        val list = root.optJSONArray("bar") ?: return null
        val out = ArrayList<BarEntry>()
        for (i in 0 until list.length()) {
            val o = list.optJSONObject(i) ?: continue
            val action = o.optString("action").trim()
            if (action.isEmpty()) continue
            out.add(BarEntry(action, o.optString("icon").trim().ifEmpty { null }, o.optString("label").trim().ifEmpty { null }, o.optString("tone").trim().ifEmpty { null }))
        }
        return out.ifEmpty { null }
    }
}
