package com.aiwa.app.brain

import android.appwidget.AppWidgetManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aiwa.app.widget.AiwaWidget

/**
 * The set-up of the rights, asked together at the start: Termux, notifications, microphone, display over other apps, no battery stop. The one-time set-up, without opening the application. Two ways in, both from the widget: its CONFIGURATION activity (the launcher opens it by itself right after the widget is put on
 * the screen), and the Super agent cell, which says « Autoriser Aiwa » and opens this on a tap while the Termux permission is missing. It asks the Termux permission, then the notification
 * one (the lock-screen card), starts the brain, redraws the widget and closes. Whatever the answers, it finishes with RESULT_OK when it is the configuration: the widget is kept, and says
 * what is missing. No UI of its own: only the system's permission dialogs.
 */
class SetupActivity : ComponentActivity() {
    private val termuxPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { askNotifications() }
    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { askMic() }
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { askOverlay() }
    private val overlaySetting = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { askBattery() }
    private val batterySetting = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { finishSetup() }
    private val prefs by lazy { getSharedPreferences("aiwa_setup", MODE_PRIVATE) }

    /** The optional rights are asked at most three times each (a person who refuses three times is left alone); the Termux one and the notifications are asked until given. */
    private fun mayAsk(key: String): Boolean {
        val asks = prefs.getInt(key, 0)
        if (asks >= 3) return false
        prefs.edit().putInt(key, asks + 1).apply()
        return true
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        if (hasTermuxPermission(this)) askNotifications() else termuxPermission.launch(TERMUX_RUN_COMMAND_PERMISSION)
    }

    private fun askNotifications() {
        val needed = Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this, "android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED
        if (needed) notificationPermission.launch("android.permission.POST_NOTIFICATIONS") else askMic()
    }

    /** The microphone: without it the agent cannot hear. */
    private fun askMic() {
        if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED && mayAsk("mic")) micPermission.launch(android.Manifest.permission.RECORD_AUDIO) else askOverlay()
    }

    /** « Afficher par-dessus d'autres applis »: without it Android drops, without a word, the screens the agent opens from the background. */
    private fun askOverlay() {
        if (!Settings.canDrawOverlays(this) && mayAsk("overlay")) {
            android.widget.Toast.makeText(this, "Autorise « Afficher par-dessus d'autres applis » pour Aiwa : il pourra ouvrir ce que tu lui demandes à la voix.", android.widget.Toast.LENGTH_LONG).show()
            try { overlaySetting.launch(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))); return } catch (err: Exception) { }
        }
        askBattery()
    }

    /** Not to be stopped in the background: the voice, the brain and the updates need it. */
    private fun askBattery() {
        if (!Battery.isExempt(this) && mayAsk("battery")) {
            try { Battery.noteAsked(this); batterySetting.launch(Battery.requestIntent(this)); return } catch (err: Exception) { }
        }
        finishSetup()
    }

    private fun finishSetup() {
        val app = applicationContext
        if (hasTermuxPermission(app)) startBrainViaTermux(app)
        AiwaWidget.render(app, force = true)
        val widgetId = intent?.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        if (widgetId != AppWidgetManager.INVALID_APPWIDGET_ID) setResult(RESULT_OK, Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId))
        finish()
    }
}
