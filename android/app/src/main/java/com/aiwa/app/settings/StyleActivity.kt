package com.aiwa.app.settings

import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.StyleView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** « Mon style »: the super agent learns how the person speaks (it keeps counts of words, never the sentences) and talks the same way. */
class StyleActivity : FloatActivity() {
    override val title = "Mon style"
    private var view: StyleView? = null
    private var loaded = false

    override fun onResume() {
        super.onResume()
        CoroutineScope(Dispatchers.Main).launch { view = withContext(Dispatchers.IO) { Aiwa.brain.style() }; loaded = true; reload() }
    }

    private fun call(work: () -> com.aiwa.client.Brain.Outcome) {
        CoroutineScope(Dispatchers.Main).launch {
            val out = withContext(Dispatchers.IO) { work() }
            if (!out.ok) toastOnMain(applicationContext, "Refusé : ${out.error}")
            view = withContext(Dispatchers.IO) { Aiwa.brain.style() }
            reload()
        }
    }

    override fun fill() {
        val style = view
        if (style == null) { note(if (loaded) "Le cerveau ne répond pas." else "…"); return }
        note("Le super agent compte les mots que tu emploies et la longueur de tes phrases (jamais le texte lui-même), pour te répondre comme tu parles.")
        note(if (style.enabled) "Activé. ${style.count} phrases comptées." + (if (style.ready) "" else " Il en faut encore quelques-unes.") else "Désactivé.", if (style.enabled) Palette.GREEN else Palette.DIM)
        if (style.note.isNotEmpty()) note(style.note)
        entry(if (style.enabled) "Désactiver" else "Activer") { call { Aiwa.brain.styleSet(!style.enabled) } }
        entry("Tout oublier", "Remet les comptes à zéro.") { call { Aiwa.brain.styleClear() } }
    }
}
