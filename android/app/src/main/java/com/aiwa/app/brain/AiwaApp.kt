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
        val app = this
        CoroutineScope(Dispatchers.Default).launch { Aiwa.state.sample(300).collect { AiwaWidget.render(app) } }
    }
}
