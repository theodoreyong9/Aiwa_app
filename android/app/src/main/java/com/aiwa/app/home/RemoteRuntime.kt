package com.aiwa.app.home

import android.content.Context
import com.aiwa.app.common.Prefs
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The runtime of the widget of the application (aiwa-home.js) follows the web, without a new APK: about every twelve seconds while a page is on the screen, a request that carries the ETag of the last file and so only
 * brings the file when it changed; the page on the screen starts again with it. The address is FIXED (the product's own repository, its main branch, over https): the runtime is the product's code, never a file of a profile.
 * The default home page (default.html, what a person sees before she has a page of her own, and again when she asks Aiwa to start over) follows the web the same way.
 * Nothing else is checked: the safety net of the whole application is the widgets of the desktop, which are in the application and cannot be changed from here. The runtime inside the application is only what a
 * page uses until the first file of the web has come.
 */
object RemoteRuntime {
    private const val URL_RAW = "https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/web/home/aiwa-home.js"
    private const val URL_DEFAULT = "https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/web/home/default.html"
    private const val EVERY_MS = 12_000L
    private val lock = Any()
    @Volatile private var fetching = false
    @Volatile private var lastAt = 0L

    private fun file(context: Context) = File(context.filesDir, "aiwa-home-remote.js")
    private fun pageFile(context: Context) = File(context.filesDir, "aiwa-home-default.html")
    private fun prefs(context: Context) = Prefs(context, "aiwa_home_remote")

    /** The runtime of the application (the assets). */
    fun bundled(context: Context): String = try { context.assets.open("web/home/aiwa-home.js").use { String(it.readBytes(), Charsets.UTF_8) } } catch (err: Exception) { "" }

    /** What is put in a page: the last file of the web, else the one of the application. `stamp` tells which (the time of the file, 0 for the application's), so that a page knows when a newer one has come. */
    class Choice(val text: String, val stamp: Long)

    fun choose(context: Context): Choice {
        synchronized(lock) {
            val f = file(context)
            if (f.isFile && f.length() > 0) {
                val text = try { f.readText(Charsets.UTF_8) } catch (err: Exception) { "" }
                if (text.isNotEmpty()) return Choice(text, f.lastModified())
            }
        }
        return Choice(bundled(context), 0L)
    }

    /** The default home page: the last one of the web, else the one of the application. */
    fun defaultPage(context: Context): String {
        synchronized(lock) {
            val f = pageFile(context)
            if (f.isFile && f.length() > 0) { val text = try { f.readText(Charsets.UTF_8) } catch (err: Exception) { "" }; if (text.isNotEmpty()) return text }
        }
        return try { context.assets.open("web/home/default.html").use { String(it.readBytes(), Charsets.UTF_8) } } catch (err: Exception) { "" }
    }

    private fun fetch(app: Context, address: String, etagKey: String, target: File): Boolean {
        val c = URL("$address?r=${System.currentTimeMillis() / 1000}").openConnection() as HttpURLConnection      // the query only goes round the cache of the web
        c.connectTimeout = 8_000; c.readTimeout = 12_000; c.instanceFollowRedirects = false
        prefs(app).string(etagKey)?.let { c.setRequestProperty("If-None-Match", it) }
        if (c.responseCode != 200) return false       // 304: nothing new
        val etag = c.getHeaderField("ETag")
        val text = String(c.inputStream.use { it.readBytes() }, Charsets.UTF_8)
        if (text.isEmpty()) return false
        synchronized(lock) {
            val tmp = File(app.filesDir, target.name + ".tmp")
            tmp.writeText(text, Charsets.UTF_8)
            if (!tmp.renameTo(target)) { target.delete(); tmp.renameTo(target) }
        }
        if (etag != null) prefs(app).put(etagKey, etag)
        return true
    }

    fun refresh(context: Context) {
        val app = context.applicationContext
        val now = System.currentTimeMillis()
        if (fetching || now - lastAt < EVERY_MS) return
        fetching = true
        lastAt = now
        Thread {
            try {
                if (fetch(app, URL_RAW, "etag", file(app))) HomeRuntime.forget()
                fetch(app, URL_DEFAULT, "etag_default", pageFile(app))
            } catch (err: Exception) {
                /* no network, or the file is not there: the runtime in use stays */
            } finally { fetching = false }
        }.start()
    }
}
