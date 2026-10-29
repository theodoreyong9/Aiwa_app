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
            val state = when { sc.creating -> "se prépare…"; sc.error != null -> "erreur : ${sc.error}"; sc.session != null -> "prêt" ; else -> "pas encore lancé" }
            entry(sc.name, "« ${sc.word} » · $state", if (sc.error != null) Palette.CARD else Palette.CARD) { menu(sc) }
        }
        entry("＋ Nouveau scénario", "un mot, une consigne, ce que son double dit et ce qu'il se tait") { startActivity(Intent(this, ScenarioEditActivity::class.java)) }
    }

    private fun menu(sc: Scenario) {
        val items = arrayOf("Lancer", "Modifier", "Supprimer")
        AlertDialog.Builder(this).setTitle(sc.name).setItems(items) { _, which ->
            when (which) {
                0 -> launch(sc)
                1 -> startActivity(Intent(this, ScenarioEditActivity::class.java).putExtra(ScenarioEditActivity.EXTRA_ID, sc.id))
                2 -> AlertDialog.Builder(this).setTitle("Supprimer « ${sc.name} » ?").setPositiveButton("Supprimer") { _, _ ->
                    CoroutineScope(Dispatchers.Main).launch { withContext(Dispatchers.IO) { Aiwa.brain.scenarioDelete(sc.id) }; load() }
                }.setNegativeButton("Garder", null).show()
            }
        }.show()
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
