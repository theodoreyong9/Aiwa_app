package com.aiwa.app.chamber

import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.Palette
import org.json.JSONObject

/** The chamber, shown (the Chambre cell of the widget opens this): who is in it, what the two super agents say, and the buttons of the chamber. It does not open or close anything by itself being opened. */
class ChamberActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var status: TextView
    private lateinit var talk: TextView
    private lateinit var scroll: ScrollView
    private lateinit var offersBox: LinearLayout
    private val buttons = LinkedHashMap<String, Button>()
    private var running = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#10132E")); setPadding(36, 36, 36, 24) }
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets -> val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()); v.setPadding(36 + bars.left, 36 + bars.top, 36 + bars.right, 24 + bars.bottom); WindowInsetsCompat.CONSUMED }
        root.addView(TextView(this).apply { text = "Chambre"; setTextColor(Color.WHITE); textSize = 26f; setTypeface(null, Typeface.BOLD) })
        status = TextView(this).apply { setTextColor(Color.parseColor("#9DB8FF")); textSize = 16f; setPadding(0, 8, 0, 16) }
        root.addView(status)
        offersBox = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(offersBox)
        scroll = ScrollView(this)
        talk = TextView(this).apply { setTextColor(Color.WHITE); textSize = 17f; setLineSpacing(6f, 1f) }
        scroll.addView(talk)
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val row1 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val row2 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fun button(id: String, row: LinearLayout) {
            val b = Button(this).apply { isAllCaps = false; textSize = 14f; setOnClickListener { ChamberActions.press(this@ChamberActivity, id); main.postDelayed({ refresh() }, 400) } }
            buttons[id] = b; row.addView(b, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        button("room", row1); button("roomtalk", row1); button("roomear", row1); button("roomcreate", row2); button("roomnote", row2)
        root.addView(row1); root.addView(row2)
        setContentView(root)
        loop()
    }

    override fun onDestroy() { running = false; super.onDestroy() }

    private fun loop() {
        if (!running) return
        refresh()
        main.postDelayed({ loop() }, 2500)
    }

    private fun refresh() {
        val s = ChamberState.status
        val shown = ChamberActions.cells(Aiwa.state.value)
        val partner = s.optJSONObject("partner")?.optString("name")
        status.text = when {
            s.optString("mode", "closed") == "closed" -> "Ta chambre est fermée. « Chambre » l'ouvre : tu attends quelqu'un."
            s.optBoolean("conversing") -> "En conversation avec $partner."
            partner != null -> "$partner est là. « Converser » lance la conversation."
            else -> "Ta chambre est ouverte : en attente."
        }
        for ((id, b) in buttons) { val e = shown[id]; b.text = e?.label ?: if (id == "roomnote") "Description" else id; b.alpha = if (e?.on == true || id == "roomnote") 1f else .6f }
        Thread {
            val view = try { Aiwa.brain.chamberCall("/api/chamber", JSONObject()) } catch (err: Exception) { null }
            val offers = view?.optJSONArray("offers")
            if (offers != null) runOnUiThread { showOffers(offers) }
            val lines = view?.optJSONArray("lines")
            if (lines != null) {
                val sb = StringBuilder()
                for (i in 0 until lines.length()) { val l = lines.getJSONObject(i); sb.append(if (l.optString("who") == "me") "▸ " else "◂ ").append(l.optString("name")).append(" : ").append(l.optString("text")).append("\n\n") }
                runOnUiThread { if (talk.text.toString() != sb.toString()) { talk.text = sb.toString(); scroll.post { scroll.fullScroll(android.view.View.FOCUS_DOWN) } } }
            }
        }.start()
    }

    /** What the other agent made and proposed: shown with its kind and its address, opened only when the person says so (https only), or dismissed. */
    private fun showOffers(offers: org.json.JSONArray) {
        offersBox.removeAllViews()
        val kinds = mapOf("docs" to "Document", "image" to "Image", "video" to "Vidéo", "page" to "Page", "app" to "App")
        for (i in 0 until offers.length()) {
            val o = offers.getJSONObject(i); val a = o.optJSONObject("attach") ?: continue
            val url = a.optString("url")
            if (!url.startsWith("https://")) continue
            val id = o.optString("id")
            offersBox.addView(TextView(this).apply { setTextColor(Color.parseColor("#E8C14A")); textSize = 16f; setPadding(0, 12, 0, 4)
                text = "${o.optString("from")} te propose : ${o.optString("text")}\n${kinds[a.optString("kind")] ?: "Fichier"} · ${a.optString("title")}\n$url" })
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            row.addView(Button(this).apply { isAllCaps = false; text = "Ouvrir"; setOnClickListener {
                Thread { Aiwa.brain.chamberCall("/api/chamber/offer", JSONObject().put("id", id).put("do", "open")) }.start()
                try { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url))) } catch (err: Exception) { }
                main.postDelayed({ refresh() }, 400) } }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(Button(this).apply { isAllCaps = false; text = "Ignorer"; setOnClickListener {
                Thread { Aiwa.brain.chamberCall("/api/chamber/offer", JSONObject().put("id", id).put("do", "dismiss")) }.start()
                main.postDelayed({ refresh() }, 400) } }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            offersBox.addView(row)
        }
    }
}
