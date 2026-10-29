package com.aiwa.client

import org.junit.Assert.assertEquals
import org.junit.Test

class SpokenTest {
    @Test fun `a short word is a confirmation, a refusal or a stop`() {
        for (s in listOf("Oui", "oui vas-y", "C'est bon, vas-y", "ok", "envoie", "d'accord")) assertEquals(s, Reply.CONFIRM, Spoken.reply(s))
        for (s in listOf("Non", "annule", "laisse tomber", "non merci")) assertEquals(s, Reply.CANCEL, Spoken.reply(s))
        for (s in listOf("stop", "Arrête", "tais-toi")) assertEquals(s, Reply.STOP, Spoken.reply(s))
    }

    @Test fun `anything longer or different is a new request`() {
        for (s in listOf("", "fais une vidéo pour mon app", "oui mais ajoute aussi une page avec les prix et les horaires", "montre-moi mes documents")) assertEquals(s, Reply.OTHER, Spoken.reply(s))
    }

    @Test fun `stop wins over the rest`() {
        assertEquals(Reply.STOP, Spoken.reply("non stop"))
    }
}
