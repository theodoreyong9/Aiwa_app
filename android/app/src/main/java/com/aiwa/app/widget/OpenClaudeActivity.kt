package com.aiwa.app.widget

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val CLAUDE_APP_PACKAGE = "com.anthropic.claude"

/**
 * The widget's « Claude » button: a no-UI trampoline that opens the current cloud session in the Claude app, where its conversation lives (Aiwa cannot show a cloud reply itself). The session
 * is the one in use or, when the next message starts a new one, the last one; with none at all, Claude's Code tab. The app is asked first (it may claim claude.ai/code links); without it,
 * whatever handles the link, the browser, gets it.
 */
class OpenClaudeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        val known = Aiwa.state.value.let { it.sessionId != null || it.status?.lastSession != null }
        if (known && open()) { finish(); return }
        // No session yet: one is made on the repository in use (this is what the button is for, not a greyed cell); without a repository, the list of them opens.
        val repo = Aiwa.state.value.status?.repo
        if (!known && repo == null) {
            toastOnMain(this, "Choisis d'abord un dépôt.")
            startActivity(Intent(this, RepoPickerActivity::class.java)); finish(); return
        }
        if (!known && repo != null) {
            toastOnMain(this, "Je crée une session sur ${repo.substringAfter('/')}… elle apparaîtra dans Claude.")
            val app = applicationContext
            CoroutineScope(Dispatchers.IO).launch { Aiwa.brain.setRepo(repo); BrainSync.refresh(); AiwaWidget.render(app, force = true) }
            finish(); return
        }
        // No session known: the process may have restarted since the widget last drew, so ask the brain which one is current (a session if there is one, else Claude's Code tab).
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { BrainSync.refresh() }
            if (!open()) toastOnMain(this@OpenClaudeActivity, "Impossible d'ouvrir l'appli Claude.")
            finish()
        }
    }

    private fun open(): Boolean {
        val snap = Aiwa.state.value
        val id = snap.sessionId ?: snap.status?.lastSession
        val url = id?.let { sid -> snap.sessions.firstOrNull { it.id == sid }?.url }
        val target = Uri.parse(url?.takeIf { it.startsWith("https://claude.ai/") } ?: if (id != null) "https://claude.ai/code/$id" else "https://claude.ai/code")
        fun view() = Intent(Intent.ACTION_VIEW, target).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val opened = try { startActivity(view().setPackage(CLAUDE_APP_PACKAGE)); true } catch (err: ActivityNotFoundException) {
            try { startActivity(view()); true } catch (err2: ActivityNotFoundException) { false }
        }
        if (opened && (snap.status?.waiting == true || (snap.status?.silenceMinutes ?: 0) > 0)) {
            // The person goes to answer: the waiting indicator has done its job.
            val app = applicationContext
            CoroutineScope(Dispatchers.IO).launch { Aiwa.brain.clearWaiting(); BrainSync.refresh(); AiwaWidget.render(app, force = true) }
        }
        return opened
    }
}
