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

    private var animating = false

    /**
     * The change of page, feigned as a movement (a widget cannot be animated, but its buttons can be hidden and shown): the grid is four by three, so its anti-diagonals (the column plus the row) hold
     * 1, 2, 3, 3, 2 and 1 buttons. The buttons of the old page go diagonal after diagonal from the top left corner, then those of the new page come back in the same order, one frame about every 70 ms.
     */
    fun switchTo(context: Context, tab: String) {
        val app = context.applicationContext
        if (animating || tab == tab(app)) return
        animating = true
        val handler = android.os.Handler(android.os.Looper.getMainLooper())
        val before = tab(app)
        val step = 70L
        val last = 5                       // the diagonals are numbered 0 to 5
        for (k in 0..last) handler.postDelayed({ draw(app, before, hideDiagonal = { d -> d <= k }) }, k * step)
        handler.postDelayed({ com.aiwa.app.common.Prefs(app, "aiwa_widget2_tab").put("tab", tab) }, (last + 1) * step - 1)
        for (k in 0..last) handler.postDelayed({ draw(app, tab, hideDiagonal = { d -> d > k }) }, (last + 1 + k) * step)
        handler.postDelayed({ animating = false; render(app) }, (2 * last + 2) * step + 40)
    }

    private fun draw(context: Context, page: String, hideDiagonal: (Int) -> Boolean) {
        val ids = ids(context)
        if (ids.isEmpty()) return
        try { AppWidgetManager.getInstance(context).updateAppWidget(ids, views(context, page, hideDiagonal)) } catch (err: Exception) { /* the last frame draws it right */ }
    }

    private val COLORS = mapOf("question" to "#F5C451", "ear" to "#5AC8FA", "files" to "#34D399", "cast" to "#A78BFA", "scenario" to "#F472B6", "swipe" to "#FB923C", "room" to "#60A5FA",
        "fav" to "#FBBF24", "repo" to "#C4B5FD", "session" to "#F59E0B", "wallet" to "#2DD4BF", "search" to "#38BDF8")

    /** One of the twelve places of the grid: what it shows (icon, word, colour of its badge, state) and what a touch does. */
    private class Slot(val icon: Int, val label: String, val color: String, val click: PendingIntent, val state: Int = 0, val desc: String = "")    // state: 0 plain, 1 on, 2 calls for an answer

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
    fun views(context: Context, page: String = tab(context), hideDiagonal: (Int) -> Boolean = { false }): RemoteViews {
        val snap = Aiwa.state.value
        val status = snap.status
        val v = RemoteViews(context.packageName, R.layout.widget2)
        val onSettings = page == "settings"
        fun voir(code: Int, mode: String) = activity(context, code, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode))
        fun group(code: Int, id: String) = activity(context, code, Intent(context, SettingsActivity::class.java).putExtra(SettingsActivity.EXTRA_GROUP, id))
        val slots: List<Slot> = if (!onSettings) {
            val scopeRepo = FilesScope.repo(context, status?.repo) ?: status?.repo
            val roomOpen = com.aiwa.app.chamber.ChamberState.rooms.any { it.optJSONObject("partner") != null || it.optBoolean("knock") }
            // the ear carries the alerts of the first widget's Super agent button (what is missing, what the agent has to say): then it is red and opens the window that answers it
            val alert = AiwaWidget.alertInfo(context, snap).alert      // the same alert, the same reasons and the same window as the Super agent button of the first widget
            listOf(
                Slot(R.drawable.fw_i_question, "Question", COLORS.getValue("question"), activity(context, 1, com.aiwa.app.question.AskActivity::class.java), if (status?.ask != null) 1 else 0, if (status?.ask != null) "En attente" else "Dialogue"),
                Slot(R.drawable.fw_i_ear, if (alert) CellModels.of(context, snap).getValue("agent").label.take(14) else if (snap.listening) "Écoute" else "Oreille", COLORS.getValue("ear"),
                    activity(context, 2, if (alert) AiwaWidget.agentTarget(context, snap) else EarToggleActivity::class.java), if (alert) 2 else if (snap.listening) 1 else 0, if (alert) "À traiter" else "Alertes"),
                Slot(R.drawable.fw_i_files, "Fichiers", COLORS.getValue("files"), activity(context, 3, FilesHubActivity::class.java), 0, "Productions"),
                Slot(R.drawable.fw_i_cast, "Cast", COLORS.getValue("cast"), activity(context, 4, CastActivity::class.java), 0, "Vers la télé"),
                Slot(R.drawable.fw_i_scenario, "Scénarios", COLORS.getValue("scenario"), activity(context, 5, ScenariosActivity::class.java), 0, "Automatismes"),
                Slot(R.drawable.fw_i_pin, "Swipe", COLORS.getValue("swipe"), activity(context, 6, com.aiwa.app.home.HomeActivity::class.java), 0, "Autour"),
                Slot(R.drawable.fw_i_room, if (roomOpen) "En cours" else "Chambres", COLORS.getValue("room"), activity(context, 7, com.aiwa.app.chamber.ChambersActivity::class.java), if (roomOpen) 1 else 0, if (roomOpen) "Conversation" else "En direct"),
                Slot(R.drawable.fw_i_star, "Favoris", COLORS.getValue("fav"), voir(8, "favoris"), 0, "Tes préférés"),
                Slot(R.drawable.fw_i_github, FilesScope.label(context, status?.repo).take(10), COLORS.getValue("repo"), activity(context, 9, RepoPickerActivity::class.java), 0, "Dépôt"),
                Slot(R.drawable.fw_i_claude, (snap.sessionTitle ?: "Session").take(10), COLORS.getValue("session"),
                    if (scopeRepo != null) activity(context, 10, Intent(context, RepoSessionActivity::class.java).putExtra(RepoSessionActivity.EXTRA_REPO, scopeRepo)) else activity(context, 10, RepoPickerActivity::class.java), 0, "Session"),
                Slot(R.drawable.fw_i_wallet, "Wallet", COLORS.getValue("wallet"), activity(context, 11, Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "wallet")), 0, "Portefeuille"),
                Slot(R.drawable.fw_i_link, "Search", COLORS.getValue("search"), activity(context, 12, SearchHubActivity::class.java), 0, "Lien · QR"),
            )
        } else {
            // the twelve tiles of the settings window, here: the groups open their window, the switches flip on the spot
            val accountsOk = status?.claudeLogin == "ok" && status.githubToken
            val listen = com.aiwa.app.voice.ListenSettings.enabled(context)
            listOf(
                Slot(R.drawable.fw_i_key, "Connexions", COLORS.getValue("question"), group(30, "accounts"), if (accountsOk) 0 else 2, if (accountsOk) "Comptes" else "À relier"),
                Slot(R.drawable.fw_i_talk, "Les mots", COLORS.getValue("ear"), group(31, "words"), 0, "Tes mots"),
                Slot(R.drawable.fw_i_trophy, "Jeu", COLORS.getValue("fav"), activity(context, 32, com.aiwa.app.settings.PersonaActivity::class.java), 0, "Points"),
                Slot(R.drawable.fw_i_aiwa, "Moi", COLORS.getValue("files"), group(33, "me"), 0, "Profil"),
                Slot(R.drawable.fw_i_volume, "Voix", COLORS.getValue("search"), group(34, "voice"), 0, "Parole"),
                Slot(R.drawable.fw_i_ear, if (listen) "Écoute ✓" else "Écoute", COLORS.getValue("room"), toggle(context, 35, "ear"), if (listen) 1 else 0, if (listen) "Micro actif" else "Micro coupé"),
                Slot(R.drawable.fw_i_papers, "Papers", COLORS.getValue("session"), activity(context, 36, com.aiwa.app.settings.PapersActivity::class.java), 0, "Tes papers"),
                Slot(R.drawable.fw_i_tools, "Modèle", COLORS.getValue("swipe"), group(37, "model"), 0, "Choix"),
                Slot(R.drawable.fw_i_report, if (com.aiwa.app.voice.ReadySettings.enabled(context)) "Prêt ✓" else "Prêt", COLORS.getValue("wallet"), toggle(context, 38, "ready"), if (com.aiwa.app.voice.ReadySettings.enabled(context)) 1 else 0, "Annonce"),
                Slot(R.drawable.fw_i_swap, if (status?.pushMain ?: true) "Push ✓" else "Push", COLORS.getValue("scenario"), toggle(context, 39, "push"), if (status?.pushMain ?: true) 1 else 0, if (status?.pushMain ?: true) "Direct main" else "Sur branche"),
                Slot(R.drawable.fw_i_image, WidgetBackground.label(context).take(10), COLORS.getValue("cast"), toggle(context, 40, "bg"), 0, "Photo"),
                Slot(R.drawable.fw_i_report, "État", COLORS.getValue("repo"), activity(context, 41, com.aiwa.app.settings.HealthActivity::class.java), 0, "Santé"),
            )
        }
        CELLS.forEachIndexed { i, id ->
            val slot = slots[i]
            fun rid(prefix: String) = context.resources.getIdentifier("w2_${prefix}_$id", "id", context.packageName)
            // solid tiles of two shapes in a checkerboard (the big corners change diagonal), each in the colour of its function; lit: a white edge; calling for an answer: red
            val shape = if (((i / 4) + (i % 4)) % 2 == 0) "a" else "b"
            val name = if (slot.state == 2) "alert" else (COLORS.entries.firstOrNull { it.value == slot.color }?.key ?: "question")
            val drawable = context.resources.getIdentifier("w2_g_${name}_$shape" + (if (slot.state == 1) "_on" else ""), "drawable", context.packageName)
            v.setOnClickPendingIntent(rid("c"), slot.click)
            v.setInt(rid("c"), "setBackgroundResource", drawable)
            v.setImageViewResource(rid("i"), slot.icon)
            v.setInt(rid("i"), "setColorFilter", android.graphics.Color.WHITE)
            v.setInt(rid("i"), "setImageAlpha", if (slot.state == 0) 70 else 120)      // the big icon behind: a watermark, clearer when the tile is lit
            v.setTextViewText(rid("t"), slot.label)
            // the short word under the name is for the Réglages page only (the tiles of Aiwa are known by their icon and their name)
            val desc = if (onSettings) slot.desc else ""
            v.setTextViewText(rid("d"), desc)
            v.setViewVisibility(rid("d"), if (desc.isEmpty()) android.view.View.GONE else android.view.View.VISIBLE)
            val diagonal = (i / 4) + (i % 4)                        // the row plus the column: 0 to 5
            v.setViewVisibility(rid("c"), if (hideDiagonal(diagonal)) android.view.View.INVISIBLE else android.view.View.VISIBLE)
        }
        // the photo chosen in the settings (Fond du widget), the same as the first widget's; none: the deep card alone
        val photo = WidgetBackground.res(context)
        v.setViewVisibility(R.id.w2_photo, if (photo != 0) android.view.View.VISIBLE else android.view.View.GONE)
        v.setViewVisibility(R.id.w2_scrim, if (photo != 0) android.view.View.VISIBLE else android.view.View.GONE)
        if (photo != 0) v.setImageViewResource(R.id.w2_photo, photo)
        // ONE tab that switches: it shows the page it goes to (Réglages from the grid of Aiwa, Aiwa from the settings); Mise à jour is there only when there is an update
        v.setOnClickPendingIntent(R.id.w2_tab_settings, tabIntent(context, 1, if (onSettings) "aiwa" else "settings"))
        v.setImageViewResource(R.id.w2_tab_i, if (onSettings) R.drawable.fw_i_build else R.drawable.fw_i_settings)
        v.setTextViewText(R.id.w2_tab_t, if (onSettings) "Aiwa" else "Réglages")
        v.setOnClickPendingIntent(R.id.w2_tab_update, activity(context, 21, InstallUpdateActivity::class.java))
        v.setViewVisibility(R.id.w2_tab_update, if (snap.appUpdateReady) android.view.View.VISIBLE else android.view.View.GONE)      // like the first widget: the update tab is there only when there is an update
        v.setInt(R.id.w2_tab_update, "setBackgroundResource", if (snap.appUpdateReady) R.drawable.w2_tab_ready else R.drawable.w2_tab_off)
        return v
    }
}

class AiwaWidget2Provider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        wakeAiwa(context)
        AiwaWidget2.render(context)
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            AiwaWidget2.ACTION_TAB -> AiwaWidget2.switchTo(context, intent.getStringExtra("tab") ?: return)
            AiwaWidget2.ACTION_TOGGLE -> AiwaWidget2.flip(context, intent.getStringExtra("what") ?: return)
            else -> super.onReceive(context, intent)
        }
    }
}
