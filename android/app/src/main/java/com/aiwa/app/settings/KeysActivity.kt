package com.aiwa.app.settings

import android.text.InputType
import android.widget.EditText
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** « Clés et plafonds »: the person's Anthropic key (the super agent speaks through it), the most tokens it may use in a day, and the way to the GitHub connection. */
class KeysActivity : FloatActivity() {
    override val title = "Clés et plafonds"

    private fun field(hintText: String, secret: Boolean, number: Boolean = false) = EditText(this).apply {
        hint = hintText; setTextColor(android.graphics.Color.WHITE); setHintTextColor(android.graphics.Color.parseColor("#7F8CC0")); setSingleLine()
        inputType = when {
            number -> InputType.TYPE_CLASS_NUMBER
            secret -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            else -> InputType.TYPE_CLASS_TEXT
        }
    }

    private fun run(work: suspend () -> com.aiwa.client.Brain.Outcome, done: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { val o = work(); BrainSync.refresh(); o }
            toastOnMain(applicationContext, if (out.ok) done else "Refusé : ${out.error}")
            reload()
        }
    }

    override fun fill() {
        val status = Aiwa.state.value.status
        val llm = status?.llm
        note("Le super agent parle avec ta propre clé Anthropic, qui reste sur ton téléphone. Sans clé, il utilise le Claude du téléphone (plus lent).")
        note(when (llm?.state) {
            "ready" -> "✓ Clé en place. Aujourd'hui : ${llm.used} jetons" + (if (llm.cap > 0) " sur ${llm.cap}." else ", sans plafond.")
            "installing" -> "Installation du moteur en cours…"
            "error" -> "La clé a été refusée."
            else -> "Pas de clé."
        }, if (llm?.state == "ready") Palette.GREEN else Palette.TEXT)
        val key = field("sk-ant-…", secret = true)
        add(key)
        entry("Enregistrer la clé") { val k = key.text.toString().trim(); if (k.isNotEmpty()) run({ Aiwa.brain.llmKey(k) }, "Clé enregistrée") }
        if (llm?.state == "ready" || llm?.state == "error") entry("Retirer la clé") { run({ Aiwa.brain.llmClearKey() }, "Clé retirée") }
        val cap = field("Plafond par jour, en jetons (0 = aucun)", secret = false, number = true)
        if (llm != null && llm.cap > 0) cap.setText(llm.cap.toString())
        add(cap, 16)
        entry("Enregistrer le plafond") { run({ Aiwa.brain.llmCap(cap.text.toString().trim().toLongOrNull() ?: 0L) }, "Plafond enregistré") }

        entry("GitHub", if (status?.githubToken == true) "Connecté" + (status.githubUser?.let { " : $it" } ?: "") else "Pas connecté") { startActivity(android.content.Intent(this, GithubConnectActivity::class.java)) }
    }
}
