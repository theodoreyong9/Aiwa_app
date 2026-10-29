package com.aiwa.client

import org.json.JSONArray
import org.json.JSONObject

/** A request to the brain that did not succeed, with the words to show. */
class BrainException(message: String) : Exception(message)

/**
 * The language the app speaks to the brain (the small server in Termux). Every call that reads returns what the brain said, or null when it did not answer;
 * every call that does something returns an [Outcome]. Nothing here touches Android: the transport is the only thing that opens a socket.
 */
class Brain(private val net: Transport = HttpTransport()) {
    /** The result of an action: done or not, with the brain's words when it refused. */
    data class Outcome(val ok: Boolean, val error: String? = null, val json: JSONObject = JSONObject())

    private fun getJson(path: String): JSONObject? = try { JSONObject(net.get(path)) } catch (e: Exception) { null }
    private fun getArray(path: String): JSONArray? = try { JSONArray(net.get(path)) } catch (e: Exception) { null }

    private fun act(path: String, body: String = "", timeoutMs: Int = 20000): Outcome = try {
        val j = JSONObject(net.post(path, body, timeoutMs))
        val ok = if (j.has("ok")) j.optBoolean("ok") else j.optBoolean("accepted")
        Outcome(ok, if (ok) null else (j.optString("error").ifBlank { j.optString("reason") }.ifBlank { "refusé" }), j)
    } catch (e: Exception) { Outcome(false, e.message ?: "le cerveau ne répond pas") }

    private fun act(path: String, body: JSONObject, timeoutMs: Int = 20000) = act(path, body.toString(), timeoutMs)

    // ---------- the state ----------
    fun status(): Status? = getJson("/api/status")?.let { Status.parse(it) }
    fun sessions(): List<Session> = getArray("/api/cloud/sessions")?.objects()?.map { Session.parse(it) } ?: emptyList()
    fun repos(): List<String> = getJson("/api/repos")?.optJSONArray("repos").objects().map { it.optString("name") }
    fun instructions(): String? = getJson("/api/instructions")?.str("text")

    // ---------- messages to Claude ----------
    /** A message to the session in use (a new one is made when there is none). The creation can last minutes. */
    fun send(text: String): Outcome = act("/api/cloud/message", text, 15 * 60 * 1000)
    fun command(text: String): Outcome = act("/api/cloud/command", text, 3 * 60 * 1000)
    fun select(sessionOrNew: String): Outcome = act("/api/cloud/select", sessionOrNew)
    fun addSession(text: String): Outcome = act("/api/cloud/add", text, 60_000)
    fun clearSessions(): Outcome = act("/api/cloud/clear")
    fun rename(id: String, title: String): Outcome = act("/api/cloud/rename", JSONObject().put("id", id).put("title", title))
    /** The repository in use; its session is made now when it has none. */
    fun setRepo(textOrLink: String): Outcome = act("/api/repo", textOrLink, 30_000)
    /** One more session on a repository, made now. */
    fun newSession(repo: String): Outcome = act("/api/session/new", repo, 30_000)
    fun setModel(model: String?): Outcome = act("/api/model", model ?: "")
    fun setEffort(level: String?): Outcome = act("/api/effort", level ?: "")
    fun setPushMain(on: Boolean): Outcome = act("/api/options", JSONObject().put("push_main", on))
    fun resendInstructions(): Outcome = act("/api/instructions/resend")
    fun clearWaiting(): Outcome = act("/api/waiting/clear")
    fun testRelay(): Outcome = act("/api/waiting/test")
    fun retestRelay(): Outcome = act("/api/relay/retest", "", 3 * 60 * 1000)

    // ---------- what is joined to the next message ----------
    fun attach(name: String, base64: String): Outcome = act("/api/attach", JSONObject().put("name", name).put("data", base64), 5 * 60 * 1000)
    fun attachRemove(index: Int): Outcome = act("/api/attach/remove", JSONObject().put("index", index))
    fun attachClear(): Outcome = act("/api/attach/clear")

    // ---------- the questions of Claude ----------
    fun answerAsk(id: String, answer: String): Outcome = act("/api/ask/answer", JSONObject().put("id", id).put("answer", answer), 15 * 60 * 1000)

    // ---------- the super agent ----------
    fun agentAsk(text: String): Outcome = act("/api/agent/ask", JSONObject().put("text", text))
    fun agentReport(): Outcome = act("/api/agent/report")
    fun agentConfirm(id: String): Outcome = act("/api/agent/confirm", JSONObject().put("id", id), 15 * 60 * 1000)
    fun agentApply(id: String): Outcome = act("/api/agent/apply", JSONObject().put("id", id), 30_000)
    fun agentCancel(id: String): Outcome = act("/api/agent/cancel", JSONObject().put("id", id))
    fun agentSpoken(id: String): Outcome = act("/api/agent/said", JSONObject().put("id", id))
    fun agentStop(): Outcome = act("/api/agent/stop")
    fun agentVocabulary(words: Map<String, List<String>>): Outcome =
        act("/api/agent/vocabulary", JSONObject().put("words", JSONObject().also { w -> words.forEach { (k, v) -> w.put(k, JSONArray(v)) } }))

    /** A question put to the super agent, answered in sentences handed to `onSentence` as they are written. True when something was said. */
    fun answerStream(question: String, onSentence: (String) -> Unit): Boolean = streamed("/api/answer_stream", JSONObject().put("question", question), onSentence)

    /** One turn of the « création à la volée » mode: the sentences, and whether the phone has something to apply. */
    fun liveStream(text: String, onSentence: (String) -> Unit): Boolean = streamed("/api/live_stream", JSONObject().put("text", text), onSentence)

    private fun streamed(path: String, body: JSONObject, onSentence: (String) -> Unit): Boolean {
        var said = false
        try {
            net.stream(path, body.toString(), 3 * 60 * 1000) { line ->
                val j = try { JSONObject(line) } catch (e: Exception) { return@stream }
                val s = j.optString("s")
                if (s.isNotBlank()) { said = true; onSentence(s) }
            }
        } catch (e: Exception) { /* what was said stays said */ }
        return said
    }

    fun liveSet(on: Boolean): Outcome = act("/api/live/set", JSONObject().put("on", on))
    fun liveEvents(): List<String> = getJson("/api/live/events")?.optJSONArray("events").strings()

    /** The natural voice's sound for a text, or null (not installed yet, or an error: the phone's own voice then speaks). */
    fun say(text: String): ByteArray? = try { net.postBytes("/api/voice/say", JSONObject().put("text", text).toString()) } catch (e: Exception) { null }
    fun voiceSetup(): Outcome = act("/api/voice/setup")

    // ---------- the productions ----------
    fun files(repo: String? = null): Files? = getJson("/api/files" + (if (repo != null) "?repo=" + java.net.URLEncoder.encode(repo, "UTF-8") else ""))?.let { Files.parse(it) }
    fun fileDelete(repo: String, tag: String): Outcome = act("/api/files/delete", JSONObject().put("repo", repo).put("tag", tag))
    fun fileShare(repo: String, tag: String, file: String): ShareInfo? {
        val o = act("/api/files/share", JSONObject().put("repo", repo).put("tag", tag).put("file", file))
        return if (o.ok) ShareInfo(o.json.optString("title"), o.json.optString("url"), o.json.optString("kind"), o.json.optString("file")) else null
    }

    /** Where the brain serves a page production as a page (the app opens it in its own window). */
    fun pageAddress(repo: String, tag: String): String =
        HttpTransport.DEFAULT_BASE + "/api/files/page?repo=" + java.net.URLEncoder.encode(repo, "UTF-8") + "&tag=" + java.net.URLEncoder.encode(tag, "UTF-8")

    // ---------- the television ----------
    fun castWish(tv: String): Outcome = act("/api/cast/pending", JSONObject().put("tv", tv))
    fun castClear(): Outcome = act("/api/cast/clear")

    // ---------- the scenarios ----------
    fun scenarios(): List<Scenario>? = getJson("/api/scenarios")?.let { list(it) }
    private fun list(j: JSONObject) = j.optJSONArray("scenarios").objects().map { Scenario.parse(it) }
    fun scenarioSave(sc: Scenario): Outcome = act("/api/scenarios/save", sc.toJson())
    fun scenarioDelete(id: String): Outcome = act("/api/scenarios/delete", JSONObject().put("id", id))
    fun scenarioLaunch(id: String = "", text: String = ""): Outcome = act("/api/scenarios/launch", JSONObject().put("id", id).put("text", text), 60_000)
    fun scenarioCreate(id: String, fresh: Boolean): Outcome = act("/api/scenarios/create", JSONObject().put("id", id).put("fresh", fresh))
    fun scenarioUse(id: String, session: String): Outcome = act("/api/scenarios/use", JSONObject().put("id", id).put("session", session))
    fun scenarioSay(id: String, text: String): Outcome = act("/api/scenarios/say", JSONObject().put("id", id).put("text", text))
    fun scenarioSaid(id: String): List<ScenarioSay> = try {
        JSONObject(net.post("/api/scenarios/said", JSONObject().put("id", id).toString(), 10_000)).optJSONArray("says").objects()
            .map { ScenarioSay(it.optString("id"), it.optString("say"), it.optString("note"), it.optBoolean("do")) }
    } catch (e: Exception) { emptyList() }

    // ---------- the chamber ----------
    fun chamber(after: Long = 0): ChamberView? = try { ChamberView.parse(JSONObject(net.post("/api/chamber", JSONObject().put("after", after).toString(), 10_000))) } catch (e: Exception) { null }
    fun chamberCall(path: String, body: JSONObject, timeoutMs: Int = 120_000): JSONObject =
        try { JSONObject(net.post(path, body.toString(), timeoutMs)) } catch (e: Exception) { JSONObject().put("ok", false).put("error", e.message ?: "le cerveau ne répond pas") }
    fun chamberNote(): String = chamberCall("/api/chamber/note", JSONObject(), 10_000).optString("text")
    fun chamberSetNote(text: String): Outcome = act("/api/chamber/note", JSONObject().put("text", text))
    fun chamberOffer(id: String, open: Boolean): Outcome = act("/api/chamber/offer", JSONObject().put("id", id).put("do", if (open) "open" else "dismiss"))
    fun match(repo: String): Outcome = act("/api/match", JSONObject().put("repo", repo), 60_000)

    // ---------- the settings of the brain ----------
    fun style(): StyleView? = getJson("/api/style")?.let { StyleView(it.optBoolean("enabled"), it.optInt("count"), it.optBoolean("ready"), it.optString("note")) }
    fun styleSet(enabled: Boolean): Outcome = act("/api/style/set", JSONObject().put("enabled", enabled))
    fun styleClear(): Outcome = act("/api/style/clear")
    fun llmKey(key: String): Outcome = act("/api/llm/key", JSONObject().put("key", key), 60_000)
    fun llmClearKey(): Outcome = act("/api/llm/key", JSONObject().put("clear", true))
    fun llmCap(tokens: Long): Outcome = act("/api/llm/key", JSONObject().put("cap", tokens))
    fun githubToken(token: String): Outcome = act("/api/github/token", JSONObject().put("token", token))
    fun githubClearToken(): Outcome = act("/api/github/token", JSONObject().put("clear", true))
    // ---------- GitHub's login on the phone (device flow: a code to type once on github.com) ----------
    fun githubLoginStart(): Outcome = act("/api/github/login/start", "", 30_000)
    fun githubLoginState(): JSONObject? = getJson("/api/github/login")
    fun githubLoginCancel(): Outcome = act("/api/github/login/cancel")
    fun profileRepo(): String? = getJson("/api/profile")?.str("repo")
    fun setProfileRepo(repo: String): Outcome = act("/api/profile", JSONObject().put("repo", repo))
    fun profileCheck(): JSONObject? = getJson("/api/profile/check")
    fun publishProfilePub(pub: String): Outcome = act("/api/profile/pub", JSONObject().put("pub", pub))
    fun profilePub(repo: String): String? = getJson("/api/profile/pub?repo=" + java.net.URLEncoder.encode(repo, "UTF-8"))?.optString("pub")?.takeIf { it.length == 64 }

    // ---------- the studio: the free stock clips and « Film de moi » ----------
    fun stockStatus(): JSONObject? = getJson("/api/stock/status")
    fun stockKey(source: String, key: String): Outcome = act("/api/stock/key", JSONObject().put("source", source).put("key", key))
    fun stockKeyClear(source: String): Outcome = act("/api/stock/key_clear", JSONObject().put("source", source))
    fun stockSearch(query: String, source: String): Outcome = act("/api/stock/search", JSONObject().put("query", query).put("source", source), 60_000)
    fun stockDownload(clip: JSONObject): Outcome = act("/api/stock/download", JSONObject().put("clip", clip), 5 * 60_000)
    fun stockPublish(id: String): Outcome = act("/api/stock/publish", JSONObject().put("id", id))
    fun filmStatus(): JSONObject? = getJson("/api/film/status")
    fun filmInfo(): JSONObject? = getJson("/api/film/info")
    fun filmGet(id: String): JSONObject? = getJson("/api/film/get?id=" + java.net.URLEncoder.encode(id, "UTF-8"))
    fun filmKey(key: String): Outcome = act("/api/film/key", JSONObject().put("key", key))
    fun filmKeyClear(): Outcome = act("/api/film/key_clear")
    fun filmCap(usd: Double): Outcome = act("/api/film/cap", JSONObject().put("cap", usd))
    fun filmVoice(base64: String, ext: String): Outcome = act("/api/film/voice", JSONObject().put("data", base64).put("ext", ext), 60_000)
    fun filmPrepare(direction: String, says: String, aspect: String, photos: List<String>, consent: Boolean, kind: String, photosProduct: List<String>, swap: String): Outcome =
        act("/api/film/prepare", JSONObject().put("direction", direction).put("says", says).put("aspect", aspect).put("photos", JSONArray(photos)).put("consent", consent).put("kind", kind)
            .put("photos_product", JSONArray(photosProduct)).put("swap", swap), 5 * 60_000)
    fun filmSource(id: String, input: java.io.InputStream, length: Long): Outcome = try {
        val j = JSONObject(net.upload("/api/film/source?id=" + java.net.URLEncoder.encode(id, "UTF-8"), input, length))
        Outcome(j.optBoolean("ok"), if (j.optBoolean("ok")) null else j.optString("error").ifBlank { "refusé" }, j)
    } catch (e: Exception) { Outcome(false, e.message ?: "le cerveau ne répond pas") }
    fun filmEdit(id: String, index: Int, situation: String?, says: String?, remove: Boolean = false): Outcome =
        act("/api/film/edit", JSONObject().put("id", id).put("index", index).put("situation", situation ?: JSONObject.NULL).put("says", says ?: JSONObject.NULL).put("remove", remove))
    fun filmStart(id: String): Outcome = act("/api/film/start", JSONObject().put("id", id).put("confirmed", true))
    fun filmPublish(id: String): Outcome = act("/api/film/publish", JSONObject().put("id", id))
    /** Where the brain serves a finished film (the player seeks in it). */
    fun filmAddress(id: String): String = HttpTransport.DEFAULT_BASE + "/api/film/file/" + id + ".mp4"

    // ---------- Claude's login on the phone ----------
    fun loginState(): JSONObject? = getJson("/api/claude/login")
    fun loginStart(): Outcome = act("/api/claude/login/start", "", 60_000)
    fun loginCode(code: String): Outcome = act("/api/claude/login/code", code, 60_000)
    fun loginCancel(): Outcome = act("/api/claude/login/cancel")
    fun loginCheck(): Outcome = act("/api/claude/check", "", 60_000)
}
