package com.aiwa.client

import java.net.URI

/**
 * Casting a video to a television with DLNA / UPnP, the part that is only text: what is sent to find the renderers on the Wi-Fi (SSDP), how their answers and descriptions
 * are read, and the SOAP messages that tell one to play an address (AVTransport). No network here, so that it is tested on a JVM. The network and the screen are the app's
 * (CastEngine.kt, CastActivity.kt).
 */
object Dlna {
    const val SSDP_ADDRESS = "239.255.255.250"
    const val SSDP_PORT = 1900
    const val RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
    private const val AVTRANSPORT_PREFIX = "urn:schemas-upnp-org:service:AVTransport:"

    /** The multicast search for media renderers (televisions, boxes, speakers that play a video). */
    fun searchRequest(maxWaitSeconds: Int = 2, target: String = RENDERER): String =
        "M-SEARCH * HTTP/1.1\r\nHOST: $SSDP_ADDRESS:$SSDP_PORT\r\nMAN: \"ssdp:discover\"\r\nMX: $maxWaitSeconds\r\nST: $target\r\n\r\n"

    data class SsdpReply(val location: String, val st: String, val usn: String)

    /** One answer to the search: where the description of the device is. Null when it is not an answer with a location. */
    fun parseSsdp(text: String): SsdpReply? {
        val lines = text.split("\r\n", "\n")
        if (lines.isEmpty() || !lines[0].startsWith("HTTP/1.1 200")) return null
        val headers = lines.drop(1).mapNotNull { line ->
            val i = line.indexOf(':')
            if (i <= 0) null else line.substring(0, i).trim().lowercase() to line.substring(i + 1).trim()
        }.toMap()
        val location = headers["location"] ?: return null
        if (!location.startsWith("http://")) return null
        return SsdpReply(location, headers["st"] ?: "", headers["usn"] ?: "")
    }

    data class Renderer(val name: String, val controlUrl: String, val host: String, val port: Int, val path: String)

    private fun tag(xml: String, name: String): String? =
        Regex("<$name>\\s*(.*?)\\s*</$name>", setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE)).find(xml)?.groupValues?.get(1)?.trim()

    /** The renderer a device description (an XML document) declares, with the absolute address of its AVTransport control point. Null when it cannot play. */
    fun parseDescription(xml: String, location: String): Renderer? {
        val name = tag(xml, "friendlyName")?.let { unescapeXml(it) } ?: return null
        val base = tag(xml, "URLBase") ?: location
        val control = Regex("<service>(.*?)</service>", setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE)).findAll(xml)
            .map { it.groupValues[1] }
            .firstOrNull { (tag(it, "serviceType") ?: "").startsWith(AVTRANSPORT_PREFIX) }
            ?.let { tag(it, "controlURL") } ?: return null
        val absolute = try { URI(base).resolve(control.trim()) } catch (err: Exception) { return null }
        if (absolute.scheme != "http" || absolute.host == null) return null
        val port = if (absolute.port > 0) absolute.port else 80
        val path = (absolute.rawPath ?: "/") + (absolute.rawQuery?.let { "?$it" } ?: "")
        return Renderer(name, absolute.toString(), absolute.host, port, path)
    }

    fun escapeXml(text: String): String = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&apos;")
    fun unescapeXml(text: String): String = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'").replace("&amp;", "&")

    /** What describes the media to the renderer (DIDL-Lite): a video, with the address it can fetch it from. */
    fun didl(title: String, url: String, mime: String = "video/mp4"): String =
        "<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\">" +
            "<item id=\"0\" parentID=\"-1\" restricted=\"1\"><dc:title>${escapeXml(title)}</dc:title><upnp:class>object.item.videoItem</upnp:class>" +
            "<res protocolInfo=\"http-get:*:$mime:*\">${escapeXml(url)}</res></item></DIDL-Lite>"

    private fun envelope(action: String, body: String): String =
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>" +
            "<s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
            "<u:$action xmlns:u=\"${AVTRANSPORT_PREFIX}1\"><InstanceID>0</InstanceID>$body</u:$action></s:Body></s:Envelope>"

    fun setUriEnvelope(url: String, title: String): String =
        envelope("SetAVTransportURI", "<CurrentURI>${escapeXml(url)}</CurrentURI><CurrentURIMetaData>${escapeXml(didl(title, url))}</CurrentURIMetaData>")

    fun playEnvelope(): String = envelope("Play", "<Speed>1</Speed>")
    fun stopEnvelope(): String = envelope("Stop", "")

    /** The SOAPACTION header of an action. */
    fun soapAction(action: String): String = "\"${AVTRANSPORT_PREFIX}1#$action\""

    /** The byte range of a `Range: bytes=a-b` request over a file of `size` bytes: (first, last) inclusive, or null when it is not satisfiable. Null header: the whole file. */
    fun byteRange(header: String?, size: Long): Pair<Long, Long>? {
        if (size <= 0) return null
        if (header == null) return 0L to size - 1
        val match = Regex("^bytes=(\\d*)-(\\d*)$").find(header.trim()) ?: return 0L to size - 1
        val (a, b) = match.destructured
        val first: Long
        val last: Long
        if (a.isEmpty()) {
            if (b.isEmpty()) return null
            first = maxOf(0L, size - b.toLong()); last = size - 1
        } else {
            first = a.toLong(); last = if (b.isEmpty()) size - 1 else minOf(b.toLong(), size - 1)
        }
        return if (first > last || first >= size) null else first to last
    }
}
