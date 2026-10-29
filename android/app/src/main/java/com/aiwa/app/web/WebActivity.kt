package com.aiwa.app.web

import android.Manifest
import android.content.ContentValues
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.view.ViewGroup
import android.webkit.GeolocationPermissions
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.openUrl
import com.aiwa.app.home.ProfileActivity
import com.aiwa.app.home.ProfileView
import com.aiwa.app.voir.VoirLinks
import com.aiwa.app.voir.VoirSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * A page of the web app in a window: the wallet, or « Voir » (nearby, by link, by QR code, the favourites). The page is the web app's; this activity only hosts it. What the page may ask of the phone goes
 * through ONE channel (the web message listener `AiwaHost`, restricted to the page's own origin): the secrets (the wallet's 12 words, kept in the Keystore), a text file into Downloads, and
 * the profile to open in full screen. The camera (to read a QR code) and a coarse position (« Voir » by proximity) are asked of Android once, and only the app's own page gets them.
 *
 * Links that leave the page open in the browser.
 */
class WebActivity : ComponentActivity() {
    private lateinit var web: WebView
    private val secrets by lazy { SecretStore(this) }

    // The page asked for the camera before the phone had given it: the request waits here for the answer.
    private var cameraRequest: PermissionRequest? = null
    private var geoAsk: Pair<String, GeolocationPermissions.Callback>? = null
    private val locationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        geoAsk?.let { (origin, callback) -> callback.invoke(origin, granted, false) }
        geoAsk = null
    }
    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        val request = cameraRequest ?: return@registerForActivityResult
        cameraRequest = null
        if (granted) request.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) else request.deny()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        web.setBackgroundColor(Color.parseColor("#F3F2FA"))
        val root = FrameLayout(this)
        root.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        setContentView(root)
        // Edge-to-edge is the default from Android 15: keep the page out of the status and navigation bars.
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        WebHost.prepare(web, this) { openUrl(this, it.toString()) }
        web.webChromeClient = object : WebChromeClient() {
            override fun onPermissionRequest(request: PermissionRequest) {
                // Only the app's own page, only the camera.
                val own = request.origin.toString().startsWith(WebHost.ORIGIN)
                val onlyCamera = request.resources.isNotEmpty() && request.resources.all { it == PermissionRequest.RESOURCE_VIDEO_CAPTURE }
                if (!own || !onlyCamera) { request.deny(); return }
                runOnUiThread {
                    if (ContextCompat.checkSelfPermission(this@WebActivity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) request.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
                    else { cameraRequest?.deny(); cameraRequest = request; cameraPermission.launch(Manifest.permission.CAMERA) }
                }
            }

            override fun onGeolocationPermissionsShowPrompt(origin: String, callback: GeolocationPermissions.Callback) {
                if (!origin.startsWith(WebHost.ORIGIN)) { callback.invoke(origin, false, false); return }
                runOnUiThread {
                    if (ContextCompat.checkSelfPermission(this@WebActivity, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) callback.invoke(origin, true, false)
                    else { geoAsk?.let { (o, c) -> c.invoke(o, false, false) }; geoAsk = origin to callback; locationPermission.launch(Manifest.permission.ACCESS_COARSE_LOCATION) }
                }
            }

            override fun onPermissionRequestCanceled(request: PermissionRequest) { if (cameraRequest == request) cameraRequest = null }
        }
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "AiwaHost", setOf(WebHost.ORIGIN)) { _, message, _, isMainFrame, replyProxy -> if (isMainFrame) handle(message, replyProxy) }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // The page closes what is open on top first; only then does the activity.
                web.evaluateJavascript("(window.aiwaHostBack ? window.aiwaHostBack() : false)") { handled -> if (handled != "true") finish() }
            }
        })
        open()
    }

    private fun open() {
        when (intent.getStringExtra(EXTRA_PAGE)) {
            "voir" -> {
                val mode = intent.getStringExtra(EXTRA_MODE) ?: "proche"
                val repo = com.aiwa.app.home.ProfileSettings.repo(this) ?: Aiwa.state.value.repo ?: ""
                CoroutineScope(Dispatchers.Main).launch {
                    // the links of what the person has to show, read from the releases of her repository (nothing is published unless she turned « Visible » on)
                    val links = withContext(Dispatchers.IO) { if (repo.isEmpty()) JSONArray() else VoirLinks.of(repo) }
                    val query = "m=$mode&pub=${if (VoirSettings.on(this@WebActivity) && links.length() > 0) "1" else "0"}&repo=${Uri.encode(repo)}&links=${Uri.encode(links.toString())}"
                    web.loadUrl(WebHost.pageUrl("voir", query))
                }
            }
            else -> {
                val coffee = intent.getStringExtra(EXTRA_COFFEE)
                web.loadUrl(WebHost.pageUrl("wallet", if (coffee != null) "coffee=${Uri.encode(coffee)}&repo=${Uri.encode(intent.getStringExtra(EXTRA_REPO).orEmpty())}" else if (intent.getBooleanExtra(EXTRA_WALL, false)) "wall=1" + (intent.getStringExtra(EXTRA_CARD)?.takeIf { Regex("[0-9a-f]{64}").matches(it) }?.let { "&card=$it" } ?: "") else ""))
            }
        }
    }

    override fun onDestroy() { web.destroy(); super.onDestroy() }

    private fun handle(message: WebMessageCompat, reply: JavaScriptReplyProxy) {
        val json = try { JSONObject(message.data ?: return) } catch (err: Exception) { return }
        val id = json.optInt("id", 0)
        when (json.optString("cmd")) {
            "favorites" -> json.optJSONArray("list")?.let { com.aiwa.app.voir.VoirFavorites.save(this, it) }
            "save" -> saveToDownloads(json.optString("name"), json.optString("mime", "application/json"), json.optString("text"))
            "profile" -> {
                val list = json.optJSONArray("repos")
                val repos = if (list == null) emptyList() else (0 until list.length()).map { list.optString(it) }.filter { ProfileView.valid(it) }
                val keys = json.optJSONArray("pubs")
                val pubs = repos.indices.map { keys?.optString(it).orEmpty().takeIf { k -> Regex("[0-9a-f]{64}").matches(k) } ?: "" }
                if (repos.isNotEmpty()) ProfileActivity.open(this, repos, json.optInt("index", 0), pubs)
            }
            "secret-get" -> respond(reply, id) { JSONObject().put("value", secrets.get(secretName(json)) ?: JSONObject.NULL) }
            "secret-set" -> respond(reply, id) { secrets.set(secretName(json), json.getString("value")); JSONObject() }
            "secret-delete" -> respond(reply, id) { secrets.delete(secretName(json)); JSONObject() }
        }
    }

    private fun secretName(json: JSONObject): String {
        val name = json.optString("key")
        require(Regex("[a-z0-9-]{1,40}").matches(name)) { "not a name this app keeps secrets under" }
        return name
    }

    // What goes back to the page, with the id it asked with: { id, result } or { id, error }.
    private fun post(reply: JavaScriptReplyProxy, id: Int, field: String, value: Any) {
        val payload = JSONObject().put("id", id).put(field, value).toString()
        runOnUiThread { reply.postMessage(payload) }
    }

    // A failure goes back as an error, never silently.
    private fun respond(reply: JavaScriptReplyProxy, id: Int, work: () -> JSONObject) {
        try { post(reply, id, "result", work()) } catch (err: Exception) { post(reply, id, "error", err.message ?: "failed") }
    }

    // A text file into the Downloads folder (MediaStore, no storage permission on Android 10+).
    private fun saveToDownloads(name: String, mime: String, text: String) {
        if (!Regex("[A-Za-z0-9._-]{1,100}").matches(name) || Build.VERSION.SDK_INT < 29) {
            Toast.makeText(this, "Impossible d'enregistrer ce fichier : copie-le plutôt.", Toast.LENGTH_LONG).show()
            return
        }
        try {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            }
            val uri: Uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values) ?: throw IllegalStateException("refusé")
            contentResolver.openOutputStream(uri)?.use { it.write(text.toByteArray(Charsets.UTF_8)) } ?: throw IllegalStateException("refusé")
            Toast.makeText(this, "Enregistré dans Téléchargements : $name", Toast.LENGTH_LONG).show()
        } catch (err: Exception) {
            Toast.makeText(this, "Impossible d'enregistrer : ${err.message}. Copie le fichier plutôt.", Toast.LENGTH_LONG).show()
        }
    }

    companion object {
        const val EXTRA_PAGE = "page"       // wallet | voir
        const val EXTRA_MODE = "mode"       // voir: proche | lien | qr | favoris
        const val EXTRA_WALL = "wall"       // wallet: the wall of the donors (what others sent)
        const val EXTRA_CARD = "card"       // wallet: whose wall (the signed card of the person; none: her own)
        const val EXTRA_COFFEE = "coffee"   // wallet: the signed card of the person to send a coffee to
        const val EXTRA_REPO = "repo"

        fun wall(context: android.content.Context, card: String? = null) {
            context.startActivity(Intent(context, WebActivity::class.java).putExtra(EXTRA_PAGE, "wallet").putExtra(EXTRA_WALL, true).apply { if (card != null) putExtra(EXTRA_CARD, card) }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }

        fun wallet(context: android.content.Context, coffee: String? = null, repo: String? = null) {
            context.startActivity(Intent(context, WebActivity::class.java).putExtra(EXTRA_PAGE, "wallet").apply { if (coffee != null) putExtra(EXTRA_COFFEE, coffee); if (repo != null) putExtra(EXTRA_REPO, repo) }.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }
}
