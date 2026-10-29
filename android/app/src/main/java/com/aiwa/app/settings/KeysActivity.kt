package com.aiwa.app.settings

import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.studio.StockSearchActivity
import com.aiwa.app.studio.VoiceSampleActivity
import org.json.JSONObject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * « Clés et plafonds »: the person's Anthropic key (the super agent speaks through it) and the most tokens it may use in a day; the fal.ai key of « Film de moi », its voice and the most a film may cost; the Pexels and
 * Pixabay keys of the free video banks; the way to the GitHub connection. A key stays in the brain's own folder on the phone and goes only to its service.
 */
class KeysActivity : FloatActivity() {
    override val title = "Clés et plafonds"
    private var film: JSONObject? = null
    private var stock: JSONObject? = null

    override fun onResume() {
        super.onResume()
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { film = Aiwa.brain.filmStatus(); stock = Aiwa.brain.stockStatus() }
            reload()
        }
    }

    /** A key line: its state, a field to paste it, and a way to remove it. */
    private fun keyBlock(label: String, has: Boolean, save: suspend (String) -> com.aiwa.client.Brain.Outcome, clear: suspend () -> com.aiwa.client.Brain.Outcome) {
        note("$label : " + (if (has) "✓ en place" else "absente"), if (has) Palette.GREEN else Palette.TEXT)
        if (!has) {
            val box = field("Ta clé $label", secret = true)
            add(box)
            entry("Enregistrer") { val k = box.text.toString().trim(); if (k.isNotEmpty()) run({ save(k) }, "Clé enregistrée") }
        } else entry("Retirer la clé") { run({ clear() }, "Clé retirée") }
    }

    private fun field(hintText: String, secret: Boolean, number: Boolean = false) = EditText(this).apply {
        hint = hintText; setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0")); setSingleLine()
        inputType = when {
            number -> InputType.TYPE_CLASS_NUMBER
            secret -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            else -> InputType.TYPE_CLASS_TEXT
        }
    }

    private fun run(work: suspend () -> com.aiwa.client.Brain.Outcome, done: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { val o = work(); BrainSync.refresh(); o }
            toastOnMain(applicationContext, if (out.ok) done else "Refusé : ${out.error}")
            withContext(Dispatchers.IO) { film = Aiwa.brain.filmStatus(); stock = Aiwa.brain.stockStatus() }
            reload()
        }
    }

    override fun fill() {
        val status = Aiwa.state.value.status
        val llm = status?.llm
        note("Le super agent parle avec ta propre clé Anthropic, qui reste sur ton téléphone. Sans clé, il utilise le Claude du téléphone (plus lent).")
        note(when (llm?.state) {
            "ready" -> "✓ Clé en place. Aujourd'hui : ${llm.used} jetons" + (if (llm.cap > 0) " sur ${llm.cap}." else ", sans plafond.")
            "installing" -> "Installation du moteur en cours…"
            "error" -> "La clé a été refusée."
            else -> "Pas de clé."
        }, if (llm?.state == "ready") Palette.GREEN else Palette.TEXT)
        val key = field("sk-ant-…", secret = true)
        add(key)
        entry("Enregistrer la clé") { val k = key.text.toString().trim(); if (k.isNotEmpty()) run({ Aiwa.brain.llmKey(k) }, "Clé enregistrée") }
        if (llm?.state == "ready" || llm?.state == "error") entry("Retirer la clé") { run({ Aiwa.brain.llmClearKey() }, "Clé retirée") }
        val cap = field("Plafond par jour, en jetons (0 = aucun)", secret = false, number = true)
        if (llm != null && llm.cap > 0) cap.setText(llm.cap.toString())
        add(cap, 16)
        entry("Enregistrer le plafond") { run({ Aiwa.brain.llmCap(cap.text.toString().trim().toLongOrNull() ?: 0L) }, "Plafond enregistré") }

        entry("GitHub", if (status?.githubToken == true) "Connecté" + (status.githubUser?.let { " : $it" } ?: "") else "Pas connecté") { startActivity(android.content.Intent(this, GithubConnectActivity::class.java)) }

        note("Film (fal.ai)", Palette.GOLD)
        note("Pour fabriquer un film de toi ou de ton produit : l'image, la voix, la bouche. Tu crées un compte sur fal.ai, tu y mets des crédits, et tu colles ici ta clé. Chaque film est facturé par fal.ai sur ton compte, jamais par Aiwa. Un devis est montré avant toute dépense.")
        val f = film
        if (f == null) note("Le cerveau ne répond pas (ou il est trop ancien).") else {
            keyBlock("fal", f.optBoolean("key"), { Aiwa.brain.filmKey(it) }, { Aiwa.brain.filmKeyClear() })
            val capNow = f.optDouble("cap", 20.0)
            entry("Plafond par film : ${String.format(java.util.Locale.FRANCE, "%.0f", capNow)} $", "Touche pour changer (10, 20, 50, 100). Un film coûte environ ${String.format(java.util.Locale.FRANCE, "%.2f", f.optDouble("per_minute"))} $ la minute.") {
                val next = listOf(10.0, 20.0, 50.0, 100.0).firstOrNull { it > capNow } ?: 10.0
                run({ Aiwa.brain.filmCap(next) }, "Plafond : ${next.toInt()} $")
            }
            entry("Ma voix : " + (if (f.optBoolean("voice")) "enregistrée" else "à enregistrer"), "Douze secondes lues à voix haute, pour que le film parle avec ta voix.") { startActivity(android.content.Intent(this, VoiceSampleActivity::class.java)) }
        }

        note("Banques de vidéos libres", Palette.GOLD)
        note("Des clips libres de droits pour tes films, avec tes propres clés gratuites (pexels.com/api et pixabay.com/api/docs).")
        val bank = stock
        if (bank == null) note("Le cerveau ne répond pas (ou il est trop ancien).") else {
            keyBlock("Pexels", bank.optBoolean("pexels"), { Aiwa.brain.stockKey("pexels", it) }, { Aiwa.brain.stockKeyClear("pexels") })
            keyBlock("Pixabay", bank.optBoolean("pixabay"), { Aiwa.brain.stockKey("pixabay", it) }, { Aiwa.brain.stockKeyClear("pixabay") })
            entry("Chercher une vidéo libre", "Garde un clip, il part dans ton dépôt pour tes films.") { startActivity(android.content.Intent(this, StockSearchActivity::class.java)) }
        }
    }
}
