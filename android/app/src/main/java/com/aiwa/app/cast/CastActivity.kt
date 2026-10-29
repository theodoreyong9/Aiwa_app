package com.aiwa.app.cast

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.ensureBrain
import com.aiwa.app.common.FloatActivity
import com.aiwa.app.common.Palette
import com.aiwa.app.common.toastOnMain
import com.aiwa.client.Dlna
import com.aiwa.client.Production
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * « Cast TV »: sends a video to a television (or any DLNA / UPnP renderer) of the same Wi-Fi. First the video (the one that was asked for, or one of the vidéos of the repositories), then the
 * television. The service does the rest: it downloads the video, serves it itself over http (a television reads that better than a github.com release address) and tells the renderer to
 * play it. If nothing is found, the screen cast of Android is offered.
 */
class CastActivity : FloatActivity() {
    override val title = "Cast TV"
    private var videos: List<Production>? = null
    private var chosen: Production? = null
    private var devices: List<Dlna.Renderer>? = null
    private var searching = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val url = intent.getStringExtra(EXTRA_URL).orEmpty()
        if (url.isNotBlank()) { chosen = Production("", "video", "", intent.getStringExtra(EXTRA_TITLE).orEmpty().ifBlank { "Vidéo Aiwa" }, "", 0, url, 0); search(); reload(); return }
        CoroutineScope(Dispatchers.Main).launch {
            videos = withContext(Dispatchers.IO) { ensureBrain(applicationContext); Aiwa.brain.files(null)?.items?.get("video").orEmpty() }
            reload()
        }
    }

    override fun fill() {
        val video = chosen
        if (video == null) {
            val list = videos
            if (list == null) { note("Je cherche tes vidéos…"); return }
            if (list.isEmpty()) { note("Aucune vidéo pour l'instant. Demande-en une au super agent : elle part en release du dépôt."); return }
            note("Quelle vidéo ?")
            list.take(20).forEach { v -> entry(v.title, v.repoName) { chosen = v; search(); reload() } }
            return
        }
        note(video.title, Palette.GOLD)
        val found = devices
        when {
            searching || found == null -> note("Je cherche les télévisions du Wi-Fi…")
            found.isEmpty() -> {
                note("Aucune TV trouvée sur ce Wi-Fi. Le partage d'écran d'Android peut la trouver autrement.")
                entry("Chercher encore") { search(); reload() }
                entry("Partage d'écran d'Android") { try { startActivity(Intent(Settings.ACTION_CAST_SETTINGS)) } catch (err: Exception) { toastOnMain(this, "Ouvre le partage d'écran dans les réglages d'Android.") }; finish() }
            }
            else -> found.forEach { tv -> entry(tv.name, "envoyer ici") { CastService.start(applicationContext, video.url, tv.name, video.title); toastOnMain(applicationContext, "Envoi à ${tv.name}…"); finish() } }
        }
    }

    private fun search() {
        searching = true
        devices = null
        CoroutineScope(Dispatchers.Main).launch {
            devices = withContext(Dispatchers.IO) { try { CastEngine.discover(applicationContext, 5000) } catch (err: Exception) { emptyList() } }
            searching = false
            reload()
        }
    }

    companion object {
        const val EXTRA_URL = "url"
        const val EXTRA_TITLE = "title"
    }
}
