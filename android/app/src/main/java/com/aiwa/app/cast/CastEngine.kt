package com.aiwa.app.cast

import android.content.Context
import android.net.wifi.WifiManager
import com.aiwa.client.Dlna
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException

/**
 * Casting a video to a television with DLNA / UPnP (the text of it is Dlna.kt in the bridge, tested). Here the network: finding the renderers of the Wi-Fi, a small HTTP
 * server on the phone that serves the video (a television reads a plain http address, with ranges, far better than a github.com release address), and the messages that tell
 * the renderer to play it. Plain sockets are used on purpose: the app's network policy forbids cleartext http for its own connections, and these are devices of the local network.
 */
object CastEngine {
    /** The renderers that answer within `waitMs`, with the name each gives itself. */
    suspend fun discover(context: Context, waitMs: Long = 4000): List<Dlna.Renderer> = withContext(Dispatchers.IO) {
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val lock = try { wifi?.createMulticastLock("aiwa-cast")?.also { it.setReferenceCounted(false); it.acquire() } } catch (err: Exception) { null }
        val locations = LinkedHashSet<String>()
        try {
            DatagramSocket().use { socket ->
                socket.soTimeout = 500
                val target = InetAddress.getByName(Dlna.SSDP_ADDRESS)
                // sent twice, for the renderers and for every device: some televisions only answer the general searches (the description decides what is a renderer)
                repeat(2) {
                    for (st in listOf(Dlna.RENDERER, "upnp:rootdevice", "ssdp:all")) {
                        val request = Dlna.searchRequest(target = st).toByteArray()
                        socket.send(DatagramPacket(request, request.size, target, Dlna.SSDP_PORT))
                    }
                }
                val buffer = ByteArray(4096)
                val end = System.currentTimeMillis() + waitMs
                while (System.currentTimeMillis() < end) {
                    try {
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.receive(packet)
                        Dlna.parseSsdp(String(packet.data, 0, packet.length, Charsets.UTF_8))?.let { locations.add(it.location) }
                    } catch (err: SocketTimeoutException) { /* keep listening until the end */ }
                }
            }
        } finally {
            try { lock?.release() } catch (err: Exception) { }
        }
        locations.mapNotNull { location ->
            try {
                val uri = java.net.URI(location)
                val (status, body) = RawHttp.request(uri.host, if (uri.port > 0) uri.port else 80, "GET", (uri.rawPath ?: "/") + (uri.rawQuery?.let { "?$it" } ?: ""), emptyMap(), null, 4000)
                if (status == 200) Dlna.parseDescription(body, location) else null
            } catch (err: Exception) { null }
        }.distinctBy { it.controlUrl }
    }

    /** The address of this phone on the network the renderer is on. */
    fun localAddressToward(host: String): String? = try {
        DatagramSocket().use { s -> s.connect(InetSocketAddress(host, 9)); s.localAddress?.hostAddress }
    } catch (err: Exception) { null }

    private fun soap(renderer: Dlna.Renderer, action: String, body: String): Pair<Int, String> =
        RawHttp.request(
            renderer.host, renderer.port, "POST", renderer.path,
            mapOf("Content-Type" to "text/xml; charset=\"utf-8\"", "SOAPACTION" to Dlna.soapAction(action)),
            body.toByteArray(), 8000,
        )

    /** Tells the renderer to play `url`. Returns null when it did, the reason when it did not. */
    suspend fun play(renderer: Dlna.Renderer, url: String, title: String): String? = withContext(Dispatchers.IO) {
        try {
            val set = soap(renderer, "SetAVTransportURI", Dlna.setUriEnvelope(url, title))
            if (set.first != 200) return@withContext "${renderer.name} a refusé l'adresse de la vidéo (code ${set.first})."
            val play = soap(renderer, "Play", Dlna.playEnvelope())
            if (play.first != 200) "${renderer.name} n'a pas pu démarrer la lecture (code ${play.first})." else null
        } catch (err: Exception) { "${renderer.name} ne répond pas : ${err.message ?: err.javaClass.simpleName}" }
    }

    suspend fun stop(renderer: Dlna.Renderer) = withContext(Dispatchers.IO) { try { soap(renderer, "Stop", Dlna.stopEnvelope()) } catch (err: Exception) { } }
}

/** A few lines of HTTP/1.1 over a plain socket: the devices of the local network speak http, which the app's own connections are not allowed to. */
object RawHttp {
    fun request(host: String, port: Int, method: String, path: String, headers: Map<String, String>, body: ByteArray?, timeoutMs: Int): Pair<Int, String> {
        Socket().use { socket ->
            socket.connect(InetSocketAddress(host, port), timeoutMs)
            socket.soTimeout = timeoutMs
            val out = socket.getOutputStream()
            val head = StringBuilder("$method $path HTTP/1.1\r\nHost: $host:$port\r\nConnection: close\r\n")
            headers.forEach { (k, v) -> head.append("$k: $v\r\n") }
            if (body != null) head.append("Content-Length: ${body.size}\r\n")
            head.append("\r\n")
            out.write(head.toString().toByteArray())
            if (body != null) out.write(body)
            out.flush()
            val bytes = ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            val input = socket.getInputStream()
            try {
                while (bytes.size() < 2_000_000) {
                    val n = input.read(buffer)
                    if (n < 0) break
                    bytes.write(buffer, 0, n)
                }
            } catch (err: SocketTimeoutException) { /* what came is what there is */ }
            val raw = bytes.toString("UTF-8")
            val split = raw.indexOf("\r\n\r\n")
            val headerText = if (split >= 0) raw.substring(0, split) else raw
            val status = Regex("^HTTP/1\\.[01] (\\d{3})").find(headerText)?.groupValues?.get(1)?.toInt() ?: 0
            var text = if (split >= 0) raw.substring(split + 4) else ""
            if (headerText.contains("transfer-encoding: chunked", ignoreCase = true)) text = unchunk(text)
            return status to text
        }
    }

    private fun unchunk(text: String): String {
        val out = StringBuilder()
        var rest = text
        while (rest.isNotEmpty()) {
            val eol = rest.indexOf("\r\n")
            if (eol < 0) break
            val size = rest.substring(0, eol).trim().substringBefore(';').toIntOrNull(16) ?: break
            if (size == 0) break
            val start = eol + 2
            if (start + size > rest.length) { out.append(rest.substring(start)); break }
            out.append(rest, start, start + size)
            rest = rest.substring(minOf(rest.length, start + size + 2))
        }
        return out.toString()
    }
}

/** Serves ONE file over http on a free port of the phone, with the byte ranges a television asks for, until it is stopped. */
class LocalMediaServer(private val file: File, private val mime: String = "video/mp4") {
    private var server: ServerSocket? = null
    @Volatile private var running = false
    val port: Int get() = server?.localPort ?: 0

    fun start() {
        val socket = ServerSocket(0)
        server = socket
        running = true
        Thread {
            while (running) {
                val client = try { socket.accept() } catch (err: Exception) { break }
                Thread { try { serve(client) } catch (err: Exception) { } finally { try { client.close() } catch (err: Exception) { } } }.start()
            }
        }.also { it.isDaemon = true }.start()
    }

    fun stop() {
        running = false
        try { server?.close() } catch (err: Exception) { }
        server = null
    }

    private fun serve(client: Socket) {
        client.soTimeout = 15_000
        val reader = client.getInputStream().bufferedReader()
        val requestLine = reader.readLine() ?: return
        val headers = HashMap<String, String>()
        while (true) {
            val line = reader.readLine() ?: break
            if (line.isEmpty()) break
            val i = line.indexOf(':')
            if (i > 0) headers[line.substring(0, i).trim().lowercase()] = line.substring(i + 1).trim()
        }
        val method = requestLine.substringBefore(' ')
        val size = file.length()
        val out = client.getOutputStream()
        val range = Dlna.byteRange(headers["range"], size)
        if (method != "GET" && method != "HEAD") { respond(out, "405 Method Not Allowed", size, null, 0, 0); return }
        if (range == null) { respond(out, "416 Range Not Satisfiable", size, null, 0, 0); return }
        val (first, last) = range
        val partial = headers["range"] != null
        respond(out, if (partial) "206 Partial Content" else "200 OK", last - first + 1, if (partial) "bytes $first-$last/$size" else null, first, last, headOnly = method == "HEAD")
    }

    private fun respond(out: OutputStream, status: String, length: Long, contentRange: String?, first: Long, last: Long, headOnly: Boolean = true) {
        val head = StringBuilder("HTTP/1.1 $status\r\nContent-Type: $mime\r\nContent-Length: $length\r\nAccept-Ranges: bytes\r\nConnection: close\r\n")
        head.append("transferMode.dlna.org: Streaming\r\ncontentFeatures.dlna.org: DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01700000000000000000000000000000\r\n")
        if (contentRange != null) head.append("Content-Range: $contentRange\r\n")
        head.append("\r\n")
        out.write(head.toString().toByteArray())
        if (!headOnly && status.startsWith("2")) {
            file.inputStream().use { input -> copyRange(input, out, first, last) }
        }
        out.flush()
    }

    private fun copyRange(input: InputStream, out: OutputStream, first: Long, last: Long) {
        var skip = first
        while (skip > 0) { val n = input.skip(skip); if (n <= 0) break; skip -= n }
        var left = last - first + 1
        val buffer = ByteArray(64 * 1024)
        while (left > 0) {
            val n = input.read(buffer, 0, minOf(buffer.size.toLong(), left).toInt())
            if (n < 0) break
            out.write(buffer, 0, n)
            left -= n
        }
    }
}
