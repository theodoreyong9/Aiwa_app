package com.aiwa.client

/** The CI publishes every build of main as the one file of a rolling release (tag android-latest), whose description names the commit. The installed build names its commit in its version (1.<first seven characters>). */
const val APP_RELEASE_API = "https://api.github.com/repos/theodoreyong9/Aiwa_app/releases/tags/android-latest"
const val APP_RELEASE_PAGE = "https://github.com/theodoreyong9/Aiwa_app/releases/tag/android-latest"

/** Whether the installed build is the one of `releaseSha` (the full commit of the release). A local build is never up to date. */
fun isUpToDate(versionName: String?, releaseSha: String): Boolean {
    val short = versionName?.substringAfterLast('.') ?: return false
    return short.length >= 7 && releaseSha.startsWith(short, ignoreCase = true)
}

/** An APK starts like any zip file, with "PK", and is far bigger than an error page. */
fun looksLikeApk(firstBytes: ByteArray, size: Long): Boolean = size > 1_000_000 && firstBytes.size >= 2 && firstBytes[0] == 'P'.code.toByte() && firstBytes[1] == 'K'.code.toByte()

/** An mp4 or a mov starts with a box whose type, "ftyp", sits at bytes 4 to 8; a web page or an error is not that. */
fun looksLikeVideo(firstBytes: ByteArray, size: Long): Boolean =
    size > 10_000 && firstBytes.size >= 8 && String(firstBytes, 4, 4, Charsets.ISO_8859_1) == "ftyp"

/** 1.0 for the same text, towards 0 as the edits needed to turn one into the other grow (Levenshtein over the longer length): the name of a television said aloud against the names found. */
fun similarityOf(a: String, b: String): Double {
    if (a == b) return 1.0
    if (a.isEmpty() || b.isEmpty()) return 0.0
    var previous = IntArray(b.length + 1) { it }
    for (i in 1..a.length) {
        val current = IntArray(b.length + 1)
        current[0] = i
        for (j in 1..b.length) {
            val cost = if (a[i - 1] == b[j - 1]) 0 else 1
            current[j] = minOf(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
        }
        previous = current
    }
    return 1.0 - previous[b.length].toDouble() / maxOf(a.length, b.length)
}
