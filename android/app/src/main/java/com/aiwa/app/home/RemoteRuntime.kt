package com.aiwa.app.home

import android.content.Context
import com.aiwa.app.common.Prefs
import com.aiwa.client.RuntimeFile
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The runtime of the widget of the application (aiwa-home.js) refreshed from the web, without a new APK. The address is FIXED: the product's own repository, its main branch, over https; nothing from a profile
 * of anyone is ever taken. A file is used only when it is made for this application (same `api`), newer than the one inside it (`rev`), a script of the right size (see RuntimeFile). The one inside the application
 * stays the fallback: if the file of the web fails to start, it is thrown away, its `rev` is remembered as refused, and the runtime of the application is put in the page instead.
 * The desktop widgets of Android have nothing to do with this: they are in the application and change with it.
 */
object RemoteRuntime {
    const val API = 1
    private const val URL_RAW = "https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/web/home/aiwa-home.js"
    private const val EVERY_MS = 60 * 60 * 1000L
    private val lock = Any()
    @Volatile private var fetching = false

    private fun file(context: Context) = File(context.filesDir, "aiwa-home-remote.js")
    private fun prefs(context: Context) = Prefs(context, "aiwa_home_remote")

    /** The runtime of the application (the assets). */
    fun bundled(context: Context): String = try { context.assets.open("web/home/aiwa-home.js").use { String(it.readBytes(), Charsets.UTF_8) } } catch (err: Exception) { "" }

    private fun rejected(context: Context): Set<Long> = (prefs(context).string("rejected") ?: "").split(',').mapNotNull { it.toLongOrNull() }.toSet()

    /** What is put in a page: the file of the web when there is a good one, else the one of the application. `remote` says which (so that a failure can be recovered from). */
    class Choice(val text: String, val remote: Boolean, val rev: Long)

    fun choose(context: Context): Choice {
        val inside = bundled(context)
        val insideRev = RuntimeFile.header(inside)?.rev ?: 0L
        synchronized(lock) {
            val f = file(context)
            if (f.isFile && f.length() in 1..RuntimeFile.MAX_BYTES) {
                val text = try { f.readText(Charsets.UTF_8) } catch (err: Exception) { null }
                if (RuntimeFile.refusal(text, API, insideRev, rejected(context)) == null) return Choice(text!!, true, RuntimeFile.header(text)!!.rev)
                f.delete()      // an older or refused file is of no use any more (a new application brings a newer one)
            }
        }
        return Choice(inside, false, insideRev)
    }

    /** The file of the web did not start in a page: it is thrown away and its revision never tried again. */
    fun reject(context: Context, rev: Long) {
        synchronized(lock) {
            file(context).delete()
            prefs(context).put("rejected", (rejected(context) + rev).toList().takeLast(20).joinToString(","))
        }
        HomeRuntime.forget()
    }

    /** Looks for a newer runtime in the background, at most once an hour; it serves from the next page that opens. */
    fun refresh(context: Context) {
        val app = context.applicationContext
        val now = System.currentTimeMillis()
        if (fetching || now - (prefs(app).string("at")?.toLongOrNull() ?: 0L) < EVERY_MS) return
        fetching = true
        prefs(app).put("at", now.toString())
        Thread {
            try {
                val insideRev = RuntimeFile.header(bundled(app))?.rev ?: 0L
                val c = URL(URL_RAW).openConnection() as HttpURLConnection
                c.connectTimeout = 10_000; c.readTimeout = 15_000; c.instanceFollowRedirects = false
                if (c.responseCode != 200 || c.contentLength > RuntimeFile.MAX_BYTES) return@Thread
                val text = String(c.inputStream.use { it.readBytes() }, Charsets.UTF_8)
                if (RuntimeFile.refusal(text, API, insideRev, rejected(app)) != null) return@Thread
                synchronized(lock) {
                    val tmp = File(app.filesDir, "aiwa-home-remote.js.tmp")
                    tmp.writeText(text, Charsets.UTF_8)
                    if (!tmp.renameTo(file(app))) { file(app).delete(); tmp.renameTo(file(app)) }
                }
                HomeRuntime.forget()
            } catch (err: Exception) {
                /* no network, or the file is not there: the runtime in use stays */
            } finally { fetching = false }
        }.start()
    }
}
