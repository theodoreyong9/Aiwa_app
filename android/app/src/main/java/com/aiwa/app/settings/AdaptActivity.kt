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

    override fun onResume() { super.onResume(); AdaptSettings.refresh(this); reload() }

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
