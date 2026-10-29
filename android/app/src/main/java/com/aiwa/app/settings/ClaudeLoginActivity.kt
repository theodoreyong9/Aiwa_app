package com.aiwa.app.settings

import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.clipboardText
import com.aiwa.app.common.copyToClipboard
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.widget.AiwaWidget
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * « Connecter Claude »: logs the CLI in to a Claude account without opening Termux. The brain runs `claude auth login` and hands over the page it prints; this window opens it in the browser, where the
 * person approves, and the page shows a CODE (the redirect goes to platform.claude.com, not to the phone). The code is taken from the clipboard when the person comes back — and submitted at once when it
 * is the one this login expects (it ends with the login's own `state`) — or pasted by hand.
 */
class ClaudeLoginActivity : FloatActivity() {
    override val title = "Connecter Claude"
    private var step: JSONObject? = null
    private var busy = true
    private var connected = false
    private var note: String? = null
    private var baseline: String? = null
    private lateinit var code: EditText
    private var typed = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { ensureBrain(applicationContext) }
            val check = withContext(Dispatchers.IO) { Aiwa.brain.loginCheck().json.optString("claude_login", "unknown") }
            if (check == "ok") { connectedNow(); return@launch }
            // Back from the browser through the recent apps, or a second tap on the widget: the login that is waiting for its code is the one to go on with, not a new one.
            val running = withContext(Dispatchers.IO) { Aiwa.brain.loginState() }
            if (running != null && running.optString("phase") == "url" && running.optString("url").isNotEmpty()) { step = running; busy = false; reload() } else begin()
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        val current = step ?: return
        if (!hasFocus || current.optString("phase") != "url" || busy) return
        val text = clipboardText(this)?.trim() ?: return
        if (text == baseline || text == typed || !looksLikeCode(text)) return
        typed = text
        if (::code.isInitialized) code.setText(text)
        val state = Uri.parse(current.optString("url")).getQueryParameter("state")
        if (state != null && text.endsWith("#$state")) submit()
    }

    override fun onDestroy() {
        // Closing the window ends a login still waiting for its code.
        if (isFinishing && !connected) CoroutineScope(Dispatchers.IO).launch { try { Aiwa.brain.loginCancel() } catch (err: Exception) { } }
        super.onDestroy()
    }

    private fun looksLikeCode(text: String) = text.length in 20..2000 && text.none { it.isWhitespace() } && !text.startsWith("http")

    private fun friendly(message: String): String =
        if (message.contains("400") || message.contains("invalid", ignoreCase = true) || message.contains("expired", ignoreCase = true)) "Code refusé ou expiré (le CLI dit : $message). Touche « Recommencer » pour une nouvelle page." else message

    private suspend fun connectedNow() {
        connected = true; busy = false
        reload()
        withContext(Dispatchers.IO) { BrainSync.refresh() }
        AiwaWidget.render(applicationContext, force = true)
        delay(1200)
        finish()
    }

    private fun begin() {
        busy = true; note = null; typed = ""; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val next = withContext(Dispatchers.IO) { Aiwa.brain.loginStart().json }
            step = next
            busy = false
            val url = next.optString("url")
            if (next.optString("phase") == "url" && url.isNotEmpty()) {
                baseline = clipboardText(this@ClaudeLoginActivity)
                if (!openUrl(this@ClaudeLoginActivity, url)) note = "Aucun navigateur pour ouvrir la page : touche « Copier le lien » et ouvre-la toi-même."
            }
            reload()
        }
    }

    private fun submit() {
        if (busy) return
        busy = true; note = null; reload()
        val sent = typed.trim()
        CoroutineScope(Dispatchers.Main).launch {
            val next = withContext(Dispatchers.IO) { Aiwa.brain.loginCode(sent).json }
            step = next
            busy = false
            if (next.optString("phase") == "done") connectedNow() else { if (next.optString("message").isNotEmpty()) note = friendly(next.optString("message")); reload() }
        }
    }

    override fun fill() {
        val current = step
        when {
            connected -> note("✓ Claude est connecté. Cette fenêtre se ferme.", Palette.GREEN)
            current == null -> note("Préparation de la connexion…")
            current.optString("phase") == "url" || current.optString("phase") == "checking" -> {
                note("1. Une page s'est ouverte : connecte-toi à Claude et appuie sur « Autoriser ».\n2. Copie le code qu'elle affiche.\n3. Reviens ici : le code est repris tout seul (sinon, colle-le ci-dessous).", Palette.TEXT)
                val url = current.optString("url")
                entry("Rouvrir la page") { openUrl(this, url) }
                entry("Copier le lien") { copyToClipboard(this, url); toastOnMain(this, "Lien copié") }
                code = EditText(this).apply {
                    hint = "Code affiché par la page"; setText(typed); setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
                    inputType = InputType.TYPE_CLASS_TEXT; setSingleLine(); isEnabled = !busy
                    addTextChangedListener(object : android.text.TextWatcher {
                        override fun afterTextChanged(s: android.text.Editable?) { typed = s?.toString().orEmpty() }
                        override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
                        override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) {}
                    })
                }
                add(code)
                entry("Coller") { clipboardText(this)?.trim()?.let { typed = it; code.setText(it) } }
                entry(if (busy) "Vérification…" else "Valider") { if (typed.isNotBlank()) submit() }
                note?.let { note(it, Palette.RED) }
            }
            else -> {
                note(note ?: current.optString("message").ifEmpty { "La connexion n'a pas abouti." }, Palette.RED)
                entry("Recommencer") { begin() }
            }
        }
    }
}
