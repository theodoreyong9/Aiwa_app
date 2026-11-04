package com.aiwa.app.settings

import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.home.AdaptSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * « Adaptation »: two switches and what the adaptation may read of her. « Voir les profils adaptés pour moi » (the profiles she visits are rewritten on her phone, when they are adaptable and have rules) and « Mon profil
 * est adaptable » (written in her Profile/aiwa.json: whoever looks at her with the first switch on sees her page rewritten for them). Below, what the rules of the profiles she visits may read of her.
 */
class AdaptActivity : FloatActivity() {
    override val title = "Adaptation"

    private var rules: List<com.aiwa.client.AdaptRule>? = null

    override fun onResume() { super.onResume(); AdaptSettings.refresh(this); loadRules(); reload() }

    private fun loadRules() {
        CoroutineScope(Dispatchers.Main).launch { rules = withContext(Dispatchers.IO) { try { Aiwa.brain.adaptRules() } catch (err: Exception) { null } }; reload() }
    }

    /** A rule is cut, lit again or removed: the brain writes the files of her repository again (a few seconds). */
    private fun change(id: String, action: String) {
        toastOnMain(applicationContext, "Je réécris ton profil…")
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.adaptRuleChange(id, action) }
            toastOnMain(applicationContext, if (out.ok) "C'est fait." else "Pas écrit : ${out.error}")
            loadRules()
        }
    }

    /** A rule typed (the usual way is to say it to the super agent): understood by the model, kept, written. */
    private fun typeRule() {
        val field = android.widget.EditText(this).apply { hint = "Si le visiteur aime le rouge, mon titre devient rouge"; setSingleLine(false); minLines = 3 }
        android.app.AlertDialog.Builder(this).setTitle("Une règle").setView(field)
            .setPositiveButton("Ajouter") { _, _ ->
                val sentence = field.text.toString().trim()
                if (sentence.isEmpty()) return@setPositiveButton
                toastOnMain(applicationContext, "Je comprends ta règle et je l'écris…")
                CoroutineScope(Dispatchers.Main).launch {
                    val out = withContext(Dispatchers.IO) { Aiwa.brain.adaptRuleAdd(sentence) }
                    toastOnMain(applicationContext, if (out.ok) "Règle écrite : ${out.json.optString("dit")}" else "Refusée : ${out.error}")
                    loadRules()
                }
            }.setNegativeButton("Annuler", null).show()
    }

    private fun switchRow(label: String, detail: String, on: Boolean, flip: (Boolean) -> Unit) {
        entryIcon(R.drawable.fw_i_swap, label, detail, Palette.GOLD, if (on) "Activé" else "Désactivé", if (on) Palette.GREEN else Palette.DIM) { flip(!on); reload() }
    }

    override fun fill() {
        note("Un profil peut se réécrire selon qui le regarde. Tout se passe sur ton téléphone : l'auteur d'une page ne sait jamais ce que tu as laissé lire, ni si une règle a joué.")
        switchRow("Voir les profils adaptés pour moi", "", AdaptSettings.wants(this)) { AdaptSettings.setWants(this, it) }
        switchRow("Mon profil est adaptable", "", AdaptSettings.adaptable(this)) { on ->
            AdaptSettings.setAdaptable(this, on)
            CoroutineScope(Dispatchers.Main).launch {
                val out = withContext(Dispatchers.IO) { Aiwa.brain.adaptPublish(on) }
                toastOnMain(applicationContext, if (out.ok) (if (on) "Ton profil est adaptable." else "Ton profil n'est plus adaptable.") else "Pas écrit : ${out.error}")
                if (!out.ok) { AdaptSettings.setAdaptable(applicationContext, !on); reload() }
            }
        }
        section("Mes règles")
        val list = rules
        when {
            list == null -> note("…")
            list.isEmpty() -> note("Aucune règle. Dis par exemple au super agent : « si le visiteur aime le rouge, mon titre devient rouge ». Il la comprend et l'écrit lui-même dans ton profil.")
            else -> list.forEach { r -> entryWithAction(r.text, if (r.on) "Active · touche pour la couper" else "Coupée · touche pour la rallumer", Palette.CARD, "Supprimer", { change(r.id, if (r.on) "off" else "on") }, { change(r.id, "remove") }) }
        }
        entryIcon(R.drawable.fw_i_note, "Écrire une règle", null, Palette.GOLD) { typeRule() }
        section("Ce que les règles peuvent lire de moi")
        AdaptSettings.TRAITS.forEach { trait ->
            switchRow(label(trait), "", AdaptSettings.exposed(this, trait)) { AdaptSettings.setExposed(this, trait, it) }
        }
        val mode = AdaptSettings.descriptionMode(this)
        entryIcon(R.drawable.fw_i_note, "Ma description", null, Palette.GOLD, listOf("Rien", "Les traits qu'on en tire", "Le texte")[mode], if (mode == 0) Palette.DIM else Palette.GREEN) {
            AdaptSettings.cycleDescription(this); AdaptSettings.refresh(this); reload()
        }
    }

    private fun label(trait: String) = mapOf("couleurs" to "Mes couleurs", "langues" to "Mes langues", "themes" to "Mes thèmes", "roles" to "Mes rôles", "ton" to "Mon ton", "mode" to "Clair ou sombre", "lieu" to "Mon lieu")[trait] ?: trait
}
