package com.aiwa.app.home

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import java.net.HttpURLConnection
import java.net.URL

/**
 * A profile is the file `Profile/index.html` of a repository (a public one): Aiwa reads it from GitHub as it is and shows it in a WebView, the pictures and videos next to it read from the same folder.
 * Nothing has to be published (no GitHub Pages): the address of the file is enough.
 *
 * The page of the person herself is her HOME: it may run its own script, and it follows what she asks (see ProfileWatch: a new commit of her `Profile/` replaces the page on the screen within seconds).
 * The page of someone else runs no script of hers (HomeRuntime.lockScripts); in both, the slots of the page are filled by the application with the buttons of whoever looks (HomeBridge.kt).
 */
object ProfileView {
    private val REPO = Regex("[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
    fun valid(repo: String?): Boolean = repo != null && REPO.matches(repo)

    /** The folder of the profile; with a commit, THAT version (an address that never changes, so no cache of GitHub's can serve an older page: the plain address is kept five minutes). */
    fun base(repo: String, sha: String? = null): String = "https://raw.githubusercontent.com/$repo/${sha ?: "HEAD"}/Profile/"

    private val shown = java.util.WeakHashMap<WebView, Int>()

    /**
     * Reads the page in the background and shows it. `own`: the page of the person (scripts allowed; when there is none yet, the home of the application, with every button, is shown instead);
     * `sha`: a precise version. A page identical to the one already on the screen is not loaded again (nothing flickers when a check finds no change).
     */
    fun load(web: WebView, repo: String?, own: Boolean = false, sha: String? = null) {
        val main = Handler(Looper.getMainLooper())
        val context = web.context.applicationContext
        if (repo == null || !valid(repo)) { fallback(web, main, context, own, "Pas de profil : choisis le dépôt du profil dans les Réglages."); return }
        Thread {
            val html = try {
                val c = URL(base(repo, sha) + "index.html").openConnection() as HttpURLConnection
                c.connectTimeout = 10_000; c.readTimeout = 15_000
                if (c.responseCode == 200) c.inputStream.bufferedReader().use { it.readText() } else null
            } catch (err: Exception) { null }
            if (html == null) fallback(web, main, context, own, "Le profil de $repo n'est pas encore là (un dossier Profile/ public avec un index.html).")
            else show(web, main, base(repo, sha), if (own) html else HomeRuntime.lockScripts(html))
        }.start()
    }

    /** No profile to show: for the person, the home of the application (the page every account has, with all the buttons) and the word that says what to do; for a visitor, a plain word. */
    private fun fallback(web: WebView, main: Handler, context: Context, own: Boolean, word: String) {
        if (own) {
            val home = HomeRuntime.defaultPage(context)
            if (home.isNotEmpty()) { show(web, main, "about:blank", home.replace("__WORD__", word)); return }
        }
        show(web, main, null, "<html><body style='margin:0;background:#10132e;color:#d4d8ff;font:16px system-ui;display:grid;place-items:center;height:100vh;text-align:center;padding:24px'>$word</body></html>")
    }

    private fun show(web: WebView, main: Handler, base: String?, page: String) {
        main.post {
            try {
                val key = page.hashCode()
                if (shown[web] == key) return@post
                shown[web] = key
                web.loadDataWithBaseURL(base ?: "about:blank", page, "text/html", "utf-8", null)
            } catch (err: Exception) { }
        }
    }
}

/**
 * Follows the profile of the person: what GitHub says of the last commit that touched her `Profile/` folder (the feed of that folder, small, asked with the ETag so that « nothing new » costs next to nothing) is looked at every
 * fifteen seconds while the page is on the screen; a new commit calls `onVersion` with its identifier, and the page is read again at THAT version. The person says « change this » to the super agent, the session writes and pushes,
 * and the page changes under her eyes.
 */
class ProfileWatch(private val repo: String, private val onVersion: (String) -> Unit) {
    @Volatile private var running = false
    private var etag: String? = null
    private var last: String? = null

    fun start() {
        if (running || !ProfileView.valid(repo)) return
        running = true
        Thread {
            while (running) {
                poll()
                try { Thread.sleep(INTERVAL_MS) } catch (err: InterruptedException) { break }
            }
        }.start()
    }

    fun stop() { running = false }

    private fun poll() {
        try {
            val c = URL("https://github.com/$repo/commits/HEAD/Profile.atom").openConnection() as HttpURLConnection
            c.connectTimeout = 8_000; c.readTimeout = 10_000
            etag?.let { c.setRequestProperty("If-None-Match", it) }
            if (c.responseCode != 200) return        // 304: nothing new
            etag = c.getHeaderField("ETag")
            val body = c.inputStream.bufferedReader().use { it.readText() }
            val sha = Regex("Grit::Commit/([0-9a-f]{40})").find(body)?.groupValues?.get(1) ?: return
            if (sha != last) { last = sha; onVersion(sha) }
        } catch (err: Exception) { /* offline: the next check */ }
    }

    companion object { const val INTERVAL_MS = 15_000L }
}
