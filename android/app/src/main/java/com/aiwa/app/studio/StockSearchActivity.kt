package com.aiwa.app.studio

import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * « Banque de vidéos libres »: a search in Pexels or Pixabay with the person's own key, a clip kept on the phone, then put in the release `stock` of the repository in use so that the sessions that make a
 * film can take it (they cannot see the phone). The author and the licence travel with each clip.
 */
class StockSearchActivity : FloatActivity() {
    override val title = "Vidéos libres"
    private var source = "pexels"
    private var typed = ""
    private var status: JSONObject? = null
    private var results: List<JSONObject>? = null
    private var note: String? = null
    private var busy = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        refresh()
    }

    private fun refresh() {
        CoroutineScope(Dispatchers.Main).launch {
            status = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.stockStatus() }
            reload()
        }
    }

    private fun search() {
        if (typed.isBlank() || busy) return
        busy = true; note = null; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.stockSearch(typed.trim(), source) }
            busy = false
            if (out.ok) { val list = out.json.optJSONArray("results"); results = (0 until (list?.length() ?: 0)).mapNotNull { list?.optJSONObject(it) }; if (results.isNullOrEmpty()) note = "Rien trouvé." }
            else note = out.error
            reload()
        }
    }

    private fun keep(clip: JSONObject) {
        if (busy) return
        busy = true; note = "Je télécharge le clip…"; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val got = withContext(Dispatchers.IO) { Aiwa.brain.stockDownload(clip) }
            if (!got.ok) { busy = false; note = got.error; reload(); return@launch }
            val id = got.json.optString("id")
            val sent = withContext(Dispatchers.IO) { Aiwa.brain.stockPublish(id) }
            busy = false
            note = if (sent.ok) "Gardé. Il part dans ton dépôt (release « stock »)." else (sent.error ?: "pas déposé")
            if (!sent.ok && sent.json.optString("needs") == "github") note = "Gardé sur le téléphone. Connecte GitHub (Réglages) pour le déposer dans ton dépôt."
            toastOnMain(applicationContext, note ?: "")
            refresh()
        }
    }

    override fun fill() {
        val st = status
        if (st == null) { note("Le cerveau ne répond pas."); return }
        val has = st.optBoolean(source)
        note("Des vidéos libres de droits, avec ta propre clé gratuite. La clé se met dans Réglages, Clés et plafonds.")
        entry("Banque : " + (if (source == "pexels") "Pexels" else "Pixabay") + (if (has) "" else " (pas de clé)"), "Touche pour changer") { source = if (source == "pexels") "pixabay" else "pexels"; results = null; reload() }
        val field = EditText(this).apply {
            hint = "Ce que tu cherches"; setText(typed); setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
            inputType = InputType.TYPE_CLASS_TEXT; setSingleLine(); isEnabled = !busy
            addTextChangedListener(object : android.text.TextWatcher {
                override fun afterTextChanged(s: android.text.Editable?) { typed = s?.toString().orEmpty() }
                override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
                override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) {}
            })
        }
        add(field)
        entry(if (busy) "Un instant…" else "Chercher") { search() }
        note?.let { note(it, Palette.GOLD) }
        results?.forEach { clip ->
            val seconds = clip.optInt("duration")
            entry(clip.optString("title"), (if (seconds > 0) "$seconds s · " else "") + clip.optString("author")) { keep(clip) }
        }
        val saved = st.optJSONArray("clips")
        if (saved != null && saved.length() > 0) {
            note("Gardés sur ce téléphone", Palette.GOLD)
            for (i in 0 until saved.length()) {
                val c = saved.optJSONObject(i) ?: continue
                val state = c.optString("saved")
                entry(c.optString("title"), when (state) { "saved" -> "✓ dans ton dépôt"; "pending" -> "dépôt en cours…"; "failed" -> "échec : " + c.optString("saved_error"); else -> "touche pour le déposer dans ton dépôt" } + " · " + c.optString("licence")) {
                    if (state != "saved" && state != "pending") CoroutineScope(Dispatchers.Main).launch {
                        val out = withContext(Dispatchers.IO) { Aiwa.brain.stockPublish(c.optString("id")) }
                        toastOnMain(applicationContext, if (out.ok) "Dépôt en cours" else (out.error ?: "refusé"))
                        refresh()
                    } else if (c.optString("page").startsWith("https://")) openUrl(this, c.optString("page"))
                }
            }
        }
    }
}
