"""The brain's HTTP server (127.0.0.1, for the app and the pages of the WebView only). It routes: every route calls a function of the module that owns the thing."""
import json
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import agent, agent_lib, asks, diagram, attachments, cast, chamber, claude_cli, config, files, github, github_login, instructions, studio, live, profile, questions, relay, repos, scenarios, sessions, state, update


def status():
    """Everything the widget shows, in one answer."""
    with state.lock:
        model, cloud_session, repo, direct, problem, effort = state.current_model, state.current_cloud, state.current_repo, state.push_main, state.github_error, state.current_effort
        missing_access = state.repo_access_missing if state.repo_access_missing == state.current_repo else None
        sending, sending_since, sending_note = state.cloud_busy, state.cloud_busy_since, state.cloud_progress
        last = state.last_cloud
    with state.waiting_lock:
        is_waiting, last_ping = state.waiting["since"] is not None, state.waiting["last_ping"]
    with state.chamber_lock:
        room = {"active": state.chamber["active"], "peer": state.chamber["peer"], "name": state.chamber["name"]}
    return {
        "version": config.BACKEND_VERSION, "sending": sending, "sending_since": sending_since, "sending_note": sending_note or None, "model": model, "effort": effort,
        "cloud_session": cloud_session, "last_session": last or next((e.get("id") for e in sessions.load_all() if e.get("id")), None),
        "repo": repo, "push_main": direct, "waiting": is_waiting, "attachments": len(state.attachments), "attachment_files": attachments.attach_list(),
        "self_update": dict(state.self_update_last), "alert_last": last_ping, "silence_minutes": relay.silence_minutes(), "cast": cast.ready(),
        "github_error": problem, "repo_access_missing": missing_access, "github_app_url": config.GITHUB_APP_URL, "github_token": github.token_value() is not None, "github_user": github.connected_user(), "session_error": state.session_error, "github_rate": github.rate(),
        "claude_login": claude_cli.login_state(), "relay_cloud": relay.cloud_state(), "ask": asks.snapshot(), "agent": agent.snapshot(), "diagram": diagram.snapshot(),
        "chamber": room, "llm": {"state": state.llm.state, **state.llm.usage()}, "voice": state.voice.state, "profile": profile.profile_state().get("repo"),
    }


def _select_session(target):
    """"new" = the next message creates a session; otherwise the id of one of the sessions."""
    if target != "new" and not config.CLOUD_ID_RE.fullmatch(target):
        return {"accepted": False, "reason": "invalid cloud session"}
    relay.clear_waiting()
    with state.lock:
        state.current_cloud = None if target == "new" else target
        if target != "new":
            state.last_cloud = target
            entry = sessions.entry_of(target)
            if entry.get("repo"):
                state.current_repo = entry["repo"]
            if "model" in entry:
                state.current_model = entry["model"] or None
            if "effort" in entry:
                state.current_effort = entry["effort"] or None
        state.save()
        return {"accepted": True, "cloud_session": state.current_cloud}


def _clear_sessions():
    """The list Aiwa keeps of its sessions, emptied: nothing is touched in Claude, the sessions stay there."""
    if state.cloud_busy:
        return {"accepted": False, "reason": "un envoi est en cours"}
    relay.clear_waiting()
    with state.store_lock:
        try:
            config.CLOUD_STORE.write_text("[]", encoding="utf-8")
        except OSError as err:
            return {"accepted": False, "reason": str(err)}
    with state.lock:
        state.current_cloud = state.last_cloud = None
        state.save()
    with state.mailbox_lock:
        state.mailbox["until"] = 0.0
    return {"accepted": True}


def _set_model(requested):
    if requested and not config.MODEL_RE.fullmatch(requested):
        return {"accepted": False, "reason": "invalid model"}
    with state.lock:
        state.current_model = requested or None
        session = state.current_cloud
        state.save()
    if session:
        sessions.update_session(session, model=requested)
    return {"accepted": True, "model": requested or None}


def _set_effort(requested):
    if requested and requested not in config.EFFORT_LEVELS:
        return {"accepted": False, "reason": "invalid effort"}
    with state.lock:
        state.current_effort = requested or None
        session = state.current_cloud
        state.save()
    if session:
        sessions.update_session(session, effort=requested)
    return {"accepted": True, "effort": requested or None}


def _set_repo(text):
    """The repository the person works on, given by its name or a link. Its session is the one linked to it, made now when there is none."""
    repo = github.parse_repo(text)
    if repo is None:
        return {"accepted": False, "reason": "aucun dépôt GitHub dans ce texte"}
    with state.lock:
        state.repo_access_missing = None      # a new choice starts afresh: the alert is shown again only if the next session fails again
    linked = sessions.start_session(repo)
    return {"accepted": True, "repo": repo, "cloud_session": linked, "creating": linked is None}


def _new_session(text):
    """A second (or first) session on a repository, made now."""
    repo = github.parse_repo(text)
    if repo is None:
        return {"accepted": False, "reason": "aucun dépôt GitHub dans ce texte"}
    with state.lock:
        if state.cloud_busy:
            return {"accepted": False, "reason": "un envoi est en cours"}
    sessions.start_session(repo, force=True)
    return {"accepted": True, "repo": repo, "creating": True}


def _set_options(options):
    if not isinstance(options, dict):
        return {"accepted": False, "reason": "invalid options"}
    retarget = None
    with state.lock:
        if isinstance(options.get("push_main"), bool):
            if options["push_main"] != state.push_main and state.current_cloud:
                retarget = state.current_cloud
            state.push_main = options["push_main"]
        state.save()
    if retarget:
        sessions.update_session(retarget, direct=state.push_main)      # the session in progress follows the switch from its next message
    return {"accepted": True}


def _retest_relay():
    """Asks the CURRENT session to run the relay test again (a new session gets it with its first message on its own)."""
    with state.lock:
        session, before = state.current_cloud, dict(state.relay_cloud)
    if not session:
        return {"accepted": False, "reason": "aucune session en cours : le test part avec la première réponse d'une nouvelle session"}
    entry = sessions.entry_of(session)
    sent = sessions.cloud_send(relay.check_text(force=True, repo=entry.get("repo"), work=entry.get("work")).strip(), command=True)
    if sent.get("ok") is not True:
        with state.lock:
            state.relay_cloud.update(before)      # nothing was asked after all
            state.save()
    return {"accepted": sent.get("ok") is True, "reason": sent.get("error")}


def _agent_api(action, data):
    if action == "ask":
        return agent.converse(spoken=str(data.get("text") or "")[:600])
    if action == "report":
        return agent.converse(report=True)
    if action == "confirm":
        return agent.confirm(str(data.get("id") or ""))
    if action == "apply":
        return agent.apply_command(str(data.get("id") or ""))
    if action == "cancel":
        return agent.cancel(str(data.get("id") or ""))
    if action == "said":
        return agent.spoken(str(data.get("id") or ""))
    if action == "stop":
        return agent.stop()
    if action == "vocabulary":
        words = data.get("words") if isinstance(data.get("words"), dict) else {}
        clean = {str(k)[:40]: [str(v)[:60] for v in vals[:8]] for k, vals in list(words.items())[:12] if isinstance(vals, list)}
        return agent.converse(spoken="[Aiwa — vocabulaire] " + agent_lib.vocabulary_message(clean)) if clean else {"ok": False}
    return None


def _style(path, data):
    if path.endswith("clear"):
        state.style.clear()
    elif isinstance(data.get("enabled"), bool):
        state.style.set_enabled(data["enabled"])
    return {"ok": True, **state.style.status()}


def _llm_key(data):
    if data.get("clear"):
        return state.llm.clear_key()
    if "cap" in data:
        return state.llm.set_cap(data.get("cap"))
    return state.llm.save_key(data.get("key"))


def _github_token(data):
    try:
        github.set_token(data.get("token") if not data.get("clear") else "")
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    files.forget()
    return {"ok": True, "github_token": github.token_value() is not None, "user": github.connected_user()}


def _relay_test():
    try:
        relay.test()
        return {"accepted": True}
    except OSError as err:
        return {"accepted": False, "reason": f"relais injoignable : {err}"}


def _rename(data):
    return sessions.session_rename(data.get("id"), data.get("title"))


def _added(body):
    added, why_not = sessions.cloud_add(body)
    return {"accepted": False, "reason": why_not} if added is None else {"accepted": True, "cloud_session": added}


# route -> function(query) for GET, function(body, data) for POST; the answer is JSON
GET = {
    "/api/status": lambda q: status(),
    "/api/cloud/sessions": lambda q: sessions.load_all(),
    "/api/repos": lambda q: {"ok": True, "repos": repos.choices()},
    "/api/instructions": lambda q: {"text": instructions.preview()},
    "/api/claude/login": lambda q: claude_cli.login_snapshot(),
    "/api/github/login": lambda q: github_login.snapshot(),
    "/api/stock/status": lambda q: studio.stock_status(),
    "/api/film/info": lambda q: studio.info(),
    "/api/film/status": lambda q: {"ok": True, **studio.film.status()},
    "/api/film/get": lambda q: studio.film.get((q.get("id") or [""])[0]),
    "/api/files": lambda q: files.listing((q.get("repo") or [""])[0] or None),
    "/api/scenarios": lambda q: scenarios.scenario_api("/api/scenarios", ""),
    "/api/chamber": lambda q: chamber.chamber_api("/api/chamber", ""),
    "/api/live/events": lambda q: live.live_api("/api/live/events", ""),
    "/api/style": lambda q: {"ok": True, **state.style.status()},
    "/api/profile": lambda q: profile.profile_state(),
    "/api/profile/check": lambda q: profile.profile_check(),
    "/api/profile/pub": lambda q: profile.pub_of((q.get("repo") or [""])[0]),
}
POST = {
    "/api/cloud/message": lambda body, data: sessions.cloud_send(body),
    "/api/cloud/command": lambda body, data: sessions.cloud_send(body, command=True),
    "/api/cloud/select": lambda body, data: _select_session(body.strip()),
    "/api/cloud/clear": lambda body, data: _clear_sessions(),
    "/api/cloud/add": lambda body, data: _added(body),
    "/api/cloud/rename": lambda body, data: _rename(data),
    "/api/model": lambda body, data: _set_model(body.strip()),
    "/api/effort": lambda body, data: _set_effort(body.strip()),
    "/api/repo": lambda body, data: _set_repo(body),
    "/api/session/new": lambda body, data: _new_session(body),
    "/api/options": lambda body, data: _set_options(data if body.strip() else {}),
    "/api/attach": lambda body, data: attachments.attach_add(body),
    "/api/attach/clear": lambda body, data: attachments.attach_clear(),
    "/api/attach/remove": lambda body, data: attachments.attach_remove(body),
    "/api/answer": lambda body, data: questions.answer_question(data.get("question")),
    "/api/files/delete": lambda body, data: files.delete(str(data.get("repo") or ""), str(data.get("tag") or "")),
    "/api/files/share": lambda body, data: files.share(str(data.get("repo") or ""), str(data.get("tag") or ""), data.get("file")),
    "/api/cast/pending": lambda body, data: cast.cast_register(data.get("tv")),
    "/api/cast/clear": lambda body, data: cast.cast_clear(),
    "/api/live/set": lambda body, data: live.live_api("/api/live/set", body),
    "/api/style/set": lambda body, data: _style("set", data),
    "/api/style/clear": lambda body, data: _style("clear", data),
    "/api/profile": lambda body, data: profile.profile_apply(data),
    "/api/diagram/set": lambda body, data: {"ok": True, "on": diagram.set_on(data.get("on"))},
    "/api/profile/pub": lambda body, data: profile.publish_pub(data.get("pub")),
    "/api/waiting/clear": lambda body, data: (relay.clear_waiting(), {"accepted": True})[1],
    "/api/waiting/test": lambda body, data: _relay_test(),
    "/api/relay/retest": lambda body, data: _retest_relay(),
    "/api/ask/answer": lambda body, data: asks.answer(body),
    "/api/instructions/resend": lambda body, data: instructions.resend(),
    "/api/claude/login/start": lambda body, data: claude_cli.login_start(),
    "/api/claude/login/code": lambda body, data: claude_cli.login_code(body),
    "/api/claude/login/cancel": lambda body, data: (claude_cli.login_cancel(), {"accepted": True})[1],
    "/api/claude/check": lambda body, data: claude_cli.check_now(),
    "/api/llm/key": lambda body, data: _llm_key(data),
    "/api/github/token": lambda body, data: _github_token(data),
    "/api/github/login/start": lambda body, data: github_login.start(),
    "/api/github/login/cancel": lambda body, data: github_login.cancel(),
    "/api/voice/setup": lambda body, data: (state.voice.install(), {"ok": True, "state": state.voice.state})[1],
}
POST_PREFIX = (
    ("/api/agent/", lambda path, body, data: _agent_api(path.rsplit("/", 1)[1], data)),
    ("/api/scenarios/", lambda path, body, data: scenarios.scenario_api(path, body)),
    ("/api/stock/", lambda path, body, data: studio.stock_api(path, body)),
    ("/api/film/", lambda path, body, data: studio.film_api(path, body)),
    ("/api/chamber", lambda path, body, data: chamber.chamber_api(path, body)),
    ("/api/match", lambda path, body, data: chamber.chamber_api(path, body)),
)


def _json_of(body):
    try:
        data = json.loads(body) if body.strip() else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


class Handler(BaseHTTPRequestHandler):
    def reply_json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, produce):
        """One JSON line per sentence, sent as it is written; the connection closes at the end."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(sentence):
            self.wfile.write((json.dumps({"s": sentence}) + "\n").encode())
            self.wfile.flush()
        try:
            self.wfile.write((json.dumps({"done": True, **produce(emit)}) + "\n").encode())
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        self.close_connection = True

    def _send_film(self, name):
        """A finished film, with Range support (the player seeks)."""
        job = re.fullmatch(r"([0-9a-f]{10})\.mp4", name or "")
        path = studio.film.home / job.group(1) / "film.mp4" if job else None
        if not path or not path.exists():
            self.send_error(404)
            return
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(path, "rb") as handle:
                handle.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = handle.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        if parts.path == "/api/files/page":
            html = files.page_html((query.get("repo") or [""])[0], (query.get("tag") or [""])[0])
            if html is None:
                self.send_error(404)
                return
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts.path.startswith("/api/film/file/"):
            self._send_film(parts.path.rsplit("/", 1)[-1])
            return
        route = GET.get(parts.path)
        if route is None:
            self.send_error(404)
            return
        self.reply_json(route(query))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/film/source":
            # the person's own video, for a swap: raw bytes (not JSON, not base64: it can be big)
            job_id = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("id") or [""])[0]
            self.reply_json(studio.film.set_source(job_id, self.rfile.read(length)))
            return
        body = self.rfile.read(length).decode()
        data = _json_of(body)
        if path == "/api/answer_stream":
            self._stream(lambda emit: {"ok": questions.answer_stream(data.get("question"), emit)})
        elif path == "/api/live_stream":
            self._stream(lambda emit: live.live_stream(data.get("text"), emit))
        elif path == "/api/voice/say":
            wav = state.voice.say(str(data.get("text", "")))
            if wav is None:
                self.reply_json({"ok": False, "state": state.voice.state, "error": state.voice.error})
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav)))
            self.end_headers()
            self.wfile.write(wav)
        elif path in POST:
            self.reply_json(POST[path](body, data))
        else:
            for prefix, route in POST_PREFIX:
                if path.startswith(prefix):
                    answer = route(path, body, data)
                    if answer is None:
                        self.send_error(404)
                    else:
                        self.reply_json(answer)
                    return
            self.send_error(404)

    def log_message(self, *args):
        pass      # the requests of the widget are many; the brain logs what matters itself


def serve():
    state.load()
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("AIWA_TEST"):      # the tests start the server alone: nothing installs, listens or updates
        state.voice.install()        # the natural voice is installed by default, in the background (about 80 MB, once); the person only switches it on or off
        state.llm.prepare()
        github_login.resume()        # a GitHub code shown before a restart is still waited for
        claude_cli.login_state()     # looks the login up in the background, so the first status already knows
        files.warm()
        threading.Thread(target=live.progress_loop, daemon=True).start()
        threading.Thread(target=relay.listen, daemon=True).start()
        threading.Thread(target=update.update_loop, daemon=True).start()
    print(f"{time.strftime('%H:%M:%S')} Aiwa brain listening on http://{config.HOST}:{config.PORT}", flush=True)
    ThreadingHTTPServer((config.HOST, config.PORT), Handler).serve_forever()
