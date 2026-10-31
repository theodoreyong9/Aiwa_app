"""« Création à la volée »: the super agent in a fluid conversation while the person builds, and the progress of her sessions told as it happens."""
import json
import subprocess
import threading
import time
import urllib.parse

from . import agent, diagram, github, live_lib, questions, sessions, state


def _claude_stream(prompt, on_piece, timeout=90):
    """The text of `claude -p` (the person's own login, no API key), handed to `on_piece` as it is written. The whole text, or None."""
    try:
        proc = subprocess.Popen(["claude", "-p", "--model", "haiku", "--output-format", "stream-json", "--include-partial-messages", "--verbose"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except (OSError, subprocess.SubprocessError):
        return None
    killer = threading.Timer(timeout, proc.kill)
    killer.start()
    whole = ""
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            delta = ((event.get("event") or {}).get("delta") or {}) if event.get("type") == "stream_event" else {}
            piece = delta.get("text") if delta.get("type") == "text_delta" else None
            if piece:
                whole += piece
                on_piece(piece)
            elif event.get("type") == "result" and not whole and isinstance(event.get("result"), str):
                whole = event["result"]
                on_piece(whole)
        proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    finally:
        killer.cancel()
        try:
            proc.kill()
        except OSError:
            pass
    return whole or None


def live_stream(text, emit):
    """One turn of the live mode: the sentences to say go to `emit` as they are written, then the actions (messages to the sessions, things for the phone) are carried out at once.
    {"ok", "do"}: `do` is true when the phone has something to apply."""
    q = " ".join(str(text or "").split())[:600]
    if not q:
        return {"ok": False, "do": False}
    state.style.observe(q)
    digest, _sig = agent.point()
    with state.live_lock:
        events = "\n".join(state.live["recent"][-5:])
    system = live_lib.system(digest, events) + ("\n\n" + state.style.note() if state.style.note() else "") + ("\n\n" + diagram.note(live=True) if diagram.is_on() else "")
    talk = questions.conversation_text()
    prompt = system + ("\n\nLa conversation jusqu'ici (continue-la, sans te répéter) :\n" + talk if talk else "") + "\n\nLa personne dit : " + q
    splitter, said = live_lib.Splitter(), []

    def speak(sentences):
        code = splitter.take_diagram()
        if code:
            diagram.show(code)          # drawn by the phone while the sentences that follow are said
        for sentence in sentences:
            said.append(sentence)
            emit(sentence)
    full = None
    if state.llm.state == "ready":
        full = state.llm.ask(system, [{"role": "user", "content": q}], max_tokens=600)
        if full:
            speak(splitter.feed(full))
    if not full:
        full = _claude_stream(prompt, lambda piece: speak(splitter.feed(piece)))
    last, actions = splitter.finish()
    speak(last)
    did = agent.act(actions.get("send"), actions.get("do"))
    if said:
        questions.conversation_add(q, " ".join(said))
    return {"ok": bool(said or actions), "do": did}


def _live_sessions():
    """The sessions to follow: the one in use first, then the most recent others (three in all), with a repository and a branch; """
    with state.lock:
        current = state.current_cloud
    entries = [e for e in sessions.load_all() if e.get("id") and e.get("repo") and e.get("work") and github.REPO_RE.fullmatch(str(e.get("repo")))]
    entries.sort(key=lambda e: e["id"] != current)
    return entries[:3], current


def look_branch(repo, work):
    """One look at a branch: its latest commit and the state of its latest workflow, {"sha", "message", "ci"} (ci: running / success / failure / None)."""
    now = {"sha": None, "message": "", "ci": None}
    branch = urllib.parse.quote(work, safe="")
    commits = github.api(f"/repos/{repo}/commits?sha={branch}&per_page=1")
    if isinstance(commits, list) and commits:
        now["sha"] = commits[0].get("sha")
        now["message"] = str(((commits[0].get("commit") or {}).get("message") or "")).split("\n")[0]
    runs = github.api(f"/repos/{repo}/actions/runs?branch={branch}&per_page=1")
    run = ((runs or {}).get("workflow_runs") or [None])[0] if isinstance(runs, dict) else None
    if run:
        now["ci"] = "running" if run.get("status") != "completed" else ("success" if run.get("conclusion") == "success" else "failure")
    return now


def _live_look(repo, work, label):
    """One look at a branch (its latest commit and workflow): what changed since the last look becomes a sentence for the person, kept for the phone to take."""
    now = look_branch(repo, work)
    with state.live_lock:
        prev = state.live["snap"].get((repo, work))
        state.live["snap"][(repo, work)] = now
        for sentence in live_lib.progress(prev, now, label):
            state.live["events"].append(sentence)
            state.live["recent"] = (state.live["recent"] + [sentence])[-8:]


def progress_once(tick=0):
    """The session in use is looked at every minute, one of the two other recent ones each minute in turn (the requests are conditional: an unchanged branch does not count in GitHub's limit). When the
    limit is reached the person is told once, and told again when it is over."""
    entries, current = _live_sessions()
    if not entries:
        return
    others = entries[1:] if entries[0]["id"] == current else entries
    chosen = ([entries[0]] if entries[0]["id"] == current else []) + (others[tick % len(others):][:1] if others else [])
    try:
        for e in chosen:
            label = "" if e["id"] == current else "Sur la session « " + str(e.get("title") or e["id"])[:40] + " » : "
            _live_look(e["repo"], e["work"], label)
        with state.live_lock:
            if state.live.get("limited"):
                state.live["limited"] = False
                state.live["events"].append(live_lib.BACK)
    except github.GithubError as err:
        if err.limited:
            with state.live_lock:
                if not state.live.get("limited"):
                    state.live["limited"] = True
                    state.live["events"].append(live_lib.LIMITED)
        else:
            raise


def progress_loop():
    time.sleep(60)
    tick = 0
    while True:
        try:
            with state.live_lock:
                on = state.live["on"]
            if on:
                progress_once(tick)
                tick += 1
        except github.GithubError:
            pass
        except Exception as err:
            print(f"[{state.ts()}] live progress: {err}", flush=True)
        time.sleep(60)


def live_api(path, body):
    try:
        data = json.loads(body) if body.strip() else {}
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    with state.live_lock:
        if path == "/api/live/set":
            state.live["on"] = data.get("on") is True
            state.live["events"].clear()
        if path == "/api/live/events":
            items, state.live["events"] = list(state.live["events"]), []
            return {"ok": True, "on": state.live["on"], "events": items}
        return {"ok": True, "on": state.live["on"]}