package com.aiwa.app.home

import android.app.Activity
import android.content.Intent
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.brain.Link
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.settings.ClaudeLoginActivity
import com.aiwa.app.settings.GithubConnectActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * What the application asks for, in order, each time it is opened until it is done: first CLAUDE (essential: nothing is made without it, the window opens by itself while the account is not connected, once
 * per opening), then GITHUB (the repositories need it: asked once per opening until it is connected, « Plus tard » only waits for the next opening). The next window comes when the previous one closes (the home asks again as it comes back to the front).
 */
object Onboarding {
    private var claudeAskedThisRun = false
    private var githubAskedThisRun = false

    fun next(activity: Activity) {
        CoroutineScope(Dispatchers.Main).launch {
            val login = withContext(Dispatchers.IO) {
                if (!ensureBrain(activity.applicationContext)) return@withContext null
                BrainSync.refresh()
                if (Aiwa.state.value.link != Link.UP) null else Aiwa.brain.loginCheck().json.optString("claude_login", "unknown")
            } ?: return@launch
            if (activity.isFinishing || activity.isDestroyed) return@launch
            if (login != "ok") {
                if (!claudeAskedThisRun) { claudeAskedThisRun = true; activity.startActivity(Intent(activity, ClaudeLoginActivity::class.java)) }
                return@launch       // GitHub comes after, once Claude is connected
            }
            if (Aiwa.state.value.status?.githubToken != true && !githubAskedThisRun) {
                githubAskedThisRun = true
                activity.startActivity(Intent(activity, GithubConnectActivity::class.java))
            }
        }
    }
}
