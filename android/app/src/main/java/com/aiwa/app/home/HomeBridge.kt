package com.aiwa.app.home

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.webkit.WebResourceRequest
import android.webkit.WebView
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.Link
import com.aiwa.app.brain.hasTermuxPermission
import com.aiwa.app.cast.CastActivity
import com.aiwa.app.chamber.ChamberActions
import com.aiwa.app.chamber.ChamberPressActivity
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.files.FilesActivity
import com.aiwa.app.question.AskActivity
import com.aiwa.app.scenario.ScenariosActivity
import com.aiwa.app.settings.SettingsActivity
import com.aiwa.app.update.InstallUpdateActivity
import com.aiwa.app.voice.AgentToggleActivity
import com.aiwa.app.voice.EarToggleActivity
import com.aiwa.app.web.WebActivity
import com.aiwa.app.widget.AddActivity
import com.aiwa.app.widget.CellModels
import com.aiwa.app.widget.OpenClaudeActivity
import com.aiwa.app.widget.ReportActivity
import com.aiwa.client.Scenario
import com.aiwa.client.ScenarioWord
import org.json.JSONObject

/**
 * The home page and the page of a profile (`Profile/index.html`) are the SAME kind of page: it draws what it wants, and wherever it puts a slot (`data-aiwa-slot="build"`, `data-aiwa-button="docs"`) the
 * application puts ITS buttons, the widget's buttons (web/home/aiwa-home.js does the drawing). The buttons act on the account of whoever looks: on the page of someone else, the design and everything
 * written in the page are hers, and the buttons of the slots are still the visitor's. A press reaches the phone by ONE channel, a web message listener (never a Java object, which every frame would
 * see), and only a press of the main frame counts. The pages of the others run no script of their own (see lockScripts); the runtime is put in by the application, outside of the page's reach.
 */
object HomeRuntime {
    private var cached: String? = null

    /** The runtime, read once from the assets. */
    fun script(context: Context): String {
        cached?.let { return it }
        val text = try { context.assets.open("web/home/aiwa-home.js").use { String(it.readBytes(), Charsets.UTF_8) } } catch (err: Exception) { "" }
        cached = text
        return text
    }

    /** The home of the application, for the person who has no profile page yet: every button, and a word that says how to make her own (the page replaces __WORD__). */
    fun defaultPage(context: Context): String = try { context.assets.open("web/home/default.html").use { String(it.readBytes(), Charsets.UTF_8) } } catch (err: Exception) { "" }

    /**
     * The channel from the page to the phone: a message {"cmd":"press","id":"docs"} or {"cmd":"scenario","scenario":{…}} (a scenario of the page, launched in the account of whoever looks).
     * `own`: the page is the person's own; `source` says whose page it is (a repository « owner/name »).
     */
    fun attach(web: WebView, own: Boolean, source: () -> String?) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) return
        try {
            WebViewCompat.addWebMessageListener(web, "AiwaHomeHost", setOf("*")) { _, message: WebMessageCompat, _, isMainFrame, _ ->
                if (!isMainFrame) return@addWebMessageListener
                val json = try { JSONObject(message.data ?: return@addWebMessageListener) } catch (err: Exception) { return@addWebMessageListener }
                when (json.optString("cmd")) {
                    "press" -> HomeActions.press(web.context, json.optString("id"), source(), own)
                    "scenario" -> json.optJSONObject("scenario")?.let { HomeActions.scenario(web.context, it, source(), own) }
                }
            }
        } catch (err: Exception) { /* a second attach on the same view */ }
    }

    /** Puts the runtime in the page (once it is loaded) and tells it what the buttons show now. */
    fun inject(web: WebView) {
        val code = script(web.context)
        if (code.isEmpty()) return
        web.evaluateJavascript(code, null)
        pushState(web)
        pump(web)
    }

    fun pushState(web: WebView) {
        val json = try { HomeActions.state(web.context).toString() } catch (err: Exception) { "{}" }
        web.evaluateJavascript("(window.aiwa&&window.aiwa.setState)&&window.aiwa.setState($json)", null)
    }

    /** What the buttons show (the agent listening, the repository, the chamber…) is sent again every few seconds, while the page is on the screen. */
    private fun pump(web: WebView) {
        if (web.getTag(com.aiwa.app.R.id.home_pump) == true) return
        web.setTag(com.aiwa.app.R.id.home_pump, true)
        val tick = object : Runnable {
            override fun run() {
                if (web.getTag(com.aiwa.app.R.id.home_pump) != true) return
                if (web.isAttachedToWindow) pushState(web)
                web.postDelayed(this, 2500)
            }
        }
        web.postDelayed(tick, 2500)
    }

    /** To be called when the view is let go: the pump stops. */
    fun release(web: WebView) { web.setTag(com.aiwa.app.R.id.home_pump, false) }

    /** Opens the widget over the page (the « Widget » button of the visitor's bar, or of the page). */
    fun openPanel(web: WebView) { web.evaluateJavascript("(window.aiwa&&window.aiwa.panel)&&window.aiwa.panel()", null) }

    /**
     * The page of someone else: its scripts, its frames and its plugins are forbidden (a policy put first in the page, which the page cannot remove), so that only the design and the words of the page count
     * and a page cannot press a button, read the state of the visitor or send anything out. The runtime of the application is not under this rule (a script run by the application itself).
     */
    fun lockScripts(html: String): String {
        val policy = "<meta http-equiv=\"Content-Security-Policy\" content=\"script-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'\">"
        val head = Regex("<head[^>]*>", RegexOption.IGNORE_CASE).find(html)
        if (head != null) return html.substring(0, head.range.last + 1) + policy + html.substring(head.range.last + 1)
        val root = Regex("<html[^>]*>", RegexOption.IGNORE_CASE).find(html)
        if (root != null) return html.substring(0, root.range.last + 1) + "<head>" + policy + "</head>" + html.substring(root.range.last + 1)
        val doctype = Regex("<!doctype[^>]*>", RegexOption.IGNORE_CASE).find(html)
        if (doctype != null) return html.substring(0, doctype.range.last + 1) + policy + html.substring(doctype.range.last + 1)
        return policy + html
    }

    /** What a page may open: only https, mail, phone and message links leave for the app that handles them. */
    fun openExternal(context: Context, request: WebResourceRequest): Boolean {
        if (request.url.scheme in setOf("https", "mailto", "tel", "sms")) try { context.startActivity(Intent(Intent.ACTION_VIEW, request.url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (err: Exception) { }
        return true
    }
}

/** What each button of the catalogue does (the same as the widget's cell, same windows) and what it shows now. */
object HomeActions {
    private fun go(context: Context, cls: Class<*>) { context.startActivity(Intent(context, cls).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    private fun go(context: Context, intent: Intent) { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }

    fun press(context: Context, id: String, source: String? = null, own: Boolean = true) {
        val snap = Aiwa.state.value
        when (id) {
            "agent" -> when {
                snap.link == Link.MISSING -> go(context, com.aiwa.app.brain.InstallHelpActivity::class.java)
                !hasTermuxPermission(context) -> go(context, com.aiwa.app.brain.SetupActivity::class.java)
                else -> go(context, AgentToggleActivity::class.java)
            }
            "listen" -> go(context, EarToggleActivity::class.java)
            "plus" -> go(context, AddActivity::class.java)
            "claude" -> if (snap.sessionId != null || snap.status?.lastSession != null) go(context, OpenClaudeActivity::class.java) else toastOnMain(context, "Pas de session Claude pour l'instant.")
            "report" -> go(context, ReportActivity::class.java)
            "docs", "image", "video", "app", "page" -> go(context, Intent(context, FilesActivity::class.java).putExtra(FilesActivity.EXTRA_KIND, id))
            "scenario" -> go(context, ScenariosActivity::class.java)
            "cast" -> go(context, CastActivity::class.java)
            "nearby" -> go(context, voir(context, "proche")); "link" -> go(context, voir(context, "lien")); "qr" -> go(context, voir(context, "qr")); "favorites" -> go(context, voir(context, "favoris"))
            "room" -> if (own) go(context, com.aiwa.app.chamber.ChamberActivity::class.java) else ChamberActions.visit(context, source)
            "roomtalk", "roomear", "roomcreate", "roomnote" -> go(context, Intent(context, ChamberPressActivity::class.java).putExtra(ChamberPressActivity.EXTRA_ID, id))
            "update" -> go(context, InstallUpdateActivity::class.java)
            "question" -> go(context, AskActivity::class.java)
            "settings" -> go(context, SettingsActivity::class.java)
            "wallet" -> WebActivity.wallet(context)
        }
    }

    private fun voir(context: Context, mode: String) = Intent(context, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode)

    /**
     * A scenario of a profile page (`Profile/scenarios.json`), launched in OUR environment: it is saved among the scenarios of the person and started (the brain makes its session: a double of her). A scenario
     * can write to her sessions and ask her phone for things, so the one that comes from someone else's page is shown whole and only runs after she says yes.
     */
    fun scenario(context: Context, raw: JSONObject, source: String?, own: Boolean) {
        val name = raw.optString("name").trim().take(40)
        val prompt = raw.optString("prompt").trim().take(1500)
        if (name.isEmpty()) return
        val run = { Thread { runScenario(context.applicationContext, raw, name, prompt, source, own) }.start() }
        if (own) { run(); return }
        val activity = context as? Activity
        if (activity == null) { toastOnMain(context, "Ouvre le profil dans Aiwa pour lancer ce scénario."); return }
        activity.runOnUiThread {
            AlertDialog.Builder(activity)
                .setTitle("Lancer « $name » ?")
                .setMessage("Ce scénario vient du profil de ${source ?: "quelqu'un d'autre"}. Une fois lancé, il agit comme un double de toi : une session à lui, qui peut écrire à tes sessions et demander des choses à ton téléphone. Voici sa consigne :\n\n$prompt")
                .setPositiveButton("Lancer") { _, _ -> run() }
                .setNegativeButton("Annuler", null)
                .show()
        }
    }

    private fun runScenario(app: Context, raw: JSONObject, name: String, prompt: String, source: String?, own: Boolean) {
        val base = raw.optString("id").ifBlank { name }
        val id = (if (own) base else "p-" + (source ?: "x") + "-" + base).lowercase().replace(Regex("[^a-z0-9-]"), "-").take(30)
        val list = raw.optJSONArray("words")
        val words = if (list == null) emptyList() else (0 until minOf(list.length(), 8)).mapNotNull {
            val w = list.optJSONObject(it) ?: return@mapNotNull null
            ScenarioWord(w.optString("word"), w.optString("does"))
        }
        val kind = if (raw.optString("kind") == "report") "report" else "double"
        val scenario = Scenario(id, name, raw.optString("word").trim(), kind, prompt, raw.optString("speak").trim(), words)
        val saved = Aiwa.brain.scenarioSave(scenario)
        if (!saved.ok) { toastOnMain(app, saved.error ?: "Scénario refusé."); return }
        val launched = Aiwa.brain.scenarioLaunch(id = id)
        toastOnMain(app, if (launched.ok) "Scénario « $name » lancé." else "Scénario « $name » ajouté, mais il ne démarre pas.")
    }

    /** What the buttons show now, by id of button: the same words and tones as the cells of the widget. */
    fun state(context: Context): JSONObject {
        val out = JSONObject()
        for ((id, cell) in CellModels.of(context, Aiwa.state.value)) {
            out.put(id, JSONObject().put("label", cell.label).put("tone", cell.tone).put("on", cell.on).put("found", cell.enabled))
        }
        return out
    }
}
