package com.aiwa.app.widget

import android.content.Intent
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.web.WebActivity

/** Search: finding someone by a link or by a QR code (the Voir screen). */
class SearchHubActivity : FloatActivity() {
    override val title = "Chercher"

    private fun voir(mode: String) { startActivity(Intent(this, WebActivity::class.java).putExtra(WebActivity.EXTRA_PAGE, "voir").putExtra(WebActivity.EXTRA_MODE, mode)); finish() }

    override fun fill() {
        entry("Lien", "partager ou ouvrir un lien de profil") { voir("lien") }
        entry("QR code", "montrer ou lire un QR code de profil") { voir("qr") }
    }
}
