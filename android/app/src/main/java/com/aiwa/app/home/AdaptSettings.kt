package com.aiwa.app.home

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.ListCache
import com.aiwa.app.common.Prefs
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * What the person decides about the adaptation of profiles, on her phone:
 *  - `wants`: the profiles she visits are adapted to her (when the visited profile is adaptable and has rules);
 *  - `adaptable`: her own profile is adaptable (written in her `Profile/aiwa.json`; this is the copy the window shows);
 *  - what the adaptation may read of her: each trait of her `aiwa.json`, and her description (nothing, only the traits drawn from it, or the text itself).
 * Nothing here is ever sent anywhere: the visited page is rewritten on this phone.
 */
object AdaptSettings {
    val TRAITS = listOf("couleurs", "langues", "themes", "roles", "ton", "mode", "lieu")
    private val DEFAULT_ON = setOf("couleurs", "langues", "themes", "roles", "ton", "mode")      // the place is off until she says so
    private fun prefs(context: Context) = Prefs(context, "aiwa_adapt")

    fun wants(context: Context): Boolean = prefs(context).bool("wants", false)
    fun setWants(context: Context, on: Boolean) = prefs(context).put("wants", on)
    fun adaptable(context: Context): Boolean = prefs(context).bool("adaptable", false)
    fun setAdaptable(context: Context, on: Boolean) = prefs(context).put("adaptable", on)

    fun exposed(context: Context, trait: String): Boolean = prefs(context).bool("expose_$trait", trait in DEFAULT_ON)
    fun setExposed(context: Context, trait: String, on: Boolean) = prefs(context).put("expose_$trait", on)

    /** 0: the description is not read; 1: only the traits drawn from it; 2: its text. */
    fun descriptionMode(context: Context): Int = prefs(context).int("description", 0)
    fun cycleDescription(context: Context): Int { val next = (descriptionMode(context) + 1) % 3; prefs(context).put("description", next); return next }

    /** What the adaptation may read of her now: {"traits":{…},"description":"…"} (only what she exposes). */
    fun visitorInput(context: Context): JSONObject {
        val traits = JSONObject()
        val own = try { JSONObject(ListCache.read(context, OWN_KEY) ?: "{}").optJSONObject("traits") } catch (err: Exception) { null }
        val mode = descriptionMode(context)
        val derived = if (mode >= 1) try { JSONObject(prefs(context).string("derived") ?: "{}") } catch (err: Exception) { JSONObject() } else JSONObject()
        for (key in TRAITS) {
            if (!exposed(context, key)) continue
            val value = own?.opt(key) ?: derived.opt(key)      // what she wrote by hand wins over what is drawn from her description
            if (value != null && value != JSONObject.NULL) traits.put(key, value)
        }
        val out = JSONObject().put("traits", traits)
        if (mode >= 2) prefs(context).string("description")?.takeIf { it.isNotBlank() }?.let { out.put("description", it) }
        return out
    }

    private const val OWN_KEY = "aiwa|own"

    /** Reads her own `Profile/aiwa.json` and her description again, in the background, and draws the traits from the description when it changed (once; the result stays on the phone). */
    fun refresh(context: Context) {
        val app = context.applicationContext
        Thread {
            try {
                ProfileSettings.repo(app)?.takeIf { ProfileView.valid(it) }?.let { repo ->
                    val text = read(URL(ProfileView.base(repo) + "aiwa.json")) ?: return@let
                    ListCache.write(app, OWN_KEY, text)
                    JSONObject(text).let { setAdaptable(app, it.optBoolean("adaptable")) }
                }
            } catch (err: Exception) { /* the copy stays */ }
            try {
                val mode = descriptionMode(app)
                if (mode == 0) return@Thread
                val description = Aiwa.brain.chamberNote()
                val p = prefs(app)
                if (description != p.string("description")) p.put("description", description)
                val mark = description.hashCode().toString()
                if (mode >= 1 && description.isNotBlank() && p.string("derived_for") != mark) {
                    Aiwa.brain.adaptDerive(description)?.let { p.put("derived", it.toString()); p.put("derived_for", mark) }
                }
            } catch (err: Exception) { /* next time */ }
        }.start()
    }

    internal fun read(url: URL): String? = try {
        val c = url.openConnection() as HttpURLConnection
        c.connectTimeout = 8_000; c.readTimeout = 10_000
        if (c.responseCode == 200) c.inputStream.bufferedReader().use { it.readText().take(200_000) } else null
    } catch (err: Exception) { null }
}

/** The files of a visited profile that drive its adaptation (`aiwa.json`, `adapt.json`), kept on the phone: the copy is used at once and renewed behind it. */
object AdaptPlan {
    private fun cached(context: Context, repo: String, sha: String?, name: String): JSONObject? {
        val key = "adapt|$repo|$name"
        val kept = ListCache.read(context, key)
        val renew = { text: String? -> if (text != null) ListCache.write(context, key, text) }
        if (kept != null) {
            Thread { renew(AdaptSettings.read(URL(ProfileView.base(repo, sha) + name))) }.start()
            return try { JSONObject(kept) } catch (err: Exception) { null }
        }
        val fresh = AdaptSettings.read(URL(ProfileView.base(repo, sha) + name))
        renew(fresh)
        return try { fresh?.let { JSONObject(it) } } catch (err: Exception) { null }
    }

    /** The changes to make to the page of `repo` for this visitor ([] when there is nothing to do). Blocking: called from the thread that reads the page. */
    fun ops(context: Context, repo: String, sha: String?): JSONArray {
        if (!AdaptSettings.wants(context)) return JSONArray()
        val host = cached(context, repo, sha, "aiwa.json") ?: return JSONArray()
        if (!host.optBoolean("adaptable")) return JSONArray()
        val rules = cached(context, repo, sha, "adapt.json") ?: return JSONArray()
        return try { com.aiwa.client.Adapt.plan(host, rules, AdaptSettings.visitorInput(context)) } catch (err: Exception) { JSONArray() }
    }

    /** The page with the script that applies the changes, put at the end of the body (it runs before the page is first drawn). */
    fun inject(html: String, ops: JSONArray): String {
        val script = "<script>" + com.aiwa.client.Adapt.script(ops) + "</script>"
        val end = Regex("</body\\s*>", RegexOption.IGNORE_CASE).findAll(html).lastOrNull()
        return if (end != null) html.substring(0, end.range.first) + script + html.substring(end.range.first) else html + script
    }
}
