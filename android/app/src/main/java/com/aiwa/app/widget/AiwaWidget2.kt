package com.aiwa.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.cast.CastActivity
import com.aiwa.app.scenario.ScenariosActivity
import com.aiwa.app.settings.SettingsActivity
import com.aiwa.app.update.InstallUpdateActivity
import com.aiwa.app.web.WebActivity

/**
 * The second widget: the same functions as the first, in a grid. Tabs: Réglages (opens the settings), Aiwa (the page shown) and Mise à jour (opens the update); in Aiwa twelve buttons: Question, Super agent (the ear), Fichiers
 * (the kinds of files and Ajouter), Cast, Scénarios, Swipe, Chambre, Favoris, Repo (the choice of the repository, a link on each line), Session (the linked session, a Claude button on each line), Wallet and
 * Search (Lien and QR code). Native views (res/layout/widget2.xml), no drawing: a tap opens the same windows as the first widget.
 */
object AiwaWidget2 {
    private val CELLS = listOf("question", "agent", "files", "cast", "scenario", "swipe", "room", "fav", "repo", "session", "wallet", "search")

    fun ids(context: Context): IntArray = AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, AiwaWidget2Provider::class.java))

    private fun activity(context: Context, code: Int, intent: Intent): PendingIntent =
        PendingIntent.getActivity(context, 200 + code, intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun activity(context: Context, code: Int, cls: Class<*>): PendingIntent = activity(context, code, Intent(context, cls))

    fun render(context: Context) {
        val ids = ids(context)
        if (ids.isEmpty()) return
        val snap = Aiwa.state.value
        val status = snap.status
        val v = RemoteViews(context.packageName, R.layout.widget2)
        fun voir(code: Int, mode: String) = activity(context, code, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))
        val scopeRepo = FilesScope.repo(context, status?.repo) ?: status?.repo
        val roomOpen = snap.chamberMode != "closed"
        val targets = mapOf(
            "question" to activity(context, 1, com.aiwa.app.question.AskActivity::class.java),
            "agent" to activity(context, 2, AiwaWidget.agentTarget(context, snap)),
            "files" to activity(context, 3, FilesHubActivity::class.java),
            "cast" to activity(context, 4, CastActivity::class.java),
            "scenario" to activity(context, 5, ScenariosActivity::class.java),
            "swipe" to activity(context, 6, com.aiwa.app.home.HomeActivity::class.java),
            "room" to activity(context, 7, com.aiwa.app.chamber.ChamberActivity::class.java),
            "fav" to voir(8, "favoris"),
            "repo" to activity(context, 9, RepoPickerActivity::class.java),
            "session" to (if (scopeRepo != null) activity(context, 10, Intent(context, RepoSessionActivity::class.java).putExtra(RepoSessionActivity.EXTRA_REPO, scopeRepo)) else activity(context, 10, RepoPickerActivity::class.java)),
            "wallet" to activity(context, 11, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "wallet")),
            "search" to activity(context, 12, SearchHubActivity::class.java),
        )
        val on = (if (snap.agentOpen || snap.listening) setOf("agent") else emptySet()) + (if (roomOpen) setOf("room") else emptySet()) + (if (status?.ask != null) setOf("question") else emptySet())
        CELLS.forEachIndexed { i, id ->
            val cell = context.resources.getIdentifier("w2_c_$id", "id", context.packageName)
            val text = context.resources.getIdentifier("w2_t_$id", "id", context.packageName)
            v.setOnClickPendingIntent(cell, targets.getValue(id))
            v.setInt(cell, "setBackgroundResource", if (id in on) R.drawable.preview_cell_agent else R.drawable.preview_cell)
            if (id == "repo") v.setTextViewText(text, FilesScope.label(context, status?.repo).take(10))
            if (id == "session") v.setTextViewText(text, (snap.sessionTitle ?: "Session").take(10))
            if (id == "agent") v.setTextViewText(text, CellModels.of(context, snap).getValue("agent").label.take(14))
            if (id == "room") v.setTextViewText(text, if (roomOpen) "En cours" else "Chambre")
        }
        v.setOnClickPendingIntent(R.id.w2_tab_settings, activity(context, 20, SettingsActivity::class.java))
        v.setOnClickPendingIntent(R.id.w2_tab_update, activity(context, 21, InstallUpdateActivity::class.java))
        v.setInt(R.id.w2_tab_update, "setBackgroundResource", if (snap.appUpdateReady) R.drawable.preview_cell_agent else R.drawable.preview_cell)
        try { AppWidgetManager.getInstance(context).updateAppWidget(ids, v) } catch (err: Exception) { /* the next change draws it again */ }
    }
}

class AiwaWidget2Provider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        wakeAiwa(context)
        AiwaWidget2.render(context)
    }
}
