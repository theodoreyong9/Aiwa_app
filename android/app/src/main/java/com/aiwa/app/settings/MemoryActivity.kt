package com.aiwa.app.settings

import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** What the super agent keeps from what she asked it to remember: read here, one note erased at a time, or all of them. Kept on the phone only. */
class MemoryActivity : FloatActivity() {
    override val title = "Mémoire"
    private var notes: List<Pair<String, String>>? = null

    override fun onResume() { super.onResume(); load() }

    private fun load() {
        CoroutineScope(Dispatchers.Main).launch {
            val got = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.memory() }
            notes = got
            reload()
        }
    }

    private fun forget(what: String) {
        CoroutineScope(Dispatchers.Main).launch {
            withContext(Dispatchers.IO) { Aiwa.brain.forgetMemory(what) }
            load()
        }
    }

    override fun fill() {
        val list = notes
        if (list == null) { note("Le cerveau ne répond pas."); return }
        if (list.isEmpty()) { note("Aiwa n'a rien retenu. Dis-lui « retiens que… » et ce sera écrit ici. Cela reste sur ton téléphone."); return }
        for ((id, text) in list.reversed()) entryWithAction(text, null, Palette.CARD, "Oublier", {}, { forget(id) })
        entry("Tout effacer", null, Palette.RED) { forget("all") }
    }
}
