package com.aiwa.app.home

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import com.aiwa.app.common.dp

/**
 * The bar at the bottom of a profile page (hers or another's): keys of glass, each with its colour, an icon and a word. It is the application's, drawn outside the page: the page, whoever designed it
 * and however it did, can neither change, hide nor cover it.
 */
object ProfileBar {
    class Spec(val icon: String, val label: String, val tone: Int, val onClick: () -> Unit)

    /** One key of the bar: its word and its state can change (the score on Match, a key that is not available yet). */
    class Key(val view: LinearLayout, private val labelView: TextView) {
        fun label(text: String) { labelView.text = text }
        fun available(on: Boolean) { view.alpha = if (on) 1f else .4f }
    }

    class Bar(val view: LinearLayout, val keys: List<Key>, val named: Map<String, Key> = emptyMap())

    val VIOLET = Color.parseColor("#A77BD6")
    val BLUE = Color.parseColor("#6B9BF5")
    val GOLD = Color.parseColor("#E8C14A")
    val GREEN = Color.parseColor("#52D6A0")
    val WHITE = Color.parseColor("#DCE4FF")

    fun height(activity: Activity) = activity.dp(78)

    /** `ids`: the name of each key (parallel to `specs`, "" for one that has none), so that the activity finds its keys by name whatever the order is. */
    fun build(activity: Activity, specs: List<Spec>, ids: List<String> = emptyList()): Bar {
        val bar = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL; setPadding(activity.dp(10), activity.dp(8), activity.dp(10), activity.dp(10))
            background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, intArrayOf(0x0010132E, 0xE610132E.toInt()))
        }
        val keys = specs.map { spec ->
            val cell = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(0, activity.dp(8), 0, activity.dp(8))
                background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, intArrayOf((spec.tone and 0x00FFFFFF) or 0x66000000, (spec.tone and 0x00FFFFFF) or 0x14000000)).apply {
                    cornerRadius = activity.dp(18).toFloat(); setStroke(activity.dp(1), (spec.tone and 0x00FFFFFF) or 0xAA000000.toInt())
                }
                elevation = activity.dp(4).toFloat()
                setOnClickListener { spec.onClick() }
            }
            cell.addView(TextView(activity).apply { text = spec.icon; textSize = 21f; gravity = Gravity.CENTER })
            val label = TextView(activity).apply { text = spec.label; setTextColor(Color.WHITE); textSize = 12f; setTypeface(null, Typeface.BOLD); gravity = Gravity.CENTER; maxLines = 1 }
            cell.addView(label)
            bar.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(activity.dp(3), 0, activity.dp(3), 0) })
            Key(cell, label)
        }
        return Bar(bar, keys, ids.zip(keys).filter { it.first.isNotEmpty() }.toMap())
    }
}
