package com.aiwa.app.settings

import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.clipboardText
import com.aiwa.app.common.openUrl
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * « Connecter GitHub »: the person's GitHub account, through a personal token (GitHub gives one on a page opened from here, with the right already ticked). Connected, Aiwa lists ALL her repositories
 * (the private ones too) and can delete a production. The token stays on the phone; GitHub refuses a wrong one at once. The window also opens by itself, once, at the first opening of the application.
 */
class GithubConnectActivity : FloatActivity() {
    override val title = "Connecter GitHub"
    private var busy = false
    private var message: String? = null
    private var typed = ""
    private var field: EditText? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CoroutineScope(Dispatchers.IO).launch { ensureBrain(applicationContext); BrainSync.refresh(); withContext(Dispatchers.Main) { reload() } }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus || busy || Aiwa.state.value.status?.githubUser != null) return
        // back from the page that made the token: it is in the clipboard
        val text = clipboardText(this)?.trim() ?: return
        if (Regex("(ghp_|github_pat_)[A-Za-z0-9_]{20,}").matches(text) && text != typed) { typed = text; field?.setText(text); connect(text) }
    }

    private fun connect(token: String) {
        busy = true; message = null; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { val o = Aiwa.brain.githubToken(token); BrainSync.refresh(); o }
            busy = false
            if (!out.ok) message = out.error ?: "refusé" else toastOnMain(applicationContext, "GitHub connecté")
            reload()
        }
    }

    private fun disconnect() {
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { Aiwa.brain.githubClearToken(); BrainSync.refresh() }
            typed = ""; message = null; reload()
        }
    }

    override fun fill() {
        val status = Aiwa.state.value.status
        val user = status?.githubUser
        if (status?.githubToken == true) {
            note(if (user != null) "✓ Connecté : $user" else "✓ Jeton en place.", Palette.GREEN)
            note("Aiwa liste tous tes dépôts, privés compris, et peut supprimer une production.")
            entry("Déconnecter", "Oublie le jeton sur ce téléphone.") { disconnect() }
            return
        }
        note("Aujourd'hui Aiwa ne voit que tes dépôts publics. Connecte ton compte GitHub pour voir tous tes dépôts, privés compris, et pouvoir supprimer une production.", Palette.TEXT)
        note("1. Touche « Créer le jeton » : GitHub s'ouvre avec le bon droit déjà coché. Connecte-toi, descends, touche « Generate token », puis copie le jeton.\n2. Reviens ici : le jeton est repris tout seul (sinon colle-le ci-dessous).")
        entry("Créer le jeton", "Ouvre github.com") { openUrl(this, "https://github.com/settings/tokens/new?scopes=repo&description=Aiwa") }
        val box = EditText(this).apply {
            hint = "ghp_… ou github_pat_…"; setText(typed); setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0"))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD; setSingleLine(); isEnabled = !busy
            addTextChangedListener(object : android.text.TextWatcher {
                override fun afterTextChanged(s: android.text.Editable?) { typed = s?.toString().orEmpty() }
                override fun beforeTextChanged(s: CharSequence?, st: Int, c: Int, a: Int) {}
                override fun onTextChanged(s: CharSequence?, st: Int, b: Int, c: Int) {}
            })
        }
        field = box
        add(box)
        entry("Coller") { clipboardText(this)?.trim()?.let { typed = it; box.setText(it) } }
        entry(if (busy) "Vérification…" else "Connecter") { if (typed.isNotBlank() && !busy) connect(typed.trim()) }
        message?.let { note(it, Palette.RED) }
        entry("Plus tard") { finish() }
    }
}
