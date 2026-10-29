package com.aiwa.app.settings

import android.content.Intent
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.openUrl
import com.aiwa.app.files.VideoPlayerActivity

/** « Papers »: the film of Aiwa (played here) and the texts that say what Aiwa is (read on GitHub, in the product's repository). */
class PapersActivity : FloatActivity() {
    override val title = "Papers"

    override fun fill() {
        note("Ce qu'est Aiwa, en film et par écrit.")
        entry("Film", "La dernière version de la vidéo d'Aiwa (1 min 18). Musique : Living Voyage, Kevin MacLeod, CC BY 4.0.") {
            startActivity(Intent(this, VideoPlayerActivity::class.java).putExtra(VideoPlayerActivity.EXTRA_URL, "$RAW/film.mp4").putExtra(VideoPlayerActivity.EXTRA_TITLE, "Aiwa"))
        }
        for ((label, detail, file) in PAPERS) entry(label, detail) { openUrl(this, "$BLOB/$file") }
    }

    companion object {
        private const val RAW = "https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/docs"
        private const val BLOB = "https://github.com/theodoreyong9/Aiwa_app/blob/main/docs"
        private val PAPERS = listOf(
            Triple("Yellow paper", "Le protocole : événements signés, minage, conservation, règles formelles.", "yellow-paper.md"),
            Triple("Valeur", "L'ontologie de la valeur.", "valeur.pdf"),
            Triple("Readme", "Ce que fait le produit, écran par écran.", "readme.md"),
        )
    }
}
