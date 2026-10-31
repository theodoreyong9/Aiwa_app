package com.aiwa.app.home

import android.content.Intent
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.web.WebActivity

/** « Give »: what one gives to a person, or opens with her, in one window: her room (Chambre), a coffee (Café), what she received (Mur). On her own page: her room and her wall. */
class GiveActivity : FloatActivity() {
    override val title = "Give"
    private val repo: String? get() = intent.getStringExtra(EXTRA_REPO)
    private val pub: String get() = intent.getStringExtra(EXTRA_PUB).orEmpty()

    override fun fill() {
        val visited = repo
        note(if (visited == null) "Chez toi" else visited, Palette.GOLD)
        entry("Chambre", if (visited == null) "Ta chambre" else "Entrer dans sa chambre") {
            startActivity(Intent(this, com.aiwa.app.chamber.ChamberActivity::class.java).apply { if (visited != null) putExtra(com.aiwa.app.chamber.ChamberActivity.EXTRA_REPO, visited) })
            finish()
        }
        entry("Café", "Offrir un café") {
            when {
                visited == null -> toastOnMain(this, "Le café s'offre à quelqu'un d'autre : ouvre son profil.")
                !com.aiwa.app.home.CoffeeSettings.walletConnected(this) -> toastOnMain(this, "Le wallet n'est pas connecté : connecte-le (widget, Wallet) pour offrir un café.")
                pub.isEmpty() -> toastOnMain(this, "Cette personne n'a pas donné sa carte dans « Voir » : pas de café.")
                else -> { WebActivity.wallet(this, pub, visited); finish() }
            }
        }
        entry("Mur", "Ce que la personne a reçu") {
            when {
                visited == null -> { WebActivity.wall(this); finish() }
                pub.isEmpty() -> toastOnMain(this, "Cette personne n'a pas donné sa carte dans « Voir » : pas de mur.")
                else -> { WebActivity.wall(this, pub); finish() }
            }
        }
    }

    companion object {
        const val EXTRA_REPO = "repo"
        const val EXTRA_PUB = "pub"
    }
}
