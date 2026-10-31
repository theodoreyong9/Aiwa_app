@file:OptIn(kotlinx.coroutines.FlowPreview::class)

package com.aiwa.app.brain

import android.app.Application
import com.aiwa.app.voice.ListenSettings
import com.aiwa.app.widget.AiwaWidget
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.sample
import kotlinx.coroutines.launch

/** Runs in every process Aiwa starts (widget, service, activity): the widget is drawn again whenever the state changes. */
class AiwaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        ListenSettings.resetForNewVersion(this)
        wakeAiwa(this)
        updateBrainWithTheBody()
        val app = this
        CoroutineScope(Dispatchers.Default).launch { Aiwa.state.sample(300).collect { AiwaWidget.render(app) } }
        // a diagram the super agent has just drawn (when the person turned the option on) is shown at once
        CoroutineScope(Dispatchers.Default).launch { Aiwa.state.collect { com.aiwa.app.web.DiagramShow.maybeOpen(app, it.status) } }
    }

    /**
     * The body and the brain go together: the first time a new build of the application runs, the brain is asked, at once, to bring its checkout up to date and restart (the start script does both), instead
     * of waiting for its own hourly check or for the keep-alive service to notice. Once per build.
     */
    private fun updateBrainWithTheBody() {
        val prefs = getSharedPreferences("aiwa_setup", MODE_PRIVATE)
        val build = try { packageManager.getPackageInfo(packageName, 0).versionName } catch (err: Exception) { null } ?: return
        if (prefs.getString("brain_for_build", null) == build) return
        prefs.edit().putString("brain_for_build", build).apply()
        if (hasTermuxPermission(this)) startBrainViaTermux(this, forceRestart = true)
    }
}
