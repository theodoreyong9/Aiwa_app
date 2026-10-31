package com.aiwa.app.voir

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.view.ViewGroup
import android.webkit.GeolocationPermissions
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.aiwa.app.home.ProfileSettings
import com.aiwa.app.home.ProfileView
import com.aiwa.app.web.WebHost
import org.json.JSONObject

/**
 * Who is around is noted by itself while Aiwa is open: the page of the zone runs in a view of one pixel, finds the people of the zone, and what it meets (the profile, and the list that profile saw) is kept for the
 * week by SwipeData; the list of what this phone crossed goes into the person's own profile repository (SeenPublisher). Nothing is shown: « Swipe » is where it can be seen. It only works while the screen
 * of Aiwa is in front, and only with the position of the phone (asked once, at the first time).
 */
class ZoneCollector(private val activity: ComponentActivity, private val container: FrameLayout) {
    private var web: WebView? = null
    private var geoAsk: Pair<String, GeolocationPermissions.Callback>? = null
    private val permission = activity.registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        geoAsk?.let { (origin, callback) -> callback.invoke(origin, granted, false) }
        geoAsk = null
    }

    fun start() {
        val repo = ProfileSettings.repo(activity)
        if (!VoirSettings.on(activity) || !ProfileView.valid(repo)) return
        web?.let { it.onResume(); return }
        val view = WebView(activity)
        WebHost.prepare(view, activity) { }
        view.webChromeClient = object : WebChromeClient() {
            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                if (!origin.startsWith(WebHost.ORIGIN)) { callback.invoke(origin, false, false); return }
                activity.runOnUiThread {
                    if (ContextCompat.checkSelfPermission(activity, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) callback.invoke(origin, true, false)
                    else { geoAsk?.let { (o, c) -> c.invoke(o, false, false) }; geoAsk = origin to callback; permission.launch(Manifest.permission.ACCESS_COARSE_LOCATION) }
                }
            }
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(view, "AiwaHost", setOf(WebHost.ORIGIN)) { _, message, _, isMainFrame, _ ->
                if (!isMainFrame) return@addWebMessageListener
                val json = try { JSONObject(message.data ?: return@addWebMessageListener) } catch (err: Exception) { return@addWebMessageListener }
                if (json.optString("cmd") == "seen") SwipeBridge.seen(activity, json)
            }
        }
        container.addView(view, FrameLayout.LayoutParams(1, 1))
        web = view
        view.loadUrl(WebHost.pageUrl("voir", "m=proche&pub=1&repo=${Uri.encode(repo!!)}&links=${Uri.encode("[]")}"))
    }

    fun pause() { web?.onPause() }

    fun destroy() {
        web?.let { (it.parent as? ViewGroup)?.removeView(it); it.destroy() }
        web = null
    }
}
