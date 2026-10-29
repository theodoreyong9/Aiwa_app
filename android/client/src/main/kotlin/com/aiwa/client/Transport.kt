package com.aiwa.client

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** How the client reaches the brain: three calls, so that a test can stand in for the network. */
interface Transport {
    /** The body of the answer to a GET. Throws IOException when the brain does not answer. */
    fun get(path: String, timeoutMs: Int = 8000): String

    /** The body of the answer to a POST. */
    fun post(path: String, body: String, timeoutMs: Int = 20000): String

    /** A POST whose answer comes line by line (the sentences of a spoken answer): each line goes to `onLine` as it arrives. */
    fun stream(path: String, body: String, timeoutMs: Int, onLine: (String) -> Unit)

    /** A POST whose answer is bytes (the natural voice's sound). */
    fun postBytes(path: String, body: String, timeoutMs: Int = 60000): ByteArray?

    /** A POST whose body is bytes read from `input` (the person's own video, which can be big): sent as they are, `length` known or -1. */
    fun upload(path: String, input: java.io.InputStream, length: Long, timeoutMs: Int = 10 * 60_000): String = throw IOException("no upload")
}

class HttpTransport(private val base: String = DEFAULT_BASE) : Transport {
    private fun open(path: String, method: String, timeoutMs: Int): HttpURLConnection =
        (URL(base + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 3000
            readTimeout = timeoutMs
            if (method == "POST") { doOutput = true; setRequestProperty("Content-Type", "text/plain; charset=utf-8") }
        }

    override fun get(path: String, timeoutMs: Int): String {
        val c = open(path, "GET", timeoutMs)
        try { return read(c) } finally { c.disconnect() }
    }

    override fun post(path: String, body: String, timeoutMs: Int): String {
        val c = open(path, "POST", timeoutMs)
        try { c.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }; return read(c) } finally { c.disconnect() }
    }

    override fun stream(path: String, body: String, timeoutMs: Int, onLine: (String) -> Unit) {
        val c = open(path, "POST", timeoutMs)
        try {
            c.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            if (c.responseCode !in 200..299) throw IOException("brain ${c.responseCode}")
            c.inputStream.bufferedReader(Charsets.UTF_8).useLines { lines -> lines.forEach { if (it.isNotBlank()) onLine(it) } }
        } finally { c.disconnect() }
    }

    override fun postBytes(path: String, body: String, timeoutMs: Int): ByteArray? {
        val c = open(path, "POST", timeoutMs)
        try {
            c.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            if (c.responseCode !in 200..299) return null
            val type = c.contentType.orEmpty()
            return if (type.startsWith("audio/")) c.inputStream.use { it.readBytes() } else null
        } finally { c.disconnect() }
    }

    override fun upload(path: String, input: java.io.InputStream, length: Long, timeoutMs: Int): String {
        val c = open(path, "POST", timeoutMs)
        try {
            if (length >= 0) c.setFixedLengthStreamingMode(length) else c.setChunkedStreamingMode(1 shl 16)
            c.outputStream.use { out -> input.use { it.copyTo(out) } }
            return read(c)
        } finally { c.disconnect() }
    }

    private fun read(c: HttpURLConnection): String {
        val code = c.responseCode
        val stream = if (code in 200..299) c.inputStream else (c.errorStream ?: throw IOException("brain $code"))
        val text = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        if (code !in 200..299) throw IOException("brain $code")
        return text
    }

    companion object { const val DEFAULT_BASE = "http://127.0.0.1:8788" }
}
