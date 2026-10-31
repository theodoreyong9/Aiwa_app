package com.aiwa.client

import org.json.JSONArray
import org.json.JSONObject

internal fun JSONObject.str(key: String): String? = if (isNull(key) || !has(key)) null else optString(key).takeIf { it.isNotEmpty() }
internal fun JSONObject.long(key: String): Long? = if (isNull(key) || !has(key)) null else optDouble(key).toLong()
internal fun JSONObject.obj(key: String): JSONObject? = if (isNull(key)) null else optJSONObject(key)
internal fun JSONArray?.objects(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }
internal fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).map { optString(it) }

/** A question Claude asked through the widget. */
data class Ask(val id: String, val question: String, val options: List<String>, val session: String?, val count: Int)

/** What the super agent wants to say, to send, to change. */
data class Say(val id: String, val text: String)
data class Target(val session: String?, val repo: String?, val message: String)
data class Proposal(val id: String, val targets: List<Target>, val readBack: String)
data class Command(val id: String, val readBack: String, val open: String?, val castTv: String?, val castWait: Boolean, val cast: Boolean, val auto: Boolean)
data class AgentView(val busy: Boolean, val error: String?, val say: Say?, val proposal: Proposal?, val command: Command?, val voice: String?, val llm: String?)

data class CastReady(val tv: String, val name: String, val url: String)
data class ChamberBrief(val active: Boolean, val peer: String?, val name: String?)
/** How many questions GitHub still allows, and whether they are asked as the person's own account. */
data class GithubRate(val limit: Long, val remaining: Long, val account: Boolean)
data class LlmView(val state: String, val used: Long, val cap: Long)

/** Everything the widget shows, from one `/api/status`. */
data class Status(
    val version: Int, val sending: Boolean, val sendingSince: Long?, val sendingNote: String?, val model: String?, val effort: String?,
    val session: String?, val lastSession: String?, val repo: String?, val pushMain: Boolean, val waiting: Boolean, val attachments: Int, val attachmentFiles: List<String>,
    val selfUpdate: String?, val silenceMinutes: Int, val cast: CastReady?, val githubError: String?, val repoAccessMissing: String?, val githubAppUrl: String?,
    val githubToken: Boolean, val claudeLogin: String, val relayCloud: String, val ask: Ask?, val agent: AgentView, val chamber: ChamberBrief, val llm: LlmView, val voice: String?, val profile: String?,
    val githubUser: String? = null, val sessionError: String? = null, val lastSend: String? = null,
    val githubRate: GithubRate? = null,
    val diagramOn: Boolean = false, val diagramId: Long = 0, val diagramCode: String = "",
) {
    companion object {
        fun parse(o: JSONObject): Status = Status(
            version = o.optInt("version"), sending = o.optBoolean("sending"), sendingSince = o.long("sending_since"), sendingNote = o.str("sending_note"), model = o.str("model"), effort = o.str("effort"),
            session = o.str("cloud_session"), lastSession = o.str("last_session"), repo = o.str("repo"), pushMain = o.optBoolean("push_main", true), waiting = o.optBoolean("waiting"),
            attachments = o.optInt("attachments"), attachmentFiles = o.optJSONArray("attachment_files").objects().map { it.optString("name") },
            selfUpdate = o.obj("self_update")?.str("result"), silenceMinutes = o.optInt("silence_minutes"),
            cast = o.obj("cast")?.let { CastReady(it.optString("tv"), it.optString("name"), it.optString("url")) },
            githubError = o.str("github_error"), repoAccessMissing = o.str("repo_access_missing"), githubAppUrl = o.str("github_app_url"), githubToken = o.optBoolean("github_token"),
            claudeLogin = o.optString("claude_login", "unknown"), relayCloud = o.optString("relay_cloud", "untested"),
            ask = o.obj("ask")?.let { a -> Ask(a.optString("id"), a.optString("question"), a.optJSONArray("options").strings(), a.str("session"), a.optInt("count", 1)) },
            agent = parseAgent(o.obj("agent")),
            chamber = o.obj("chamber")?.let { ChamberBrief(it.optBoolean("active"), it.str("peer"), it.str("name")) } ?: ChamberBrief(false, null, null),
            llm = o.obj("llm")?.let { LlmView(it.optString("state", "none"), it.optLong("used"), it.optLong("cap")) } ?: LlmView("none", 0, 0),
            voice = o.str("voice"), profile = o.str("profile"), githubUser = o.str("github_user"), sessionError = o.str("session_error"), lastSend = o.obj("last_send")?.let { l -> (if (l.optBoolean("ok")) "parti" else "ÉCHEC : " + l.optString("error")) + " (" + l.optDouble("seconds") + " s, il y a " + ((System.currentTimeMillis() / 1000 - l.optLong("at")) / 60) + " min)" }, diagramOn = o.obj("diagram")?.optBoolean("on") ?: false, diagramId = o.obj("diagram")?.optLong("id") ?: 0, diagramCode = o.obj("diagram")?.optString("code").orEmpty(), githubRate = o.obj("github_rate")?.let { GithubRate(it.optLong("limit"), it.optLong("remaining"), it.optBoolean("account")) },
        )

        fun parseAgent(a: JSONObject?): AgentView {
            if (a == null) return AgentView(false, null, null, null, null, null, null)
            val say = a.obj("say")?.let { Say(it.optString("id"), it.optString("text")) }
            val proposal = a.obj("proposal")?.let { p ->
                val first = Target(p.str("session"), p.str("repo"), p.optString("message"))
                Proposal(p.optString("id"), listOf(first) + p.optJSONArray("more").objects().map { Target(it.str("session"), it.str("repo"), it.optString("message")) }, p.optString("read_back"))
            }
            val command = a.obj("command")?.let { c ->
                val cast = c.obj("cast")
                Command(c.optString("id"), c.optString("read_back"), c.str("open"), cast?.str("tv"), cast?.optBoolean("wait") == true, cast != null, c.optBoolean("auto"))
            }
            return AgentView(a.optBoolean("busy"), a.str("error"), say, proposal, command, a.str("voice"), a.str("llm"))
        }
    }
}

/** One production: a file of a release. `kind` is docs / image / video / app / page. */
data class Production(val repo: String, val kind: String, val tag: String, val title: String, val file: String, val size: Long, val url: String, val ts: Long) {
    val repoName: String get() = repo.substringAfter('/')
}

data class Files(val repo: String?, val repos: List<String>, val error: String?, val items: Map<String, List<Production>>) {
    companion object {
        fun parse(o: JSONObject): Files {
            val items = LinkedHashMap<String, List<Production>>()
            val by = o.obj("items")
            for (kind in KINDS) {
                items[kind] = by?.optJSONArray(kind).objects().map {
                    Production(it.optString("repo"), kind, it.optString("tag"), it.optString("title"), it.optString("file"), it.optLong("size"), it.optString("url"), it.optLong("ts"))
                }
            }
            return Files(o.str("repo"), o.optJSONArray("repos").strings(), o.str("error"), items)
        }
        val KINDS = listOf("docs", "image", "video", "app", "page")
    }
}

data class ShareInfo(val title: String, val url: String, val kind: String, val file: String)

data class ScenarioWord(val word: String, val does: String)
data class Scenario(
    val id: String, val name: String, val word: String, val kind: String, val prompt: String, val speak: String, val words: List<ScenarioWord>,
    val session: String? = null, val creating: Boolean = false, val error: String? = null,
    val sessions: List<ScenarioSession> = emptyList(), val repo: String? = null, val watching: Boolean = false, val turns: Int = 0,
) {
    fun toJson(): JSONObject = JSONObject().put("id", id).put("name", name).put("word", word).put("kind", kind).put("prompt", prompt).put("speak", speak)
        .put("words", JSONArray(words.map { JSONObject().put("word", it.word).put("does", it.does) }))

    companion object {
        fun parse(o: JSONObject) = Scenario(
            o.optString("id"), o.optString("name"), o.optString("word"), o.optString("kind", "double"), o.optString("prompt"), o.optString("speak"),
            o.optJSONArray("words").objects().map { ScenarioWord(it.optString("word"), it.optString("does")) }, o.str("session"), o.optBoolean("creating"), o.str("error"),
            o.optJSONArray("sessions").objects().map { ScenarioSession(it.optString("id"), it.optString("title"), it.optBoolean("current")) }, o.str("repo"), o.optBoolean("watching"), o.optInt("turns"),
        )
    }
}

/** One of the sessions a scenario's double has had (the current one is flagged). */
data class ScenarioSession(val id: String, val title: String, val current: Boolean)

data class ScenarioSay(val id: String, val say: String, val note: String, val screen: Boolean)

data class ChamberLine(val n: Long, val who: String, val name: String, val kind: String, val text: String)
data class Offer(val id: String, val from: String, val text: String, val kind: String, val title: String, val url: String)
data class ChamberView(val active: Boolean, val peer: String?, val name: String?, val lines: List<ChamberLine>, val offers: List<Offer>) {
    companion object {
        fun parse(o: JSONObject) = ChamberView(
            o.optBoolean("active"), o.str("peer"), o.str("name"),
            o.optJSONArray("lines").objects().map { ChamberLine(it.optLong("n"), it.optString("who"), it.optString("name"), it.optString("kind", "say"), it.optString("text")) },
            o.optJSONArray("offers").objects().mapNotNull { x ->
                val a = x.obj("attach") ?: return@mapNotNull null
                Offer(x.optString("id"), x.optString("from"), x.optString("text"), a.optString("kind"), a.optString("title"), a.optString("url"))
            },
        )
    }
}

data class Session(val id: String, val title: String, val repo: String?, val url: String?) {
    companion object { fun parse(o: JSONObject) = Session(o.optString("id"), o.optString("title").ifBlank { o.optString("id") }, o.str("repo"), o.str("url")) }
}

data class StyleView(val enabled: Boolean, val count: Int, val ready: Boolean, val note: String)
