package com.aiwa.app.home

import android.graphics.Color
import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.widget.CellModels

/**
 * The buttons of Aiwa shown by the application itself, for a visited profile in the closed zone (its page has no runtime, so no button of its own): the same ones as the widget, by group, the same actions.
 * Réglages is the twelve tiles of the settings, whose switches flip on the spot.
 */
class WidgetPanelActivity : FloatActivity() {
    override val title = "Widget"
    override val compactRows = true
    override val gridColumns = 3

    private class Tile(val id: String, val icon: Int)

    private val groups = listOf(
        "Agent" to listOf(Tile("agent", R.drawable.fw_i_robot), Tile("plus", R.drawable.fw_i_plus), Tile("claude", R.drawable.fw_i_claude), Tile("scenario", R.drawable.fw_i_scenario), Tile("cast", R.drawable.fw_i_cast), Tile("question", R.drawable.fw_i_question)),
        "Files" to listOf(Tile("docs", R.drawable.fw_i_docs), Tile("image", R.drawable.fw_i_image), Tile("video", R.drawable.fw_i_media), Tile("app", R.drawable.fw_i_app), Tile("page", R.drawable.fw_i_page)),
        "Game" to listOf(Tile("wallet", R.drawable.fw_i_wallet), Tile("nearby", R.drawable.fw_i_pin), Tile("room", R.drawable.fw_i_room), Tile("link", R.drawable.fw_i_link), Tile("qr", R.drawable.fw_i_qr), Tile("favorites", R.drawable.fw_i_star)),
        "Réglages" to listOf(
            Tile("set_accounts", R.drawable.fw_i_key), Tile("set_words", R.drawable.fw_i_talk), Tile("set_persona", R.drawable.fw_i_trophy), Tile("set_me", R.drawable.fw_i_aiwa), Tile("set_voice", R.drawable.fw_i_volume), Tile("set_ear", R.drawable.fw_i_ear),
            Tile("set_papers", R.drawable.fw_i_papers), Tile("set_model", R.drawable.fw_i_tools), Tile("set_ready", R.drawable.fw_i_report), Tile("set_push", R.drawable.fw_i_swap), Tile("set_bg", R.drawable.fw_i_image), Tile("set_health", R.drawable.fw_i_report),
        ),
    )

    override fun fill() {
        val models = CellModels.of(this, Aiwa.state.value)
        for ((name, tiles) in groups) {
            section(name)
            for (t in tiles) {
                val m = models[t.id]
                entryIcon(t.icon, m?.label ?: t.id, null, Color.parseColor("#B79CFF")) {
                    HomeActions.press(this, t.id, ScreenNow.repo, false)
                    if (!t.id.startsWith("set_ear") && !t.id.startsWith("set_ready") && !t.id.startsWith("set_push") && !t.id.startsWith("set_bg")) finish() else reload()
                }
            }
        }
    }
}
