package com.aiwa.app.home

import android.annotation.SuppressLint
import android.content.Context
import android.content.MutableContextWrapper
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.webkit.WebView

/**
 * One page engine kept ready: creating the first WebView of a process starts the whole browser engine, which is what makes a profile (or the Swipe) open with a jerk. A spare is made a moment after the
 * application starts (and again after each use), so the window takes it instead of building one; it is dropped when the system asks for memory. Main thread only.
 */
object WebWarm {
    private var spare: WebView? = null
    private val main = Handler(Looper.getMainLooper())

    @SuppressLint("SetJavaScriptEnabled")
    fun configure(web: WebView) {
        web.setBackgroundColor(Color.parseColor("#10132E"))
        web.settings.javaScriptEnabled = true       // only for the runtime of the application (evaluateJavascript): the page's own scripts are held by a policy put first in it
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.settings.mediaPlaybackRequiresUserGesture = false      // the video behind a profile starts by itself (muted)
    }

    /** Makes the spare, a little later (never while something else is being drawn). */
    fun prepare(context: Context, delayMs: Long = 2500) {
        val app = context.applicationContext
        main.postDelayed({
            if (spare == null) {
                try { spare = WebView(MutableContextWrapper(app)).also { configure(it) } } catch (err: Exception) { /* no engine now: a window builds its own */ }
            }
        }, delayMs)
    }

    /** The spare, tied to the window that takes it (a new spare is made right after); null when there is none. */
    fun take(context: Context): WebView? {
        val web = spare ?: return null
        spare = null
        (web.context as? MutableContextWrapper)?.setBaseContext(context)
        prepare(context, 800)
        return web
    }

    fun drop() {
        spare?.let { try { it.destroy() } catch (err: Exception) { } }
        spare = null
    }
}
