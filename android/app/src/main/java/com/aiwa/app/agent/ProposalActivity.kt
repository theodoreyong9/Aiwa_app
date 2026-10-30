package com.aiwa.app.agent

import android.os.Bundle
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.AgentView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * What the super agent proposes, written in full and answerable with a finger: the red button of the widget opens it. The voice reads the same words, but nothing depends on it (a voice that fails,
 * a room too loud, a bubble that did not come): the proposal stays here until it is sent or dropped, and the outcome of the sending is shown.
 */
class ProposalActivity : FloatActivity() {
    override val title = "Le super agent propose"
    private var agent: AgentView? = null
    private var loaded = false
    private var sending = false
    private var outcome: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        refresh()
    }

    private fun refresh() {
        CoroutineScope(Dispatchers.Main).launch { agent = AgentVoice.fresh(); loaded = true; reload() }
    }

    override fun fill() {
        if (!loaded) { note("Je lis ce que l'agent a préparé…"); return }
        outcome?.let { note(it, Palette.GOLD) }
        val view = agent
        val proposal = view?.proposal
        val command = view?.command?.takeIf { !it.auto }
        when {
            proposal != null -> {
                note(proposal.readBack, Palette.TEXT)
                if (sending) { note("Envoi en cours : la machine du cloud peut mettre quelques minutes à répondre.", Palette.DIM); return }
                entry("Envoyer", "C'est bon, ça part", Palette.CARD) { send(proposal.id) }
                entry("Annuler", "Rien n'est envoyé") { drop(proposal.id) }
            }
            command != null -> {
                note(command.readBack, Palette.TEXT)
                entry("Appliquer", "C'est bon") { CoroutineScope(Dispatchers.Main).launch { AgentScreens.apply(applicationContext, command); finish() } }
                entry("Annuler", "Rien n'est changé") { drop(command.id) }
            }
            view?.say != null -> { note(view!!.say!!.text, Palette.TEXT); entry("Fermer") { finish() } }
            else -> { note("Rien n'attend de toi."); entry("Fermer") { finish() } }
        }
    }

    private fun send(id: String) {
        sending = true; outcome = null; reload()
        CoroutineScope(Dispatchers.Main).launch {
            val result = withContext(Dispatchers.IO) { Aiwa.brain.agentConfirm(id) }
            withContext(Dispatchers.IO) { BrainSync.refresh() }
            sending = false
            if (result.ok) { toastOnMain(applicationContext, "Envoyé à la session."); finish() }
            else {
                val why = if (result.error == "busy") "un autre envoi est encore en cours" else result.error ?: "le message n'est pas parti"
                outcome = "Pas envoyé : $why. Tu peux réessayer."
                agent = AgentVoice.fresh(); reload()
            }
        }
    }

    private fun drop(id: String) {
        CoroutineScope(Dispatchers.Main).launch { withContext(Dispatchers.IO) { Aiwa.brain.agentCancel(id); BrainSync.refresh() }; finish() }
    }
}
