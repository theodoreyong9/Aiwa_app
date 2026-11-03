package com.aiwa.app.home

import android.content.Context
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * The pictures of the profiles, kept on the phone: a picture seen once is shown at once the next time (the page is on the screen before its pictures are downloaded again). A picture of a precise version of
 * a page (an address with a commit) never changes; the others are served from the copy and renewed behind it once they are old. Only pictures and fonts, small ones: videos and everything else go the normal way.
 * Any failure gives null, and the WebView loads the address itself. Called from the WebView's own thread.
 */
object MediaCache {
    private val KINDS = mapOf("png" to "image/png", "jpg" to "image/jpeg", "jpeg" to "image/jpeg", "gif" to "image/gif", "webp" to "image/webp", "svg" to "image/svg+xml", "avif" to "image/avif", "ico" to "image/x-icon", "woff2" to "font/woff2", "woff" to "font/woff")
    private const val MAX_FILE = 6L * 1024 * 1024
    private const val MAX_TOTAL = 150L * 1024 * 1024
    private const val RENEW_MS = 6L * 60 * 60 * 1000
    private val PINNED = Regex("/[0-9a-f]{40}/")

    private fun dir(context: Context) = File(context.cacheDir, "media").apply { mkdirs() }
    private fun name(url: String) = MessageDigest.getInstance("SHA-1").digest(url.toByteArray()).joinToString("") { "%02x".format(it) }

    fun intercept(context: Context, request: WebResourceRequest): WebResourceResponse? {
        try {
            if (request.method != "GET") return null
            val uri = request.url
            if (uri.scheme != "https" || uri.host != "raw.githubusercontent.com") return null
            val mime = KINDS[uri.lastPathSegment?.substringAfterLast('.', "")?.lowercase().orEmpty()] ?: return null
            val url = uri.toString()
            val file = File(dir(context), name(url))
            val fresh = file.isFile && (PINNED.containsMatchIn(url) || System.currentTimeMillis() - file.lastModified() < RENEW_MS)
            if (file.isFile) {
                if (!fresh) Thread { fetch(url, file) }.start()      // renewed behind the copy, which is shown now
                return answer(mime, file)
            }
            return if (fetch(url, file)) answer(mime, file) else null
        } catch (err: Exception) { return null }
    }

    private fun answer(mime: String, file: File) = WebResourceResponse(mime, null, 200, "OK", mapOf("Access-Control-Allow-Origin" to "*", "Cache-Control" to "max-age=3600"), file.inputStream())

    private fun fetch(url: String, file: File): Boolean = try {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 8_000; c.readTimeout = 15_000
        if (c.responseCode != 200 || (c.contentLengthLong > MAX_FILE)) false
        else {
            val tmp = File(file.parentFile, file.name + ".part")
            var size = 0L
            c.inputStream.use { input -> tmp.outputStream().use { out -> val buf = ByteArray(16 * 1024); while (true) { val n = input.read(buf); if (n < 0) break; size += n; if (size > MAX_FILE) throw java.io.IOException("too big"); out.write(buf, 0, n) } } }
            tmp.renameTo(file).also { trim(file.parentFile!!) }
        }
    } catch (err: Exception) { false }

    /** The folder stays under its limit: the least recently written go first. */
    private fun trim(dir: File) {
        val files = dir.listFiles()?.filter { it.isFile && !it.name.endsWith(".part") } ?: return
        var total = files.sumOf { it.length() }
        for (f in files.sortedBy { it.lastModified() }) { if (total <= MAX_TOTAL) break; total -= f.length(); f.delete() }
    }
}
