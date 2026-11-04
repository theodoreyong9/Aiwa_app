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
    /**
     * Opens a screen. From the background (the voice service, an answer that came after thirty seconds) Android 10+ lets an application start a window only if it has the overlay right; otherwise the start is
     * dropped WITHOUT an error, and the agent would say « c'est ouvert » for nothing. So without that right a notification is offered (a touch opens the screen, and it comes up by itself when the phone allows it).
     */
    private fun go(context: Context, intent: Intent) {
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (context !is android.app.Activity && android.os.Build.VERSION.SDK_INT >= 29 && !android.provider.Settings.canDrawOverlays(context)) { offer(context, intent); return }
        try { context.startActivity(intent) } catch (err: Exception) { offer(context, intent) }
    }

    private fun offer(context: Context, intent: Intent) {
        try {
            val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            nm.createNotificationChannel(android.app.NotificationChannel("aiwa_open", "Ouvrir ce que tu demandes", android.app.NotificationManager.IMPORTANCE_HIGH))
            val pending = android.app.PendingIntent.getActivity(context, intent.toString().hashCode(), intent, android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT)
            nm.notify(7311, android.app.Notification.Builder(context, "aiwa_open").setSmallIcon(com.aiwa.app.R.drawable.ic_aiwa).setContentTitle("Aiwa").setContentText("Touche pour ouvrir ce que tu as demandé")
                .setContentIntent(pending).setFullScreenIntent(pending, true).setAutoCancel(true).build())
        } catch (err: Exception) { /* no notification right: the toast below is all there is */ }
        toastOnMain(context, "Android ne me laisse pas ouvrir l'écran depuis l'arrière-plan : touche la notification (ou autorise « Afficher par-dessus d'autres applis » pour Aiwa).")
    }
    private fun go(context: Context, cls: Class<*>) = go(context, Intent(context, cls))
    private fun files(context: Context, kind: String) = go(context, Intent(context, FilesActivity::class.java).putExtra(FilesActivity.EXTRA_KIND, kind))
    private fun voir(context: Context, mode: String) = go(context, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))

    /** What `open` knows how to open: also what the file of the application's look may name as an action. */
    val TOKENS = setOf(
        "files_docs", "files_image", "files_video", "files_app", "files_page", "files", "build", "scenario", "cast", "voir", "voir_near", "voir_link", "voir_qr", "voir_fav", "voir_on", "voir_off",
        "chambre", "chambres", "settings", "update", "question", "claude", "add", "listen", "wallet", "report", "home", "github", "health", "claude_login", "keys", "style", "wall",
        // what the widgets show, by voice too: the choice of the repository, the sessions, the tiles of the settings one by one and their switches
        "repo", "session", "scan", "trust_open", "trust_close", "set_accounts", "set_words", "set_persona", "set_me", "set_voice", "set_papers", "set_model", "set_health", "set_ear", "set_ready", "set_push", "set_bg",
    )

    fun open(context: Context, token: String) {
        when (token) {
            "files_docs" -> files(context, "docs"); "files_image" -> files(context, "image"); "files_video" -> files(context, "video"); "files_app" -> files(context, "app"); "files_page" -> files(context, "page")
            "files" -> { WidgetTab.set(context, "files"); AiwaWidget.render(context, force = true) }
            "build" -> { WidgetTab.set(context, "agent"); AiwaWidget.render(context, force = true) }
            "scenario" -> go(context, ScenariosActivity::class.java)
            "cast" -> go(context, CastActivity::class.java)
            "voir" -> go(context, com.aiwa.app.home.ProfileActivity.homeIntent(context)); "voir_near" -> go(context, com.aiwa.app.home.ProfileActivity.homeIntent(context)); "voir_link" -> voir(context, "lien"); "voir_qr" -> voir(context, "qr"); "voir_fav" -> voir(context, "favoris")
            "voir_on" -> com.aiwa.app.voir.VoirSettings.setOn(context, true)
            "voir_off" -> com.aiwa.app.voir.VoirSettings.setOn(context, false)
            "memory" -> go(context, com.aiwa.app.settings.MemoryActivity::class.java)
            "chambre", "chambres" -> go(context, com.aiwa.app.chamber.ChambersActivity::class.java)      // the list: one line per person she called
            // the profile on the screen: scanned (an opinion by a session, read-only), or its access to the widget given (asked in full first) or taken back
            "scan" -> {
                val repo = com.aiwa.app.home.ScreenNow.repo
                if (repo == null || com.aiwa.app.home.ScreenNow.own) toastOnMain(context, "Aucun profil d'une autre personne à l'écran.")
                else Thread { try { Aiwa.brain.agentAsk("Scanne cette page ($repo) : lis ses fichiers publics (la page, ses scénarios, les contrats qu'elle cite) et dis-moi si quelque chose est dangereux ou douteux. Lecture seule.") } catch (err: Exception) { } }.start()
            }
            "trust_open" -> {
                val repo = com.aiwa.app.home.ScreenNow.repo
                if (repo == null || com.aiwa.app.home.ScreenNow.own) toastOnMain(context, "Aucun profil d'une autre personne à l'écran.")
                else go(context, Intent(context, com.aiwa.app.home.TrustConfirmActivity::class.java).putExtra(com.aiwa.app.home.TrustConfirmActivity.EXTRA_REPO, repo))
            }
            "trust_close" -> {
                val repo = com.aiwa.app.home.ScreenNow.repo
                if (repo == null || com.aiwa.app.home.ScreenNow.own) toastOnMain(context, "Aucun profil d'une autre personne à l'écran.")
                else { com.aiwa.app.home.TrustedProfiles.set(context, repo, false); com.aiwa.app.home.ScreenNow.reload?.invoke(); toastOnMain(context, "Accès retiré : la page de $repo est de nouveau fermée.") }
            }
            "repo" -> go(context, com.aiwa.app.widget.RepoPickerActivity::class.java)
            "session" -> {
                val repo = com.aiwa.app.widget.FilesScope.repo(context, Aiwa.state.value.status?.repo) ?: Aiwa.state.value.status?.repo
                if (repo != null) go(context, Intent(context, com.aiwa.app.widget.RepoSessionActivity::class.java).putExtra(com.aiwa.app.widget.RepoSessionActivity.EXTRA_REPO, repo)) else go(context, com.aiwa.app.widget.RepoPickerActivity::class.java)
            }
            "set_accounts" -> go(context, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, "accounts"))
            "set_words" -> go(context, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, "words"))
            "set_me" -> go(context, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, "me"))
            "set_voice" -> go(context, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, "voice"))
            "set_model" -> go(context, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, "model"))
            "set_persona" -> go(context, com.aiwa.app.settings.PersonaActivity::class.java)
            "set_papers" -> go(context, com.aiwa.app.settings.PapersActivity::class.java)
            "set_ear" -> com.aiwa.app.widget.AiwaWidget2.flip(context, "ear")
            "set_ready" -> com.aiwa.app.widget.AiwaWidget2.flip(context, "ready")
            "set_push" -> com.aiwa.app.widget.AiwaWidget2.flip(context, "push")
            "set_bg" -> com.aiwa.app.widget.AiwaWidget2.flip(context, "bg")
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
            "health", "set_health" -> go(context, com.aiwa.app.settings.HealthActivity::class.java)
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
        command.press?.let { com.aiwa.app.home.ScreenNow.press(it) }
        command.find?.let { q ->
            val now = com.aiwa.app.home.ScreenNow.find
            if (now != null) now(q) else go(context, com.aiwa.app.home.ProfileActivity.homeIntent(context).putExtra(com.aiwa.app.home.ProfileActivity.EXTRA_FIND, q))
        }
        if (command.cast) withContext(Dispatchers.IO) {
            if (command.castWait) Aiwa.brain.castWish(command.castTv.orEmpty())
            else com.aiwa.app.cast.CastService.startLatest(context, command.castTv.orEmpty())
        }
        withContext(Dispatchers.IO) { com.aiwa.app.brain.BrainSync.refresh() }
        AiwaWidget.render(context, force = true)
    }
}
