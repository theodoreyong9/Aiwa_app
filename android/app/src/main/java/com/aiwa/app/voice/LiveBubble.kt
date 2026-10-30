package com.aiwa.app.voice

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.TextView
import com.aiwa.app.common.toastOnMain

/**
 * A bubble over the other applications while the super agent listens: what the person says as it is being written (the recognizer's partial results), then what the agent answers, for a few seconds.
 * It needs the permission « afficher par-dessus les autres applis » (asked once, when the agent is opened); without it nothing is drawn and the notification (visible on the lock screen) carries the same
 * conversation. It never takes a touch: it is only a view. Everything is drawn on the main thread, whoever calls.
 */
object LiveBubble {
    private var view: TextView? = null
    private var user = ""
    private var agent = ""
    private val main = Handler(Looper.getMainLooper())
    private val hideLater = Runnable { hide() }

    fun can(context: Context): Boolean = Settings.canDrawOverlays(context)

    /** The first time the agent is opened: explains and opens the setting where the person allows the bubble (once; she may refuse, the notification stays). */
    fun askOnce(context: Context) {
        if (can(context)) return
        val prefs = context.getSharedPreferences("aiwa_overlay", Context.MODE_PRIVATE)
        if (prefs.getBoolean("asked", false)) return
        prefs.edit().putBoolean("asked", true).apply()
        toastOnMain(context, "Autorise « Afficher par-dessus les autres applis » pour voir ce que tu dis, en direct, pendant que tu parles à l'agent.")
        try { context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + context.packageName)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (err: Exception) { }
    }

    /** What the person says right now, as the recognizer understands it so far. */
    fun partial(context: Context, text: String) { val app = context.applicationContext; main.post { user = "Toi : $text …"; show(app) } }

    /** A sentence is done: the person's words as they were taken, or what the agent says. */
    fun said(context: Context, mine: Boolean, text: String) { val app = context.applicationContext; main.post { if (mine) user = "Toi : $text" else agent = text; show(app) } }

    private fun show(app: Context) {
        if (!can(app)) return
        val text = listOf(user, agent).filter { it.isNotBlank() }.joinToString("\n")
        if (text.isBlank()) return
        val density = app.resources.displayMetrics.density
        val v = view ?: TextView(app).apply {
            setTextColor(Color.WHITE); textSize = 17f
            val pad = (16 * density).toInt(); setPadding(pad, pad, pad, pad)
            background = GradientDrawable().apply { setColor(Color.argb(235, 16, 19, 46)); cornerRadius = 24 * density }
            try {
                val params = WindowManager.LayoutParams(
                    (app.resources.displayMetrics.widthPixels * 0.92).toInt(), WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN, PixelFormat.TRANSLUCENT,
                ).apply { gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL; y = (110 * density).toInt() }
                app.getSystemService(WindowManager::class.java).addView(this, params)
            } catch (err: Exception) { return }
            view = this
        }
        v.text = text
        main.removeCallbacks(hideLater)
        main.postDelayed(hideLater, 7_000)
    }

    fun hide() {
        main.post {
            main.removeCallbacks(hideLater)
            val v = view ?: return@post
            view = null; user = ""; agent = ""
            try { v.context.getSystemService(WindowManager::class.java).removeView(v) } catch (err: Exception) { }
        }
    }
}
