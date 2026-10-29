package com.aiwa.app.home

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.aiwa.app.brain.wakeAiwa
import com.aiwa.app.voice.ListenSettings
import com.aiwa.app.voice.VoiceService
import com.aiwa.app.widget.WidgetPin

/**
 * The home of the application, the one the icon opens: the page of the person (the `Profile/` folder of her repository), drawn as she wants, with the buttons of Aiwa where she put slots. When she has none yet,
 * the home of the application: every button, and a word that says how to make her own. It follows her `Profile/` on GitHub: a new commit replaces the page on the screen within seconds (a change asked of the
 * super agent shows at once). Her page may run its own script (WebGL, her design); it has no file access and opens nothing but https / mail / tel links.
 */
class HomeActivity : ComponentActivity() {
    private lateinit var web: WebView
    private var watch: ProfileWatch? = null
    private var watched: String? = null

    // The ear listens whenever Aiwa is opened and the microphone is allowed; it asks for the microphone once, at the first opening
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if (granted) VoiceService.ensureStarted(applicationContext) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        wakeAiwa(applicationContext)
        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#10132E"))
            settings.javaScriptEnabled = true
            settings.javaScriptCanOpenWindowsAutomatically = false
            settings.allowFileAccess = false
            settings.mediaPlaybackRequiresUserGesture = false      // the video behind a profile starts by itself (muted)
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(v: WebView, request: WebResourceRequest): Boolean = HomeRuntime.openExternal(this@HomeActivity, request)
                override fun onPageFinished(v: WebView, url: String?) { HomeRuntime.inject(v) }
            }
        }
        HomeRuntime.attach(web, true) { ProfileSettings.repo(this) }
        val root = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#10132E")) }
        root.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT).apply { bottomMargin = ProfileBar.height(this@HomeActivity) })
        // her page is the profile and nothing else; the keys under it are the application's: the matches around her, her room, her wallet (the coffees she is offered), the wall of those who offered, the widget
        val bar = ProfileBar.build(this, listOf(
            ProfileBar.Spec("🤝", "Match", ProfileBar.VIOLET) { startActivity(Intent(this, com.aiwa.app.web.WebActivity::class.java).putExtra(com.aiwa.app.web.WebActivity.EXTRA_PAGE, "voir").putExtra(com.aiwa.app.web.WebActivity.EXTRA_MODE, "proche")) },
            ProfileBar.Spec("🚪", "Chambre", ProfileBar.BLUE) { startActivity(Intent(this, com.aiwa.app.chamber.ChamberActivity::class.java)) },
            ProfileBar.Spec("☕", "Café", ProfileBar.GOLD) { com.aiwa.app.web.WebActivity.wallet(this) },
            ProfileBar.Spec("🏆", "Mur", ProfileBar.GREEN) { com.aiwa.app.web.WebActivity.wall(this) },
            ProfileBar.Spec("✦", "Widget", ProfileBar.WHITE) { HomeRuntime.openPanel(web) },
        ))
        root.addView(bar.view, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, android.view.Gravity.BOTTOM))
        setContentView(root)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        ProfileView.load(web, ProfileSettings.repo(this), own = true)
    }

    override fun onResume() {
        super.onResume()
        startWatch()
        startEar()
        // The widget is asked for at every opening while there is none (the system's window, one tap on « Ajouter »), once the screen is really in front and has settled.
        window.decorView.postDelayed({ if (!isFinishing && !isDestroyed) WidgetPin.offerOnce(this) }, 800)
        // Claude first (essential), then GitHub (once): see Onboarding
        window.decorView.postDelayed({ if (!isFinishing && !isDestroyed) Onboarding.next(this) }, 1500)
    }

    override fun onPause() { watch?.stop(); watch = null; super.onPause() }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        ProfileView.load(web, ProfileSettings.repo(this), own = true)
    }

    private fun startWatch() {
        val repo = ProfileSettings.repo(this)
        if (!ProfileView.valid(repo)) { watch?.stop(); watch = null; return }
        if (watch != null && watched == repo) return
        watch?.stop()
        if (watched != repo) { watched = repo; ProfileView.load(web, repo, own = true) }       // another repository chosen in the settings
        watch = ProfileWatch(repo!!) { sha -> runOnUiThread { ProfileView.load(web, repo, own = true, sha = sha) } }.also { it.start() }
    }

    private fun startEar() {
        if (!ListenSettings.enabled(this)) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) { VoiceService.ensureStarted(applicationContext); return }
        val prefs = getSharedPreferences("aiwa_hints", MODE_PRIVATE)
        if (!prefs.getBoolean("mic_asked", false)) { prefs.edit().putBoolean("mic_asked", true).apply(); micPermission.launch(Manifest.permission.RECORD_AUDIO) }
    }

    override fun onDestroy() {
        watch?.stop()
        HomeRuntime.release(web)
        web.destroy()
        super.onDestroy()
    }
}
