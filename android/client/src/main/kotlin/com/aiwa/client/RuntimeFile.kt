package com.aiwa.client

/**
 * The runtime of the widget of the application (web/home/aiwa-home.js) can be refreshed from the product's repository without a new APK. Its first line says which door of the application it was made for
 * (`api`: the messages and buttons the application understands) and when it was written (`rev`, YYYYMMDDHHMM), as a comment of the script that reads: aiwa-home-runtime api=1 rev=202611021430.
 * A file from the web is taken only when it is made for THIS application (same `api`), is newer than the one in the application (`rev`), is not too big, is a script and not a page, and was not rejected before.
 */
object RuntimeFile {
    const val MAX_BYTES = 300_000
    private val HEADER = Regex("""^/\*\s*aiwa-home-runtime\s+api=(\d{1,4})\s+rev=(\d{12})\s*\*/""")

    class Header(val api: Int, val rev: Long)

    fun header(text: String?): Header? {
        val first = text?.lineSequence()?.firstOrNull()?.trim() ?: return null
        val m = HEADER.find(first) ?: return null
        return Header(m.groupValues[1].toInt(), m.groupValues[2].toLong())
    }

    /** Null when the file is good to use, else why not. */
    fun refusal(text: String?, api: Int, bundledRev: Long, rejected: Set<Long>): String? {
        if (text == null) return "rien reçu"
        if (text.length > MAX_BYTES) return "trop gros"
        val h = header(text) ?: return "pas l'en-tête du runtime"
        if (h.api != api) return "fait pour une autre version de l'application"
        if (h.rev <= bundledRev) return "pas plus récent que celui de l'application"
        if (h.rev in rejected) return "déjà refusé"
        if (!text.contains("window.__aiwaHome")) return "ce n'est pas le runtime"
        if (text.trimStart().startsWith("<")) return "une page, pas un script"
        return null
    }
}
