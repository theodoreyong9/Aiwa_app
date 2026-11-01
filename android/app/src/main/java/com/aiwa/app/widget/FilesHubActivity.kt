package com.aiwa.app.widget

import android.content.Intent
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.files.FilesActivity

/** Fichiers: the kinds of files (with how many there are) and Ajouter. */
class FilesHubActivity : FloatActivity() {
    override val title = "Fichiers"

    override fun fill() {
        val counts = Aiwa.state.value.fileCounts
        for ((kind, label) in listOf("docs" to "Docs", "image" to "Images", "video" to "Vidéos", "app" to "Apps", "page" to "Pages")) {
            val n = counts[kind] ?: 0
            entry(label, if (n > 0) "$n" else "aucun pour l'instant") { startActivity(Intent(this, FilesActivity::class.java).putExtra(FilesActivity.EXTRA_KIND, kind)); finish() }
        }
        entry("Ajouter", "joindre un fichier à ton prochain message") { startActivity(Intent(this, AddActivity::class.java)); finish() }
    }
}
