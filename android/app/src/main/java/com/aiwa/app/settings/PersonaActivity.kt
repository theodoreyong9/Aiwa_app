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
        note("La course", Palette.GOLD)
        note("Toi et ton super agent partez à 100 points et en perdez un par jour. Il en gagne 10 quand tu acceptes ce qu'il propose de lui-même, 5 de moins quand tu refuses. Tes propositions, il les juge : oui +10, non -5 pour toi, avec sa raison. Vous pouvez vous donner des points (« je te donne 20 points »). Manche finie quand l'un tombe à zéro (l'autre gagne), ou après 30 jours : le meilleur gagne s'il a au moins ${p.game.minimum} points. Le premier à 10 manches est le grand gagnant. Son but est de gagner.")
        val g = p.game
        entry(if (g.on) "● Course lancée" else "○ Course arrêtée", if (g.on) "Touche pour l'arrêter." else "Touche pour la lancer.") { call { Aiwa.brain.personaGame(!g.on) } }
        if (g.on) {
            note("Toi ${g.user} · lui ${g.agent} · jour ${g.day + 1}/${g.days} · manches : toi ${g.winsUser}, lui ${g.winsAgent}", Palette.GREEN)
            g.grand?.let { note((if (it == "user") "Tu es" else "Il est") + " le grand gagnant !", Palette.GOLD) }
            if (g.ended != null && g.grand == null) note(when (g.ended) { "user" -> "Manche gagnée par toi."; "agent" -> "Manche gagnée par lui."; else -> "Manche nulle." } + " Plus aucun point ne bouge : recommence.", Palette.GOLD)
            if (g.ended == null) entry("Lui donner 10 points", "Ou dis-le à voix haute.") { call { Aiwa.brain.personaGive(10) } }
            if (g.grand == null) entry("Recommencer la manche", "Vous repartez à 100 chacun, les victoires restent.") { call { Aiwa.brain.personaRestart() } }
            entry("Tout remettre à zéro", "Efface aussi les victoires.") { call { Aiwa.brain.personaResetAll() } }
            if (g.history.isNotEmpty()) { note("Derniers verdicts et points", Palette.GOLD); for (h in g.history) note(h) }
        }
    }
}
