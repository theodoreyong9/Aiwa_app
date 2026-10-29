package com.aiwa.app.home

import android.app.Activity
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import com.aiwa.app.common.dp

/** The bar at the bottom of a profile page (hers or another's): keys of glass, equal in width. It is the application's, never the page's. */
object ProfileBar {
    fun build(activity: Activity, keys: List<Pair<String, () -> Unit>>): LinearLayout {
        val bar = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL; setPadding(activity.dp(10), activity.dp(8), activity.dp(10), activity.dp(10)) }
        for ((label, onClick) in keys) {
            val cell = TextView(activity).apply {
                text = label; setTextColor(Color.WHITE); textSize = 15f; gravity = Gravity.CENTER; setPadding(0, activity.dp(12), 0, activity.dp(12))
                background = GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, intArrayOf(0x66FFFFFF, 0x1AFFFFFF)).apply { cornerRadius = activity.dp(10).toFloat(); setStroke(activity.dp(1), 0x66FFFFFF) }
                setOnClickListener { onClick() }
            }
            bar.addView(cell, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(activity.dp(3), 0, activity.dp(3), 0) })
        }
        return bar
    }
}
