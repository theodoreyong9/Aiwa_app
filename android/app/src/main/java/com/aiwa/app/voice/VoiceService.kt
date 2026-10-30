package com.aiwa.app.voice

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import androidx.core.content.ContextCompat
import com.aiwa.app.R
import com.aiwa.app.agent.AgentScreens
import com.aiwa.app.agent.AgentVoice
import com.aiwa.app.brain.Aiwa
import com.aiwa.app.brain.BrainSync
import com.aiwa.app.common.toastOnMain
import com.aiwa.app.widget.AiwaWidget
import com.aiwa.client.AgentView
import com.aiwa.client.Reply
import com.aiwa.client.Scenario
import com.aiwa.client.Spoken
import com.aiwa.client.WakeKind
import com.aiwa.client.isQuestion
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.vosk.LibVosk
import org.vosk.LogLevel
import org.vosk.Model
import org.vosk.SpeakerModel

/**
 * The microphone of Aiwa, in one foreground service of the microphone type (the phone shows its green dot while it runs). Two things happen here:
 *
 *  - THE EAR (the permanent listening, off until the person turns it on): a small model listens for a few phrases only (the call of the super agent, stop, éteins), on the phone, nothing
 *    leaves it. Heard, the call opens the super agent.
 *  - THE SUPER AGENT (the button, or the call): it listens with the phone's recognizer, the brain answers, the phone speaks, and a proposal is read back and sent only on the person's word.
 *    A question is answered at once, sentence by sentence; with « création à la volée » everything goes to the agent without a read-back; with a scenario, to its double.
 *
 * What it is not: Android does not let a service of this kind start by itself after a restart of the phone: opening the application once starts it again.
 */
class VoiceService : Service() {
    companion object {
        private const val CHANNEL_ID = "aiwa_listen"
        private const val NOTIFICATION_ID = 7
        private const val ACTION_STOP = "com.aiwa.app.LISTEN_STOP"
        private const val ACTION_OPEN_AGENT = "com.aiwa.app.OPEN_AGENT"
        private const val EXTRA_SCENARIO = "scenario"
        private const val QUIET_MS = 30_000L

        @Volatile var instance: VoiceService? = null

        /** Called whenever Aiwa is on screen: the ear listens again if it is wanted and is not running (after a restart, which Android does not allow to do from the background). */
        fun ensureStarted(context: Context) {
            if (!ListenSettings.enabled(context) || instance != null) return
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
            start(context, quiet = true)
        }

        /** From a visible screen only: Android refuses to start a microphone service from the background. */
        fun start(context: Context, quiet: Boolean = false) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                if (!quiet) toastOnMain(context, "Écoute : la permission du micro manque.")
                return
            }
            try { ContextCompat.startForegroundService(context, Intent(context, VoiceService::class.java)) } catch (err: Exception) {
                if (!quiet) toastOnMain(context, "Écoute impossible : ${err.message}")
            }
        }

        /** From a visible screen: opens the super agent (and starts the service if needed); `scenario` makes it talk to the double of that scenario. */
        fun openAgent(context: Context, scenario: Scenario? = null) {
            pendingScenario = scenario
            val running = instance
            if (running != null) { running.main.post { running.openAgent() }; return }
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) { toastOnMain(context, "Le micro est refusé : le super agent ne peut pas écouter."); return }
            try { ContextCompat.startForegroundService(context, Intent(context, VoiceService::class.java).setAction(ACTION_OPEN_AGENT)) } catch (err: Exception) { toastOnMain(context, "Écoute impossible : ${err.message}") }
        }

        fun closeAgent(context: Context) { instance?.let { it.main.post { it.closeAgent() } } }

        fun stop(context: Context) { context.stopService(Intent(context, VoiceService::class.java)) }

        /** The words changed: the small model listens for the new ones. */
        fun reload(context: Context) { instance?.reloadWords() }

        @Volatile private var pendingScenario: Scenario? = null
    }

    private val main = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var preparing: Job? = null
    private var model: Model? = null
    private var speakerModel: SpeakerModel? = null
    private var detector: WakeWordDetector? = null
    private var listener: AgentListener? = null
    private var lock: PowerManager.WakeLock? = null
    private var agentMode = false
    private var working = false
    private var scenario: Scenario? = null
    private var scenarioPoll: Job? = null
    private var liveWatch: Job? = null
    private var bargeIn: BargeIn? = null
    private val convo = ArrayDeque<Pair<Boolean, String>>()
    private var openWhenReady = false

    override fun onBind(intent: Intent?): IBinder? = null

    fun isAgentOpen(): Boolean = agentMode

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { ListenSettings.setEnabled(this, false); stopSelf(); return START_NOT_STICKY }
        try {
            val notification = notification("Je prépare l'écoute…")
            if (Build.VERSION.SDK_INT >= 30) startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE) else startForeground(NOTIFICATION_ID, notification)
        } catch (err: Exception) {
            // Android refuses a microphone service started while the app is not on screen: no message, and the wish is kept: it starts as soon as Aiwa is shown (ensureStarted)
            stopSelf()
            return START_NOT_STICKY
        }
        instance = this
        Aiwa.update { it.copy(listening = ListenSettings.enabled(this)) }
        AiwaWidget.render(applicationContext, force = true)
        if (intent?.action == ACTION_OPEN_AGENT) openWhenReady = true
        if (preparing?.isActive != true) preparing = scope.launch { prepare() }
        // Not sticky on purpose: restarted by the system from the background, a microphone service is refused, and it would loop.
        return START_NOT_STICKY
    }

    private suspend fun prepare() {
        if (ListenSettings.enabled(this)) {
            if (!VoskModelStore.isReady(this)) {
                say("Je télécharge le modèle vocal (environ 41 Mo)…")
                val failure = withContext(Dispatchers.IO) { VoskModelStore.download(this@VoiceService) { percent -> say("Je télécharge le modèle vocal : $percent %") } }
                if (failure != null) { fail("Le modèle vocal n'a pas pu être installé : $failure"); return }
            }
            val loaded = withContext(Dispatchers.IO) {
                try { LibVosk.setLogLevel(LogLevel.WARNINGS); Model(VoskModelStore.dir(this@VoiceService).absolutePath) } catch (err: Throwable) { null }   // an Error too: the native library may not load on this phone
            }
            if (loaded == null) {
                VoskModelStore.dir(this).deleteRecursively()
                fail("Le modèle vocal ne se charge pas sur ce téléphone (supprimé : il sera retéléchargé au prochain essai).")
                return
            }
            model = loaded
            if (VoiceLock.enabled(this) && VoiceLock.print(this) != null && SpeakerModelStore.isReady(this)) {
                speakerModel = withContext(Dispatchers.IO) { try { SpeakerModel(SpeakerModelStore.dir(this@VoiceService).absolutePath) } catch (err: Throwable) { null } }
            }
        }
        acquireLock()
        if (openWhenReady) { openWhenReady = false; openAgent() } else listen()
    }

    private fun acquireLock() {
        if (lock == null) {
            lock = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "aiwa:voice").also { it.acquire(12 * 60 * 60 * 1000L) }
        }
    }

    // ---------- the ear ----------

    private fun listen() {
        if (agentMode || model == null || !ListenSettings.enabled(this)) { if (!agentMode && !ListenSettings.enabled(this)) stopSelf(); return }
        say("J'écoute : dis « ${Words.variants(this, "call").firstOrNull()?.let { Words.name(this, "call").ifEmpty { it } } ?: "mon super agent"} ».")
        detector?.stop()
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        detector = WakeWordDetector(
            model = model!!, customs = Words.customs(this), speaker = speakerModel, print = VoiceLock.print(this), maxDistance = VoiceLock.maxDistance(this),
            onWake = { kind -> main.post { onWake(kind) } }, onFailure = { reason -> main.post { fail("Le micro s'est arrêté : $reason") } },
            mediaPlaying = { audio.isMusicActive }, pauseOnMedia = Words.pauseOnMedia(this),
        ).also { it.start() }
    }

    fun reloadWords() {
        main.post {
            if (agentMode || model == null || detector == null) return@post
            detector?.stop(); detector = null
            listen()
        }
    }

    private fun onWake(kind: WakeKind) {
        detector = null
        when (kind) {
            WakeKind.CALL -> openAgent()
            WakeKind.STOP -> { stopEverything(); listen() }
            WakeKind.OFF -> switchOff()
        }
    }

    private fun switchOff() {
        scope.launch {
            ListenSettings.setEnabled(applicationContext, false)
            Aiwa.update { it.copy(listening = false, agentOpen = false) }
            AiwaWidget.render(applicationContext, force = true)
            Speaker.speakNatural(applicationContext, Words.spoken(applicationContext, "asleep"))
            stopSelf()
        }
    }

    /** « stop »: the voice stops, what waits is dropped, the sessions the super agent last spoke to are asked to forget its comment. */
    private fun stopEverything() {
        Speaker.interrupt()
        scope.launch { withContext(Dispatchers.IO) { Aiwa.brain.agentStop() } }
    }

    // ---------- the super agent ----------

    fun openAgent() {
        if (agentMode) return
        agentMode = true
        detector?.stop(); detector = null
        scenario = pendingScenario; pendingScenario = null
        Aiwa.update { it.copy(agentOpen = true) }
        AiwaWidget.render(applicationContext, force = true)
        LiveBubble.askOnce(applicationContext)
        scope.launch {
            Speaker.resetInterrupt()
            val name = scenario?.name
            Speaker.speakNatural(applicationContext, if (name != null) "Scénario $name. ${Words.spoken(applicationContext, "listening")}" else Words.spoken(applicationContext, "listening"))
            if (scenario != null) startScenarioPoll()
            if (LiveSettings.enabled(applicationContext)) startLiveWatch()
            resolvePending()          // something proposed while the microphone was closed: read back now
            listenAgent()
        }
    }

    fun closeAgent() {
        if (!agentMode) return
        agentMode = false
        listener?.stop(); listener = null
        scenarioPoll?.cancel(); scenarioPoll = null; scenario = null
        liveWatch?.cancel(); liveWatch = null
        stopBarge()
        LiveBubble.hide()
        Aiwa.update { it.copy(agentOpen = false) }
        AiwaWidget.render(applicationContext, force = true)
        if (ListenSettings.enabled(this) && model != null) listen() else if (!ListenSettings.enabled(this)) stopSelf()
    }

    private fun listenAgent() {
        if (!agentMode) return
        listener?.stop()
        listener = AgentListener(
            this, onQuiet = { main.post { scope.launch { Speaker.speakNatural(applicationContext, Words.spoken(applicationContext, "asleep")); closeAgent() } } }, quietMs = QUIET_MS,
            completeSilenceMs = 1500L, possiblySilenceMs = 1000L, earlyQuestion = true,
            onPartial = { partial -> showLine(partial, partial = true) },
            onHeard = { text -> listener = null; scope.launch { handle(text) } },
        ).also { it.start() }
    }

    private fun startBarge() {
        if (bargeIn != null) return
        bargeIn = BargeIn(this) { main.post { Speaker.interrupt() } }.also { it.start() }
    }

    private fun stopBarge() { bargeIn?.stop(); bargeIn = null }

    /** One thing the person said. */
    private suspend fun handle(text: String) {
        if (!agentMode) return
        working = true
        showLine(text)
        try {
            val scenarioNow = scenario
            when {
                Spoken.reply(text) == Reply.STOP -> { stopEverything(); Speaker.speakNatural(applicationContext, "D'accord.") }
                scenarioNow != null -> talkToScenario(scenarioNow, text)
                LiveSettings.enabled(applicationContext) -> live(text)
                isQuestion(text) -> answerAloud(text)
                else -> turn(text)
            }
        } catch (err: Exception) {
            toastOnMain(applicationContext, "Super agent : ${err.message ?: err.javaClass.simpleName}")
        } finally {
            working = false
            if (agentMode) { delay(300); listenAgent() }
        }
    }

    /** A question: answered sentence by sentence, the voice starts on the first one. */
    private suspend fun answerAloud(text: String) {
        val sentences = kotlinx.coroutines.channels.Channel<String>(kotlinx.coroutines.channels.Channel.UNLIMITED)
        val said = StringBuilder()
        startBarge()
        val speaking = scope.launch { Speaker.speakFlow(applicationContext, sentences) }
        val ok = withContext(Dispatchers.IO) { Aiwa.brain.answerStream(text) { s -> said.append(s).append(' '); sentences.trySend(s); LiveBubble.said(applicationContext, false, s) } }
        sentences.close()
        speaking.join()
        stopBarge()
        if (!ok) Speaker.speakNatural(applicationContext, "Je n'ai pas de réponse : il me faut une clé Claude, ou que Claude soit connecté sur le téléphone.") else showLine(said.toString().trim(), mine = false)
    }

    /** A request for the super agent: it answers with words, and maybe a proposal for a session or settings for the phone. */
    private suspend fun turn(text: String) {
        val asked = withContext(Dispatchers.IO) { Aiwa.brain.agentAsk(text) }
        if (!asked.ok) { Speaker.speakNatural(applicationContext, asked.error ?: "Le cerveau ne répond pas."); return }
        val agent = AgentVoice.awaitAnswer()
        if (agent == null || agent.error != null) { Speaker.speakNatural(applicationContext, agent?.error ?: "Je n'ai pas de réponse."); return }
        startBarge()
        AgentVoice.speakSay(applicationContext, agent)
        stopBarge()
        agent.say?.let { showLine(it.text, mine = false) }
        resolvePending()
    }

    /** Settings and proposals the agent made: each is read back and applied or sent only on the person's word (an automatic command, from a master, goes at once). */
    private suspend fun resolvePending() {
        var agent: AgentView? = AgentVoice.fresh()
        agent?.command?.let { c ->
            if (c.auto) AgentScreens.apply(applicationContext, c)
            else {
                val (reply, heard) = askAloud(applicationContext, c.readBack + " C'est bon ?")
                when (reply) {
                    Reply.CONFIRM -> AgentScreens.apply(applicationContext, c)
                    Reply.OTHER -> { withContext(Dispatchers.IO) { Aiwa.brain.agentCancel(c.id) }; if (heard.isNotBlank()) { turn(heard); return } }
                    else -> withContext(Dispatchers.IO) { Aiwa.brain.agentCancel(c.id) }
                }
            }
        }
        agent = AgentVoice.fresh()
        agent?.proposal?.let { p ->
            val (reply, heard) = askAloud(applicationContext, p.readBack + " On y va ?")
            when (reply) {
                Reply.CONFIRM -> {
                    Speaker.speakNatural(applicationContext, "C'est parti.")
                    val sent = withContext(Dispatchers.IO) { Aiwa.brain.agentConfirm(p.id) }
                    if (!sent.ok) Speaker.speakNatural(applicationContext, sent.error ?: "Le message n'est pas parti.")
                    withContext(Dispatchers.IO) { BrainSync.refresh() }
                    AiwaWidget.render(applicationContext, force = true)
                }
                Reply.OTHER -> { withContext(Dispatchers.IO) { Aiwa.brain.agentCancel(p.id) }; if (heard.isNotBlank()) turn(heard) }
                else -> { withContext(Dispatchers.IO) { Aiwa.brain.agentCancel(p.id) }; Speaker.speakNatural(applicationContext, "J'annule.") }
            }
        }
    }

    // ---------- « création à la volée » ----------

    /** What is said goes to the agent without a read-back; its orders leave at once; the progress of the sessions is told as it happens. */
    private suspend fun live(text: String) {
        val sentences = kotlinx.coroutines.channels.Channel<String>(kotlinx.coroutines.channels.Channel.UNLIMITED)
        val speaking = scope.launch { Speaker.speakFlow(applicationContext, sentences) }
        startBarge()
        withContext(Dispatchers.IO) { Aiwa.brain.liveStream(text) { s -> sentences.trySend(s); LiveBubble.said(applicationContext, false, s) } }
        sentences.close()
        speaking.join()
        stopBarge()
        val agent = AgentVoice.fresh()
        agent?.command?.takeIf { it.auto }?.let { AgentScreens.apply(applicationContext, it) }
    }

    private fun startLiveWatch() {
        liveWatch?.cancel()
        withBrainLive(true)
        liveWatch = scope.launch {
            while (agentMode) {
                delay(20_000)
                if (working) continue
                val events = withContext(Dispatchers.IO) { Aiwa.brain.liveEvents() }
                for (event in events) Speaker.speakNatural(applicationContext, event)
            }
        }
    }

    private fun withBrainLive(on: Boolean) { scope.launch { withContext(Dispatchers.IO) { Aiwa.brain.liveSet(on) } } }

    // ---------- a scenario's double ----------

    private suspend fun talkToScenario(sc: Scenario, text: String) {
        val plain = com.aiwa.client.WakeWords.plain(text)
        if (plain.contains("fin du scenario") || plain.contains("stop scenario") || plain.contains("fin scenario")) {
            Speaker.speakNatural(applicationContext, "Scénario terminé.")
            scenario = null
            scenarioPoll?.cancel()
            return
        }
        val out = withContext(Dispatchers.IO) { Aiwa.brain.scenarioSay(sc.id, text) }
        if (!out.ok) Speaker.speakNatural(applicationContext, out.error ?: "La session du scénario n'est pas prête.")
    }

    /** The double speaks through the relay: what it says is spoken here, what it notes is shown. */
    private fun startScenarioPoll() {
        val sc = scenario ?: return
        scenarioPoll?.cancel()
        scenarioPoll = scope.launch {
            withContext(Dispatchers.IO) { Aiwa.brain.scenarioLaunch(id = sc.id) }
            while (agentMode && scenario?.id == sc.id) {
                val says = withContext(Dispatchers.IO) { Aiwa.brain.scenarioSaid(sc.id) }
                for (item in says) {
                    if (item.note.isNotBlank()) showLine(item.note, mine = false)
                    if (item.say.isNotBlank()) { showLine(item.say, mine = false); Speaker.speakNatural(applicationContext, item.say) }
                    if (item.screen) AgentVoice.fresh()?.command?.takeIf { it.auto }?.let { AgentScreens.apply(applicationContext, it) }
                }
                delay(2500)
            }
        }
    }

    // ---------- the notification ----------

    private fun showLine(text: String, mine: Boolean = true, partial: Boolean = false) {
        if (text.isBlank()) return
        if (!partial) { convo.addLast(mine to text.trim()); while (convo.size > 4) convo.removeFirst() }
        val lines = convo.map { (me, t) -> (if (me) "▸ " else "◂ ") + t } + (if (partial) listOf("▸ $text …") else emptyList())
        if (agentMode) { if (partial) LiveBubble.partial(this, text) else LiveBubble.said(this, mine, text.trim()) }
        say(lines.joinToString("\n"))
    }

    private fun say(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    private fun fail(message: String) {
        toastOnMain(applicationContext, message)
        ListenSettings.setEnabled(this, false)
        Aiwa.update { it.copy(listening = false, agentOpen = false) }
        AiwaWidget.render(applicationContext, force = true)
        stopSelf()
    }

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (manager.getNotificationChannel(CHANNEL_ID) == null) manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Écoute d'Aiwa", NotificationManager.IMPORTANCE_LOW).apply { setShowBadge(false); lockscreenVisibility = Notification.VISIBILITY_PUBLIC })
        val stop = PendingIntent.getService(this, 0, Intent(this, VoiceService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle(if (agentMode) "Super agent · à l'écoute" else "Aiwa écoute")
            .setContentText(text.lineSequence().firstOrNull().orEmpty())
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setSmallIcon(R.drawable.ic_agent)
            .setOngoing(true).setShowWhen(false).setOnlyAlertOnce(true)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .addAction(Notification.Action.Builder(android.graphics.drawable.Icon.createWithResource(this, R.drawable.ic_agent), "Éteindre", stop).build())
            .build()
    }

    override fun onDestroy() {
        instance = null
        listener?.stop(); detector?.stop(); stopBarge(); LiveBubble.hide()
        try { model?.close() } catch (err: Throwable) { }
        try { speakerModel?.close() } catch (err: Throwable) { }
        try { lock?.takeIf { it.isHeld }?.release() } catch (err: Exception) { }
        scope.cancel()
        Aiwa.update { it.copy(listening = false, agentOpen = false) }
        AiwaWidget.render(applicationContext, force = true)
        super.onDestroy()
    }
}
