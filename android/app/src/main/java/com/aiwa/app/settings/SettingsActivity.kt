package com.aiwa.app.settings

import android.content.Intent
import android.graphics.Color
import android.text.InputType
import android.widget.EditText
import kotlinx.coroutines.launch
import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.home.ProfileSettings
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
        // the state shown (GitHub connected or not, the score of the game) is the brain's of now, not the one the window opened with
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { com.aiwa.app.brain.BrainSync.refresh(); persona = try { Aiwa.brain.persona() } catch (err: Exception) { null } }
            reload()
        }
    }

    private var persona: com.aiwa.client.PersonaView? = null
    private val ON = Palette.GREEN

    /** A line with a switch: its state is a pill (Activé / Désactivé) and a touch flips it. */
    private fun switchRow(icon: Int, label: String, detail: String, on: Boolean, accent: Int = Palette.DIM, flip: (Boolean) -> Unit) {
        entryIcon(icon, label, detail, accent, if (on) "Activé" else "Désactivé", if (on) ON else Palette.DIM) { flip(!on); reload() }
    }

    private fun open(cls: Class<*>) = startActivity(Intent(this, cls))

    /** The next value of a short list (the first after the last one); the brain keeps it, the window shows it again. */
    private fun cycle(choices: List<String?>, now: String?, set: (String?) -> Unit) {
        val next = choices[(choices.indexOf(now).let { if (it < 0) 0 else it } + 1) % choices.size]
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { set(next); com.aiwa.app.brain.BrainSync.refresh() }
            reload()
        }
    }

    override fun fill() {
        val status = Aiwa.state.value.status
        val game = persona?.game
        section("Mes comptes")
        entryIcon(R.drawable.fw_i_claude, "Connexion Claude", "Relier le Claude du téléphone à ton compte.", Color.parseColor("#F29B6B"),
            if (status?.claudeLogin == "needed") "À relier" else if (status?.claudeLogin == "ok") "Relié" else null, if (status?.claudeLogin == "needed") Palette.RED else Palette.GREEN) { open(ClaudeLoginActivity::class.java) }
        entryIcon(R.drawable.fw_i_github, "Connexion GitHub", if (status?.githubToken == true) "Connecté" + (status.githubUser?.let { " : $it" } ?: "") else "Pour que tes productions arrivent dans tes dépôts.", Color.parseColor("#B79CFF"),
            if (status?.githubToken == true) "Connecté" else "À connecter", if (status?.githubToken == true) Palette.GREEN else Palette.RED) { open(GithubConnectActivity::class.java) }

        section("Mon super agent")
        entryIcon(R.drawable.fw_i_trophy, "Mode jeu", "La course de points entre toi et ton super agent.", Palette.GOLD,
            if (game?.on == true) (if (game.ended != null) "Manche finie" else "${game.user} · ${game.agent}") else "Arrêté", if (game?.on == true) Palette.GOLD else Palette.DIM) { open(PersonaActivity::class.java) }
        entryIcon(R.drawable.fw_i_talk, "Personnalité", "Son ton : neutre, vanneur, chaleureux, sec.", Color.parseColor("#7FD0FF"), persona?.styles?.firstOrNull { it.first == persona?.style }?.second, Palette.DIM) { open(PersonaActivity::class.java) }
        entryIcon(R.drawable.fw_i_note, "Ma description", "Ce que ton super agent dit de toi dans une chambre.", Color.parseColor("#52D6A0")) { open(DescriptionActivity::class.java) }
        entryIcon(R.drawable.fw_i_aiwa, "Mon profil", ProfileSettings.repo(this) ?: "Le dépôt qui contient ta page : pas encore choisi", Color.parseColor("#B79CFF")) { chooseProfile() }

        section("Voix")
        switchRow(R.drawable.fw_i_volume, "Voix naturelle", "Sinon, la voix du téléphone parle.", NaturalVoice.enabled(this), Color.parseColor("#7FD0FF")) { NaturalVoice.setEnabled(this, it) }
        switchRow(R.drawable.fw_i_create, "Création à la volée", "Le super agent suit ce que tu dis pendant que tu construis, sans relecture.", LiveSettings.enabled(this), Color.parseColor("#F29B6B")) { LiveSettings.set(this, it) }
        switchRow(R.drawable.fw_i_report, "« C'est prêt »", "Dit à voix haute qu'une production vient d'arriver.", ReadySettings.enabled(this), Color.parseColor("#52D6A0")) { ReadySettings.set(this, it) }
        entryIcon(R.drawable.fw_i_ear, "Ma voix", "Pour que seul toi réveilles le super agent.", Color.parseColor("#E8C14A")) { open(VoicePrintActivity::class.java) }
        entryIcon(R.drawable.fw_i_talk, "Mes mots", "Ce que tu dis : réveil, stop, éteins, validation.", Color.parseColor("#7FD0FF")) { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, true)) }
        entryIcon(R.drawable.fw_i_robot, "Ses mots", "Ce que dit Aiwa : j'écoute, à toute, c'est prêt.", Color.parseColor("#F29B6B")) { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, false)) }
        entryIcon(R.drawable.fw_i_note, "Mon style", "Il te répond comme tu parles.", Color.parseColor("#B79CFF")) { open(StyleActivity::class.java) }

        section("Aiwa")
        entryIcon(R.drawable.fw_i_papers, "Papers", "Yellow paper, valeur, readme, film.", Palette.GOLD) { open(PapersActivity::class.java) }

        section("Vie privée")
        switchRow(R.drawable.fw_i_voir, "Se cacher", "Tes liens ne sont pas montrés aux gens à proximité.", !VoirSettings.on(this), Color.parseColor("#B79CFF")) { VoirSettings.setOn(this, !it) }
        switchRow(R.drawable.fw_i_room, "Chambre ouverte écran éteint", "La chambre reste ouverte quand l'écran s'éteint.", ChamberSettings.awake(this), Color.parseColor("#7FD0FF")) { ChamberSettings.setAwake(this, it) }

        section("Sessions")
        entryIcon(R.drawable.fw_i_tools, "Modèle", "Touche pour changer (ou dis-le à ton agent).", Color.parseColor("#F29B6B"), status?.model ?: "automatique", Palette.DIM) { cycle(listOf(null, "opus", "sonnet", "haiku"), status?.model) { m -> Aiwa.brain.setModel(m) } }
        entryIcon(R.drawable.fw_i_build, "Effort", "Touche pour changer (ou dis-le à ton agent).", Color.parseColor("#E8C14A"), status?.effort ?: "automatique", Palette.DIM) { cycle(listOf(null, "low", "medium", "high", "xhigh", "max"), status?.effort) { e -> Aiwa.brain.setEffort(e) } }
        switchRow(R.drawable.fw_i_swap, "Push direct", "Quand c'est fini, la session intègre son travail dans la branche principale ; sinon il reste sur sa branche.", status?.pushMain ?: true, Color.parseColor("#52D6A0")) { on ->
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch { Aiwa.brain.setPushMain(on); com.aiwa.app.brain.BrainSync.refresh() }
        }

        section("Widget et clés")
        entryIcon(R.drawable.fw_i_image, "Fond du widget", "Touche pour changer.", Color.parseColor("#7FD0FF"), com.aiwa.app.widget.WidgetBackground.label(this), Palette.DIM) { com.aiwa.app.widget.WidgetBackground.next(this); reload() }
        entryIcon(R.drawable.fw_i_key, "Clés et plafonds", "Ta clé Anthropic et son plafond, fal, Pexels, Pixabay, Hugging Face.", Palette.GOLD) { open(KeysActivity::class.java) }
        entryIcon(R.drawable.fw_i_report, "État d'Aiwa", "Ce qui marche, ce qui manque.", Palette.GREEN) { open(HealthActivity::class.java) }
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
