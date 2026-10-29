package com.aiwa.app.home

import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import com.aiwa.app.brain.Aiwa

/**
 * The newest video of the product's own repository, played in a loop (muted) behind the page of the person's profile, inside the page: a video element laid under the content by the application, so
 * the page itself does not have to ask for it. It is read from the releases (the brain asks GitHub, conditionally), and put in the page again at each load of the page and when a newer video exists.
 * A page whose own background is opaque hides it: that is her page's choice.
 */
object ProfileVideo {
    @Volatile private var url: String? = null

    /** Reads the newest video, then puts it in the page on the screen. */
    fun refresh(web: WebView, repo: String = ProfileSettings.DEFAULT_REPO) {
        Thread {
            val newest = try { Aiwa.brain.files(repo)?.items?.get("video")?.firstOrNull { it.url.isNotEmpty() } } catch (err: Exception) { null }
            if (newest != null && newest.url != url) { url = newest.url; Handler(Looper.getMainLooper()).post { inject(web) } }
        }.start()
    }

    /** Puts the video in the page (nothing when no video is known yet; the same video is not put twice). */
    fun inject(web: WebView) {
        val address = url ?: return
        val quoted = org.json.JSONObject.quote(address)
        web.evaluateJavascript(
            "(function(u){var v=document.getElementById('aiwa-profile-video');if(v&&v.dataset.src===u)return;if(v)v.remove();" +
                "v=document.createElement('video');v.id='aiwa-profile-video';v.dataset.src=u;v.src=u;v.muted=true;v.loop=true;v.autoplay=true;v.setAttribute('playsinline','');" +
                "v.style.cssText='position:fixed;left:0;top:0;width:100%;height:100%;object-fit:cover;z-index:-1;pointer-events:none;background:#10132e';" +
                "(document.body||document.documentElement).prepend(v);var p=v.play();if(p&&p.catch)p.catch(function(){});})($quoted)", null)
    }
}
