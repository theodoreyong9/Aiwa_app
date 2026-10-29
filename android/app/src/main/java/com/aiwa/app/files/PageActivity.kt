package com.aiwa.app.files

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.common.openUrl

/**
 * A production that is a page (one HTML file of a release) in the application's own window. The brain hands the page over (a release file is served as a download, not as a page). The page
 * is the person's own work, so it may run script; it has no access to files and no channel to the application, and a link to another address leaves for the browser.
 */
class PageActivity : ComponentActivity() {
    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repo = intent.getStringExtra(EXTRA_REPO).orEmpty()
        val tag = intent.getStringExtra(EXTRA_TAG).orEmpty()
        val root = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#10132E")) }
        val web = WebView(this).apply {
            setBackgroundColor(Color.WHITE)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mediaPlaybackRequiresUserGesture = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    if (request.url.host == "127.0.0.1") return false
                    if (request.url.scheme == "https") openUrl(this@PageActivity, request.url.toString())
                    return true
                }
            }
        }
        root.addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            WindowInsetsCompat.CONSUMED
        }
        setContentView(root)
        web.loadUrl(Aiwa.brain.pageAddress(repo, tag))
    }

    companion object {
        const val EXTRA_REPO = "repo"
        const val EXTRA_TAG = "tag"
        const val EXTRA_TITLE = "title"
    }
}
