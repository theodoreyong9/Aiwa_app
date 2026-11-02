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
import com.aiwa.app.voice.AgentToggleActivity
import com.aiwa.app.voice.EarToggleActivity
import com.aiwa.app.web.WebActivity

/**
 * The second widget: the same functions as the first, in a grid. Tabs: Réglages (opens the settings), Aiwa (the page shown) and Mise à jour (opens the update); in Aiwa twelve buttons: Question, Oreille (it also carries the alerts), Fichiers
 * (the kinds of files and Ajouter), Cast, Scénarios, Swipe, Chambre, Favoris, Repo (the choice of the repository, a link on each line), Session (the linked session, a Claude button on each line), Wallet and
 * Search (Lien and QR code). Native views (res/layout/widget2.xml), no drawing: a tap opens the same windows as the first widget.
 */
object AiwaWidget2 {
    private val CELLS = listOf("question", "ear", "files", "cast", "scenario", "swipe", "room", "fav", "repo", "session", "wallet", "search")

    fun ids(context: Context): IntArray = AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, AiwaWidget2Provider::class.java))

    private fun activity(context: Context, code: Int, intent: Intent): PendingIntent =
        PendingIntent.getActivity(context, 200 + code, intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun activity(context: Context, code: Int, cls: Class<*>): PendingIntent = activity(context, code, Intent(context, cls))

    fun render(context: Context) {
        val ids = ids(context)
        if (ids.isEmpty()) return
        try { AppWidgetManager.getInstance(context).updateAppWidget(ids, views(context)) } catch (err: Exception) { /* the next change draws it again */ }
    }

    const val ACTION_TAB = "com.aiwa.app.AW2_TAB"
    const val ACTION_TOGGLE = "com.aiwa.app.AW2_TOGGLE"
    private val TABS = listOf("aiwa", "settings")
    fun tab(context: Context): String = com.aiwa.app.common.Prefs(context, "aiwa_widget2_tab").string("tab", "aiwa")?.takeIf { it in TABS } ?: "aiwa"
    fun setTab(context: Context, tab: String) { com.aiwa.app.common.Prefs(context, "aiwa_widget2_tab").put("tab", tab); render(context) }

    private val COLORS = mapOf("question" to "#F5C451", "ear" to "#5AC8FA", "files" to "#34D399", "cast" to "#A78BFA", "scenario" to "#F472B6", "swipe" to "#FB923C", "room" to "#60A5FA",
        "fav" to "#FBBF24", "repo" to "#C4B5FD", "session" to "#F59E0B", "wallet" to "#2DD4BF", "search" to "#38BDF8")

    /** One of the twelve places of the grid: what it shows (icon, word, colour of its badge, state) and what a touch does. */
    private class Slot(val icon: Int, val label: String, val color: String, val click: PendingIntent, val state: Int = 0)    // state: 0 plain, 1 on, 2 calls for an answer

    private fun toggle(context: Context, code: Int, what: String): PendingIntent =
        PendingIntent.getBroadcast(context, 300 + code, Intent(context, AiwaWidget2Provider::class.java).setAction(ACTION_TOGGLE).putExtra("what", what).addFlags(Intent.FLAG_RECEIVER_FOREGROUND), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun tabIntent(context: Context, code: Int, tab: String): PendingIntent =
        PendingIntent.getBroadcast(context, 400 + code, Intent(context, AiwaWidget2Provider::class.java).setAction(ACTION_TAB).putExtra("tab", tab).addFlags(Intent.FLAG_RECEIVER_FOREGROUND), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    /** A switch of the settings flipped from the widget itself (no window): what the same line of the settings does. */
    fun flip(context: Context, what: String) {
        val app = context.applicationContext
        when (what) {
            "ear" -> {
                val on = !com.aiwa.app.voice.ListenSettings.enabled(app)
                com.aiwa.app.voice.ListenSettings.setEnabled(app, on)
                if (on) com.aiwa.app.voice.VoiceService.start(app) else { com.aiwa.app.voice.VoiceService.stop(app); Aiwa.update { it.copy(listening = false) } }
            }
            "ready" -> com.aiwa.app.voice.ReadySettings.set(app, !com.aiwa.app.voice.ReadySettings.enabled(app))
            "push" -> {
                val now = Aiwa.state.value.status?.pushMain ?: true
                Thread { try { Aiwa.brain.setPushMain(!now); com.aiwa.app.brain.BrainSync.refresh() } catch (err: Exception) { }; AiwaWidget.render(app, force = true) }.start()
            }
            "bg" -> WidgetBackground.next(app)
        }
        AiwaWidget.render(app, force = true)
    }

    /** The widget as it is now (also what the picker is shown as its preview). */
    fun views(context: Context): RemoteViews {
        val snap = Aiwa.state.value
        val status = snap.status
        val v = RemoteViews(context.packageName, R.layout.widget2)
        val onSettings = tab(context) == "settings"
        fun voir(code: Int, mode: String) = activity(context, code, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))
        fun group(code: Int, id: String) = activity(context, code, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, id))
        val slots: List<Slot> = if (!onSettings) {
            val scopeRepo = FilesScope.repo(context, status?.repo) ?: status?.repo
            val roomOpen = com.aiwa.app.chamber.ChamberState.rooms.any { it.optJSONObject("partner") != null || it.optBoolean("knock") }
            // the ear carries the alerts of the first widget's Super agent button (what is missing, what the agent has to say): then it is red and opens the window that answers it
            val alert = AiwaWidget.agentTarget(context, snap) != AgentToggleActivity::class.java
            listOf(
                Slot(R.drawable.fw_i_question, "Question", COLORS.getValue("question"), activity(context, 1, com.aiwa.app.question.AskActivity::class.java), if (status?.ask != null) 1 else 0),
                Slot(R.drawable.fw_i_ear, if (alert) CellModels.of(context, snap).getValue("agent").label.take(14) else if (snap.listening) "Écoute" else "Oreille", COLORS.getValue("ear"),
                    activity(context, 2, if (alert) AiwaWidget.agentTarget(context, snap) else EarToggleActivity::class.java), if (alert) 2 else if (snap.listening) 1 else 0),
                Slot(R.drawable.fw_i_files, "Fichiers", COLORS.getValue("files"), activity(context, 3, FilesHubActivity::class.java)),
                Slot(R.drawable.fw_i_cast, "Cast", COLORS.getValue("cast"), activity(context, 4, CastActivity::class.java)),
                Slot(R.drawable.fw_i_scenario, "Scénarios", COLORS.getValue("scenario"), activity(context, 5, ScenariosActivity::class.java)),
                Slot(R.drawable.fw_i_pin, "Swipe", COLORS.getValue("swipe"), activity(context, 6, com.aiwa.app.home.HomeActivity::class.java)),
                Slot(R.drawable.fw_i_room, if (roomOpen) "En cours" else "Chambres", COLORS.getValue("room"), activity(context, 7, com.aiwa.app.chamber.ChambersActivity::class.java), if (roomOpen) 1 else 0),
                Slot(R.drawable.fw_i_star, "Favoris", COLORS.getValue("fav"), voir(8, "favoris")),
                Slot(R.drawable.fw_i_github, FilesScope.label(context, status?.repo).take(10), COLORS.getValue("repo"), activity(context, 9, RepoPickerActivity::class.java)),
                Slot(R.drawable.fw_i_claude, (snap.sessionTitle ?: "Session").take(10), COLORS.getValue("session"),
                    if (scopeRepo != null) activity(context, 10, Intent(context, RepoSessionActivity::class.java).putExtra(RepoSessionActivity.EXTRA_REPO, scopeRepo)) else activity(context, 10, RepoPickerActivity::class.java)),
                Slot(R.drawable.fw_i_wallet, "Wallet", COLORS.getValue("wallet"), activity(context, 11, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "wallet"))),
                Slot(R.drawable.fw_i_link, "Search", COLORS.getValue("search"), activity(context, 12, SearchHubActivity::class.java)),
            )
        } else {
            // the twelve tiles of the settings window, here: the groups open their window, the switches flip on the spot
            val accountsOk = status?.claudeLogin == "ok" && status.githubToken
            val listen = com.aiwa.app.voice.ListenSettings.enabled(context)
            listOf(
                Slot(R.drawable.fw_i_key, "Connexions", COLORS.getValue("question"), group(30, "accounts"), if (accountsOk) 0 else 2),
                Slot(R.drawable.fw_i_talk, "Les mots", COLORS.getValue("ear"), group(31, "words")),
                Slot(R.drawable.fw_i_trophy, "Jeu", COLORS.getValue("fav"), activity(context, 32, com.aiwa.app.settings.PersonaActivity::class.java)),
                Slot(R.drawable.fw_i_aiwa, "Moi", COLORS.getValue("files"), group(33, "me")),
                Slot(R.drawable.fw_i_volume, "Voix", COLORS.getValue("search"), group(34, "voice")),
                Slot(R.drawable.fw_i_ear, if (listen) "Écoute ✓" else "Écoute", COLORS.getValue("room"), toggle(context, 35, "ear"), if (listen) 1 else 0),
                Slot(R.drawable.fw_i_papers, "Papers", COLORS.getValue("session"), activity(context, 36, com.aiwa.app.settings.PapersActivity::class.java)),
                Slot(R.drawable.fw_i_tools, "Modèle", COLORS.getValue("swipe"), group(37, "model")),
                Slot(R.drawable.fw_i_report, if (com.aiwa.app.voice.ReadySettings.enabled(context)) "Prêt ✓" else "Prêt", COLORS.getValue("wallet"), toggle(context, 38, "ready"), if (com.aiwa.app.voice.ReadySettings.enabled(context)) 1 else 0),
                Slot(R.drawable.fw_i_swap, if (status?.pushMain ?: true) "Push ✓" else "Push", COLORS.getValue("scenario"), toggle(context, 39, "push"), if (status?.pushMain ?: true) 1 else 0),
                Slot(R.drawable.fw_i_image, WidgetBackground.label(context).take(10), COLORS.getValue("cast"), toggle(context, 40, "bg")),
                Slot(R.drawable.fw_i_report, "État", COLORS.getValue("repo"), activity(context, 41, com.aiwa.app.settings.HealthActivity::class.java)),
            )
        }
        CELLS.forEachIndexed { i, id ->
            val slot = slots[i]
            fun rid(prefix: String) = context.resources.getIdentifier("w2_${prefix}_$id", "id", context.packageName)
            v.setOnClickPendingIntent(rid("c"), slot.click)
            v.setInt(rid("c"), "setBackgroundResource", when (slot.state) { 2 -> R.drawable.w2_cell_alert; 1 -> R.drawable.w2_cell_on; else -> R.drawable.w2_cell })
            v.setImageViewResource(rid("i"), slot.icon)
            v.setInt(rid("i"), "setColorFilter", android.graphics.Color.parseColor(slot.color))
            v.setInt(rid("b"), "setBackgroundResource", badge(slot.color))
            v.setTextViewText(rid("t"), slot.label)
        }
        // the photo chosen in the settings (Fond du widget), the same as the first widget's; none: the deep card alone
        val photo = WidgetBackground.res(context)
        v.setViewVisibility(R.id.w2_photo, if (photo != 0) android.view.View.VISIBLE else android.view.View.GONE)
        v.setViewVisibility(R.id.w2_scrim, if (photo != 0) android.view.View.VISIBLE else android.view.View.GONE)
        if (photo != 0) v.setImageViewResource(R.id.w2_photo, photo)
        // the tabs: Réglages and Aiwa are the two pages of the grid; the open one is lit; Mise à jour is there only when there is an update
        v.setOnClickPendingIntent(R.id.w2_tab_settings, tabIntent(context, 1, "settings"))
        v.setOnClickPendingIntent(R.id.w2_tab_aiwa, tabIntent(context, 2, "aiwa"))
        v.setInt(R.id.w2_tab_settings, "setBackgroundResource", if (onSettings) R.drawable.w2_tab_on else R.drawable.w2_tab_off)
        v.setInt(R.id.w2_tab_aiwa, "setBackgroundResource", if (onSettings) R.drawable.w2_tab_off else R.drawable.w2_tab_on)
        v.setOnClickPendingIntent(R.id.w2_tab_update, activity(context, 21, InstallUpdateActivity::class.java))
        v.setViewVisibility(R.id.w2_tab_update, if (snap.appUpdateReady) android.view.View.VISIBLE else android.view.View.GONE)      // like the first widget: the update tab is there only when there is an update
        v.setInt(R.id.w2_tab_update, "setBackgroundResource", if (snap.appUpdateReady) R.drawable.w2_tab_ready else R.drawable.w2_tab_off)
        return v
    }

    /** The badge (a round glass of the colour of the icon) for a colour of the table above. */
    private fun badge(color: String): Int {
        val key = COLORS.entries.firstOrNull { it.value == color }?.key ?: "question"
        return when (key) {
            "question" -> R.drawable.w2_badge_question; "ear" -> R.drawable.w2_badge_ear; "files" -> R.drawable.w2_badge_files; "cast" -> R.drawable.w2_badge_cast
            "scenario" -> R.drawable.w2_badge_scenario; "swipe" -> R.drawable.w2_badge_swipe; "room" -> R.drawable.w2_badge_room; "fav" -> R.drawable.w2_badge_fav
            "repo" -> R.drawable.w2_badge_repo; "session" -> R.drawable.w2_badge_session; "wallet" -> R.drawable.w2_badge_wallet; else -> R.drawable.w2_badge_search
        }
    }
}

class AiwaWidget2Provider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        wakeAiwa(context)
        AiwaWidget2.render(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            AiwaWidget2.ACTION_TAB -> AiwaWidget2.setTab(context, intent.getStringExtra("tab") ?: return)
            AiwaWidget2.ACTION_TOGGLE -> AiwaWidget2.flip(context, intent.getStringExtra("what") ?: return)
            else -> super.onReceive(context, intent)
        }
    }
}
