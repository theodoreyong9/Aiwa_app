package com.aiwa.app.voir

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Prefs
import org.json.JSONArray
import org.json.JSONObject

/** « Voir »: whether the person publishes the links of her productions to the people near (off by default, « Se cacher » in the settings), and how far (0 = 100 m, 1 = 1 km, 2 = 10 km, 3 = the town). */
object VoirSettings {
    private fun prefs(context: Context) = Prefs(context, "aiwa_voir")
    fun on(context: Context): Boolean = prefs(context).bool("on", false)
    fun setOn(context: Context, on: Boolean) { prefs(context).put("on", on); com.aiwa.app.widget.AiwaWidget.render(context, force = true) }
    fun radius(context: Context): Int = prefs(context).int("radius", 1).coerceIn(0, 3)
    fun setRadius(context: Context, radius: Int) = prefs(context).put("radius", radius.coerceIn(0, 3))
}

/** The public links of what the person has made, one per kind: the page of the newest release of that kind (a stranger opens it on GitHub). Only a public repository has any: a private one shows nothing. */
object VoirLinks {
    /** Blocking: it asks the brain, which reads the releases. */
    fun of(repo: String): JSONArray {
        val out = JSONArray()
        val files = Aiwa.brain.files(repo) ?: return out
        for (kind in listOf("docs", "image", "video", "app", "page")) {
            val newest = files.items[kind]?.firstOrNull() ?: continue
            out.put(JSONObject().put("kind", kind).put("url", "https://github.com/$repo/releases/tag/${newest.tag}"))
        }
        return out
    }
}
