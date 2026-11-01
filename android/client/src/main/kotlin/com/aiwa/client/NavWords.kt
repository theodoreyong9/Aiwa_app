package com.aiwa.client

/**
 * The words of the voice navigation, only when they are said ALONE (« suivant », not « passe au suivant projet »): next and previous move the cursor on the screen that is open, open goes one level down
 * (the detail, the video), close goes one level up. « ouvre » alone is the navigation; « ouvre les réglages » is a screen and goes to the agent.
 */
object NavWords {
    private val WORDS = mapOf(
        "suivant" to "next", "suivante" to "next", "suivants" to "next",
        "precedent" to "prev", "precedente" to "prev",
        "ouvre" to "open", "ouvrir" to "open", "ouvre le" to "open", "ouvre la" to "open", "ouvre ca" to "open",
        "ferme" to "close", "fermer" to "close", "ferme le" to "close", "ferme la" to "close", "ferme ca" to "close",
    )

    /** "next", "prev", "open" or "close" when the whole sentence is one of the words, else null. */
    fun commandOf(text: String): String? = WORDS[WakeWords.plain(text)]
}
