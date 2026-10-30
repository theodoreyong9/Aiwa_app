package com.aiwa.client

import java.text.Normalizer

/** What the small listening model hears: CALL wakes the super agent (a conversation: it sends when asked to), DIRECT wakes the agent that sends at once what is dictated, STOP silences it, OFF puts the permanent listening to sleep. */
enum class WakeKind { CALL, DIRECT, STOP, OFF }

/** The spellings (as the small model hears them) of the words the person chose; empty lists mean the words of origin only. */
data class WakeCustoms(val call: List<String> = emptyList(), val stop: List<String> = emptyList(), val off: List<String> = emptyList(), val direct: List<String> = emptyList()) {
    fun all(): List<String> = call + stop + off + direct
}

/**
 * The words the person chose, as the engine HEARS them. The detector's grammar can only hold words that the small French model knows ("Aiwa" is not one of them), so a chosen
 * word is not written but SAID: the person says it a few times, the model writes what it hears with its nearest French words ("ail oua", "ai oua"…), and those spellings,
 * the variants, are what the detector listens for. It works for any word, because it keeps how the engine hears it, not how it is spelt.
 */
object WakeWords {
    /** What the detector always listens for. */
    val DEFAULT_PHRASES = listOf("heille wa", "haye wa", "mon agent", "mon super agent", "stop claude", "arrête claude", "stop la commande", "stop aiwa", "éteins", "éteins toi")
    const val MIN_LETTERS = 5
    const val MAX_VARIANTS = 6

    private val CALL_PAIRS = listOf("heille" to "wa", "haye" to "wa", "super" to "agent")
    private val DIRECT_PAIRS = listOf("mon" to "agent")
    private val STOP_WORDS = setOf("stop", "arrete")
    private val STOP_TARGETS = setOf("claude", "aiwa", "commande")

    // Words so common that, heard alone, they would wake the phone all day long.
    private val COMMON = setOf(
        "oui", "non", "ok", "ca", "le", "la", "les", "un", "une", "des", "et", "ou", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "de", "du", "en", "ce", "se", "me", "te", "ne", "pas",
        "que", "qui", "est", "bon", "salut", "allo", "ail", "eau", "aie", "voila", "alors", "donc", "merci", "bonjour", "allez", "tiens", "hein", "ben", "bah", "euh", "mais", "comme", "avec", "pour",
        "dans", "sur", "par", "plus", "tout", "tous", "cette", "cela", "ici", "bien", "tres", "fait", "faire", "dit", "dire", "va", "vas", "vais", "suis", "es", "sont", "ete", "etre", "avoir",
    )

    private fun plainWord(word: String): String {
        val noAccent = Normalizer.normalize(word.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "")
        return noAccent.substringAfterLast('\'').substringAfterLast('’').filter { it in 'a'..'z' || it in '0'..'9' }
    }

    /** A transcription as a plain phrase: lowercase, no accent, no punctuation, one space between words. "[unk]" and an empty text give "". */
    fun plain(text: String): String = text.trim().split(Regex("\\s+")).map { plainWord(it) }.filter { it.isNotEmpty() && it != "unk" }.joinToString(" ")

    sealed class Check {
        data class Ok(val variants: List<String>) : Check()
        data class Rejected(val reason: String) : Check()
    }

    /** What was heard when the person said their word, one text per try: the variants to keep, or why this word cannot be listened for. */
    fun check(heard: List<String>): Check {
        val phrases = heard.map { plain(it) }.filter { it.isNotEmpty() }
        if (phrases.size < 2) return Check.Rejected("Je n'ai rien compris de ton mot (${phrases.size} essai sur ${heard.size}). Redis-le distinctement, au moins deux fois, dans le calme.")
        val variants = phrases.distinct().take(MAX_VARIANTS)
        val defaults = DEFAULT_PHRASES.map { plain(it) }
        for (v in variants) {
            val letters = v.count { it in 'a'..'z' || it in '0'..'9' }
            val parts = v.split(' ')
            when {
                v in defaults -> return Check.Rejected("« $v » est déjà un mot d'origine : choisis-en un autre.")
                letters < MIN_LETTERS -> return Check.Rejected("J'ai entendu « $v » : c'est trop court (au moins $MIN_LETTERS lettres), il se déclencherait sans arrêt. Choisis un mot plus long ou deux mots.")
                parts.all { it in COMMON } -> return Check.Rejected("J'ai entendu « $v » : ce sont des mots trop courants, ils se déclencheraient dans toutes les conversations. Choisis un mot plus rare.")
            }
        }
        return Check.Ok(variants)
    }

    /** The grammar of the detector (the JSON list of the Vosk Recognizer): the phrases of origin, the variants of the chosen words, and "[unk]" for everything else. */
    fun grammar(variants: List<String>): String =
        (DEFAULT_PHRASES + variants.map { plain(it) }.filter { it.isNotEmpty() } + "[unk]").distinct().joinToString(prefix = "[", postfix = "]") { "\"" + it.replace("\\", "\\\\").replace("\"", "\\\"") + "\"" }

    /** Is one of the chosen spellings in what was heard? (a variant, as a whole word or whole words: "ail oua" in "ail oua t'en es où"). */
    fun heardCustom(heard: String, variants: List<String>): Boolean {
        val h = plain(heard)
        if (h.isEmpty()) return false
        return variants.any { v -> v.isNotEmpty() && (h == v || " $h ".contains(" $v ")) }
    }

    /** What a finished sentence of the small model means, or null when it is none of the words. */
    fun kind(heard: String, customs: WakeCustoms = WakeCustoms()): WakeKind? {
        val words = plain(heard).split(' ').filter { it.isNotEmpty() }
        if (words.isEmpty()) return null
        for (i in 1 until words.size) if (words[i] in STOP_TARGETS && words[i - 1] in STOP_WORDS) return WakeKind.STOP
        for (i in 2 until words.size) if (words[i] == "commande" && words[i - 1] == "la" && words[i - 2] in STOP_WORDS) return WakeKind.STOP
        if (customs.stop.isNotEmpty() && heardCustom(heard, customs.stop)) return WakeKind.STOP
        if (words.any { it == "eteins" } || (customs.off.isNotEmpty() && heardCustom(heard, customs.off))) return WakeKind.OFF
        if (customs.direct.isNotEmpty() && heardCustom(heard, customs.direct)) return WakeKind.DIRECT
        if (customs.call.isNotEmpty() && heardCustom(heard, customs.call)) return WakeKind.CALL
        for (i in 1 until words.size) if ((words[i - 1] to words[i]) in DIRECT_PAIRS) return WakeKind.DIRECT
        for (i in 1 until words.size) if ((words[i - 1] to words[i]) in CALL_PAIRS) return WakeKind.CALL
        return null
    }
}

/** What opens a QUESTION as opposed to a request for work: a spoken answer is wanted at once. Plain words. */
private val QUESTION_STARTS = listOf(
    "est ce que", "qu est ce", "quest ce", "c est quoi", "ca veut dire", "ca sert a quoi", "explique", "expliquez", "dis moi", "dit moi", "raconte", "resume", "resumer", "decris", "decrire",
    "pourquoi", "comment", "combien", "quand", "ou est", "ou sont", "ou en", "qui ", "quel ", "quelle ", "quels ", "quelles ", "quoi", "peux tu m expliquer", "tu peux m expliquer", "t en es ou",
    "a quoi", "de quoi", "en quoi", "il y a quoi", "y a t il", "qu est", "que fait", "que font", "que veut",
)

/** A question to answer by voice: it opens with a question word (« explique-moi le projet », « c'est quoi ce dépôt », « pourquoi… »). */
fun isQuestion(text: String): Boolean {
    val plain = Normalizer.normalize(text.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").replace(Regex("[^a-z0-9]+"), " ").trim()
    if (plain.isEmpty()) return false
    return QUESTION_STARTS.any { plain == it.trim() || plain.startsWith(if (it.endsWith(" ")) it else "$it ") }
}
