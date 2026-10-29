package com.aiwa.app.settings

import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.Battery
import com.aiwa.app.brain.EXPECTED_BRAIN_VERSION
import com.aiwa.app.brain.Link
import com.aiwa.app.brain.isTermuxInstalled
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.copyToClipboard
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.update.AppUpdater
import com.aiwa.client.BOOTSTRAP_COMMAND

/** « État d'Aiwa »: every part that has to work, one line each, green or red, and the gesture that fixes a red one. */
class HealthActivity : FloatActivity() {
    override val title = "État d'Aiwa"

    private fun line(ok: Boolean, text: String) = note((if (ok) "✓ " else "✗ ") + text, if (ok) Palette.GREEN else Palette.RED)

    override fun onResume() { super.onResume(); reload() }

    override fun fill() {
        val snap = Aiwa.state.value
        val status = snap.status
        line(isTermuxInstalled(this), "Termux" + if (isTermuxInstalled(this)) "" else " : à installer depuis F-Droid")
        line(snap.link == Link.UP, "Cerveau : " + when (snap.link) {
            Link.UP -> "répond (version ${status?.version})"
            Link.STARTING -> "démarre…"
            Link.MISSING -> "pas installé"
            else -> "ne répond pas"
        })
        if (status != null && status.version < EXPECTED_BRAIN_VERSION) line(false, "Cerveau trop ancien (${status.version}, il faut ${EXPECTED_BRAIN_VERSION}) : relance la ligne d'installation")
        if (snap.link != Link.UP) entry("Copier la ligne d'installation", "À coller dans Termux.") { copyToClipboard(this, BOOTSTRAP_COMMAND); toastOnMain(this, "Ligne copiée") }
        if (status != null) {
            line(status.claudeLogin == "ok", "Claude : " + if (status.claudeLogin == "ok") "connecté" else "à connecter")
            if (status.claudeLogin != "ok") entry("Connecter Claude") { startActivity(android.content.Intent(this, ClaudeLoginActivity::class.java)) }
            line(status.llm.state == "ready", "Clé du super agent : " + if (status.llm.state == "ready") "en place" else "absente (il passera par le Claude du téléphone)")
            line(status.relayCloud == "ok", "Relais (Claude te prévient) : " + status.relayCloud)
            line(status.githubToken, "GitHub : " + if (status.githubToken) "connecté" + (status.githubUser?.let { " ($it)" } ?: "") else "pas connecté (dépôts publics seulement)")
            if (!status.githubToken) entry("Connecter GitHub") { startActivity(android.content.Intent(this, GithubConnectActivity::class.java)) }
            line(status.voice == "ready", "Voix naturelle : " + (status.voice ?: "pas installée"))
            status.githubError?.let { line(false, "GitHub : $it") }
            status.repoAccessMissing?.let { line(false, "Claude n'a pas accès à $it") }
        }
        line(com.aiwa.app.brain.hasTermuxPermission(this), "Autorisation de lancer le cerveau dans Termux" + if (com.aiwa.app.brain.hasTermuxPermission(this)) "" else " : manquante (c'est ce qui rend le bouton Super agent rouge)")
        if (!com.aiwa.app.brain.hasTermuxPermission(this)) entry("Autoriser", "Ouvre l'écran qui la demande") { startActivity(android.content.Intent(this, com.aiwa.app.brain.SetupActivity::class.java)) }
        if (status?.waiting == true || (status?.silenceMinutes ?: 0) > 0) line(false, "Claude attend ta réponse (c'est ce qui rend le bouton Claude rouge) : ouvre-le ou réponds dans Question")
        status?.sessionError?.let { line(false, "La dernière session n'a pas pu être créée : $it") }
        line(Battery.isExempt(this), "Batterie : " + if (Battery.isExempt(this)) "Aiwa n'est pas endormi" else "Android peut endormir Aiwa")
        if (!Battery.isExempt(this)) entry("Autoriser en arrière-plan") { try { startActivity(Battery.requestIntent(this)) } catch (err: Exception) { toastOnMain(this, "Écran indisponible") } }
        line(!snap.appUpdateReady, "Application : version ${AppUpdater.installedVersion(this) ?: "?"}" + if (snap.appUpdateReady) " (une mise à jour attend)" else "")
        line(snap.listening, "Écoute : " + if (snap.listening) "active" else "éteinte")
    }
}
