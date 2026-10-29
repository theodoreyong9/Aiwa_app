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
        card.addView(TextView(this).apply { text = title; setTextColor(Palette.TEXT); textSize = 20f; setTypeface(null, Typeface.BOLD); setPadding(0, 0, 0, dp(8)) })
        fill()
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

    /** Anything else to put in the card (a field, a row of buttons). */
    protected fun add(view: View, topMargin: Int = 8) { card.addView(view, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { this.topMargin = dp(topMargin) }) }
}
