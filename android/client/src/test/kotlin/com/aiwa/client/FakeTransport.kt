package com.aiwa.client

import java.io.IOException

/** The brain, as a table of answers: what was asked is kept so that a test can look at it. */
class FakeTransport(private val answers: MutableMap<String, String> = mutableMapOf()) : Transport {
    val asked = mutableListOf<Pair<String, String>>()
    var streamLines: List<String> = emptyList()
    var bytes: ByteArray? = null

    fun on(path: String, answer: String) { answers[path] = answer }

    override fun get(path: String, timeoutMs: Int): String { asked += path to ""; return answers[path] ?: throw IOException("no answer for $path") }
    override fun post(path: String, body: String, timeoutMs: Int): String { asked += path to body; return answers[path] ?: throw IOException("no answer for $path") }
    override fun stream(path: String, body: String, timeoutMs: Int, onLine: (String) -> Unit) { asked += path to body; streamLines.forEach(onLine) }
    override fun postBytes(path: String, body: String, timeoutMs: Int): ByteArray? { asked += path to body; return bytes }
}
