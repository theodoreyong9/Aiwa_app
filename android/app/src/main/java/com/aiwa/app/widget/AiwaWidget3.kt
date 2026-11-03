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
import com.aiwa.app.voice.EarToggleActivity

/**
 * The third widget: ONE row with no background, each button a name at the left and a big coloured icon at the right: Question (red when a question waits), Oreille (the same state and the same alerts as the Super agent button
 * of the first widget), Ajouter and Swipe. Native views (res/layout/widget3.xml), not resizable.
 */
object AiwaWidget3 {
    private val SLOTS = listOf("question", "ear", "add", "swipe")
    private val COLORS = mapOf("question" to "#F5C451", "ear" to "#5AC8FA", "add" to "#E09A7C", "swipe" to "#FB923C")

    fun ids(context: Context): IntArray = AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, AiwaWidget3Provider::class.java))

    private fun activity(context: Context, code: Int, intent: Intent): PendingIntent =
        PendingIntent.getActivity(context, 500 + code, intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    private fun activity(context: Context, code: Int, cls: Class<*>): PendingIntent = activity(context, code, Intent(context, cls))

    fun render(context: Context) {
        val ids = ids(context)
        if (ids.isEmpty()) return
        try { AppWidgetManager.getInstance(context).updateAppWidget(ids, views(context)) } catch (err: Exception) { /* the next change draws it again */ }
    }

    /** The widget as it is now (also what the picker is shown as its preview). */
    fun views(context: Context): RemoteViews {
        val snap = Aiwa.state.value
        val v = RemoteViews(context.packageName, R.layout.widget3)
        val alert = AiwaWidget.alertInfo(context, snap).alert      // the same alert, the same reasons and the same window as the first widget's Super agent button
        class Tile(val icon: Int, val label: String, val color: String, val click: PendingIntent, val state: Int = 0)
        val asked = snap.status?.ask != null      // a question of Claude waits for an answer: the key is red, like the one of the second widget
        val tiles = mapOf(
            "question" to Tile(R.drawable.fw_i_question, "Question", "question", activity(context, 1, com.aiwa.app.question.AskActivity::class.java), if (asked) 2 else 0),
            "ear" to Tile(R.drawable.fw_i_ear, AiwaWidget2.earLabel(context, snap, alert), "ear",
                activity(context, 2, if (alert) AiwaWidget.agentTarget(context, snap) else EarToggleActivity::class.java), if (alert) 2 else if (snap.listening) 1 else 0),
            "add" to Tile(R.drawable.fw_i_plus, "Ajouter", "add", activity(context, 3, AddActivity::class.java)),
            "swipe" to Tile(R.drawable.fw_i_pin, "Swipe", "swipe", activity(context, 4, com.aiwa.app.home.HomeActivity::class.java)),
        )
        SLOTS.forEach { id ->
            fun rid(prefix: String) = context.resources.getIdentifier("w3_${prefix}_$id", "id", context.packageName)
            val tile = tiles.getValue(id)
            v.setViewVisibility(rid("c"), View.VISIBLE)
            v.setOnClickPendingIntent(rid("c"), tile.click)
            v.setImageViewResource(rid("i"), tile.icon)
            // no background: the colour is in the icon (red when it calls for an answer, brighter when it is on) and in the name
            val iconColor = if (tile.state == 2) "#FF6B6B" else COLORS.getValue(tile.color)
            v.setInt(rid("i"), "setColorFilter", android.graphics.Color.parseColor(iconColor))
            v.setInt(rid("i"), "setImageAlpha", if (tile.state == 0) 235 else 255)
            v.setTextColor(rid("t"), android.graphics.Color.parseColor(if (tile.state == 2) "#FFB4B4" else if (tile.state == 1) "#B8FFE0" else "#FFFFFF"))
            v.setTextViewText(rid("t"), tile.label)
        }
        return v
    }
}

class AiwaWidget3Provider : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        wakeAiwa(context)
        AiwaWidget3.render(context)
    }
}
