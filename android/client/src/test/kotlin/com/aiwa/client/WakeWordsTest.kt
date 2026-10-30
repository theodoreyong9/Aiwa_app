package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class WakeWordsTest {
    @Test fun `a transcription is plain words`() {
        assertEquals("heille wa", WakeWords.plain("Heille Wa !"))
        assertEquals("es ou la", WakeWords.plain("[unk] t'es où là"))
        assertEquals("", WakeWords.plain("[unk]"))
    }

    @Test fun `the words of origin are understood`() {
        assertEquals(WakeKind.CALL, WakeWords.kind("heille wa"))
        assertEquals(WakeKind.CALL, WakeWords.kind("mon super agent"))
        assertEquals(WakeKind.DIRECT, WakeWords.kind("mon agent"))
        assertEquals(WakeKind.STOP, WakeWords.kind("stop claude"))
        assertEquals(WakeKind.STOP, WakeWords.kind("arrête la commande"))
        assertEquals(WakeKind.OFF, WakeWords.kind("éteins toi"))
        assertNull(WakeWords.kind("bonjour tout le monde"))
        assertNull(WakeWords.kind("stop"))
    }

    @Test fun `a word of the person is the spellings the engine heard`() {
        val customs = WakeCustoms(call = listOf("ail oua", "ai oua"))
        assertEquals(WakeKind.CALL, WakeWords.kind("ail oua", customs))
        assertEquals(WakeKind.CALL, WakeWords.kind("ail oua t'en es où", customs))
        assertNull(WakeWords.kind("ail oua"))
    }

    @Test fun `a word that would fire all day is refused`() {
        assertTrue(WakeWords.check(listOf("ail oua", "ail oua")) is WakeWords.Check.Ok)
        assertTrue(WakeWords.check(listOf("ail oua")) is WakeWords.Check.Rejected)
        assertTrue(WakeWords.check(listOf("bon", "bon")) is WakeWords.Check.Rejected)
        assertTrue(WakeWords.check(listOf("mon agent", "mon agent")) is WakeWords.Check.Rejected)
        assertTrue(WakeWords.check(listOf("salut alors", "salut alors")) is WakeWords.Check.Rejected)
    }

    @Test fun `the grammar holds the words of origin, the spellings and the unknown`() {
        val grammar = WakeWords.grammar(listOf("Ail Oua"))
        assertTrue(grammar.startsWith("[") && grammar.endsWith("]"))
        for (w in listOf("\"mon agent\"", "\"ail oua\"", "\"[unk]\"", "\"éteins\"")) assertTrue(w, grammar.contains(w))
    }

    @Test fun `a question is not a request for work`() {
        for (s in listOf("c'est quoi ce dépôt", "Pourquoi le build échoue", "explique-moi le projet", "où en est la vidéo")) assertTrue(s, isQuestion(s))
        for (s in listOf("fais une vidéo", "ajoute une page", "")) assertFalse(s, isQuestion(s))
    }

    @Test fun `a television is recognised by its name said aloud`() {
        assertEquals(1.0, similarityOf("salon", "salon"), 0.0)
        assertTrue(similarityOf("salon", "saloon") > 0.7)
        assertTrue(similarityOf("salon", "chambre") < 0.4)
    }
}
