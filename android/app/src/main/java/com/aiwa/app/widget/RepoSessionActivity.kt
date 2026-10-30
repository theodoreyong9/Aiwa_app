package com.aiwa.app.widget

import android.os.Bundle
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The sessions of one repository (the one of the Files page): the one in use is marked, a touch makes another the one in use, and « Nouvelle session » makes one now. */
class RepoSessionActivity : FloatActivity() {
    override val title: String get() = intent.getStringExtra(EXTRA_REPO)?.substringAfter('/') ?: "Sessions"
    private var sessions: List<com.aiwa.client.Session>? = null
    private val repo: String get() = intent.getStringExtra(EXTRA_REPO).orEmpty()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.Main).launch {
            sessions = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.sessions() }
            reload()
        }
    }

    private fun act(done: String, call: () -> com.aiwa.client.Brain.Outcome) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { val o = call(); BrainSync.refresh(); o }
            toastOnMain(applicationContext, if (out.ok) done else "Refusé : ${out.error}")
            AiwaWidget.render(applicationContext, force = true)
            if (out.ok) finish() else reload()
        }
    }

    /** A long touch on a session: its name, as the person wants it (the widget and the lists show it). */
    private fun rename(s: com.aiwa.client.Session) {
        val field = android.widget.EditText(this).apply { setText(s.title); setSelection(text.length); setSingleLine(true); filters = arrayOf(android.text.InputFilter.LengthFilter(60)) }
        android.app.AlertDialog.Builder(this).setTitle("Renommer la session").setView(field)
            .setPositiveButton("Renommer") { _, _ ->
                val title = field.text.toString().trim()
                if (title.isNotEmpty()) CoroutineScope(Dispatchers.Main).launch {
                    val out = withContext(Dispatchers.IO) { val o = Aiwa.brain.rename(s.id, title); BrainSync.refresh(); o }
                    toastOnMain(applicationContext, if (out.ok) "Session renommée : $title" else "Refusé : ${out.error}")
                    sessions = withContext(Dispatchers.IO) { Aiwa.brain.sessions() }
                    AiwaWidget.render(applicationContext, force = true)
                    reload()
                }
            }.setNegativeButton("Annuler", null).show()
    }

    override fun fill() {
        val list = sessions
        if (list == null) { note("Je cherche les sessions…"); return }
        val current = Aiwa.state.value.status?.session
        // the sessions of this repository, and those made before a repository was known (they have none noted): the one in use is always there, first
        val mine = list.filter { it.repo.equals(repo, ignoreCase = true) || it.repo.isNullOrBlank() || it.id == current }.sortedByDescending { it.id == current }
        if (mine.isEmpty()) note("Aucune session sur ce dépôt pour l'instant.")
        for (s in mine) entry((if (s.id == current) "● " else "○ ") + s.title, (if (s.id == current) "en cours" else if (s.repo.isNullOrBlank()) "dépôt non noté · touche pour en faire la session en cours" else "Touche pour en faire la session en cours") + " · appui long : renommer", Palette.CARD) {
            act("Session : ${s.title}") { Aiwa.brain.select(s.id) }
        }.setOnLongClickListener { rename(s); true }
        entry("＋ Nouvelle session", "Je la crée tout de suite sur ce dépôt") { act("Je crée une session sur ${repo.substringAfter('/')}…") { Aiwa.brain.newSession(repo) } }
    }

    companion object { const val EXTRA_REPO = "repo" }
}
