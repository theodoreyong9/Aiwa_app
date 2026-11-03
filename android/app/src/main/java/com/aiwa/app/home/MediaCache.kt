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
    private val VIDEOS = mapOf("mp4" to "video/mp4", "m4v" to "video/mp4", "webm" to "video/webm")
    /** The beginning of each video seen is kept (the first two megabytes, a few seconds of a muted background video): the next time it starts from the phone while the rest comes from the network. */
    private const val PREFIX = 2L * 1024 * 1024
    private const val VIDEO_RENEW_MS = 60L * 60 * 1000
    private val fetching = java.util.Collections.synchronizedSet(HashSet<String>())
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
            val ext = uri.lastPathSegment?.substringAfterLast('.', "")?.lowercase().orEmpty()
            val url = uri.toString()
            VIDEOS[ext]?.let { return video(context, request, url, it) }
            val mime = KINDS[ext] ?: return null
            val file = File(dir(context), name(url))
            val fresh = file.isFile && (PINNED.containsMatchIn(url) || System.currentTimeMillis() - file.lastModified() < RENEW_MS)
            if (file.isFile) {
                if (!fresh) Thread { fetch(url, file) }.start()      // renewed behind the copy, which is shown now
                return answer(mime, file)
            }
            return if (fetch(url, file)) answer(mime, file) else null
        } catch (err: Exception) { return null }
    }

    /**
     * A video asked by range from its start: when its beginning is kept, the answer is that beginning (a partial answer, which the player completes by asking for the rest); otherwise the normal way, and the
     * beginning is fetched behind it for the next time. Any doubt gives null (the WebView loads the address itself).
     */
    private fun video(context: Context, request: WebResourceRequest, url: String, mime: String): WebResourceResponse? {
        val range = request.requestHeaders.entries.firstOrNull { it.key.equals("Range", ignoreCase = true) }?.value ?: return null
        val m = Regex("bytes=(\\d+)-(\\d*)").matchEntire(range.trim()) ?: return null
        val start = m.groupValues[1].toLong()
        val wanted = m.groupValues[2].toLongOrNull()
        val data = File(dir(context), name(url) + ".v")
        val meta = File(dir(context), name(url) + ".vm")
        val pinned = PINNED.containsMatchIn(url)
        val usable = data.isFile && meta.isFile && (pinned || System.currentTimeMillis() - data.lastModified() < VIDEO_RENEW_MS)
        if (!usable) {
            if (start == 0L && fetching.add(url)) Thread { try { fetchPrefix(url, data, meta) } finally { fetching.remove(url) } }.start()
            return null
        }
        val have = data.length()
        val total = meta.readText().trim().toLongOrNull() ?: return null
        if (start >= have) return null
        val end = minOf(wanted ?: (have - 1), have - 1)
        if (end < start) return null
        val bytes = java.io.RandomAccessFile(data, "r").use { f -> f.seek(start); ByteArray((end - start + 1).toInt()).also { f.readFully(it) } }
        return WebResourceResponse(mime, null, 206, "Partial Content", mapOf("Content-Range" to "bytes $start-$end/$total", "Accept-Ranges" to "bytes", "Content-Length" to bytes.size.toString(), "Access-Control-Allow-Origin" to "*"), java.io.ByteArrayInputStream(bytes))
    }

    private fun fetchPrefix(url: String, data: File, meta: File) {
        try {
            val c = URL(url).openConnection() as HttpURLConnection
            c.connectTimeout = 8_000; c.readTimeout = 15_000
            c.setRequestProperty("Range", "bytes=0-${PREFIX - 1}")
            val code = c.responseCode
            if (code != 200 && code != 206) return
            val total = c.getHeaderField("Content-Range")?.substringAfter('/')?.trim()?.toLongOrNull() ?: c.contentLengthLong.takeIf { it > 0 } ?: return
            val tmp = File(data.parentFile, data.name + ".part")
            var size = 0L
            c.inputStream.use { input -> tmp.outputStream().use { out -> val buf = ByteArray(16 * 1024); while (size < PREFIX) { val n = input.read(buf, 0, minOf(buf.size.toLong(), PREFIX - size).toInt()); if (n < 0) break; out.write(buf, 0, n); size += n } } }
            c.disconnect()
            if (size <= 0) { tmp.delete(); return }
            if (code == 200 && size < PREFIX && size != total) { tmp.delete(); return }      // a short read that is not the whole file: not kept
            meta.writeText(total.toString())
            tmp.renameTo(data)
            trim(data.parentFile!!)
        } catch (err: Exception) { /* nothing kept: the next time tries again */ }
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
