package com.aiwa.app.voice

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.Scenario
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * The « Super agent » button of the widget: opens the conversation with the super agent, or closes it. A no-UI trampoline, because Android starts a microphone service only from a visible tap:
 * the first tap asks for the microphone if needed, and after that everything goes by voice. With a scenario, the double of that scenario is the one that is talked to.
 */
class AgentToggleActivity : ComponentActivity() {
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) open() else toastOnMain(applicationContext, "Sans la permission du micro, le super agent ne peut pas écouter.")
        finish()
    }

    private fun open() {
        val scenario = pending
        pending = null
        VoiceService.openAgent(applicationContext, scenario)
        CoroutineScope(Dispatchers.IO).launch { ensureBrain(applicationContext) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        when {
            // The service knows whether it listens; the brain's flag can be stale
            VoiceService.instance?.isAgentOpen() == true -> VoiceService.closeAgent(applicationContext)
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED -> { micPermission.launch(Manifest.permission.RECORD_AUDIO); return }
            else -> open()
        }
        finish()
    }

    companion object {
        /** The scenario to talk to as soon as the super agent opens (chosen on the scenario's screen). */
        @Volatile var pending: Scenario? = null
    }
}
