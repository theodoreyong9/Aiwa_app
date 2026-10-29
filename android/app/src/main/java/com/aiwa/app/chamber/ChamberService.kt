package com.aiwa.app.chamber

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewClientCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.home.ProfileSettings
import com.aiwa.app.home.HomeActivity
import com.aiwa.app.voice.ChamberSettings
import com.aiwa.app.voice.Speaker
import com.aiwa.app.web.WebHost
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The connection of the chamber, held by a foreground service: the page of the Store that finds the other phone (apps/web chambre.js) runs in a view without a screen, so the room stays open with the application
 * closed and the screen off. While a room is open the phone keeps the CPU (and the Wi-Fi) awake and shows a notification with a button to close it; the service stops with the room.
 * Android may still end a service on a phone with an aggressive battery saver: Aiwa should be allowed to run in the background.
 */
class ChamberService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private var web: WebView? = null
    private var ready = false
    private val queue = ArrayList<JSONObject>()
    private var lock: PowerManager.WakeLock? = null
    private var wifi: WifiManager.WifiLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Chambre", NotificationManager.IMPORTANCE_LOW))
        val notification = notification("Chambre ouverte")
        if (Build.VERSION.SDK_INT >= 34) startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(NOTIFICATION, notification)
        lock = (getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aiwa:chamber").also { it.setReferenceCounted(false); it.acquire(12 * 60 * 60 * 1000L) }
        @Suppress("DEPRECATION")
        wifi = (applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager).createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "aiwa:chamber").also { it.setReferenceCounted(false); it.acquire() }
        ChamberHost.runner = { cmd -> main.post { command(cmd) } }
        main.post { ensureWeb(); ChamberHost.drain().forEach { command(it) } }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_CLOSE) { command(JSONObject().put("cmd", "close")); return START_NOT_STICKY }
        main.post { ChamberHost.drain().forEach { command(it) } }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        ChamberHost.runner = null
        ChamberState.update(this, JSONObject())
        web?.destroy(); web = null
        try { lock?.release() } catch (err: Exception) { /* not held */ }
        try { wifi?.release() } catch (err: Exception) { /* not held */ }
        super.onDestroy()
    }

    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, HomeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val close = PendingIntent.getService(this, 1, Intent(this, ChamberService::class.java).setAction(ACTION_CLOSE), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.stat_notify_chat).setContentTitle("Chambre Aiwa").setContentText(text)
            .setContentIntent(open).addAction(Notification.Action.Builder(null, "Fermer la chambre", close).build()).setOngoing(true).build()
    }

    private fun command(cmd: JSONObject) {
        ensureWeb()
        if (ready) web?.evaluateJavascript("(window.aiwaChamber&&window.aiwaChamber.cmd($cmd))", null) else queue.add(cmd)
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun ensureWeb() {
        if (web != null) return
        val loader = WebViewAssetLoader.Builder().addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(this)).build()
        val view = WebView(applicationContext)
        with(view.settings) { javaScriptEnabled = true; domStorageEnabled = true; allowFileAccess = false; allowContentAccess = false; mediaPlaybackRequiresUserGesture = false }
        view.webViewClient = object : WebViewClientCompat() {
            override fun shouldInterceptRequest(v: WebView, request: WebResourceRequest): WebResourceResponse? = loader.shouldInterceptRequest(request.url)
            override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean = request.url.host != "appassets.androidplatform.net"
            override fun onPageFinished(v: WebView, url: String?) {
                ready = true
                queue.forEach { v.evaluateJavascript("(window.aiwaChamber&&window.aiwaChamber.cmd($it))", null) }
                queue.clear()
            }
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(view, "AiwaHost", setOf("https://appassets.androidplatform.net")) { _, message, _, isMainFrame, replyProxy -> if (isMainFrame) handle(message, replyProxy) }
        }
        web = view
        val repo = ProfileSettings.repo(this) ?: ""
        view.loadUrl(WebHost.pageUrl("chambre", "me=${Uri.encode(repo)}&name=${Uri.encode(repo.substringBefore('/'))}"))
    }

    private fun post(reply: JavaScriptReplyProxy, id: Int, value: JSONObject) {
        val payload = JSONObject().put("id", id).put("result", value).toString()
        main.post { reply.postMessage(payload) }
    }

    private fun handle(message: WebMessageCompat, reply: JavaScriptReplyProxy) {
        val json = try { JSONObject(message.data ?: return) } catch (err: Exception) { return }
        val id = json.optInt("id", 0)
        when (json.optString("cmd")) {
            "chamber-status" -> json.optJSONObject("status")?.let { status ->
                ChamberState.update(this, status)
                if (status.optString("mode") == "closed") main.postDelayed({ if (ChamberState.status.optString("mode") == "closed") stopSelf() }, 1500)
            }
            "chamber-active", "chamber-deliver", "chamber-note" -> CoroutineScope(Dispatchers.IO).launch {
                val path = when (json.optString("cmd")) { "chamber-active" -> "/api/chamber/active"; "chamber-note" -> "/api/chamber/note"; else -> "/api/chamber/deliver" }
                post(reply, id, Aiwa.brain.chamberCall(path, JSONObject(json.toString())))
            }
            "chamber-turn" -> turn(json, reply, id)
        }
    }

    // The words of the chamber: the brain makes what our agent says; if the person listens, both sides are said aloud (the other's voice lower).
    private fun turn(json: JSONObject, reply: JavaScriptReplyProxy, id: Int) {
        val app = applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val heard = json.optJSONObject("incoming")?.optString("text").orEmpty()
                if (ChamberState.status.optBoolean("ear") && heard.isNotBlank()) Speaker.speakAndWait(app, heard, 0.8f)
                val body = JSONObject(json.toString())
                val answer = Aiwa.brain.chamberCall("/api/chamber/turn", body)
                val say = answer.optString("say")
                if (ChamberState.status.optBoolean("ear") && answer.optBoolean("ok", false) && say.isNotBlank()) Speaker.speakNatural(app, say)
                post(reply, id, answer)
            } catch (err: Exception) {
                post(reply, id, JSONObject().put("ok", false).put("error", err.message ?: "?"))
            }
        }
    }

    companion object {
        private const val CHANNEL = "aiwa_chamber"
        private const val NOTIFICATION = 8301
        private const val ACTION_CLOSE = "com.aiwa.store.CHAMBER_CLOSE"
    }
}
