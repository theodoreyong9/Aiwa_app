package com.aiwa.app.voir

import android.content.Context
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Prefs
import org.json.JSONArray
import org.json.JSONObject

/** « Voir »: whether the person publishes the links of her productions to the people near (off by default, « Se cacher » in the settings), and how far (0 = 100 m, 1 = 1 km, 2 = 10 km, 3 = the town). */
object VoirSettings {
    private fun prefs(context: Context) = Prefs(context, "aiwa_voir")
    fun on(context: Context): Boolean = prefs(context).bool("on", true)
    fun setOn(context: Context, on: Boolean) { prefs(context).put("on", on); com.aiwa.app.widget.AiwaWidget.render(context, force = true) }
    fun radius(context: Context): Int = prefs(context).int("radius", 1).coerceIn(0, 3)
    fun setRadius(context: Context, radius: Int) = prefs(context).put("radius", radius.coerceIn(0, 3))
}

/** The favourites the Voir page keeps (links of repositories), copied here so that her own profile can show them. */
object VoirFavorites {
    private fun prefs(context: Context) = Prefs(context, "aiwa_voir")
    fun save(context: Context, list: JSONArray) = prefs(context).put("favs", list.toString())
    fun load(context: Context): JSONArray = try { JSONArray(prefs(context).string("favs", "[]")) } catch (err: Exception) { JSONArray() }
}

/** The repositories kept as favourites, whoever added them (the Voir page, or the key « Favoris » of a profile). */
object FavoriteRepos {
    fun all(context: Context): List<String> {
        val list = VoirFavorites.load(context)
        return (0 until list.length()).mapNotNull { list.optJSONObject(it)?.optString("repo")?.takeIf { r -> r.isNotBlank() } }
    }
    fun has(context: Context, repo: String): Boolean = repo in all(context)
    /** Adds or removes the repository; true when it is a favourite afterwards. */
    fun toggle(context: Context, repo: String): Boolean {
        val list = VoirFavorites.load(context)
        val kept = JSONArray()
        var found = false
        for (i in 0 until list.length()) { val o = list.optJSONObject(i) ?: continue; if (o.optString("repo") == repo) found = true else kept.put(o) }
        if (!found) kept.put(JSONObject().put("repo", repo).put("links", JSONArray()))
        VoirFavorites.save(context, kept)
        return !found
    }
}

/**
 * What « Swipe » navigates: the profiles this phone saw in the last week and at which reach (level 0 = 50 m … 7 = the world), and the lists of the profiles the people met had seen themselves (gossip: repository names
 * only, no place and no time). A week old, an item is forgotten.
 */
object SwipeData {
    private const val WEEK = 7L * 24 * 3600 * 1000
    val LEVEL_LABELS = listOf("50 m", "150 m", "1 km", "5 km", "40 km", "150 km", "1 250 km", "Monde")
    private fun prefs(context: Context) = Prefs(context, "aiwa_swipe")
    private fun read(context: Context): JSONObject = try { JSONObject(prefs(context).string("data", "{}")) } catch (err: Exception) { JSONObject() }

    /** A profile was seen at `level`, and it told these profiles. */
    @Synchronized fun note(context: Context, repo: String, level: Int, seen: List<String>) {
        val now = System.currentTimeMillis()
        val data = read(context)
        val observed = data.optJSONObject("observed") ?: JSONObject()
        val lists = data.optJSONObject("lists") ?: JSONObject()
        observed.put(repo, JSONObject().put("level", level.coerceIn(0, 7)).put("ts", now))
        lists.put(repo, JSONObject().put("ts", now).put("repos", JSONArray(seen.take(40))))
        for (group in listOf(observed, lists)) group.keys().asSequence().toList().forEach { k -> if (now - (group.optJSONObject(k)?.optLong("ts") ?: 0L) > WEEK) group.remove(k) }
        prefs(context).put("data", JSONObject().put("observed", observed).put("lists", lists).toString())
    }

    /** The profiles seen within the reach `maxLevel`, the nearest first. */
    fun observed(context: Context, maxLevel: Int): List<String> {
        val observed = read(context).optJSONObject("observed") ?: return emptyList()
        return observed.keys().asSequence().map { it to observed.getJSONObject(it) }.filter { it.second.optInt("level") <= maxLevel }
            .sortedWith(compareBy({ it.second.optInt("level") }, { -it.second.optLong("ts") })).map { it.first }.toList()
    }

    /** The list this profile told when it was met, or empty. */
    fun listFor(context: Context, repo: String): List<String> {
        val repos = read(context).optJSONObject("lists")?.optJSONObject(repo)?.optJSONArray("repos") ?: return emptyList()
        return (0 until repos.length()).map { repos.optString(it) }.filter { it.isNotBlank() }
    }
}

/** What the Voir page tells the app when it meets someone: who was seen, and (kept as a copy) the list that person saw. */
object SwipeBridge {
    fun seen(context: Context, json: JSONObject) {
        val repo = json.optString("repo")
        if (!com.aiwa.app.home.ProfileView.valid(repo)) return
        val list = json.optJSONArray("seen")
        val names = if (list == null) emptyList() else (0 until list.length()).map { list.optString(it) }.filter { com.aiwa.app.home.ProfileView.valid(it) }
        SwipeData.note(context, repo, json.optInt("level", 0), names)
        SeenPublisher.maybe(context)
    }
}

/** The list of the profiles crossed this week goes into the person's own profile repository (names only), whenever something new was seen; the brain writes it when it changed and at most once an hour. */
object SeenPublisher {
    @Volatile private var last = 0L
    fun maybe(context: Context) {
        val now = System.currentTimeMillis()
        if (now - last < 10 * 60 * 1000) return
        last = now
        val list = SwipeData.observed(context, 7)
        if (list.isEmpty() || !com.aiwa.app.home.ProfileView.valid(com.aiwa.app.home.ProfileSettings.repo(context))) return
        Thread { try { Aiwa.brain.publishProfileSeen(list) } catch (err: Exception) { } }.start()
    }
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
