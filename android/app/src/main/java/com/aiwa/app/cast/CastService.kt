package com.aiwa.app.cast

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import com.aiwa.app.R
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.voice.Speaker
import com.aiwa.client.Dlna
import com.aiwa.client.looksLikeVideo
import com.aiwa.client.similarityOf
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Casting a video to a television WITHOUT the screen: a foreground service with a visible notification. It does what CastActivity does (find the television, download the
 * video, serve it, tell the renderer to play it) but stays alive on its own, so that « envoie la vidéo sur la TV » works by voice, with the screen off, and so that a cast asked
 * together with a message (« fais une vidéo et envoie-la sur la TV ») starts by itself when Claude has made the video. It speaks the result. It stops with « arrête la TV »,
 * the notification's button, or after two hours.
 */
class CastService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var job: Job? = null
    private var server: LocalMediaServer? = null
    private var renderer: Dlna.Renderer? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopCasting(); return START_NOT_STICKY }
        val url = intent?.getStringExtra(EXTRA_URL).orEmpty()
        val tv = intent?.getStringExtra(EXTRA_TV).orEmpty()
        val name = intent?.getStringExtra(EXTRA_NAME).orEmpty().ifBlank { "Vidéo Aiwa" }
        startForeground(NOTIFICATION_ID, notification("Envoi de la vidéo à la TV…", name))
        job?.cancel()
        job = scope.launch { cast(url, tv, name) }
        return START_NOT_STICKY
    }

    private fun notification(text: String, title: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Envoi à la TV", NotificationManager.IMPORTANCE_LOW))
        val stop = PendingIntent.getService(this, 7, Intent(this, CastService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL)
            .setContentTitle(title).setContentText(text).setSmallIcon(R.drawable.ic_video)
            .addAction(Notification.Action.Builder(null, "Arrêter", stop).build())
            .setOngoing(true).build()
    }

    private fun say(text: String, title: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text, title))
    }

    /** The television whose name looks like what was said: the only one when nothing was said, none when it is not clear. */
    private fun pick(devices: List<Dlna.Renderer>, said: String): Dlna.Renderer? {
        if (devices.isEmpty()) return null
        if (said.isBlank()) return if (devices.size == 1) devices[0] else null
        val spoken = said.lowercase().filter { it.isLetterOrDigit() }
        val scored = devices.map { it to (if (it.name.lowercase().filter { c -> c.isLetterOrDigit() }.contains(spoken)) 1.0 else similarityOf(spoken, it.name)) }.sortedByDescending { it.second }
        val top = scored.first()
        val gap = top.second - (scored.getOrNull(1)?.second ?: 0.0)
        return if (top.second >= 0.6 && gap >= 0.1) top.first else null
    }

    private suspend fun cast(url: String, said: String, title: String) {
        val app = applicationContext
        try {
            if (!url.startsWith("https://")) throw IllegalStateException("cette vidéo n'a pas d'adresse sûre")
            val devices = CastEngine.discover(app, 5000)
            val tv = pick(devices, said)
            if (tv == null) {
                val why = when {
                    devices.isEmpty() -> "Je ne trouve aucune TV sur le Wi-Fi."
                    said.isBlank() -> "Plusieurs TV répondent (${devices.joinToString(", ") { it.name }}) : dis laquelle."
                    else -> "Aucune TV ne s'appelle « $said » (${devices.joinToString(", ") { it.name }})."
                }
                finish(why, title)
                return
            }
            renderer = tv
            say("Préparation de la vidéo pour ${tv.name}…", title)
            val file = withContext(Dispatchers.IO) {
                val dir = File(app.cacheDir, "share").apply { mkdirs() }
                val target = File(dir, "cast.mp4")
                val connection = (URL(url).openConnection() as HttpURLConnection).apply { connectTimeout = 15_000; readTimeout = 60_000; instanceFollowRedirects = true }
                connection.inputStream.use { input -> target.outputStream().use { input.copyTo(it) } }
                val head = target.inputStream().use { s -> ByteArray(12).also { s.read(it) } }
                check(looksLikeVideo(head, target.length())) { "le fichier téléchargé n'est pas une vidéo" }
                target
            }
            val local = CastEngine.localAddressToward(tv.host) ?: throw IllegalStateException("le téléphone n'est pas sur le même réseau que ${tv.name}")
            server?.stop()
            val media = LocalMediaServer(file).also { it.start() }
            server = media
            val refused = CastEngine.play(tv, "http://$local:${media.port}/video.mp4", title)
            if (refused != null) { finish(refused, title); return }
            say("Lecture sur ${tv.name}", title)
            Speaker.speakAndWait(app, "La vidéo joue sur ${tv.name}.")
            // the phone serves the file: it stays for as long as the video can play
            delay(2 * 60 * 60 * 1000L)
            stopCasting()
        } catch (err: kotlinx.coroutines.CancellationException) {
            throw err
        } catch (err: Exception) {
            finish("Envoi impossible : ${err.message ?: err.javaClass.simpleName}", title)
        }
    }

    /** The result is said (notification and voice), then the service ends. */
    private suspend fun finish(text: String, title: String) {
        say(text, title)
        Speaker.speakAndWait(applicationContext, text)
        stopCasting()
    }

    private fun stopCasting() {
        job?.cancel()
        server?.stop(); server = null
        renderer?.let { r -> CoroutineScope(Dispatchers.IO).launch { CastEngine.stop(r) } }
        renderer = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        scope.coroutineContext[Job]?.cancel()
        server?.stop()
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "aiwa_cast"
        private const val NOTIFICATION_ID = 4242
        const val EXTRA_URL = "url"
        const val EXTRA_TV = "tv"
        const val EXTRA_NAME = "name"
        private const val ACTION_STOP = "com.aiwa.store.CAST_STOP"

        fun start(context: Context, url: String, tv: String, name: String) {
            context.startForegroundService(Intent(context, CastService::class.java).putExtra(EXTRA_URL, url).putExtra(EXTRA_TV, tv).putExtra(EXTRA_NAME, name))
        }

        /** The latest video of all the repositories, to the television named (or the only one): what « envoie la dernière vidéo sur la TV » does. Blocking: it asks the brain. */
        fun startLatest(context: Context, tv: String) {
            val latest = Aiwa.brain.files(null)?.items?.get("video")?.firstOrNull()
            if (latest == null) { com.aiwa.app.common.toastOnMain(context, "Je ne trouve aucune vidéo à envoyer."); return }
            try { start(context, latest.url, tv, latest.title) } catch (err: Exception) { com.aiwa.app.common.toastOnMain(context, "Envoi à la TV impossible depuis l'arrière-plan : ouvre Cast TV.") }
        }

        fun stop(context: Context) {
            context.startService(Intent(context, CastService::class.java).setAction(ACTION_STOP))
        }
    }
}
