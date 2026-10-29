package com.aiwa.app.widget

import android.os.Bundle
import androidx.activity.ComponentActivity
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.common.toastOnMain
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * The « Rapport » button: the super agent reads all that happened (sessions, repositories, new productions, workflows, questions, scenarios, the chamber) and says it aloud with one useful idea.
 * No window: the agent's words are spoken as soon as they are there (KeepAliveService), or by the open agent.
 */
class ReportActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = applicationContext
        wakeAiwa(app)
        toastOnMain(app, "Le super agent prépare le rapport…")
        CoroutineScope(Dispatchers.IO).launch {
            if (!ensureBrain(app)) { toastOnMain(app, "Le cerveau ne répond pas."); return@launch }
            val out = com.aiwa.app.brain.Aiwa.brain.agentReport()
            if (!out.ok) toastOnMain(app, out.error ?: "Le rapport n'est pas parti.")
        }
        finish()
    }
}
