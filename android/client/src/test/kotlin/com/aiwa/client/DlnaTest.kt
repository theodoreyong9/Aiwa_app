package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DlnaTest {
    private val description = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0"><device><friendlyName>Salon &amp; Cuisine</friendlyName>
<serviceList>
<service><serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType><controlURL>/RenderingControl/control</controlURL></service>
<service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><controlURL>/AVTransport/control</controlURL></service>
</serviceList></device></root>"""

    @Test fun theSearchAsksForMediaRenderersOnTheMulticastAddress() {
        val request = Dlna.searchRequest()
        assertTrue(request.startsWith("M-SEARCH * HTTP/1.1\r\n"))
        assertTrue(request.contains("HOST: 239.255.255.250:1900"))
        assertTrue(request.contains("ST: urn:schemas-upnp-org:device:MediaRenderer:1"))
        assertTrue(request.endsWith("\r\n\r\n"))
    }

    @Test fun anAnswerGivesWhereTheDeviceIsDescribed() {
        val reply = Dlna.parseSsdp("HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nLOCATION: http://192.168.1.20:7676/xml/desc.xml\r\nST: urn:schemas-upnp-org:device:MediaRenderer:1\r\nUSN: uuid:abc::x\r\n\r\n")
        assertNotNull(reply)
        assertEquals("http://192.168.1.20:7676/xml/desc.xml", reply!!.location)
        assertNull(Dlna.parseSsdp("NOTIFY * HTTP/1.1\r\nLOCATION: http://x/\r\n\r\n"))
        assertNull(Dlna.parseSsdp("HTTP/1.1 200 OK\r\nLOCATION: https://x/desc.xml\r\n\r\n"))     // only plain http on the local network
        assertNull(Dlna.parseSsdp("HTTP/1.1 200 OK\r\nST: x\r\n\r\n"))
    }

    @Test fun theDescriptionGivesTheNameAndTheControlPointOfAVTransport() {
        val renderer = Dlna.parseDescription(description, "http://192.168.1.20:7676/xml/desc.xml")!!
        assertEquals("Salon & Cuisine", renderer.name)
        assertEquals("http://192.168.1.20:7676/AVTransport/control", renderer.controlUrl)
        assertEquals(Triple("192.168.1.20", 7676, "/AVTransport/control"), Triple(renderer.host, renderer.port, renderer.path))
    }

    @Test fun aDeviceThatCannotPlayIsLeftOut() {
        assertNull(Dlna.parseDescription("<root><device><friendlyName>Barre de son</friendlyName><serviceList><service><serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType><controlURL>/rc</controlURL></service></serviceList></device></root>", "http://10.0.0.5/d.xml"))
        assertNull(Dlna.parseDescription("<root></root>", "http://10.0.0.5/d.xml"))
    }

    @Test fun theUrlBaseOfTheDescriptionWins() {
        val xml = "<root><URLBase>http://192.168.1.30:9000/</URLBase><device><friendlyName>TV</friendlyName><serviceList><service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><controlURL>ctl/av</controlURL></service></serviceList></device></root>"
        assertEquals("http://192.168.1.30:9000/ctl/av", Dlna.parseDescription(xml, "http://192.168.1.30:8080/d.xml")!!.controlUrl)
    }

    @Test fun theMessagesCarryTheAddressAndEscapeTheTitle() {
        val set = Dlna.setUriEnvelope("http://192.168.1.5:8080/video.mp4?a=1&b=2", "Café <du> Port & Cie")
        assertTrue(set.contains("<u:SetAVTransportURI"))
        assertTrue(set.contains("<CurrentURI>http://192.168.1.5:8080/video.mp4?a=1&amp;b=2</CurrentURI>"))
        assertTrue(set.contains("Caf") && !set.contains("<du>"))                    // the title cannot break the document
        assertTrue(set.contains("&amp;lt;du&amp;gt;"))                              // escaped twice: once in the metadata, once as the content of the element
        assertTrue(Dlna.playEnvelope().contains("<Speed>1</Speed>"))
        assertTrue(Dlna.stopEnvelope().contains("<u:Stop"))
        assertEquals("\"urn:schemas-upnp-org:service:AVTransport:1#Play\"", Dlna.soapAction("Play"))
    }

    @Test fun theRangeOfAnRequestIsReadTheWayTelevisionsAskForIt() {
        assertEquals(0L to 999L, Dlna.byteRange(null, 1000))
        assertEquals(100L to 999L, Dlna.byteRange("bytes=100-", 1000))
        assertEquals(100L to 199L, Dlna.byteRange("bytes=100-199", 1000))
        assertEquals(900L to 999L, Dlna.byteRange("bytes=-100", 1000))          // the last 100 bytes
        assertEquals(0L to 999L, Dlna.byteRange("bytes=0-5000", 1000))
        assertNull(Dlna.byteRange("bytes=2000-", 1000))
        assertNull(Dlna.byteRange("bytes=-", 1000))
    }
}
