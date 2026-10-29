package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BrainTest {
    private val net = FakeTransport()
    private val brain = Brain(net)

    @Test fun `the status carries what the widget shows`() {
        net.on("/api/status", """{"version":200,"sending":true,"sending_since":1700000000.5,"sending_note":"création","model":null,"cloud_session":"session_A","repo":"me/app","push_main":false,
            "waiting":true,"attachments":2,"attachment_files":[{"name":"a.pdf","size":3}],"silence_minutes":12,"claude_login":"needed","relay_cloud":"ok","github_token":true,
            "ask":{"id":"e1","question":"Quelle couleur ?","options":["rouge","bleu"],"session":"S","count":2},
            "agent":{"busy":false,"error":null,"say":{"id":"s1","text":"Salut","ts":1},"proposal":{"id":"p1","session":null,"repo":"me/app","message":"fais une vidéo","more":[{"session":"session_B","repo":null,"message":"autre"}],"read_back":"J'envoie"},
                     "command":{"id":"c1","read_back":"J'applique","open":"files_video","cast":{"tv":"Salon","wait":true},"auto":true},"voice":"ready","llm":"ready"},
            "chamber":{"active":true,"peer":"anna/profil","name":"Anna"},"llm":{"state":"capped","day":"2026-07-01","used":900,"cap":800},"profile":"me/me"}""")
        val s = brain.status()!!
        assertEquals(200, s.version)
        assertTrue(s.sending); assertEquals("me/app", s.repo); assertFalse(s.pushMain); assertEquals(listOf("a.pdf"), s.attachmentFiles)
        assertEquals("needed", s.claudeLogin); assertEquals(2, s.ask!!.count); assertEquals(listOf("rouge", "bleu"), s.ask!!.options)
        val agent = s.agent
        assertEquals("Salut", agent.say!!.text)
        assertEquals(listOf("me/app" to null, null to "session_B"), agent.proposal!!.targets.map { it.repo to it.session })
        assertEquals("files_video", agent.command!!.open); assertEquals("Salon", agent.command!!.castTv); assertTrue(agent.command!!.castWait); assertTrue(agent.command!!.auto)
        assertEquals("Anna", s.chamber.name); assertEquals("capped", s.llm.state); assertEquals(900L, s.llm.used)
    }

    @Test fun `a brain that does not answer is null, never an exception`() {
        assertNull(brain.status())
        assertNull(brain.files())
        assertTrue(brain.sessions().isEmpty())
        val out = brain.send("bonjour")
        assertFalse(out.ok); assertNotNull(out.error)
    }

    @Test fun `an action says why it was refused`() {
        net.on("/api/files/delete", """{"ok":false,"error":"pour supprimer, il faut un jeton GitHub"}""")
        net.on("/api/model", """{"accepted":false,"reason":"invalid model"}""")
        assertEquals("pour supprimer, il faut un jeton GitHub", brain.fileDelete("me/app", "video-a").error)
        assertEquals("invalid model", brain.setModel("???").error)
        net.on("/api/effort", """{"accepted":true,"effort":"high"}""")
        assertTrue(brain.setEffort("high").ok)
    }

    @Test fun `the productions come per kind`() {
        net.on("/api/files?repo=me%2Fapp", """{"repo":"me/app","repos":["me/app","me/other"],"error":null,"items":{"docs":[],"image":[],"video":[{"repo":"me/app","kind":"video","tag":"video-a","title":"Promo","file":"promo.mp4","size":10,"url":"https://x/p.mp4","ts":5}],"app":[],"page":[]}}""")
        val files = brain.files("me/app")!!
        assertEquals("me/app", files.repo)
        assertEquals("Promo", files.items["video"]!!.single().title)
        assertEquals("app", files.items["video"]!!.single().repoName)
        assertEquals(Files.KINDS, files.items.keys.toList())
    }

    @Test fun `sharing gives the address and the page address is the brain's`() {
        net.on("/api/files/share", """{"ok":true,"title":"Promo","url":"https://x/p.mp4","kind":"video","file":"promo.mp4"}""")
        assertEquals("https://x/p.mp4", brain.fileShare("me/app", "video-a", "promo.mp4")!!.url)
        net.on("/api/files/share", """{"ok":false,"error":"cette production n'existe plus"}""")
        assertNull(brain.fileShare("me/app", "video-a", "promo.mp4"))
        assertEquals("http://127.0.0.1:8787/api/files/page?repo=me%2Fapp&tag=page-a", brain.pageAddress("me/app", "page-a"))
    }

    @Test fun `a spoken answer arrives sentence by sentence`() {
        net.streamLines = listOf("""{"s":"Alors, voilà."}""", "pas du json", """{"s":"C'est prêt."}""", """{"done":true,"ok":true}""")
        val said = mutableListOf<String>()
        assertTrue(brain.answerStream("où en est-on ?", said::add))
        assertEquals(listOf("Alors, voilà.", "C'est prêt."), said)
        net.streamLines = listOf("""{"done":true,"ok":false}""")
        assertFalse(brain.answerStream("rien", {}))
    }

    @Test fun `what is asked of the agent travels as the brain reads it`() {
        net.on("/api/agent/ask", """{"ok":true}""")
        net.on("/api/agent/confirm", """{"ok":true,"sent":["session_A"]}""")
        assertTrue(brain.agentAsk("fais une vidéo").ok)
        assertTrue(brain.agentConfirm("p1").ok)
        assertEquals("""{"text":"fais une vidéo"}""", net.asked.first { it.first == "/api/agent/ask" }.second)
        assertEquals("""{"id":"p1"}""", net.asked.first { it.first == "/api/agent/confirm" }.second)
    }

    @Test fun `scenarios round-trip`() {
        net.on("/api/scenarios", """{"ok":true,"scenarios":[{"id":"entretien","name":"Entretien","word":"scénario entretien","kind":"double","prompt":"p","speak":"s","words":[{"word":"scène","does":"résume"}],"session":"session_A","creating":false,"error":null}]}""")
        val sc = brain.scenarios()!!.single()
        assertEquals("scène", sc.words.single().word); assertEquals("session_A", sc.session)
        val back = Scenario.parse(sc.toJson())
        assertEquals(sc.copy(session = null), back)
        net.on("/api/scenarios/said", """{"ok":true,"says":[{"id":"1","say":"Voilà","note":"n","ts":1,"do":true}]}""")
        assertEquals(listOf(ScenarioSay("1", "Voilà", "n", true)), brain.scenarioSaid("entretien"))
    }

    @Test fun `the chamber shows its lines and the offers with a published attachment only`() {
        net.on("/api/chamber", """{"ok":true,"active":true,"peer":"anna/profil","name":"Anna","lines":[{"n":1,"who":"them","name":"Anna","kind":"say","text":"Salut"}],
            "offers":[{"id":"o1","from":"Anna","text":"Regarde","attach":{"kind":"video","title":"Ma vidéo","url":"https://x/v.mp4"}},{"id":"o2","from":"Anna","text":"sans pièce"}]}""")
        val view = brain.chamber()!!
        assertEquals("Salut", view.lines.single().text)
        assertEquals(listOf("o1"), view.offers.map { it.id })
    }

    @Test fun `the natural voice is bytes or nothing`() {
        assertNull(brain.say("bonjour"))
        net.bytes = byteArrayOf(1, 2, 3)
        assertEquals(3, brain.say("bonjour")!!.size)
    }
}
