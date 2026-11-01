package com.aiwa.app.files

import android.content.Context
import android.content.Intent
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * « PJ » of a target: ALL the files, every kind and every repository, with a tick. The ones ticked are the files that go with this target (the CV and the letter for this journal); the choice is
 * remembered at once, by the brain, and can be changed any time. Nothing is moved, nothing is sent: a label only. No proposal from anybody: the person chooses.
 */
class PjActivity : FloatActivity() {
    override val title: String get() = "PJ : " + (intent.getStringExtra(EXTRA_FOR) ?: "")
    private var all: List<com.aiwa.client.Production>? = null
    private val ticked = LinkedHashSet<String>()
    private val repo get() = intent.getStringExtra(EXTRA_REPO).orEmpty()
    private val tag get() = intent.getStringExtra(EXTRA_TAG).orEmpty()
    private val file get() = intent.getStringExtra(EXTRA_FILE).orEmpty()
    private val cible get() = intent.getStringExtra(EXTRA_CIBLE).orEmpty()

    override fun onResume() {
        super.onResume()
        CoroutineScope(Dispatchers.Main).launch {
            val got = withContext(Dispatchers.IO) { try { Aiwa.brain.files(null) } catch (err: Exception) { null } }
            val saved = withContext(Dispatchers.IO) { try { Aiwa.brain.links(repo, tag, file)[cible].orEmpty() } catch (err: Exception) { emptyList() } }
            ticked.clear(); ticked.addAll(saved)
            all = got?.items?.values?.flatten()?.filterNot { it.repo == repo && it.tag == tag && it.file == file }
            reload()
        }
    }

    private fun idOf(p: com.aiwa.client.Production) = p.repo + "|" + p.tag + "|" + p.file

    override fun fill() {
        val list = all
        if (list == null) { note("Je lis tes fichiers…"); return }
        if (list.isEmpty()) { note("Aucun autre fichier."); return }
        note("Coche les fichiers qui vont avec cette cible. Ton choix est gardé.")
        val kinds = mapOf("docs" to "Document", "image" to "Image", "video" to "Vidéo", "app" to "App", "page" to "Page")
        for (p in list) {
            val on = idOf(p) in ticked
            entry((if (on) "☑  " else "☐  ") + p.title, (kinds[p.kind] ?: p.kind) + " · " + p.repoName, if (on) Palette.CARD else Palette.CARD) {
                if (on) ticked.remove(idOf(p)) else ticked.add(idOf(p))
                val now = ticked.toList()
                CoroutineScope(Dispatchers.IO).launch { try { Aiwa.brain.setLinks(repo, tag, file, cible, now) } catch (err: Exception) { } }
                reload()
            }.alpha = if (on) 1f else 0.75f
        }
    }

    companion object {
        private const val EXTRA_REPO = "repo"
        private const val EXTRA_TAG = "tag"
        private const val EXTRA_FILE = "file"
        private const val EXTRA_CIBLE = "cible"
        private const val EXTRA_FOR = "for"
        fun intent(context: Context, repo: String, tag: String, file: String, cible: String, label: String): Intent = Intent(context, PjActivity::class.java)
            .putExtra(EXTRA_REPO, repo).putExtra(EXTRA_TAG, tag).putExtra(EXTRA_FILE, file).putExtra(EXTRA_CIBLE, cible).putExtra(EXTRA_FOR, cible.take(40))
    }
}
