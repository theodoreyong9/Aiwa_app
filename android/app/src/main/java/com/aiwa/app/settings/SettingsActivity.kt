package com.aiwa.app.settings

import android.content.Intent
import android.text.InputType
import android.widget.EditText
import kotlinx.coroutines.launch
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.home.CoffeeSettings
import com.aiwa.app.home.ProfileSettings
import com.aiwa.app.voice.AgentToggleActivity
import com.aiwa.app.voice.ChamberSettings
import com.aiwa.app.voice.LiveSettings
import com.aiwa.app.voice.NaturalVoice
import com.aiwa.app.voice.ReadySettings
import com.aiwa.app.voice.VoicePrintActivity
import com.aiwa.app.voice.WordsActivity
import com.aiwa.app.voir.VoirSettings
import com.aiwa.app.widget.AiwaWidget

/** « Réglages »: the whole list, one line each. A line with a switch shows its state and flips on a touch; the others open their own window. */
class SettingsActivity : FloatActivity() {
    override val title = "Réglages"

    override fun onResume() {
        super.onResume()
        reload()
        // the state shown (GitHub connected or not) is the brain's of now, not the one the window opened with
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch { kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { com.aiwa.app.brain.BrainSync.refresh() }; reload() }
    }

    private fun switch(label: String, detail: String, on: Boolean, flip: (Boolean) -> Unit) {
        entry((if (on) "● " else "○ ") + label, detail, if (on) Palette.CARD else Palette.CARD) { flip(!on); reload() }
    }

    private fun open(cls: Class<*>) = startActivity(Intent(this, cls))

    override fun fill() {
        note("Vie privée", Palette.GOLD)
        switch("Se cacher", "Tes liens ne sont pas montrés aux gens à proximité.", !VoirSettings.on(this)) { VoirSettings.setOn(this, !it) }
        switch("Chambre ouverte écran éteint", "La chambre reste ouverte quand l'écran s'éteint.", ChamberSettings.awake(this)) { ChamberSettings.setAwake(this, it) }
        switch("Café", "Un bouton ☕ sur les profils que tu visites : envoyer de l'AIWA à la personne.", CoffeeSettings.on(this)) { CoffeeSettings.setOn(this, it) }

        note("Moi", Palette.GOLD)
        entry("Ma description", "Ce que ton super agent dit de toi dans une chambre.") { open(DescriptionActivity::class.java) }
        entry("Ma voix", "Pour que seul toi réveilles le super agent.") { open(VoicePrintActivity::class.java) }
        entry("Mon style", "Il te répond comme tu parles.") { open(StyleActivity::class.java) }
        entry("Mes mots", "Ce que tu dis : réveil, stop, éteins, validation.") { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, true)) }
        entry("Ses mots", "Ce que dit Aiwa : j'écoute, à toute, c'est prêt.") { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, false)) }
        entry("Profil", "Le dépôt qui contient ta page : " + (ProfileSettings.repo(this) ?: "pas encore choisi")) { chooseProfile() }

        note("Voix", Palette.GOLD)
        switch("Voix naturelle", "Sinon, la voix du téléphone parle.", NaturalVoice.enabled(this)) { NaturalVoice.setEnabled(this, it) }
        switch("Création à la volée", "Le super agent suit ce que tu dis pendant que tu construis, sans relecture.", LiveSettings.enabled(this)) { LiveSettings.set(this, it) }
        switch("« C'est prêt »", "Dit à voix haute qu'une production vient d'arriver.", ReadySettings.enabled(this)) { ReadySettings.set(this, it) }
        entry("Super agent", "Ouvrir ou fermer la conversation.") { open(AgentToggleActivity::class.java) }

        note("Comptes", Palette.GOLD)
        entry("Clés et plafonds", "Ta clé Anthropic, son plafond du jour, ton jeton GitHub.") { open(KeysActivity::class.java) }
        entry("Connecter GitHub", Aiwa.state.value.status?.let { if (it.githubToken) "Connecté" + (it.githubUser?.let { u -> " : $u" } ?: "") else "Pas connecté : seuls tes dépôts publics sont vus." } ?: "Voir tous tes dépôts, privés compris.") { open(GithubConnectActivity::class.java) }
        entry("Connecter Claude", "Relier le Claude du téléphone à ton compte.") { open(ClaudeLoginActivity::class.java) }

        note("Aiwa", Palette.GOLD)
        entry("Papers", "Yellow paper, valeur, readme, film.") { open(PapersActivity::class.java) }
        entry("État d'Aiwa", "Ce qui marche, ce qui manque.") { open(HealthActivity::class.java) }
    }

    override fun onPause() { super.onPause(); AiwaWidget.render(applicationContext, force = true) }

    private fun chooseProfile() {
        val field = EditText(this).apply { setText(ProfileSettings.repo(this@SettingsActivity).orEmpty()); hint = "proprietaire/depot"; inputType = InputType.TYPE_CLASS_TEXT; setSingleLine() }
        android.app.AlertDialog.Builder(this)
            .setTitle("Dépôt du profil").setMessage("Le dépôt dont le dossier Profile/ est ta page.").setView(field)
            .setPositiveButton("Enregistrer") { _, _ -> field.text.toString().trim().takeIf { it.contains('/') }?.let { ProfileSettings.set(this, it); reload() } }
            .setNeutralButton("Vérifier") { _, _ -> ProfileSettings.check(this) }
            .setNegativeButton("Annuler", null)
            .show()
    }
}
