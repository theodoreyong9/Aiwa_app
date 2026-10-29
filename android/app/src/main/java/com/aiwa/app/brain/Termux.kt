package com.aiwa.app.brain

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import com.aiwa.client.Verdict
import com.aiwa.client.problemMessage
import com.aiwa.client.verdict

const val TERMUX_RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND"

/** Whether Aiwa may ask Termux to run commands (a permission the user grants once). */
fun hasTermuxPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, TERMUX_RUN_COMMAND_PERMISSION) == PackageManager.PERMISSION_GRANTED

private const val TERMUX_PACKAGE = "com.termux"
private const val RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
private const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"
private const val TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash"

// Runs inside Termux via `bash -c`. Inline on purpose: a script that lives in the checkout can be missing on the phone when the checkout is stale (Termux then answers "executable
// regular file not found"). Fast-forwards the checkout, restarts the brain only if the code actually changed (or the app asked: $1 = "restart") so a warm `claude` is not thrown away
// on every opening, and does not launch a second brain when one already answers. `[a]iwa_brain` keeps pkill from matching this very script's own command line.
private val START_SCRIPT = listOf(
    // What this script does, step by step, in ~/aiwa_start.log (appended, cut
    // when it grows): its output otherwise goes nowhere, and "the backend did
    // not start" could not be told apart from "Termux never ran the script".
    "log=\"\$HOME/aiwa_start.log\"",
    "[ \"\$(wc -c < \"\$log\" 2>/dev/null || echo 0)\" -gt 20000 ] && : > \"\$log\"",
    "exec >> \"\$log\" 2>&1",
    "echo \"=== \$(date +%T) — Aiwa asked Termux to start the backend (arg: '\$1') ===\"",
    "cd \"\$HOME/aiwa_app\" || { echo \"no ~/aiwa_app checkout: run bootstrap.sh once\"; exit 1; }",
    // ONE start at a time. The app, the widget's keep-alive service and the
    // pickers can all ask for a start; while the port is not open yet (10-20 s)
    // each ask used to launch its own proot Ubuntu — several at once made the
    // phone crawl. start.sh records its pid in this file for as long as it runs.
    "pidfile=\"\$HOME/.aiwa_app_start.pid\"",
    "pid=\$(cat \"\$pidfile\" 2>/dev/null)",
    "running() { [ -n \"\$1\" ] && grep -q start.sh \"/proc/\$1/cmdline\" 2>/dev/null; }",
    "answers() { curl -sf http://127.0.0.1:8788/api/status >/dev/null 2>&1; }",
    // A server that is working on a message (creating a cloud session takes up to a few minutes) is not killed under it.
    "busy() { curl -sf -m 3 http://127.0.0.1:8788/api/status 2>/dev/null | grep -q '\"sending\": *true'; }",
    "if running \"\$pid\" && ! answers; then echo \"a start is already in progress (pid \$pid): nothing to do\"; exit 0; fi",
    "old=\$(git rev-parse HEAD 2>/dev/null)",
    // Bounded: a slow network must not hold the start back for long.
    "t0=\$(date +%s)",
    // The checkout is Aiwa's own copy of the repository, not a place to work: it is aligned on origin/main, whatever state it was left in (another branch, no upstream, local changes,
    // a history that does not fast-forward). A plain `git pull --ff-only` failed silently in those cases and left the brain old for ever (version 124 for days). A failed or slow fetch
    // changes nothing: only a fetch that worked can move the checkout.
    // ONE update at a time: the app, the keep-alive service and the pickers can ask for a start together, and two fetches at once fail on "cannot lock ref" (seen in the log).
    "lock=\"\$HOME/.aiwa_app_pull.lock\"",
    "[ -d \"\$lock\" ] && [ -n \"\$(find \"\$lock\" -maxdepth 0 -mmin +2 2>/dev/null)\" ] && rmdir \"\$lock\" 2>/dev/null",
    "got=0; for i in \$(seq 1 40); do if mkdir \"\$lock\" 2>/dev/null; then got=1; break; fi; sleep 1; done",
    "if [ \$got = 1 ]; then",
    "  if timeout \$([ \"\$1\" = restart ] && echo 45 || echo 20) git fetch -q origin main; then",
    // `reset --hard` also deletes the untracked files that stand in the way of tracked ones, which made `git pull` abort ("Please move or remove them before you merge")
    "    git merge --ff-only -q FETCH_HEAD 2>/dev/null || { echo \"cannot fast-forward (untracked files in the way, local changes, another branch or a history that moved): the checkout is aligned on origin/main\"; git reset --hard -q FETCH_HEAD; }",
    "  else echo \"git fetch failed or timed out (code \$?), keeping the checkout as is\"; fi",
    "  rmdir \"\$lock\" 2>/dev/null",
    "else echo \"another update is running: not updating twice\"; fi",
    "new=\$(git rev-parse HEAD 2>/dev/null)",
    "echo \"checkout \$old -> \$new (pull took \$(( \$(date +%s) - t0 )) s)\"",
    "if [ \"\$old\" != \"\$new\" ] || [ \"\$1\" = \"restart\" ]; then",
    "  busy && echo \"a message is being sent: restart waits for it (at most 3 min)\"",
    "  for i in \$(seq 1 90); do busy || break; sleep 2; done",
    "  pkill -f \"[a]iwa_brain\" >/dev/null 2>&1",
    // Wait for the old server (and the start.sh that supervised it) to be really
    // gone — usually well under a second — instead of a fixed pause.
    "  for i in 1 2 3 4 5 6 7 8; do answers || break; sleep 0.5; done",
    "  for i in 1 2 3 4 5 6; do running \"\$pid\" || break; sleep 0.5; done",
    "fi",
    "if answers; then echo \"already answering\"; exit 0; fi",
    "echo \"\$(date +%T) starting scripts/start.sh (log: ~/aiwa_app_backend.log)\"",
    "exec bash \"\$HOME/aiwa_app/scripts/start.sh\"",
).joinToString("\n")

/** Whether Termux is on the phone (the manifest's <queries> lets this app see it). */
fun isTermuxInstalled(context: Context): Boolean = try {
    context.packageManager.getPackageInfo(TERMUX_PACKAGE, 0)
    true
} catch (err: PackageManager.NameNotFoundException) {
    false
}

/**
 * Starts (and keeps up to date) the brain inside Termux through its RUN_COMMAND automation API, in the background.
 * Two real gates this cannot bypass: Android's runtime permission com.termux.permission.RUN_COMMAND, and Termux's own opt-in `allow-external-apps=true` in ~/.termux/termux.properties.
 */
fun startBrainViaTermux(context: Context, forceRestart: Boolean = false): Result<Unit> = try {
    // Android says nothing when the service of an app that is not there is started: without this check it looked like a launch.
    if (!isTermuxInstalled(context)) {
        Aiwa.update { it.copy(link = Link.MISSING, missing = "termux") }
        throw IllegalStateException(problemMessage(Verdict.TERMUX_MISSING))
    }
    val intent = Intent(ACTION_RUN_COMMAND).apply {
        setClassName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE)
        putExtra("com.termux.RUN_COMMAND_PATH", TERMUX_BASH)
        putExtra("com.termux.RUN_COMMAND_ARGUMENTS", arrayOf("-c", START_SCRIPT, "_", if (forceRestart) "restart" else ""))
        putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
    }
    context.startService(intent)
    // Counted until the brain answers (BrainSync): two starts in vain mean it is not installed, not slow.
    Aiwa.update { it.copy(starts = it.starts + 1) }
    // Only when the brain was known to be down: launching this script while it runs is a no-op, and must not make the widget claim it is starting.
    if (Aiwa.state.value.link == Link.DOWN) Aiwa.markStarting()
    Result.success(Unit)
} catch (err: Exception) {
    Result.failure(err)
}

/** The words for someone whose widget was tapped while the brain is down: what is being done, or what is missing. */
fun startMessage(context: Context): String {
    val known = Aiwa.state.value
    if (known.link == Link.MISSING) return problemMessage(if (known.missing == "termux") Verdict.TERMUX_MISSING else Verdict.NOT_INSTALLED)
    if (!isTermuxInstalled(context)) {
        Aiwa.update { it.copy(link = Link.MISSING, missing = "termux") }
        return problemMessage(Verdict.TERMUX_MISSING)
    }
    val result = startBrainViaTermux(context)
    return if (result.isSuccess) {
        val said = verdict(termuxInstalled = true, startsWithoutAnswer = Aiwa.state.value.starts - 1)
        if (said == Verdict.NOT_INSTALLED) Aiwa.update { it.copy(link = Link.MISSING, missing = "install") }
        problemMessage(said)
    } else {
        "Le cerveau n'a pas démarré et le widget ne peut pas le lancer (${result.exceptionOrNull()?.message}) — ouvre l'application Aiwa une fois pour autoriser le démarrage automatique."
    }
}
