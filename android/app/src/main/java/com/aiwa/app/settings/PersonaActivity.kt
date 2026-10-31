package com.aiwa.app.settings

import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.PersonaView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** « Personnalité »: the style the super agent speaks in (what it says aloud, never what it writes to the sessions) and the game mode (points given by voice, one lost an hour). */
class PersonaActivity : FloatActivity() {
    override val title = "Personnalité"
    private var view: PersonaView? = null
    private var loaded = false

    override fun onResume() {
        super.onResume()
        CoroutineScope(Dispatchers.Main).launch { view = withContext(Dispatchers.IO) { Aiwa.brain.persona() }; loaded = true; reload() }
    }

    private fun call(work: () -> com.aiwa.client.Brain.Outcome) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { work() }
            if (!out.ok) toastOnMain(applicationContext, "Refusé : ${out.error}")
            view = withContext(Dispatchers.IO) { Aiwa.brain.persona() }
            reload()
        }
    }

    override fun fill() {
        val p = view
        if (p == null) { note(if (loaded) "Le cerveau ne répond pas (ou il est trop ancien)." else "…"); return }
        note("Style", Palette.GOLD)
        note("Le ton de ce que le super agent te dit à voix haute. Les messages qu'il envoie à tes sessions restent neutres. La vanne reste un ton : jamais d'insulte.")
        for ((id, label) in p.styles) entry((if (id == p.style) "● " else "○ ") + label) { call { Aiwa.brain.personaStyle(id) } }
        note("Mode jeu", Palette.GOLD)
        note("Tu lui donnes des points à voix haute (« je te donne 20 points »). Il en perd un par heure, cinq quand tu refuses ce qu'il propose de lui-même, il en gagne dix quand tu acceptes. À zéro, il ne peut plus parler jusqu'à ce que tu lui en redonnes.")
        entry(if (p.game) "● Mode jeu activé" + (p.points?.let { " : $it points" } ?: "") else "○ Mode jeu désactivé", if (p.game) "Touche pour l'arrêter." else "Touche pour le lancer (il commence avec 48 points).") { call { Aiwa.brain.personaGame(!p.game) } }
        if (p.game) entry("Lui donner 10 points", "Ou dis-le à voix haute.") { call { Aiwa.brain.personaPoints(10) } }
    }
}
