package com.aiwa.app.brain

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import com.aiwa.app.R
import com.aiwa.app.agent.AgentVoice
import com.aiwa.app.cast.CastService
import com.aiwa.app.files.FilesWatch
import com.aiwa.app.question.AskActivity
import com.aiwa.app.update.AppUpdater
import com.aiwa.app.voice.AgentToggleActivity
import com.aiwa.app.voice.ReadySettings
import com.aiwa.app.voice.Speaker
import com.aiwa.app.voice.Words
import com.aiwa.app.widget.AiwaWidget
import com.aiwa.app.widget.OpenClaudeActivity
import com.aiwa.client.Status
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val CHANNEL_ID = "aiwa_lockscreen"
private const val ALERT_CHANNEL_ID = "aiwa_alerts"
private const val NOTIFICATION_ID = 1
private const val ASK_NOTIFICATION_ID = 3
private const val AGENT_NOTIFICATION_ID = 4
private const val CAST_NOTIFICATION_ID = 5
private const val UPDATE_NOTIFICATION_ID = 6
private const val READY_NOTIFICATION_ID = 8

/** What the lock-screen card says, and what a tap on it opens. */
private data class Card(val title: String, val status: String, val detail: String, val target: Class<*>)

/**
 * Keeps Aiwa's process resident (a foreground service: the widget and the voice start at once, without a cold start) and does its small jobs: every few seconds it asks the brain for its
 * state and the widget is drawn again when something it shows has changed; it starts the brain through Termux when it is down or older than this app expects; it looks for a newer build of the
 * application; it reads how many productions there are; it says what the super agent has to say; it tells the person that a question waits, that a production is ready, that a video can go
 * to the television.
 *
 * The lock screen: this service's own notification is a MEDIA notification, backed by a MediaSession — the mechanism a web page uses when its audio shows a player on the lock screen. It is
 * a card with the name of the session, what is going on, and the logo; tapping it opens what the card is about. It is silent and permanent. No audio ever plays: the session only reports a
 * non-advancing "playing" state so that the system keeps the card.
 */
class KeepAliveService : Service() {
    private var poller: Job? = null
    private var watcher: Job? = null
    private var session: MediaSession? = null
    private var logo: Bitmap? = null
    private var shown: Card? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Aiwa sur l'écran verrouillé", NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false); lockscreenVisibility = Notification.VISIBILITY_PUBLIC })
        manager.createNotificationChannel(NotificationChannel(ALERT_CHANNEL_ID, "Ce qu'Aiwa te signale", NotificationManager.IMPORTANCE_HIGH).apply { lockscreenVisibility = Notification.VISIBILITY_PUBLIC })
        logo = BitmapFactory.decodeResource(resources, R.drawable.logo_round)
        val mediaSession = MediaSession(this, "Aiwa")
        mediaSession.setCallback(object : MediaSession.Callback() {})
        // Set once: a session that goes back to "playing" would claim the headphone buttons again from whatever the user is really listening to.
        mediaSession.setPlaybackState(PlaybackState.Builder().setActions(0L).setState(PlaybackState.STATE_PLAYING, PlaybackState.PLAYBACK_POSITION_UNKNOWN, 0f).build())
        mediaSession.isActive = true
        session = mediaSession
        publish(cardFor(Aiwa.state.value), first = true)
        watcher = CoroutineScope(Dispatchers.Default).launch {
            Aiwa.state.collect {
                publish(cardFor(it), first = false)
                it.status?.let { status ->
                    announceAsk(status)
                    announceAgent(status)
                    startCastIfAsked(status)
                }
            }
        }
        if (poller?.isActive != true) poller = CoroutineScope(Dispatchers.IO).launch { pollBrain() }
    }

    private fun cardFor(snap: Snapshot): Card {
        val status = snap.status
        val hasSession = snap.sessionId != null || status?.lastSession != null
        val loginNeeded = status?.claudeLogin == "needed"
        val line = when {
            snap.link == Link.STARTING -> "⏳ Démarrage du cerveau…"
            snap.link == Link.DOWN -> "⚠ Le cerveau est arrêté — relance en cours"
            snap.link == Link.MISSING -> "⚠ Le cerveau n'est pas installé — touche pour savoir comment"
            loginNeeded -> "⚠ Claude n'est pas connecté — touche pour le connecter"
            status?.sending == true -> "Envoi en cours…"
            status?.ask != null -> "❓ Claude te pose une question"
            status?.agent?.let { it.say != null || it.proposal != null || it.command != null } == true -> "● Le super agent a quelque chose à dire"
            status?.waiting == true -> "● Claude attend ta réponse"
            (status?.silenceMinutes ?: 0) > 0 -> "⏳ Rien de Claude depuis ${status?.silenceMinutes} min — touche pour ouvrir la conversation"
            else -> "Prêt"
        }
        val target: Class<*> = when {
            snap.link == Link.MISSING -> InstallHelpActivity::class.java
            loginNeeded -> com.aiwa.app.settings.ClaudeLoginActivity::class.java
            status?.ask != null -> AskActivity::class.java
            (status?.waiting == true || (status?.silenceMinutes ?: 0) > 0) && hasSession -> OpenClaudeActivity::class.java
            else -> AgentToggleActivity::class.java
        }
        val detail = status?.repo?.let { "⎇ ${it.substringAfter('/')} · " + (if (status.pushMain) "Push main" else "Push branche") } ?: "Aucun dépôt pour l'instant"
        return Card(snap.sessionTitle ?: "Aiwa", line, detail, target)
    }

    // The video asked for « sur la TV » has been made (the brain says so): the cast starts by itself, with no screen. If Android refuses to start it from here, a notification that opens the cast
    // window is left (a tap is allowed to start it).
    private fun startCastIfAsked(status: Status) {
        val cast = status.cast ?: return
        val prefs = getSharedPreferences("aiwa_hints", MODE_PRIVATE)
        if (prefs.getString("cast_started", "") == cast.url) return
        prefs.edit().putString("cast_started", cast.url).apply()
        try {
            CastService.start(this, cast.url, cast.tv, cast.name)
        } catch (err: Exception) {
            val tap = PendingIntent.getActivity(this, 2, Intent(this, com.aiwa.app.cast.CastActivity::class.java).putExtra(com.aiwa.app.cast.CastActivity.EXTRA_URL, cast.url).putExtra(com.aiwa.app.cast.CastActivity.EXTRA_TITLE, cast.name).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            alert(CAST_NOTIFICATION_ID, "La vidéo est prête : ${cast.name}", "Touche pour l'envoyer à la TV", R.drawable.ic_video, tap)
        }
        CoroutineScope(Dispatchers.IO).launch { Aiwa.brain.castClear() }
    }

    // A question from Claude (not yet answered, not yet announced): a notification that opens the window where it is answered.
    private fun announceAsk(status: Status) {
        val manager = getSystemService(NotificationManager::class.java)
        val ask = status.ask
        if (ask == null) { manager.cancel(ASK_NOTIFICATION_ID); return }
        val prefs = getSharedPreferences("aiwa_hints", MODE_PRIVATE)
        if (prefs.getString("ask_told", "") == ask.id) return
        prefs.edit().putString("ask_told", ask.id).apply()
        val tap = PendingIntent.getActivity(this, 2, Intent(this, AskActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        alert(ASK_NOTIFICATION_ID, "Claude te pose une question", ask.question, R.drawable.ic_claude, tap)
    }

    // What the super agent has to say (the report, a message of the other agent in the chamber, a scenario's double): said aloud as soon as it is there, unless the agent is open (it speaks itself). A
    // proposal or a setting that waits for a word is left as a notification: the microphone cannot be opened from the background, a tap on it opens the super agent, which reads it back.
    private var spokenFor = 0L

    private fun announceAgent(status: Status) {
        val manager = getSystemService(NotificationManager::class.java)
        val agent = status.agent
        if (!AgentVoice.waiting(agent)) manager.cancel(AGENT_NOTIFICATION_ID)
        val say = agent.say
        if (say != null && !Aiwa.state.value.agentOpen) CoroutineScope(Dispatchers.Main).launch { AgentVoice.speakSay(applicationContext, agent) }
        if (AgentVoice.waiting(agent) && !Aiwa.state.value.agentOpen) {
            val text = agent.proposal?.readBack ?: agent.command?.readBack ?: return
            val tap = PendingIntent.getActivity(this, 4, Intent(this, AgentToggleActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            alert(AGENT_NOTIFICATION_ID, "Le super agent propose", text + " Touche pour qu'il te le lise et que tu dises oui ou non.", R.drawable.ic_agent, tap)
        }
    }

    private fun alert(id: Int, title: String, text: String, icon: Int, tap: PendingIntent) {
        val notification = Notification.Builder(this, ALERT_CHANNEL_ID)
            .setContentTitle(title).setContentText(text).setStyle(Notification.BigTextStyle().bigText(text))
            .setSmallIcon(icon).setContentIntent(tap).setAutoCancel(true).setVisibility(Notification.VISIBILITY_PUBLIC).build()
        getSystemService(NotificationManager::class.java).notify(id, notification)
    }

    /** A new production: said aloud (« c'est prêt ») and left as a notification that opens the list. */
    fun announceNew(title: String, kind: String) {
        val tap = PendingIntent.getActivity(this, 8, Intent(this, com.aiwa.app.files.FilesActivity::class.java).putExtra(com.aiwa.app.files.FilesActivity.EXTRA_KIND, kind).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        alert(READY_NOTIFICATION_ID, "C'est prêt : $title", "Touche pour l'ouvrir.", R.drawable.ic_download, tap)
        if (ReadySettings.enabled(applicationContext)) CoroutineScope(Dispatchers.Main).launch { Speaker.speakNatural(applicationContext, Words.spoken(applicationContext, "ready") + " $title.") }
    }

    // A new build, already downloaded: tapping the notification opens the system's installer.
    private fun announceAppUpdate(file: java.io.File) {
        val prefs = getSharedPreferences("aiwa_hints", MODE_PRIVATE)
        if (prefs.getString("update_told", null) == file.name) return
        prefs.edit().putString("update_told", file.name).apply()
        val tap = PendingIntent.getActivity(this, 6, AppUpdater.installIntent(this, file), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        alert(UPDATE_NOTIFICATION_ID, "Mise à jour d'Aiwa prête", "Touche pour l'installer (un seul tap sur « Installer »)", R.drawable.ic_update, tap)
    }

    @Synchronized
    private fun publish(card: Card, first: Boolean) {
        if (!first && card == shown) return
        shown = card
        val mediaSession = session ?: return
        val tap = PendingIntent.getActivity(this, 0, Intent(this, card.target).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        mediaSession.setSessionActivity(tap)
        mediaSession.setMetadata(
            MediaMetadata.Builder()
                .putString(MediaMetadata.METADATA_KEY_TITLE, card.title).putString(MediaMetadata.METADATA_KEY_ARTIST, card.status).putString(MediaMetadata.METADATA_KEY_ALBUM, card.detail)
                .putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, logo).putBitmap(MediaMetadata.METADATA_KEY_ART, logo).build(),
        )
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle(card.title).setContentText(card.status).setSubText(card.detail)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now).setLargeIcon(logo).setContentIntent(tap)
            .setOngoing(true).setShowWhen(false).setOnlyAlertOnce(true).setVisibility(Notification.VISIBILITY_PUBLIC)
            .setStyle(Notification.MediaStyle().setMediaSession(mediaSession.sessionToken)).build()
        if (first) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(NOTIFICATION_ID, notification)
        } else getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification)
    }

    // Keeps the widget honest: the brain is the source of truth for what it shows, and nothing else tells the widget that Claude started to wait.
    private suspend fun pollBrain() {
        var lastLaunch = 0L
        var versionKicked = false
        var lastAppCheck = 0L
        var lastPull = System.currentTimeMillis()
        while (true) {
            try {
                BrainSync.refresh()
                val current = Aiwa.state.value
                val version = current.status?.version ?: 0
                // An older brain still answers after an app update (nothing opened the app to replace it): update and restart it, once.
                if (versionKicked && System.currentTimeMillis() - lastLaunch > 15 * 60 * 1000L && current.link == Link.UP && version in 1 until EXPECTED_BRAIN_VERSION) versionKicked = false   // the first try failed (a slow pull)
                if (!versionKicked && current.link == Link.UP && version in 1 until EXPECTED_BRAIN_VERSION) {
                    versionKicked = true
                    lastLaunch = System.currentTimeMillis()
                    startBrainViaTermux(applicationContext, forceRestart = true)
                    Aiwa.markStarting()
                }
                // Every half hour the checkout is brought up to date (the start script pulls, and restarts the brain only if the code moved).
                if (current.link == Link.UP && System.currentTimeMillis() - lastPull > 30 * 60 * 1000L) {
                    lastPull = System.currentTimeMillis()
                    startBrainViaTermux(applicationContext)
                }
                // Down: bring it back on its own (at most every 90 s), so it is usually up already when you tap — a cold start takes a while.
                if (Aiwa.state.value.link == Link.DOWN && System.currentTimeMillis() - lastLaunch > 90_000) {
                    lastLaunch = System.currentTimeMillis()
                    startBrainViaTermux(applicationContext)
                }
                // The application itself: a newer build is looked for every minute (a conditional request: nothing counts when nothing changed) and downloaded; one notification, one tap on « Installer ».
                val clock = SystemClock.elapsedRealtime()
                if (lastAppCheck == 0L || clock - lastAppCheck > 60 * 1000L) {
                    lastAppCheck = clock
                    val ready = withContext(Dispatchers.IO) { AppUpdater.prepareQuietly(applicationContext) }
                    if (ready != null) announceAppUpdate(ready)
                }
                val updateReady = AppUpdater.readyFile(applicationContext) != null
                if (updateReady != Aiwa.state.value.appUpdateReady) Aiwa.update { it.copy(appUpdateReady = updateReady) }
                FilesWatch.tick(applicationContext, this@KeepAliveService)
                AiwaWidget.render(applicationContext)
            } catch (err: Exception) {
                // The brain is not up (yet): try again next round.
            }
            delay(if (Aiwa.state.value.link == Link.UP) 5_000 else 10_000)
        }
    }

    override fun onDestroy() {
        poller?.cancel()
        watcher?.cancel()
        session?.release()
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY
}
