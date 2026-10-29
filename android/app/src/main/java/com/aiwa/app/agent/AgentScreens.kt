package com.aiwa.app.agent

import android.content.Context
import android.content.Intent
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.cast.CastActivity
import com.aiwa.app.chamber.ChamberActivity
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.files.FilesActivity
import com.aiwa.app.home.HomeActivity
import com.aiwa.app.question.AskActivity
import com.aiwa.app.scenario.ScenariosActivity
import com.aiwa.app.settings.SettingsActivity
import com.aiwa.app.update.InstallUpdateActivity
import com.aiwa.app.voice.EarToggleActivity
import com.aiwa.app.voice.VoiceService
import com.aiwa.app.web.WebActivity
import com.aiwa.app.widget.AddActivity
import com.aiwa.app.widget.AiwaWidget
import com.aiwa.app.widget.OpenClaudeActivity
import com.aiwa.app.widget.ReportActivity
import com.aiwa.app.widget.WidgetTab
import com.aiwa.client.Command
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** What the super agent may open or do on the phone: the same screens as a tap on the widget. The words it uses are agent_lib.OPEN_KINDS of the brain. */
object AgentScreens {
    private fun go(context: Context, intent: Intent) { try { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (err: Exception) { toastOnMain(context, "Je ne peux pas ouvrir cet écran d'ici : ouvre Aiwa d'abord.") } }
    private fun go(context: Context, cls: Class<*>) = go(context, Intent(context, cls))
    private fun files(context: Context, kind: String) = go(context, Intent(context, FilesActivity::class.java).putExtra(FilesActivity.EXTRA_KIND, kind))
    private fun voir(context: Context, mode: String) = go(context, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))

    fun open(context: Context, token: String) {
        when (token) {
            "files_docs" -> files(context, "docs"); "files_image" -> files(context, "image"); "files_video" -> files(context, "video"); "files_app" -> files(context, "app"); "files_page" -> files(context, "page")
            "files" -> { WidgetTab.set(context, "files"); AiwaWidget.render(context, force = true) }
            "build" -> { WidgetTab.set(context, "agent"); AiwaWidget.render(context, force = true) }
            "scenario" -> go(context, ScenariosActivity::class.java)
            "cast" -> go(context, CastActivity::class.java)
            "voir" -> voir(context, "proche"); "voir_near" -> voir(context, "proche"); "voir_link" -> voir(context, "lien"); "voir_qr" -> voir(context, "qr"); "voir_fav" -> voir(context, "favoris")
            "voir_on" -> com.aiwa.app.voir.VoirSettings.setOn(context, true)
            "voir_off" -> com.aiwa.app.voir.VoirSettings.setOn(context, false)
            "chambre" -> go(context, ChamberActivity::class.java)
            "settings" -> go(context, SettingsActivity::class.java)
            "update" -> go(context, InstallUpdateActivity::class.java)
            "question" -> go(context, AskActivity::class.java)
            "claude" -> go(context, OpenClaudeActivity::class.java)
            "add" -> go(context, AddActivity::class.java)
            "listen" -> go(context, EarToggleActivity::class.java)
            "wallet" -> go(context, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "wallet"))
            "report" -> go(context, ReportActivity::class.java)
            "home" -> go(context, HomeActivity::class.java)
            "github" -> go(context, com.aiwa.app.settings.GithubConnectActivity::class.java)
            "health" -> go(context, com.aiwa.app.settings.HealthActivity::class.java)
            "claude_login" -> go(context, com.aiwa.app.settings.ClaudeLoginActivity::class.java)
            "keys" -> go(context, com.aiwa.app.settings.KeysActivity::class.java)
            "style" -> go(context, com.aiwa.app.settings.StyleActivity::class.java)
            "wall" -> WebActivity.wall(context)
        }
    }

    /** Applies a command the person agreed to (or that a master launched): the brain changes the repository and the session, the phone opens the screen and starts the cast. */
    suspend fun apply(context: Context, command: Command) {
        val out = withContext(Dispatchers.IO) { Aiwa.brain.agentApply(command.id) }
        if (!out.ok) { toastOnMain(context, out.error ?: "Les réglages ne sont plus d'actualité."); return }
        command.open?.let { open(context, it) }
        if (command.cast) withContext(Dispatchers.IO) {
            if (command.castWait) Aiwa.brain.castWish(command.castTv.orEmpty())
            else com.aiwa.app.cast.CastService.startLatest(context, command.castTv.orEmpty())
        }
        withContext(Dispatchers.IO) { com.aiwa.app.brain.BrainSync.refresh() }
        AiwaWidget.render(context, force = true)
    }
}
