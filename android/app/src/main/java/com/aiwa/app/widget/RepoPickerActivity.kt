package com.aiwa.app.widget

import android.os.Bundle
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** What the Files page looks at: every repository, or one of them (the ones used, the ones of the sessions, the public ones of the owner, and all of them with a GitHub token). */
class RepoPickerActivity : FloatActivity() {
    override val title = "Files : quel dépôt ?"
    private var repos: List<String>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { ensureBrain(applicationContext); repos = Aiwa.brain.repos() }
            reload()
        }
    }

    override fun fill() {
        val chosen = FilesScope.chosen(this)
        entry("Tous les dépôts", "les productions de tous tes dépôts, ensemble", if (chosen == FilesScope.ALL) com.aiwa.app.common.Palette.GREEN else com.aiwa.app.common.Palette.CARD) { pick(FilesScope.ALL) }
        val list = repos
        if (list == null) { note("Je cherche tes dépôts…"); return }
        list.take(30).forEach { name -> entry(name, null, if (chosen == name) com.aiwa.app.common.Palette.GREEN else com.aiwa.app.common.Palette.CARD) { pick(name) } }
    }

    private fun pick(scope: String) { FilesScope.set(this, scope); com.aiwa.app.files.FilesWatch.refreshNow(applicationContext); finish() }
}
