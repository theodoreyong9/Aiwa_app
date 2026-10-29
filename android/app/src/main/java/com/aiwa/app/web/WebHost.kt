package com.aiwa.app.web

import android.annotation.SuppressLint
import android.content.Context
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewClientCompat

/**
 * The web app (wallet, voir, chambre, and the home runtime) is part of the APK: served by the application itself at https://appassets.androidplatform.net/, never from a file:// address, so that a
 * page has a real origin (IndexedDB for the wallet, module scripts, fetch). What a page may ask of the phone goes through ONE channel, a web message listener restricted to that origin.
 */
object WebHost {
    const val ORIGIN = "https://appassets.androidplatform.net"

    fun pageUrl(page: String, query: String = ""): String = "$ORIGIN/assets/web/$page.html" + (if (query.isEmpty()) "" else "?$query")

    fun loader(context: Context): WebViewAssetLoader = WebViewAssetLoader.Builder().addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(context)).build()

    /** A page of the web app in a view: scripts, storage, no access to files. `leave` is called with a link that leaves the app (only https goes on, to the browser). */
    @SuppressLint("SetJavaScriptEnabled")
    fun prepare(web: WebView, context: Context, leave: (android.net.Uri) -> Unit) {
        val loader = loader(context)
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true          // IndexedDB: the wallet's journal
            allowFileAccess = false
            allowContentAccess = false
            setSupportMultipleWindows(false)
            mediaPlaybackRequiresUserGesture = false      // the camera's preview starts by itself
            setGeolocationEnabled(true)
        }
        web.webViewClient = object : WebViewClientCompat() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? = loader.shouldInterceptRequest(request.url)

            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                // A frame inside the page navigates as a browser frame does: it never makes the phone open anything. Only a link of the page itself (the main frame) leaves for the browser, and only over https.
                if (!request.isForMainFrame || request.url.host == "appassets.androidplatform.net") return false
                if (request.url.scheme == "https") leave(request.url)
                return true
            }
        }
    }
}
