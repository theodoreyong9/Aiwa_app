package com.aiwa.app.widget

import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.clipboardText
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** What the Files page looks at: every repository, or one of them (the ones used, the ones of the sessions, the public ones of the owner, and all of them with a GitHub token). */
class RepoPickerActivity : FloatActivity() {
    override val title = "Files : quel dépôt ?"
    private var repos: List<String>? = null
    private var sessions: List<com.aiwa.client.Session> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { ensureBrain(applicationContext); repos = Aiwa.brain.repos(); sessions = Aiwa.brain.sessions() }
            reload()
        }
    }

    override fun fill() {
        val chosen = FilesScope.chosen(this)
        entry("Tous les dépôts", "les productions de tous tes dépôts, ensemble", if (chosen == FilesScope.ALL) com.aiwa.app.common.Palette.GREEN else com.aiwa.app.common.Palette.CARD) { pick(FilesScope.ALL) }
        val list = repos
        if (list == null) { note("Je cherche tes dépôts…"); return }
        val inUse = Aiwa.state.value.status?.repo
        list.take(30).forEach { name ->
            val mine = sessions.count { it.repo == name }
            entry(name, if (mine > 0) "$mine session(s)" + (if (name == inUse) " · en cours" else "") else null, if (chosen == name) com.aiwa.app.common.Palette.GREEN else com.aiwa.app.common.Palette.CARD) { pick(name) }
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            fun small(text: String, click: () -> Unit) = Button(this).apply { this.text = text; isAllCaps = false; textSize = 13f; setOnClickListener { click() } }
                .also { row.addView(it, LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f)) }
            small("Voir le dépôt") { openUrl(this, "https://github.com/$name") }
            small("Changer de session") { chooseSession(name) }
            add(row, 2)
        }
        entry("Un autre dépôt", "copie son lien GitHub, puis touche ici") {
            val text = clipboardText(this)?.trim().orEmpty()
            val repo = Regex("github\\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\\.git)?(?:[/?#\\s]|$)").find(text)?.let { it.groupValues[1] + "/" + it.groupValues[2] }
                ?: text.takeIf { Regex("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+").matches(it) }
            if (repo == null) toastOnMain(this, "Copie d'abord le lien du dépôt (github.com/…/…).") else pick(repo)
        }
    }

    /** The sessions that work on this repository (the one in use is marked), or a new one: the next message then goes there. */
    private fun chooseSession(repo: String) {
        val mine = sessions.filter { it.repo == repo }
        val current = Aiwa.state.value.status?.session
        val labels = mine.map { (if (it.id == current) "● " else "") + it.title } + "＋ Nouvelle session"
        android.app.AlertDialog.Builder(this).setTitle(repo.substringAfter('/')).setItems(labels.toTypedArray()) { _, i ->
            CoroutineScope(Dispatchers.Main).launch {
                val out = withContext(Dispatchers.IO) {
                    if (i < mine.size) Aiwa.brain.select(mine[i].id)
                    else { val r = Aiwa.brain.setRepo(repo); if (r.ok) Aiwa.brain.select("new") else r }
                }
                withContext(Dispatchers.IO) { com.aiwa.app.brain.BrainSync.refresh() }
                toastOnMain(applicationContext, if (!out.ok) "Refusé : ${out.error}" else if (i < mine.size) "Session : ${mine[i].title}" else "Nouvelle session sur ${repo.substringAfter('/')} au prochain message")
                AiwaWidget.render(applicationContext, force = true)
                reload()
            }
        }.setNegativeButton("Annuler", null).show()
    }

    private fun pick(scope: String) { FilesScope.set(this, scope); com.aiwa.app.files.FilesWatch.refreshNow(applicationContext); finish() }
}
