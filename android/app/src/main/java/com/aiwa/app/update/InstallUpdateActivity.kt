package com.aiwa.app.update

import android.os.Bundle
import androidx.activity.ComponentActivity
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.widget.AiwaWidget

/**
 * The « Mise à jour » of the widget's top bar: one tap opens the system's installer on the build that was downloaded in the background (Android asks for its own « Installer »).
 * With none downloaded (installed meanwhile, or not yet there), it looks again. No UI of its own.
 */
class InstallUpdateActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = applicationContext
        val file = AppUpdater.readyFile(app)
        if (file != null && !app.packageManager.canRequestPackageInstalls()) {
            // Asked once: the setting where Aiwa may install apps. The person comes back and touches the button again.
            toastOnMain(app, "Autorise Aiwa à installer des applications, puis reviens toucher « Mise à jour » sur le widget.")
            startActivity(android.content.Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, android.net.Uri.parse("package:${app.packageName}")).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
        } else if (file != null) startActivity(AppUpdater.installIntent(app, file))
        else {
            Aiwa.update { it.copy(appUpdateReady = false) }
            toastOnMain(app, "Aucune mise à jour téléchargée : je cherche.")
            AppUpdater.update(app)
            AiwaWidget.render(app, force = true)
        }
        finish()
    }
}
