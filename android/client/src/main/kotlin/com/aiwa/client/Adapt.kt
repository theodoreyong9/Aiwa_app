package com.aiwa.client

import org.json.JSONArray
import org.json.JSONObject
import java.text.Normalizer

/**
 * The adaptation of a visited page to the person who looks at it, done on HER phone: the visited profile publishes `aiwa.json` (the zones of its page that may change, and whether it is adaptable) and `adapt.json`
 * (its rules: when the visitor's traits or description match, such zone changes so); the visitor gives what she lets the adaptation read of her. Nothing here is code: a rule is data, its effects are a short list
 * of changes to named zones (a text, a colour, a background, visible or not, the order of the items, a variant), each one allowed or not by the zone's own declaration. The host decides how the visitor's words
 * enter its page (`{traits.themes.0}`, `{description}`); it never learns what matched.
 *
 * aiwa.json  : {"adaptable":true, "traits":{…}, "zones":{"titre":{"modifiable":["texte","couleur"]}, …}}
 * adapt.json : {"regles":[{"si":{"traits.couleurs":{"contient":"rouge"}}, "alors":[{"zone":"titre","couleur":"{traits.couleurs.0}"}]}]}
 */
object Adapt {
    const val MAX_RULES = 50
    const val MAX_ACTIONS = 20
    const val MAX_TEXT = 400
    private val ZONE = Regex("[a-z0-9_-]{1,30}")
    private val COLORS = mapOf("rouge" to "#e11d48", "bleu" to "#2563eb", "vert" to "#16a34a", "jaune" to "#eab308", "orange" to "#f97316", "violet" to "#7c3aed", "rose" to "#ec4899",
        "noir" to "#111111", "blanc" to "#ffffff", "gris" to "#6b7280", "marron" to "#92400e", "turquoise" to "#14b8a6",
        "red" to "#e11d48", "blue" to "#2563eb", "green" to "#16a34a", "yellow" to "#eab308", "purple" to "#7c3aed", "pink" to "#ec4899", "black" to "#111111", "white" to "#ffffff", "gray" to "#6b7280", "brown" to "#92400e")
    private val HEX = Regex("#[0-9a-fA-F]{3,8}")

    fun plain(text: String): String {
        val folded = Normalizer.normalize(text.lowercase().replace("œ", "oe"), Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "")
        return folded.replace(Regex("[^a-z0-9 ]+"), " ").trim().replace(Regex("\\s+"), " ")
    }

    /** What the path points at in the visitor's data, as plain words (an array gives all its items; none when it is not there). */
    private fun walk(root: JSONObject, path: String): Any? {
        var node: Any? = root
        for (part in path.split('.')) {
            val here = node
            node = when (here) {
                is JSONObject -> here.opt(part)
                is JSONArray -> { val index = part.toIntOrNull(); if (index != null && index in 0 until here.length()) here.opt(index) else null }
                else -> null
            }
            if (node == null) return null
        }
        return node
    }

    private fun values(root: JSONObject, path: String): List<String> {
        val node = walk(root, path)
        return when {
            node == null || node === JSONObject.NULL || node is JSONObject -> emptyList()
            node is JSONArray -> (0 until node.length()).map { plain(node.get(it).toString()) }.filter { it.isNotEmpty() }
            else -> plain(node.toString()).let { if (it.isEmpty()) emptyList() else listOf(it) }
        }
    }

    private fun operator(items: List<String>, op: String, arg: Any?): Boolean {
        val wanted = if (arg is JSONArray) (0 until arg.length()).map { plain(arg.get(it).toString()) } else listOf(plain(arg?.toString().orEmpty()))
        return when (op) {
            "present" -> (arg == true) == items.isNotEmpty()
            "absent" -> (arg != false) == items.isEmpty()
            "egal" -> items.any { it in wanted }
            "parmi" -> items.any { it in wanted }
            "contient" -> wanted.any { w -> w.isNotEmpty() && items.any { it == w || it.contains(w) } }
            else -> false
        }
    }

    private fun matches(cond: JSONObject, visitor: JSONObject, depth: Int = 0): Boolean {
        if (depth > 6) return false
        val keys = cond.keys().asSequence().toList()
        if (keys.isEmpty()) return true
        return keys.all { key ->
            when (key) {
                "et" -> (cond.optJSONArray("et") ?: JSONArray()).let { a -> (0 until a.length()).all { a.optJSONObject(it)?.let { c -> matches(c, visitor, depth + 1) } ?: false } }
                "ou" -> (cond.optJSONArray("ou") ?: JSONArray()).let { a -> (0 until a.length()).any { a.optJSONObject(it)?.let { c -> matches(c, visitor, depth + 1) } ?: false } }
                "non" -> cond.optJSONObject("non")?.let { !matches(it, visitor, depth + 1) } ?: false
                else -> {
                    val tests = cond.optJSONObject(key) ?: return@all false
                    val items = values(visitor, key)
                    tests.keys().asSequence().all { op -> operator(items, op, tests.get(op)) }
                }
            }
        }
    }

    /** `{traits.themes.0}` filled from the visitor's data; null when one of the places is empty (the action is then dropped, never half written). */
    private fun fill(text: String, visitor: JSONObject): String? {
        var missing = false
        val out = Regex("\\{([a-z0-9_.]{1,60})}").replace(text) { m ->
            val found = values(visitor, m.groupValues[1])
            if (found.isEmpty()) { missing = true; "" } else originalText(visitor, m.groupValues[1], found)
        }
        return if (missing) null else out
    }

    /** The first value as written (not folded to plain letters): the text a visitor wrote keeps its accents and capitals. */
    private fun originalText(root: JSONObject, path: String, fallback: List<String>): String {
        val node = walk(root, path)
        val text = when {
            node is JSONArray -> if (node.length() > 0) node.get(0).toString() else fallback.first()
            node == null || node === JSONObject.NULL -> fallback.first()
            else -> node.toString()
        }
        return text.replace(Regex("[\\u0000-\\u001f\\u007f<>]"), " ").take(MAX_TEXT)
    }

    private fun color(raw: String): String? {
        val v = raw.trim()
        if (HEX.matches(v)) return v
        return COLORS[plain(v)]
    }

    /**
     * The changes to make to the page. `host`: the aiwa.json of the visited profile; `rules`: its adapt.json; `visitor`: {"traits":{…},"description":"…"} (only what the visitor lets the adaptation read).
     * Empty when the page is not adaptable, when no rule matches, or when a change is not allowed by its zone. Later rules win over earlier ones for the same zone and property.
     */
    fun plan(host: JSONObject, rules: JSONObject, visitor: JSONObject): JSONArray {
        if (!host.optBoolean("adaptable")) return JSONArray()
        val zones = host.optJSONObject("zones") ?: return JSONArray()
        val result = LinkedHashMap<String, JSONObject>()
        val list = rules.optJSONArray("regles") ?: return JSONArray()
        for (i in 0 until minOf(list.length(), MAX_RULES)) {
            val rule = list.optJSONObject(i) ?: continue
            if (!matches(rule.optJSONObject("si") ?: JSONObject(), visitor)) continue
            val actions = rule.optJSONArray("alors") ?: continue
            for (j in 0 until minOf(actions.length(), MAX_ACTIONS)) {
                val action = actions.optJSONObject(j) ?: continue
                val zone = action.optString("zone")
                if (!ZONE.matches(zone)) continue
                val allowed = zones.optJSONObject(zone)?.optJSONArray("modifiable")?.strings() ?: continue
                val entry = result.getOrPut(zone) { JSONObject().put("zone", zone) }
                for (prop in listOf("texte", "couleur", "fond", "visible", "ordre", "variante")) {
                    if (!action.has(prop) || prop !in allowed) continue
                    when (prop) {
                        "texte" -> fill(action.optString(prop), visitor)?.let { entry.put(prop, it.replace(Regex("[\\u0000-\\u001f\\u007f<>]"), " ").take(MAX_TEXT)) }
                        "couleur", "fond" -> fill(action.optString(prop), visitor)?.let { c -> color(c)?.let { entry.put(prop, it) } }
                        "visible" -> if (action.get(prop) is Boolean) entry.put(prop, action.getBoolean(prop))
                        "ordre" -> action.optJSONArray(prop)?.strings()?.filter { ZONE.matches(it) }?.take(30)?.let { entry.put(prop, JSONArray(it)) }
                        "variante" -> action.optString(prop).takeIf { ZONE.matches(it) }?.let { entry.put(prop, it) }
                    }
                }
            }
        }
        return JSONArray(result.values.filter { it.length() > 1 })
    }

    /** The script that applies the changes inside the page: a fixed text of the application with the changes as data (only text content and a few style properties are set, never markup). */
    fun script(ops: JSONArray): String {
        val data = ops.toString().replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        return "(function(o){function q(z){return document.querySelectorAll('[data-aiwa-zone=\"'+z+'\"]')}" +
            "o.forEach(function(p){q(p.zone).forEach(function(e){" +
            "if(p.texte!=null)e.textContent=p.texte;if(p.couleur)e.style.color=p.couleur;if(p.fond)e.style.background=p.fond;if(p.visible===false)e.style.display='none';" +
            "if(p.variante){[].forEach.call(e.querySelectorAll('[data-aiwa-variant]'),function(v){v.style.display=v.getAttribute('data-aiwa-variant')===p.variante?'':'none'})}" +
            "if(p.ordre){p.ordre.forEach(function(id){var c=e.querySelector('[data-aiwa-item=\"'+id+'\"]');if(c)e.appendChild(c)})}" +
            "})})})($data)"
    }
}
