package com.aiwa.app.scenario

import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.voice.VoiceService
import com.aiwa.client.Scenario
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The scenarios: a prompt the person would repeat by hand, kept under a launch word of her own. Touching one launches it: a double of her (a session of its own) that she talks to by voice, and
 * that can send work to her sessions. The « Rapport » is a scenario too: it asks the super agent for the report. A scenario is made or changed on its own screen.
 */
class ScenariosActivity : FloatActivity() {
    override val title = "Scénarios"
    private var list: List<Scenario>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        load()
    }

    override fun onResume() { super.onResume(); if (list != null) load() }

    private fun load() {
        CoroutineScope(Dispatchers.Main).launch {
            list = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.scenarios() }
            reload()
        }
    }

    override fun fill() {
        val items = list
        if (items == null) { note("Je lis tes scénarios…"); return }
        note("Touche un scénario pour le lancer. Tu peux aussi dire son mot de lancement au super agent.")
        items.forEach { sc ->
            val state = when { sc.creating -> "se prépare…"; sc.error != null -> "erreur : ${sc.error}"; sc.watching -> "veille en cours · ${sc.turns} tour(s) · dis stop pour l'arrêter"; sc.session != null -> "prêt" ; else -> "pas encore lancé" }
            entry(sc.name, "« ${sc.word} » · $state" + (sc.repo?.let { " · $it" } ?: ""), Palette.CARD) { menu(sc) }
        }
        entry("＋ Nouveau scénario", "un mot, une consigne, ce que son double dit et ce qu'il se tait") { startActivity(Intent(this, ScenarioEditActivity::class.java)) }
    }

    private fun menu(sc: Scenario) {
        val items = if (sc.kind == "report") arrayOf("Lancer", "Modifier", "Supprimer") else arrayOf("Lancer", "Changer de session", "Modifier", "Supprimer")
        AlertDialog.Builder(this).setTitle(sc.name).setItems(items) { _, picked ->
            val which = if (sc.kind == "report" && picked > 0) picked + 1 else picked
            when (which) {
                0 -> launch(sc)
                1 -> sessionPicker(sc)
                2 -> startActivity(Intent(this, ScenarioEditActivity::class.java).putExtra(ScenarioEditActivity.EXTRA_ID, sc.id))
                3 -> AlertDialog.Builder(this).setTitle("Supprimer « ${sc.name} » ?").setPositiveButton("Supprimer") { _, _ ->
                    CoroutineScope(Dispatchers.Main).launch { withContext(Dispatchers.IO) { Aiwa.brain.scenarioDelete(sc.id) }; load() }
                }.setNegativeButton("Garder", null).show()
            }
        }.show()
    }

    /** The session of the double: the ones it has had (the current one is ticked), a new one, or one of the person's own sessions. */
    private fun sessionPicker(sc: Scenario) {
        val own = Aiwa.state.value.sessions.filter { s -> sc.sessions.none { it.id == s.id } }.take(10)
        val labels = ArrayList<String>()
        val actions = ArrayList<() -> Unit>()
        sc.sessions.forEach { s -> labels.add((if (s.current) "✓ " else "") + s.title); actions.add { use(sc, s.id) } }
        labels.add("＋ Une nouvelle session"); actions.add { CoroutineScope(Dispatchers.Main).launch { withContext(Dispatchers.IO) { Aiwa.brain.scenarioCreate(sc.id, true) }; toastOnMain(applicationContext, "Une nouvelle session se prépare…"); load() } }
        own.forEach { s -> labels.add("Prendre « ${s.title} »"); actions.add { use(sc, s.id) } }
        AlertDialog.Builder(this).setTitle("Session de « ${sc.name} »").setItems(labels.toTypedArray()) { _, i -> actions[i]() }.setNegativeButton("Fermer", null).show()
    }

    private fun use(sc: Scenario, session: String) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { Aiwa.brain.scenarioUse(sc.id, session) }
            toastOnMain(applicationContext, if (out.ok) "La session de « ${sc.name} » a changé." else (out.error ?: "Impossible de changer de session."))
            load()
        }
    }

    private fun launch(sc: Scenario) {
        if (sc.kind == "report") {
            CoroutineScope(Dispatchers.Main).launch {
                val out = withContext(Dispatchers.IO) { Aiwa.brain.scenarioLaunch(id = sc.id) }
                toastOnMain(applicationContext, if (out.ok) "Le super agent prépare le rapport…" else (out.error ?: "Le rapport n'est pas parti."))
                finish()
            }
            return
        }
        // the double is talked to by voice: the super agent opens on it (a microphone service starts from a visible window only)
        VoiceService.openAgent(applicationContext, sc)
        finish()
    }
}
