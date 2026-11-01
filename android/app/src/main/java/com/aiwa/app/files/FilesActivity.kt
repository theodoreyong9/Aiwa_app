package com.aiwa.app.files

import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.format.DateFormat
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.copyToClipboard
import com.aiwa.app.common.dp
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.widget.FilesScope
import com.aiwa.client.Files
import com.aiwa.client.Production
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Date

/**
 * The productions of one kind (docs, images, vidéos, apps, pages) in the scope of the Files page: one repository, or all. A tap opens one; each line has « Partager » and « Supprimer ».
 * Everything is a file of a release of the repository: the list is read from there.
 */
class FilesActivity : FloatActivity() {
    private val kind: String by lazy { intent.getStringExtra(EXTRA_KIND) ?: "docs" }
    override val title: String get() = LABELS[kind] ?: "Productions"
    private var listing: Files? = null
    private var failed = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        load()
    }

    private fun load() {
        CoroutineScope(Dispatchers.Main).launch {
            val scope = FilesScope.repo(this@FilesActivity, Aiwa.state.value.status?.repo)
            val got = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.files(scope) }
            failed = got == null
            listing = got
            reload()
        }
    }

    override fun fill() {
        val scope = FilesScope.repo(this, Aiwa.state.value.status?.repo)
        note(if (scope == null) "Tous tes dépôts" else scope, Palette.GOLD)
        val files = listing
        if (failed) { note("Le cerveau ne répond pas."); return }
        if (files == null) { note("Je lis les releases…"); return }
        files.error?.let { note(it, Palette.RED) }
        val items = files.items[kind].orEmpty()
        if (items.isEmpty()) { note(EMPTY[kind] ?: "Rien pour l'instant."); return }
        items.forEach { addLine(it, scope == null) }
    }

    private fun addLine(item: Production, showRepo: Boolean) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply { setColor(Palette.CARD); cornerRadius = dp(14).toFloat() }
            setPadding(dp(14), dp(10), dp(14), dp(8))
        }
        val head = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setOnClickListener { FileActions.open(this@FilesActivity, item) } }
        head.addView(TextView(this).apply { text = item.title; setTextColor(Palette.TEXT); textSize = 16f })
        val date = DateFormat.format("d MMM yyyy", Date(item.ts * 1000)).toString()
        head.addView(TextView(this).apply { text = listOfNotNull(if (showRepo) item.repoName else null, date, size(item.size)).joinToString(" · "); setTextColor(Palette.DIM); textSize = 13f })
        row.addView(head)
        if (item.cibles.isNotEmpty()) {
            val chips = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(6), 0, 0) }
            for (c in item.cibles.take(4)) chips.addView(TextView(this).apply {
                text = (when (c.kind) { "mail" -> "✉ "; "url" -> "🔗 "; else -> "◎ " }) + (c.label.ifBlank { c.value }).take(22)
                setTextColor(Palette.TEXT); textSize = 12.5f; alpha = if (c.verified) 1f else 0.55f
                setPadding(dp(10), dp(5), dp(10), dp(5))
                background = GradientDrawable().apply { setColor(Color.parseColor("#2A3070")); cornerRadius = dp(12).toFloat() }
                setOnClickListener { useCible(c) }
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { rightMargin = dp(6) })
            row.addView(chips)
        }
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.END }
        if (item.cibles.isEmpty()) buttons.addView(Button(this).apply { text = "Cibles"; isAllCaps = false; textSize = 13f; setOnClickListener { askCibles(item) } })
        buttons.addView(Button(this).apply { text = "Partager"; isAllCaps = false; textSize = 13f; setOnClickListener { FileActions.share(this@FilesActivity, item) } })
        buttons.addView(Button(this).apply { text = "Supprimer"; isAllCaps = false; textSize = 13f; setOnClickListener { confirmDelete(item) } })
        row.addView(buttons, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        add(row)
    }

    /** A target: a mail opens the mail application with the address, a web address opens in the browser, an identifier is copied. */
    private fun useCible(c: com.aiwa.client.Cible) {
        when (c.kind) {
            "mail" -> try { startActivity(Intent(Intent.ACTION_SENDTO, android.net.Uri.parse("mailto:" + c.value))) } catch (err: Exception) { copyToClipboard(this, c.value); toastOnMain(this, "Adresse copiée : ${c.value}") }
            "url" -> if (!openUrl(applicationContext, c.value)) { copyToClipboard(this, c.value); toastOnMain(this, "Adresse copiée") }
            else -> { copyToClipboard(this, c.value); toastOnMain(this, "Copié : ${c.value}") }
        }
        if (!c.verified) toastOnMain(this, "Cette cible n'a pas de source : vérifie-la avant d'écrire.")
    }

    /** « Cibles »: asks the session of the repository to look for who this production could be sent to and to write the card next to it. Nothing is sent to anybody. */
    private fun askCibles(item: Production) {
        val message = "Cherche à qui je pourrais envoyer « ${item.title} » (${item.file}, release ${item.tag}) : des adresses e-mail, des pages web ou des identifiants publics et professionnels, trouvés pour de vrai, jamais inventés, chacun avec la page où tu l'as trouvé. Écris-les dans la release ${item.tag}, dans le fichier ${item.file}.cibles.json (format du fichier d'instructions). Ne contacte personne."
        CoroutineScope(Dispatchers.Main).launch {
            toastOnMain(applicationContext, "Je demande à la session de chercher des cibles…")
            val out = withContext(Dispatchers.IO) { Aiwa.brain.send(message) }
            toastOnMain(applicationContext, if (out.ok) "Demande envoyée : reviens voir la liste dans quelques minutes." else "Pas envoyé : ${out.error ?: "la session n'a pas répondu"}")
        }
    }

    private fun confirmDelete(item: Production) {
        AlertDialog.Builder(this)
            .setTitle("Supprimer « ${item.title} » ?")
            .setMessage("La release ${item.tag} de ${item.repo} est supprimée de GitHub, avec son fichier. C'est définitif.")
            .setPositiveButton("Supprimer") { _, _ -> FileActions.delete(this, item) { load() } }
            .setNegativeButton("Garder", null)
            .show()
    }

    private fun size(bytes: Long): String? = when {
        bytes <= 0 -> null
        bytes < 1024 * 1024 -> "${(bytes + 1023) / 1024} Ko"
        else -> "${bytes / (1024 * 1024)} Mo"
    }

    companion object {
        const val EXTRA_KIND = "kind"
        private val LABELS = mapOf("docs" to "Documents", "image" to "Images", "video" to "Vidéos", "app" to "Apps", "page" to "Pages")
        private val EMPTY = mapOf(
            "docs" to "Aucun document. Demande-en un au super agent : il part en release du dépôt.",
            "image" to "Aucune image pour l'instant.", "video" to "Aucune vidéo pour l'instant.", "app" to "Aucune app pour l'instant.", "page" to "Aucune page pour l'instant.",
        )
    }
}
