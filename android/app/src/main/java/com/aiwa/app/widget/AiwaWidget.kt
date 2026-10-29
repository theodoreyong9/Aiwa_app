package com.aiwa.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.Link
import com.aiwa.app.brain.Snapshot
import com.aiwa.app.brain.hasTermuxPermission
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.cast.CastActivity
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.files.FilesActivity
import com.aiwa.app.question.AskActivity
import com.aiwa.app.scenario.ScenariosActivity
import com.aiwa.app.settings.SettingsActivity
import com.aiwa.app.update.InstallUpdateActivity
import com.aiwa.app.voice.AgentToggleActivity
import com.aiwa.app.voice.EarToggleActivity
import com.aiwa.app.web.WebActivity

/**
 * The widget: five pictures drawn by WidgetArt (one per page, the card included) under invisible touch zones (res/layout/fast_widget.xml, written by scripts/gen-widget-layout.py).
 * A tap on a tab only turns the two ViewFlippers (a partial update): nothing is read, nothing is drawn again, so it is instant. The pictures are drawn again whenever the state changes.
 *
 * The tab strip, from the left: Réglages (opens the settings), Agent, Files, Game, then Mise à jour (only when an update exists).
 * Pages: Agent (a Chambre en cours cell at the left of the Super agent while a room is open, Claude; below: Écoute, Ajouter, Scénario, Cast TV) · Files (the repository or all, with a button to see it and one to change its session, then docs, images,
 * vidéos, apps, pages) · Game (Wallet; Proximité, Lien, QR code, Favoris). The top bar, at the right of the tabs: Mise à jour (only when an update exists), Réglages.
 * Question (the report is in it) is the last cell of the Agent page.
 * The Chambre has no page here: it lives in the application.
 */
object AiwaWidget {
    const val ACTION_TAB = "com.aiwa.app.AW_TAB"
    const val ACTION_BUSY = "com.aiwa.app.AW_BUSY"
    private var lastSignature = ""
    private val IMG = intArrayOf(R.id.fw_img0, R.id.fw_img1, R.id.fw_img2)
    private val LETTER = listOf("a", "f", "v")
    private val TAB_IDS = listOf("t_agent", "t_files", "t_voir")

    fun ids(context: Context): IntArray = AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, AiwaWidgetProvider::class.java))

    /** The tap on a tab: ONLY the page of the two flippers changes, with a partial update. */
    fun switchTab(context: Context, tab: String) {
        WidgetTab.set(context, tab)
        val ids = ids(context)
        if (ids.isEmpty()) return
        val v = RemoteViews(context.packageName, R.layout.fast_widget)
        val page = WidgetTab.PAGES.indexOf(tab).coerceAtLeast(0)
        v.setDisplayedChild(R.id.fw_img_flip, page)
        v.setDisplayedChild(R.id.fw_zone_flip, page)
        try { AppWidgetManager.getInstance(context).partiallyUpdateAppWidget(ids, v) } catch (err: Exception) { render(context, force = true) }
        lastSignature = ""      // the next full drawing is not skipped
    }

    /** Draws the widget again from the current state; `force` also when nothing visible changed (a new widget, a new size). */
    fun render(context: Context, force: Boolean = false) {
        val ids = ids(context)
        if (ids.isEmpty()) return
        val snap = Aiwa.state.value
        val tab = WidgetTab.get(context)
        val signature = listOf(
            tab, snap.link, snap.status?.repo, snap.status?.session, snap.status?.sending, snap.status?.waiting, snap.status?.silenceMinutes, snap.status?.attachments, snap.status?.claudeLogin,
            snap.status?.ask?.id, snap.status?.agent?.say?.id, snap.status?.agent?.proposal?.id, snap.status?.agent?.command?.id, snap.status?.githubError, snap.listening, snap.agentOpen, snap.appUpdateReady,
            snap.fileCounts, FilesScope.chosen(context), snap.chamberMode, snap.status?.chamber?.active,
            hasTermuxPermission(context), WidgetBackground.key(context), snap.sessionTitle,
        ).joinToString("|")
        if (!force && signature == lastSignature) return
        lastSignature = signature
        val views = try { build(context, snap, tab) } catch (err: Throwable) { return }
        try { AppWidgetManager.getInstance(context).updateAppWidget(ids, views) } catch (err: Exception) { }
    }

    private fun activity(context: Context, code: Int, intent: Intent): PendingIntent =
        PendingIntent.getActivity(context, code, intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun activity(context: Context, code: Int, cls: Class<*>): PendingIntent = activity(context, code, Intent(context, cls))

    private fun broadcast(context: Context, code: Int, action: String, vararg extras: Pair<String, String>): PendingIntent {
        // FLAG_RECEIVER_FOREGROUND: the tap goes to the front of the queue of broadcasts, it does not wait behind the others
        val intent = Intent(context, AiwaWidgetProvider::class.java).setAction(action).addFlags(Intent.FLAG_RECEIVER_FOREGROUND)
        extras.forEach { intent.putExtra(it.first, it.second) }
        return PendingIntent.getBroadcast(context, code, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }

    /** One cell of a page: what is drawn, its share of the row, and what a tap does (none = nothing). */
    private class Cell(val btn: WidgetArt.Btn, val weight: Float, val click: PendingIntent?, val zone: Int? = null)

    private fun id(context: Context, name: String): Int = context.resources.getIdentifier(name, "id", context.packageName)

    private fun build(context: Context, snap: Snapshot, tab: String): RemoteViews {
        val v = RemoteViews(context.packageName, R.layout.fast_widget)
        val status = snap.status
        val agent = status?.agent
        val agentNeeds = agent != null && (agent.say != null || agent.proposal != null || agent.command != null)
        val brainBad = snap.link == Link.DOWN || snap.link == Link.MISSING || status?.claudeLogin == "needed"
        val waiting = status?.waiting == true || (status?.silenceMinutes ?: 0) > 0
        val alert = waiting || agentNeeds || !hasTermuxPermission(context) || brainBad
        // ---- the tabs, then the top bar ----
        val tabs = listOfNotNull(
            WidgetArt.Tab(R.drawable.fw_i_settings, "Réglages", "grey", weight = 0.55f),
            WidgetArt.Tab(R.drawable.fw_i_build, "Agent", if (alert) "red" else "orange", always = alert, dot = snap.agentOpen || snap.listening),
            WidgetArt.Tab(R.drawable.fw_i_files, "Files", "green"),
            WidgetArt.Tab(R.drawable.fw_i_game, "Game", "violet"),
            if (snap.appUpdateReady) WidgetArt.Tab(R.drawable.fw_i_update, "Mise à jour", "green", weight = 0.55f, always = true) else null,
        )
        v.setViewVisibility(R.id.t_upd, if (snap.appUpdateReady) View.VISIBLE else View.GONE)
        WidgetTab.PAGES.forEachIndexed { i, name -> v.setOnClickPendingIntent(id(context, TAB_IDS[i]), broadcast(context, 1 + i, ACTION_TAB, "tab" to name)) }
        v.setOnClickPendingIntent(R.id.t_upd, activity(context, 6, InstallUpdateActivity::class.java))
        v.setOnClickPendingIntent(R.id.t_settings, activity(context, 8, SettingsActivity::class.java))
        val models = CellModels.of(context, snap)
        fun btn(icon: Int, id: String, iconOnly: Boolean = false): WidgetArt.Btn { val m = models.getValue(id); return WidgetArt.Btn(icon, m.label, m.tone, m.enabled, iconOnly) }
        // ---- Build ----
        val needsSetup = !hasTermuxPermission(context)
        val robotTarget: Class<*> = when {
            snap.link == Link.MISSING -> com.aiwa.app.brain.InstallHelpActivity::class.java
            needsSetup -> com.aiwa.app.brain.SetupActivity::class.java
            status?.claudeLogin == "needed" -> com.aiwa.app.settings.ClaudeLoginActivity::class.java
            else -> AgentToggleActivity::class.java
        }
        val hasSession = snap.sessionId != null || status?.lastSession != null
        val roomOpen = snap.chamberMode != "closed" || status?.chamber?.active == true
        val firstRow = buildList {
            // the room in progress, at the left of the Super agent: only while there is one (its touch zone is gone otherwise, the rest keeps its shares)
            if (roomOpen) add(Cell(WidgetArt.Btn(R.drawable.fw_i_room, "Chambre en cours", "violet", true, true), 1f, activity(context, 15, com.aiwa.app.chamber.ChamberActivity::class.java), zone = 0))
            add(Cell(btn(R.drawable.fw_i_robot, "agent"), 3f, activity(context, 10, robotTarget), zone = 1))
            add(Cell(btn(R.drawable.fw_i_claude, "claude", iconOnly = true), 1f, activity(context, 11, OpenClaudeActivity::class.java), zone = 2))
        }
        val agentPage = listOf(
            firstRow,
            listOf(
                Cell(btn(R.drawable.fw_i_ear, "listen", iconOnly = true), 1f, activity(context, 12, EarToggleActivity::class.java)),
                Cell(btn(R.drawable.fw_i_plus, "plus", iconOnly = true), 1f, activity(context, 13, AddActivity::class.java)),
                Cell(btn(R.drawable.fw_i_scenario, "scenario", iconOnly = true), 1f, activity(context, 30, ScenariosActivity::class.java)),
                Cell(btn(R.drawable.fw_i_cast, "cast", iconOnly = true), 1f, activity(context, 31, CastActivity::class.java)),
                Cell(btn(R.drawable.fw_i_question, "question", iconOnly = true), 1f, activity(context, 7, AskActivity::class.java)),
            ),
        )
        // ---- Files ----
        val kinds = listOf("docs" to R.drawable.fw_i_docs, "image" to R.drawable.fw_i_image, "video" to R.drawable.fw_i_media, "app" to R.drawable.fw_i_app, "page" to R.drawable.fw_i_page)
        val kindCells = kinds.mapIndexed { i, (kind, icon) ->
            Cell(btn(icon, kind, iconOnly = true), 1f, activity(context, 20 + i, Intent(context, FilesActivity::class.java).putExtra(FilesActivity.EXTRA_KIND, kind)))
        }
        val scopeRepo = FilesScope.repo(context, status?.repo)
        val files = listOf(
            listOf(
                Cell(btn(R.drawable.fw_i_files, "scope"), 6f, activity(context, 19, RepoPickerActivity::class.java)),
                Cell(btn(R.drawable.fw_i_link, "repoview", iconOnly = true), 1f, scopeRepo?.let { activity(context, 17, Intent(Intent.ACTION_VIEW, android.net.Uri.parse("https://github.com/$it"))) }),
                Cell(btn(R.drawable.fw_i_swap, "reposession", iconOnly = true), 1f, scopeRepo?.let { activity(context, 18, Intent(context, RepoSessionActivity::class.java).putExtra(RepoSessionActivity.EXTRA_REPO, it)) }),
            ),
            kindCells,
        )
        // ---- Voir ----
        fun voir(code: Int, mode: String) = activity(context, code, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))
        val voirPage = listOf(
            listOf(
                Cell(btn(R.drawable.fw_i_wallet, "wallet"), 1f, activity(context, 44, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "wallet"))),
                Cell(btn(R.drawable.fw_i_pin, "nearby"), 1f, voir(40, "proche")),
            ),
            listOf(
                Cell(btn(R.drawable.fw_i_link, "link", iconOnly = true), 1f, voir(41, "lien")),
                Cell(btn(R.drawable.fw_i_qr, "qr", iconOnly = true), 1f, voir(42, "qr")),
                Cell(btn(R.drawable.fw_i_star, "favorites", iconOnly = true), 1f, voir(43, "favoris")),
            ),
        )
        val pages = listOf(agentPage, files, voirPage)
        // ---- the pictures and the touch zones ----
        val (pw, ph) = sizePx(context)
        pages.forEachIndexed { p, rows ->
            v.setImageViewBitmap(IMG[p], WidgetArt.full(context, pw, ph, alert, WidgetBackground.res(context), tabs, p + 1, rows.map { row -> row.map { it.btn to it.weight } }))
            rows.forEachIndexed { r, row ->
                row.forEachIndexed { c, cell -> id(context, "z_${LETTER[p]}_${r}_${cell.zone ?: c}").let { zid -> v.setViewVisibility(zid, View.VISIBLE); cell.click?.let { v.setOnClickPendingIntent(zid, it) } } }
            }
        }
        if (!roomOpen) v.setViewVisibility(id(context, "z_a_0_0"), View.GONE)
        val page = WidgetTab.PAGES.indexOf(tab).coerceAtLeast(0)
        v.setDisplayedChild(R.id.fw_img_flip, page)
        v.setDisplayedChild(R.id.fw_zone_flip, page)
        return v
    }

    /** The size, in pixels, of the pictures: the size of the widget (from its options) and never so many pixels that three of them exceed what a RemoteViews may carry (a fraction of the screen's memory). */
    private fun sizePx(context: Context): Pair<Int, Int> {
        val dm = context.resources.displayMetrics
        val d = dm.density
        var w = 330f
        var h = 80f
        try {
            val id = ids(context).firstOrNull()
            if (id != null) {
                val o = AppWidgetManager.getInstance(context).getAppWidgetOptions(id)
                val minW = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0)
                val maxH = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0)
                if (minW > 0) w = minW.toFloat()
                if (maxH > 0) h = maxH.toFloat()
            }
        } catch (err: Exception) { /* the default size */ }
        val budget = dm.widthPixels.toFloat() * dm.heightPixels * 4f * 1.5f * 0.7f / (3f * 4f)   // pixels per picture
        val k = minOf(1f, 900f / (w * d), Math.sqrt((budget / (w * d * h * d)).toDouble()).toFloat())
        return maxOf(150, (w * d * k).toInt()) to maxOf(60, (h * d * k).toInt())
    }
}

class AiwaWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        wakeAiwa(context)
        AiwaWidget.render(context, force = true)
    }

    override fun onAppWidgetOptionsChanged(context: Context, manager: AppWidgetManager, id: Int, options: android.os.Bundle) = AiwaWidget.render(context, force = true)

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            AiwaWidget.ACTION_TAB -> AiwaWidget.switchTab(context, intent.getStringExtra("tab") ?: return)
            AiwaWidget.ACTION_BUSY -> toastOnMain(context, "Un message est en route : attends qu'il soit parti.")
            else -> super.onReceive(context, intent)
        }
    }
}
