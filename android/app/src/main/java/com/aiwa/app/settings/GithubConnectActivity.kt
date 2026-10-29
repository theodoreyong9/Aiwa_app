package com.aiwa.app.settings

import android.os.Bundle
import android.view.Gravity
import android.widget.TextView
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.copyToClipboard
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * « Connecter GitHub », the way the first Aiwa did it: GitHub's device flow. A short code is shown, the person types it ONCE on github.com (the page opens by itself, the code is copied), and the brain
 * waits for GitHub to hand the access over: nothing to create, nothing to paste. Connected, Aiwa lists ALL her repositories (the private ones too) and can delete a production.
 * The window also opens by itself, once, at the first opening of the application.
 */
class GithubConnectActivity : FloatActivity() {
    override val title = "Connecter GitHub"
    private var step: JSONObject? = null
    private var error: String? = null
    private var busy = false
    private var watching = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.IO).launch {
            ensureBrain(applicationContext); BrainSync.refresh()
            // a login already waiting for its code (the window was closed and opened again) is the one to go on with
            val running = Aiwa.brain.githubLoginState()
            withContext(Dispatchers.Main) { if (running != null && running.optString("phase") == "code") { step = running; watch() }; reload() }
        }
    }

    private fun begin() {
        busy = true; error = null; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.githubLoginStart() }
            busy = false
            if (!out.ok) { error = out.error ?: "refusé"; reload(); return@launch }
            step = out.json
            val code = out.json.optString("user_code")
            copyToClipboard(this@GithubConnectActivity, code)
            openUrl(this@GithubConnectActivity, out.json.optString("uri"))
            watch()
            reload()
        }
    }

    /** The brain waits for GitHub; this only looks at its answer every few seconds, until it is done or has failed. */
    private fun watch() {
        if (watching) return
        watching = true
        CoroutineScope(Dispatchers.Main).launch {
            while (!isDestroyed) {
                delay(3000)
                val now = withContext(Dispatchers.IO) { Aiwa.brain.githubLoginState() } ?: continue
                when (now.optString("phase")) {
                    "done" -> {
                        withContext(Dispatchers.IO) { BrainSync.refresh() }
                        toastOnMain(applicationContext, "GitHub connecté")
                        step = null; watching = false; reload(); return@launch
                    }
                    "failed" -> { error = now.optString("message").ifEmpty { "La connexion n'a pas abouti." }; step = null; watching = false; reload(); return@launch }
                    "idle" -> { step = null; watching = false; reload(); return@launch }
                }
            }
            watching = false
        }
    }

    private fun disconnect() {
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { Aiwa.brain.githubClearToken(); BrainSync.refresh() }
            step = null; error = null; reload()
        }
    }

    override fun fill() {
        val status = Aiwa.state.value.status
        if (status?.githubToken == true) {
            note(if (status.githubUser != null) "✓ Connecté : ${status.githubUser}" else "✓ Connecté.", Palette.GREEN)
            note("Aiwa liste tous tes dépôts, privés compris, et peut supprimer une production.")
            entry("Déconnecter", "Oublie l'accès sur ce téléphone.") { disconnect() }
            return
        }
        val code = step?.optString("user_code").orEmpty()
        if (code.isNotEmpty()) {
            note("GitHub s'est ouvert. Tape ce code (il est déjà copié : colle-le) puis touche « Authorize ». Cette fenêtre se ferme toute seule.", Palette.TEXT)
            add(TextView(this).apply { text = code; textSize = 34f; setTextColor(Palette.GOLD); gravity = Gravity.CENTER; setPadding(0, 16, 0, 16); setTypeface(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD) })
            entry("Rouvrir GitHub", "Copie le code et ouvre la page") { copyToClipboard(this, code); openUrl(this, step?.optString("uri").orEmpty()) }
            return
        }
        note("Aujourd'hui Aiwa ne voit que tes dépôts publics. Connecte ton compte GitHub pour voir tous tes dépôts, privés compris, et pouvoir supprimer une production.", Palette.TEXT)
        entry(if (busy) "Un instant…" else "Connecter avec GitHub", "Un code à taper une fois sur github.com") { if (!busy) begin() }
        error?.let { note(it, Palette.RED) }
        entry("Plus tard") { finish() }
    }
}
