package com.aiwa.app.brain

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.aiwa.app.voice.VoiceService

/**
 * The keep-alive service started only when the application was opened, so after a restart of the phone or an update the process was cold again until then. Starting it on boot and on
 * package replacement closes that gap.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        try { ContextCompat.startForegroundService(context, Intent(context, KeepAliveService::class.java)) } catch (err: Exception) { /* background start refused: the next opening or tap does it */ }
        // The ear too, when the phone allows a microphone service to start from here (older Androids); otherwise it starts the next time Aiwa is opened
        try { VoiceService.ensureStarted(context) } catch (err: Exception) { }
    }
}
