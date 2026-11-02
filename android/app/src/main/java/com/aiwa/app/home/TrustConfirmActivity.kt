package com.aiwa.app.home

import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette

/** Giving a visited profile access to the widget: asked every time, shown in full, never done without her word (by the button or by the voice). */
class TrustConfirmActivity : FloatActivity() {
    override val title = "Donner l'accès ?"
    private val repo: String? get() = intent.getStringExtra(EXTRA_REPO)

    override fun fill() {
        val r = repo
        if (r == null) { note("Aucun profil à l'écran."); return }
        note("Profil : $r", Palette.GOLD)
        note("Avec l'accès, sa page se comporte comme la tienne : ses emplacements de boutons fonctionnent et ses scripts peuvent utiliser le widget (réglages, micro, envois, scénarios). Fais-le seulement pour quelqu'un en qui tu as confiance. Tu peux le retirer à tout moment.")
        entry("Donner l'accès", null, Palette.GREEN) { TrustedProfiles.set(this, r, true); ScreenNow.reload?.invoke(); finish() }
        entry("Laisser fermé") { finish() }
    }

    companion object { const val EXTRA_REPO = "repo" }
}
