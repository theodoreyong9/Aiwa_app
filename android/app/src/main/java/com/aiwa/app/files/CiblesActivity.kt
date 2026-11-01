package com.aiwa.app.files

import android.content.Context
import android.content.Intent
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.copyToClipboard
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.Cible
import com.aiwa.client.Production
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** The « Cibles » of a production: who it could be sent to (a mail, a web address, an identifier, each with where it was found), and a line to ask the session for more. Nothing is sent to anybody from here. */
class CiblesActivity : FloatActivity() {
    override val title: String get() = intent.getStringExtra(EXTRA_TITLE) ?: "Cibles"
    private val list: List<Cible> by lazy {
        val raw = try { JSONArray(intent.getStringExtra(EXTRA_CIBLES) ?: "[]") } catch (err: Exception) { JSONArray() }
        (0 until raw.length()).mapNotNull { raw.optJSONObject(it) }.map { Cible(it.optString("kind"), it.optString("value"), it.optString("label"), it.optString("source"), it.optBoolean("verified"), it.optString("subject"), it.optString("body")) }
    }

    private var links: Map<String, List<String>> = emptyMap()

    override fun onResume() {
        super.onResume()
        // the files ticked for each target (they may have just been changed in the window of the files)
        CoroutineScope(Dispatchers.Main).launch {
            links = withContext(Dispatchers.IO) { try { Aiwa.brain.links(repo, tag, file) } catch (err: Exception) { emptyMap() } }
            reload()
        }
    }

    private val repo: String get() = intent.getStringExtra(EXTRA_REPO) ?: ""
    private val tag: String get() = intent.getStringExtra(EXTRA_TAG) ?: ""
    private val file: String get() = intent.getStringExtra(EXTRA_FILE) ?: ""

    override fun fill() {
        if (list.isEmpty()) note("Aucune cible pour l'instant.")
        else note("Touche une cible : un mail ouvre ta messagerie avec l'objet et le texte déjà écrits, une adresse web s'ouvre (le texte est copié pour que tu le colles), un identifiant est copié. Les cibles pâles n'ont pas de source : vérifie-les avant d'écrire.")
        for (c in list) {
            val mark = when (c.kind) { "mail" -> "✉"; "url" -> "🔗"; else -> "◎" }
            val row = entry("$mark  " + c.label.take(70).ifBlank { c.value }, c.value + (if (c.source.isNotBlank()) "\nSource : " + c.source else "\nSans source : à vérifier")) { use(c) }
            row.alpha = if (c.verified) 1f else 0.6f
            row.setOnLongClickListener { copyToClipboard(this, c.value); toastOnMain(this, "Copié : ${c.value}"); true }
            val tools = android.widget.LinearLayout(this).apply { orientation = android.widget.LinearLayout.HORIZONTAL; gravity = android.view.Gravity.END }
            val n = links[c.value]?.size ?: 0
            tools.addView(android.widget.Button(this).apply {
                text = if (n == 0) "PJ" else "PJ ($n)"; isAllCaps = false; textSize = 13f
                if (n > 0) setTextColor(Palette.GREEN)
                setOnClickListener { startActivity(PjActivity.intent(this@CiblesActivity, repo, tag, file, c.value, title)) }
            })
            if (c.body.isNotBlank()) tools.addView(android.widget.Button(this).apply { text = "Texte"; isAllCaps = false; textSize = 13f; setOnClickListener { showText(c) } })
            add(tools, 2)
        }
        entry("＋ Chercher d'autres cibles", "Je demande à la session d'en trouver et d'écrire la fiche. Personne n'est contacté.") { ask() }
    }

    private fun showText(c: Cible) {
        android.app.AlertDialog.Builder(this).setTitle(c.subject.ifBlank { "Texte pour " + c.value }).setMessage(c.body)
            .setPositiveButton("Copier") { _, _ -> copyToClipboard(this, c.body); toastOnMain(this, "Texte copié") }.setNegativeButton("Fermer", null).show()
    }

    /** A mail opens the messagerie with the address, the subject and the text already written (the person reads it and sends it herself); a web address opens after the text was copied; an identifier is copied with the text. */
    private fun use(c: Cible) {
        when (c.kind) {
            "mail" -> {
                if (c.body.isNotBlank()) copyToClipboard(this, c.body)      // also in the clipboard: some messageries drop the text of a mailto
                val uri = android.net.Uri.parse("mailto:" + android.net.Uri.encode(c.value, "@") + "?subject=" + android.net.Uri.encode(c.subject) + "&body=" + android.net.Uri.encode(c.body))
                try { startActivity(Intent(Intent.ACTION_SENDTO, uri).putExtra(Intent.EXTRA_SUBJECT, c.subject).putExtra(Intent.EXTRA_TEXT, c.body)) } catch (err: Exception) { copyToClipboard(this, c.value); toastOnMain(this, "Adresse copiée : ${c.value}") }
            }
            "url" -> {
                if (c.body.isNotBlank()) { copyToClipboard(this, c.body); toastOnMain(this, "Texte copié : colle-le dans le formulaire.") }
                if (!openUrl(applicationContext, c.value)) { copyToClipboard(this, c.value); toastOnMain(this, "Adresse copiée") }
            }
            else -> { copyToClipboard(this, if (c.body.isNotBlank()) c.body else c.value); toastOnMain(this, if (c.body.isNotBlank()) "Texte copié (identifiant : ${c.value})" else "Copié : ${c.value}") }
        }
        if (!c.verified) toastOnMain(this, "Cette cible n'a pas de source : vérifie-la avant d'écrire.")
    }

    private fun ask() {
        val title = intent.getStringExtra(EXTRA_TITLE) ?: ""
        val file = intent.getStringExtra(EXTRA_FILE) ?: ""
        val tag = intent.getStringExtra(EXTRA_TAG) ?: ""
        val known = if (list.isEmpty()) "" else " Tu as déjà trouvé : " + list.joinToString(", ") { it.value } + " ; cherche-en d'AUTRES et garde les anciennes dans la fiche."
        val message = "Cherche à qui je pourrais envoyer « $title » ($file, release $tag) : des adresses e-mail, des pages web ou des identifiants publics et professionnels, trouvés pour de vrai, jamais inventés, chacun avec la page où tu l'as trouvé.$known Écris-les dans la release $tag, dans le fichier $file.cibles.json (format du fichier d'instructions), ou, si tu n'as pas le droit d'écrire dans les releases, dans aiwa-out/$file.cibles.json sur ta branche. Ne contacte personne."
        CoroutineScope(Dispatchers.Main).launch {
            toastOnMain(applicationContext, "Je demande à la session de chercher des cibles…")
            val out = withContext(Dispatchers.IO) { Aiwa.brain.send(message) }
            toastOnMain(applicationContext, if (out.ok) "Demande envoyée : reviens voir la liste dans quelques minutes." else "Pas envoyé : ${out.error ?: "la session n'a pas répondu"}")
            if (out.ok) finish()
        }
    }

    companion object {
        private const val EXTRA_REPO = "repo"
        private const val EXTRA_TITLE = "title"
        private const val EXTRA_FILE = "file"
        private const val EXTRA_TAG = "tag"
        private const val EXTRA_CIBLES = "cibles"
        fun intent(context: Context, item: Production): Intent = Intent(context, CiblesActivity::class.java)
            .putExtra(EXTRA_REPO, item.repo).putExtra(EXTRA_TITLE, item.title).putExtra(EXTRA_FILE, item.file).putExtra(EXTRA_TAG, item.tag)
            .putExtra(EXTRA_CIBLES, JSONArray(item.cibles.map { JSONObject().put("kind", it.kind).put("value", it.value).put("label", it.label).put("source", it.source).put("verified", it.verified).put("subject", it.subject).put("body", it.body) }).toString())
    }
}
