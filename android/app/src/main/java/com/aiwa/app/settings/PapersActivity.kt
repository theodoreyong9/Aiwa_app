package com.aiwa.app.settings

import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.openUrl

/** « Papers »: the texts that say what Aiwa is. They are read on GitHub, in the product's repository. */
class PapersActivity : FloatActivity() {
    override val title = "Papers"

    override fun fill() {
        note("Ce qu'est Aiwa, par écrit.")
        for ((label, detail, file) in PAPERS) entry(label, detail) { openUrl(this, "$BASE/$file") }
    }

    companion object {
        private const val BASE = "https://github.com/theodoreyong9/Aiwa_app/blob/main/docs"
        private val PAPERS = listOf(
            Triple("Yellow paper", "Le protocole : comment les super agents se rencontrent et comment l'AIWA est émis.", "yellow-paper.md"),
            Triple("Valeur", "D'où vient la valeur de l'AIWA et pourquoi elle se brûle.", "valeur.md"),
            Triple("Readme", "Ce que fait le produit, écran par écran.", "readme.md"),
            Triple("Film", "Le scénario du film de présentation.", "film.md"),
        )
    }
}
