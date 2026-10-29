package com.aiwa.client

import java.text.Normalizer

/** What a short spoken answer means to the app: the agent has read a proposal back and waits for a word. */
enum class Reply { CONFIRM, CANCEL, STOP, OTHER }

object Spoken {
    private fun plain(text: String): String =
        Normalizer.normalize(text.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").replace(Regex("[^a-z0-9 ]"), " ").split(' ').filter { it.isNotEmpty() }.joinToString(" ")

    private val CONFIRM = listOf("oui", "ouais", "ok", "okay", "d accord", "c est bon", "vas y", "va y", "go", "envoie", "envoie le", "confirme", "confirmer", "fais le", "fais la", "lance", "lance le", "allez")
    private val CANCEL = listOf("non", "annule", "annuler", "laisse tomber", "oublie", "pas maintenant", "ne l envoie pas", "n envoie pas")
    private val STOP = listOf("stop", "arrete", "arrete toi", "tais toi", "silence", "assez")

    /** The meaning of what was said when it is only a confirmation, a refusal or a stop; anything longer is a new request for the agent. */
    fun reply(text: String): Reply {
        val words = plain(text)
        if (words.isEmpty() || words.split(' ').size > 6) return Reply.OTHER
        fun has(list: List<String>) = list.any { words == it || words.startsWith("$it ") || words.endsWith(" $it") || words.contains(" $it ") }
        return when {
            has(STOP) -> Reply.STOP
            has(CANCEL) -> Reply.CANCEL
            has(CONFIRM) -> Reply.CONFIRM
            else -> Reply.OTHER
        }
    }
}
