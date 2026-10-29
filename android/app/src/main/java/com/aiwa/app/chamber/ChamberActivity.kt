package com.aiwa.app.chamber

import android.os.Handler
import android.os.Looper
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import org.json.JSONArray
import org.json.JSONObject

/**
 * The chamber: its four buttons (Chambre, Converser, Écouter, Create) and, under them, one line that says where it stands, and what the other agent proposes when it proposes something. Nothing else: no page to
 * read. Opened from the bar of a profile: for a profile that is not hers, « Chambre » goes into that person's room (or leaves it); otherwise it opens or closes her own.
 */
class ChamberActivity : FloatActivity() {
    override val title = "Chambre"
    private val main = Handler(Looper.getMainLooper())
    private var running = true
    private var offers: JSONArray? = null
    private var shownSignature = ""
    private val visited: String? get() = intent.getStringExtra(EXTRA_REPO)

    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        super.onCreate(savedInstanceState)
        loop()
    }

    override fun onDestroy() { running = false; super.onDestroy() }

    private fun loop() {
        if (!running) return
        Thread {
            val view = try { Aiwa.brain.chamberCall("/api/chamber", JSONObject()) } catch (err: Exception) { null }
            val found = view?.optJSONArray("offers")
            main.post { if (running) { offers = found; redraw() } }
        }.start()
        main.postDelayed({ loop() }, 2500)
    }

    private fun statusLine(): String {
        val s = ChamberState.status
        val partner = s.optJSONObject("partner")?.optString("name")
        return when {
            s.optString("mode", "closed") == "closed" -> "Ta chambre est fermée."
            s.optBoolean("conversing") -> "En conversation avec $partner."
            partner != null -> "$partner est là."
            else -> "Ta chambre est ouverte : en attente."
        }
    }

    /** Draws the window again only when something it shows changed (the buttons are touched while it is open). */
    private fun redraw() {
        val shown = ChamberActions.cells(Aiwa.state.value)
        val signature = statusLine() + "|" + shown.entries.joinToString { "${it.key}:${it.value.label}:${it.value.on}" } + "|" + (offers?.toString() ?: "")
        if (signature != shownSignature) { shownSignature = signature; reload() }
    }

    override fun fill() {
        val shown = ChamberActions.cells(Aiwa.state.value)
        for (id in listOf("room", "roomtalk", "roomear", "roomcreate")) {
            val cell = shown[id] ?: continue
            entry(cell.label, null, if (cell.on) Palette.GREEN else Palette.CARD) {
                if (id == "room" && visited != null) ChamberActions.visit(this, visited) else ChamberActions.press(this, id)
                main.postDelayed({ redraw() }, 400)
            }
        }
        note(statusLine())
        val list = offers ?: return
        val kinds = mapOf("docs" to "Document", "image" to "Image", "video" to "Vidéo", "page" to "Page", "app" to "App")
        for (i in 0 until list.length()) {
            val o = list.getJSONObject(i)
            val a = o.optJSONObject("attach") ?: continue
            val url = a.optString("url")
            if (!url.startsWith("https://")) continue
            val id = o.optString("id")
            note("${o.optString("from")} te propose : ${o.optString("text")}\n${kinds[a.optString("kind")] ?: "Fichier"} · ${a.optString("title")}", Palette.GOLD)
            entry("Ouvrir") {
                Thread { Aiwa.brain.chamberCall("/api/chamber/offer", JSONObject().put("id", id).put("do", "open")) }.start()
                try { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))) } catch (err: Exception) { }
            }
            entry("Ignorer") { Thread { Aiwa.brain.chamberCall("/api/chamber/offer", JSONObject().put("id", id).put("do", "dismiss")) }.start() }
        }
    }

    companion object { const val EXTRA_REPO = "repo" }
}
