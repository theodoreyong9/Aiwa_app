package com.aiwa.app.voice

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.widget.AiwaWidget
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * The « Écoute » cell: the switch of the permanent listening. On, it starts the small model that waits for the call of the super agent (the window is on screen for a moment, which is what Android
 * asks to start a microphone service); off, it stops it. It is closed at each installation and each update. A no-UI trampoline.
 */
class EarToggleActivity : ComponentActivity() {
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) turnOn() else toastOnMain(applicationContext, "Écoute permanente : sans la permission du micro, rien à faire.")
        finish()
    }

    private fun turnOn() {
        ListenSettings.setEnabled(this, true)
        VoiceService.start(this)
        refreshWidget()
    }

    private fun refreshWidget() {
        val app = applicationContext
        CoroutineScope(Dispatchers.Default).launch {
            AiwaWidget.render(app, force = true)
            delay(1_500)      // the service has started by then: the cell shows it
            AiwaWidget.render(app, force = true)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        val running = VoiceService.instance != null
        when {
            ListenSettings.enabled(this) && running -> {
                ListenSettings.setEnabled(this, false)
                VoiceService.stop(this)
                Aiwa.update { it.copy(listening = false) }
                refreshWidget()
            }
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED -> { micPermission.launch(Manifest.permission.RECORD_AUDIO); return }
            else -> turnOn()
        }
        finish()
    }
}
