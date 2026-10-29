"""The relay: how a Claude session in the cloud reaches the phone. A public topic (ntfy.sh) Claude pings, and, when the cloud's network blocks it, a file pushed to its own branch on GitHub."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import asks, config, github, instructions, scenarios, sessions, state


def relay_url():
    """Where a session writes what it has to say to the phone."""
    return f"{config.NTFY_SERVER}/{state.waiting_topic}"


def _ping_seen(text):
    with state.waiting_lock:
        state.waiting["since"] = state.waiting["last_ping"] = time.time()
    print(f"[{state.ts()}] alert received from the relay: {text[:40]!r}", flush=True)


def note_message_sent():
    with state.lock:
        state.last_message_at = int(time.time())
        state.save()


def check_text(force=False, repo=None, work=None):
    """The test that tells whether Claude's cloud environment can reach the relay
    (its network access must allow ntfy.sh — a setting only claude.ai can change):
    added to the first message of a NEW session while the relay is unconfirmed, and
    sent on its own by the app's "Retester". "" when already confirmed."""
    with state.lock:
        if state.relay_cloud["ok"] is not None and not force:
            return ""
        state.relay_cloud.update(asked=time.time(), ok=None)
        topic = state.waiting_topic
        state.save()
    return (
        "\n\n[Aiwa] Test du relais, à faire tout de suite avant le reste : exécute "
        f"`curl -s -m 8 -H 'Title: aiwa-check' -d ok {config.NTFY_SERVER}/{topic}` puis continue normalement ; "
        + (
            f"si elle échoue (réseau bloqué), repli : {instructions.mailbox_signal('check', work)}, puis continue sans t'y attarder."
            if repo and work else "si le réseau la bloque, ignore l'erreur et ne t'y attarde pas."
        )
    )


def cloud_state():
    """ok (a command of Claude's reached the relay), pending (asked a moment ago),
    missing (asked, nothing came: the environment probably blocks ntfy.sh) or untested."""
    with state.lock:
        asked, ok = state.relay_cloud["asked"], state.relay_cloud["ok"]
    if ok is not None:
        return "ok"
    if asked is None:
        return "untested"
    return "pending" if time.time() - asked < config.CLOUD_CHECK_WAIT else "missing"


def _cloud_check_seen():
    with state.lock:
        first = state.relay_cloud["ok"] is None
        state.relay_cloud["ok"] = time.time()
        state.save()
    if first:
        print(f"[{state.ts()}] the cloud environment reaches the relay", flush=True)


def raw_get(url, limit):
    """The bytes at `url` (None for anything but a 200, a timeout, or something larger than `limit`)."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "aiwa", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=15) as reply:
            data = reply.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


def _mailbox_once(repo, work):
    """One look at `aiwa-out/SIGNAL` of Claude's branch, one line: `attend <time>` (Claude waits
    for an answer: the alert) or `check <time>` (the relay test). A signal is acted on once, and only if it answers our last message. True if one was."""
    base = f"{config.RAW_BASE}/{repo}/refs/heads/{work}/aiwa-out"
    stamp = int(time.time() * 1000)          # a new address each time: the raw CDN keeps a file for minutes
    raw_signal = raw_get(f"{base}/SIGNAL?t={stamp}", 300)
    line = raw_signal.decode("utf-8", "replace").strip() if raw_signal else ""
    parts = line.split()
    if len(parts) == 2 and parts[0] in ("attend", "check", "ask", "scenario") and parts[1].isdigit():
        kind, moment = parts[0], int(parts[1])
    else:
        return False
    with state.mailbox_lock:
        if state.mailbox["seen"] == (repo, work, line):
            return False
    with state.lock:
        asked = state.last_message_at
    if asked and moment < asked - 120:
        return False                          # older than our last message: not an answer to it
    with state.mailbox_lock:
        state.mailbox["seen"] = (repo, work, line)
    if kind == "ask":
        raw = raw_get(f"{base}/ask.json?t={stamp}", 4000)
        if raw:
            asks.ask_set(raw.decode("utf-8", "replace"), f"github:{repo}@{work}:{moment}")
    if kind == "scenario":
        raw = raw_get(f"{base}/scenario.json?t={stamp}", 6000)
        if raw:
            scenarios.said(raw.decode("utf-8", "replace"))
    if kind == "attend":
        _ping_seen("attend (GitHub)")
    _cloud_check_seen()                       # a signal that came through proves the cloud can say something to the phone
    return True


def _mailbox_loop(repo, work):
    while True:
        with state.mailbox_lock:
            if time.time() >= state.mailbox["until"] or state.mailbox["key"] != (repo, work):
                state.mailbox["running"] = False
                return
        try:
            _mailbox_once(repo, work)
        except Exception as err:  # a bad answer must never end the watch
            print(f"[{state.ts()}] mailbox: {err}", flush=True)
        time.sleep(config.MAILBOX_EVERY)


def resume_mailbox():
    """After a restart (the brain updates itself, and a watch lives only in memory): the session in use is watched again when a message was sent to it less than the watch's length ago,
    so that what Claude pushed to its branch while the brain was restarting is still read."""
    with state.lock:
        current, sent = state.current_cloud, state.last_message_at
    if not current or not sent or time.time() - sent > config.MAILBOX_WAIT:
        return False
    entry = sessions.entry_of(current)
    if not entry.get("repo") or not entry.get("work"):
        return False
    mailbox_watch(entry["repo"], entry["work"])
    return True


def mailbox_watch(repo, work):
    """After a message on a repository session: for a while, look for what Claude pushes to its branch when the relay is blocked (the app, the
    alert, the relay test). Nothing is read unless the repository is public: for a private one nothing comes, and the app is pasted."""
    if not repo or not work or not github.REPO_RE.fullmatch(repo) or not config.BRANCH_RE.fullmatch(work) or ".." in work:
        return
    with state.mailbox_lock:
        state.mailbox.update(key=(repo, work), until=time.time() + config.MAILBOX_WAIT)
        if state.mailbox["running"]:
            return
        state.mailbox["running"] = True
    threading.Thread(target=_mailbox_loop, args=(repo, work), daemon=True).start()


def _relay_event(event):
    """One message of the relay topic: a scenario's word (title aiwa-scenario), a question (aiwa-ask), the relay test (aiwa-check) or Claude's "I wait for you" ping."""
    now = time.time()
    with state.lock:
        if event.get("id") and event.get("id") == state.relay_seen["id"]:
            return  # the last one, replayed after a restart
        state.relay_seen.update(id=event.get("id"), time=event["time"] if isinstance(event.get("time"), int) else int(now))
        state.save()
    title = str(event.get("title") or "")
    if title == "aiwa-check":
        _cloud_check_seen()
    elif title == "aiwa-scenario":
        scenarios.said(event.get("message"))
        _cloud_check_seen()
    elif title == "aiwa-ask":
        asks.ask_set(event.get("message"), event.get("id"))
        _cloud_check_seen()
    else:
        text = str(event.get("message", ""))
        if isinstance(event.get("time"), int) and now - event["time"] > 120:
            return  # a ping replayed long after the fact must not wake the alert again
        _ping_seen(text)
        if text != "test":  # "test" is Aiwa's own ping: it proves the phone side only
            _cloud_check_seen()


def listen():
    """Listens to the relay topic Claude pings when it waits for an answer, and
    through which its answers and the relay test come back. Forever, reconnecting
    with a growing pause: an unreachable relay just means no alert."""
    backoff = 5
    with state.lock:
        since = str(state.relay_seen["time"]) if state.relay_seen["time"] else str(int(time.time()))
    while True:
        try:
            request = urllib.request.Request(f"{config.NTFY_SERVER}/{state.waiting_topic}/json?since={since}", headers={"User-Agent": "aiwa"})
            with urllib.request.urlopen(request, timeout=90) as reply:
                backoff = 5
                for raw in reply:
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("id"):
                        since = event["id"]
                    if event.get("event") == "message":
                        _relay_event(event)
        except (OSError, ValueError):
            pass
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def clear_waiting():
    with state.waiting_lock:
        state.waiting["since"] = None
    # The person went to look in Claude: the silence alert has done its job for this message
    state.silence["acked_for"] = state.last_message_at


def silence_minutes(now=None):
    """How many minutes without a sign of Claude since the last message, or 0 when there is nothing to say."""
    now = time.time() if now is None else now
    with state.lock:
        sent, busy, pending_ask = state.last_message_at, state.cloud_busy, bool(asks.pending_list())
        session = state.current_cloud or state.last_cloud
    if not sent or busy or pending_ask:
        return 0
    waited = now - sent
    if waited < config.SILENCE_AFTER or waited > config.SILENCE_UNTIL or state.silence["acked_for"] >= sent:
        return 0
    with state.waiting_lock:
        ping = state.waiting["last_ping"]
    if ping and ping >= sent:
        return 0                                  # the session pinged the relay after the message
    entry = sessions.entry_of(session) if session else {}
    repo, branch = (entry or {}).get("repo"), (entry or {}).get("work")
    if repo and branch and github.REPO_RE.fullmatch(repo) and config.BRANCH_RE.fullmatch(branch):
        when = github.newest_commit_time(repo, branch)
        if when and when >= sent:
            return 0                              # a commit on its branch
    return int(waited // 60)


def test():
    """A ping sent by Aiwa itself: proves the phone side (relay reachable
    and listened to) — not that Claude's session may reach the relay."""
    request = urllib.request.Request(f"{config.NTFY_SERVER}/{state.waiting_topic}", data=b"test", method="POST", headers={"User-Agent": "aiwa"})
    with urllib.request.urlopen(request, timeout=10):
        pass