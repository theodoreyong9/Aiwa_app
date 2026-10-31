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
    override val title: String get() = when (intent.getStringExtra(EXTRA_GROUP)) { "words" -> "Les mots"; "me" -> "Moi"; "voice" -> "Voix"; "model" -> "Modèle"; else -> "Réglages" }
    override val compactRows = true      // an icon and a name, no explanation
    override val gridColumns = 3         // several icons on a row

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

    private val group: String? by lazy { intent.getStringExtra(EXTRA_GROUP) }

    private fun openGroup(id: String) = startActivity(Intent(this, SettingsActivity::class.java).putExtra(EXTRA_GROUP, id))

    private val SKY = Color.parseColor("#7FD0FF")
    private val PEACH = Color.parseColor("#F29B6B")
    private val MINT = Color.parseColor("#52D6A0")
    private val LILAC = Color.parseColor("#B79CFF")

    override fun fill() {
        when (group) {
            "words" -> words()
            "me" -> me()
            "voice" -> voice()
            "model" -> model()
            else -> main()
        }
    }

    /** The first window: the groups, each one a tile that opens its own. */
    private fun main() {
        val status = Aiwa.state.value.status
        val game = persona?.game
        entryIcon(R.drawable.fw_i_claude, "Connexion Claude", null, PEACH,
            if (status?.claudeLogin == "needed") "À relier" else if (status?.claudeLogin == "ok") "Relié" else null, if (status?.claudeLogin == "needed") Palette.RED else Palette.GREEN) { open(ClaudeLoginActivity::class.java) }
        entryIcon(R.drawable.fw_i_github, "Connexion GitHub", null, LILAC,
            if (status?.githubToken == true) "Connecté" else "À connecter", if (status?.githubToken == true) Palette.GREEN else Palette.RED) { open(GithubConnectActivity::class.java) }
        entryIcon(R.drawable.fw_i_talk, "Les mots", null, SKY) { openGroup("words") }
        entryIcon(R.drawable.fw_i_trophy, "Jeu et personnalité", null, Palette.GOLD,
            if (game?.on == true) (if (game.ended != null) "Manche finie" else "${game.user} · ${game.agent}") else "Arrêté", if (game?.on == true) Palette.GOLD else Palette.DIM) { open(PersonaActivity::class.java) }
        entryIcon(R.drawable.fw_i_aiwa, "Moi", null, MINT) { openGroup("me") }
        entryIcon(R.drawable.fw_i_volume, "Voix", null, SKY) { openGroup("voice") }
        entryIcon(R.drawable.fw_i_papers, "Papers", null, Palette.GOLD) { open(PapersActivity::class.java) }
        entryIcon(R.drawable.fw_i_tools, "Modèle", null, PEACH, status?.model ?: "auto", Palette.DIM) { openGroup("model") }
        switchRow(R.drawable.fw_i_report, "« C'est prêt »", "", ReadySettings.enabled(this), MINT) { ReadySettings.set(this, it) }
        switchRow(R.drawable.fw_i_swap, "Push direct", "", status?.pushMain ?: true, MINT) { on ->
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch { Aiwa.brain.setPushMain(on); com.aiwa.app.brain.BrainSync.refresh() }
        }
        entryIcon(R.drawable.fw_i_image, "Fond du widget", null, SKY, com.aiwa.app.widget.WidgetBackground.label(this), Palette.DIM) { com.aiwa.app.widget.WidgetBackground.next(this); reload() }
        entryIcon(R.drawable.fw_i_key, "Clés et plafonds", null, Palette.GOLD) { open(KeysActivity::class.java) }
        entryIcon(R.drawable.fw_i_report, "État d'Aiwa", null, Palette.GREEN) { open(HealthActivity::class.java) }
    }

    private fun words() {
        entryIcon(R.drawable.fw_i_talk, "Mes mots", null, SKY) { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, true)) }
        entryIcon(R.drawable.fw_i_robot, "Ses mots", null, PEACH) { startActivity(Intent(this, WordsActivity::class.java).putExtra(WordsActivity.EXTRA_MINE, false)) }
    }

    private fun me() {
        entryIcon(R.drawable.fw_i_note, "Ma description", null, MINT) { open(DescriptionActivity::class.java) }
        entryIcon(R.drawable.fw_i_aiwa, "Mon profil", null, LILAC) { chooseProfile() }
        switchRow(R.drawable.fw_i_voir, "Se cacher", "", !VoirSettings.on(this), LILAC) { VoirSettings.setOn(this, !it) }
        switchRow(R.drawable.fw_i_room, "Chambre ouverte écran éteint", "", ChamberSettings.awake(this), SKY) { ChamberSettings.setAwake(this, it) }
    }

    private fun voice() {
        switchRow(R.drawable.fw_i_volume, "Voix naturelle", "", NaturalVoice.enabled(this), SKY) { NaturalVoice.setEnabled(this, it) }
        switchRow(R.drawable.fw_i_create, "Création à la volée", "", LiveSettings.enabled(this), PEACH) { LiveSettings.set(this, it) }
        entryIcon(R.drawable.fw_i_ear, "Ma voix", null, Palette.GOLD) { open(VoicePrintActivity::class.java) }
        entryIcon(R.drawable.fw_i_note, "Mon style", null, LILAC) { open(StyleActivity::class.java) }
    }

    private fun model() {
        val status = Aiwa.state.value.status
        entryIcon(R.drawable.fw_i_tools, "Modèle", null, PEACH, status?.model ?: "auto", Palette.DIM) { cycle(listOf(null, "opus", "sonnet", "haiku"), status?.model) { m -> Aiwa.brain.setModel(m) } }
        entryIcon(R.drawable.fw_i_build, "Effort", null, Palette.GOLD, status?.effort ?: "auto", Palette.DIM) { cycle(listOf(null, "low", "medium", "high", "xhigh", "max"), status?.effort) { e -> Aiwa.brain.setEffort(e) } }
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

    companion object { const val EXTRA_GROUP = "group" }
}
