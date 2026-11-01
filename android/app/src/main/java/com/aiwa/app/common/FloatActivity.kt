package com.aiwa.app.common

import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity

/**
 * The small windows the widget opens (a list, a choice, a form): a card in the middle of a dimmed screen. A tap outside closes it. The theme is translucent and has no transition, so that a tap on
 * the widget shows the window at once. The card is built by `fill`, called once the window exists; `reload` empties it and calls `fill` again (the list of a window that changed).
 */
abstract class FloatActivity : ComponentActivity() {
    protected abstract val title: String
    protected abstract fun fill()

    private lateinit var card: LinearLayout

    /** True for a window whose lines are an icon and a name only (the settings): the explanations of `entryIcon` are not shown. */
    protected open val compactRows: Boolean = false

    /** More than one: the lines of `entryIcon` become tiles (an icon over a name), this many on a row, and the section titles are not drawn (the tiles flow on). */
    protected open val gridColumns: Int = 1
    private val TILE_HEIGHT = 128
    private var gridRow: LinearLayout? = null
    private var gridCount = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setBackgroundDrawable(ColorDrawable(Color.parseColor("#AA000000")))
        val root = FrameLayout(this)
        root.setOnClickListener { finish() }
        card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply { setColor(Palette.BACK); cornerRadius = dp(22).toFloat(); setStroke(dp(1), Color.parseColor("#47FFFFFF")) }
            setPadding(dp(16), dp(14), dp(16), dp(14))
            isClickable = true
        }
        val scroll = ScrollView(this).apply { addView(card) }
        root.addView(scroll, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER).apply { setMargins(dp(18), dp(40), dp(18), dp(40)) })
        setContentView(root)
        reload()
    }

    protected fun reload() {
        card.removeAllViews()
        gridRow = null; gridCount = 0
        card.addView(TextView(this).apply { text = title; setTextColor(Palette.TEXT); textSize = 20f; setTypeface(null, Typeface.BOLD); setPadding(0, 0, 0, dp(8)) })
        fill()
        closeGridRow()
    }

    /** The last row of tiles is completed with empty places, so that the tiles keep the same width. */
    private fun closeGridRow() {
        val row = gridRow ?: return
        while (gridCount < gridColumns) { row.addView(View(this), LinearLayout.LayoutParams(0, dp(TILE_HEIGHT), 1f).apply { setMargins(dp(4), 0, dp(4), 0) }); gridCount++      // MATCH_PARENT like the tiles: a fixed height here made the whole row collapse }
        gridRow = null; gridCount = 0
    }

    /** A tile: a round badge with the icon in the colour of the tile, the name under it, and the state (if there is one) in small letters. */
    private fun tile(icon: Int, label: String, accent: Int, state: String?, stateColor: Int, onClick: () -> Unit) {
        if (gridRow == null || gridCount >= gridColumns) {
            closeGridRow()
            gridRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            card.addView(gridRow, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) })
            gridCount = 0
        }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            background = GradientDrawable().apply { setColor(Palette.CARD); cornerRadius = dp(16).toFloat(); setStroke(dp(1), Color.parseColor("#22FFFFFF")) }
            setPadding(dp(6), dp(12), dp(6), dp(10))
            setOnClickListener { onClick() }
        }
        val badge = FrameLayout(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(46, Color.red(accent), Color.green(accent), Color.blue(accent))); setStroke(dp(1), Color.argb(90, Color.red(accent), Color.green(accent), Color.blue(accent))) }
        }
        badge.addView(android.widget.ImageView(this).apply { setImageResource(icon); setColorFilter(accent) }, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER))
        box.addView(badge, LinearLayout.LayoutParams(dp(46), dp(46)))
        box.addView(TextView(this).apply { text = label; setTextColor(Palette.TEXT); textSize = 12.5f; gravity = Gravity.CENTER; maxLines = 2; setPadding(0, dp(7), 0, 0) },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        if (state != null) box.addView(TextView(this).apply { text = state; setTextColor(stateColor); textSize = 11f; setTypeface(null, Typeface.BOLD); gravity = Gravity.CENTER; maxLines = 1; setPadding(0, dp(3), 0, 0) },
            LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        gridRow!!.addView(box, LinearLayout.LayoutParams(0, dp(TILE_HEIGHT), 1f).apply { setMargins(dp(4), 0, dp(4), 0) })      // a fixed height, the same for the tiles and the empty places: no row can collapse
        gridCount++
    }

    /** A line of explanation. */
    protected fun note(text: String, color: Int = Palette.DIM): TextView = TextView(this).apply {
        this.text = text; setTextColor(color); textSize = 14f; setPadding(0, dp(4), 0, dp(4)); setLineSpacing(3f, 1f)
        card.addView(this)
    }

    /** A line to touch: a title, and under it what it does. */
    protected fun entry(label: String, detail: String? = null, tone: Int = Palette.CARD, onClick: () -> Unit): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = GradientDrawable().apply { setColor(tone); cornerRadius = dp(14).toFloat() }
            setPadding(dp(14), dp(11), dp(14), dp(11))
            setOnClickListener { onClick() }
        }
        row.addView(TextView(this).apply { text = label; setTextColor(Palette.TEXT); textSize = 16f })
        if (detail != null) row.addView(TextView(this).apply { text = detail; setTextColor(Palette.DIM); textSize = 13f })
        card.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) })
        return row
    }

    /** A section title: small, spaced, with a thin line after it. */
    protected fun section(text: String) {
        if (gridColumns > 1) return
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        row.addView(TextView(this).apply { this.text = text.uppercase(); setTextColor(Palette.GOLD); textSize = 12f; letterSpacing = 0.12f; setTypeface(null, Typeface.BOLD) })
        row.addView(View(this).apply { setBackgroundColor(Color.parseColor("#33FFFFFF")) }, LinearLayout.LayoutParams(0, dp(1), 1f).apply { leftMargin = dp(10) })
        card.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(18) })
    }

    /** A styled line: a round badge with the icon in the colour of the row, the title and what it does, and at the right either what state it is in (a pill) or an arrow. */
    protected fun entryIcon(icon: Int, label: String, detail: String? = null, accent: Int = Palette.DIM, state: String? = null, stateColor: Int = Palette.DIM, onClick: () -> Unit): View {
        if (gridColumns > 1) { tile(icon, label, accent, state, stateColor, onClick); return card }
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = GradientDrawable().apply { setColor(Palette.CARD); cornerRadius = dp(16).toFloat(); setStroke(dp(1), Color.parseColor("#22FFFFFF")) }
            setPadding(dp(12), dp(10), dp(12), dp(10))
            setOnClickListener { onClick() }
        }
        val badge = FrameLayout(this).apply {
            background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.argb(46, Color.red(accent), Color.green(accent), Color.blue(accent))); setStroke(dp(1), Color.argb(90, Color.red(accent), Color.green(accent), Color.blue(accent))) }
        }
        badge.addView(android.widget.ImageView(this).apply { setImageResource(icon); setColorFilter(accent) }, FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        row.addView(badge, LinearLayout.LayoutParams(dp(42), dp(42)))
        val texts = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        texts.addView(TextView(this).apply { text = label; setTextColor(Palette.TEXT); textSize = 16f; setTypeface(null, Typeface.BOLD) })
        if (detail != null && !compactRows) texts.addView(TextView(this).apply { text = detail; setTextColor(Palette.DIM); textSize = 12.5f; setLineSpacing(2f, 1f) })
        row.addView(texts, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { leftMargin = dp(12); rightMargin = dp(8) })
        if (state != null) row.addView(TextView(this).apply {
            text = state; setTextColor(stateColor); textSize = 12f; setTypeface(null, Typeface.BOLD); setPadding(dp(10), dp(4), dp(10), dp(4))
            background = GradientDrawable().apply { cornerRadius = dp(12).toFloat(); setColor(Color.argb(40, Color.red(stateColor), Color.green(stateColor), Color.blue(stateColor))) }
        })
        else row.addView(TextView(this).apply { text = "›"; setTextColor(Palette.DIM); textSize = 22f })
        card.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) })
        return row
    }

    /** Anything else to put in the card (a field, a row of buttons). */
    protected fun add(view: View, topMargin: Int = 8) { card.addView(view, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { this.topMargin = dp(topMargin) }) }
}
