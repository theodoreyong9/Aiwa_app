package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NavWordsTest {
    @Test fun `the words alone are commands`() {
        assertEquals("next", NavWords.commandOf("Suivant"))
        assertEquals("next", NavWords.commandOf("suivant."))
        assertEquals("prev", NavWords.commandOf("Précédent !"))
        assertEquals("open", NavWords.commandOf("ouvre"))
        assertEquals("close", NavWords.commandOf("Ferme"))
        assertEquals("close", NavWords.commandOf("ferme ça"))
    }

    @Test fun `the same words in a sentence are not`() {
        assertNull(NavWords.commandOf("passe au suivant projet"))
        assertNull(NavWords.commandOf("ouvre les réglages"))
        assertNull(NavWords.commandOf("ouvre l'application aiwa"))
        assertNull(NavWords.commandOf("ferme la fenêtre de la chambre"))
        assertNull(NavWords.commandOf(""))
    }
}
