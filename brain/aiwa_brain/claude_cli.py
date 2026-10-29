"""The `claude` command line: run in a terminal of its own, its log, whether it is logged in, the login flow the app drives."""
import fcntl
import json
import os
import pty
import re
import select
import shlex
import signal
import struct
import subprocess
import termios
import threading
import time

from . import config, github, state


def _signal_group(proc, sig):
    try:
        os.killpg(proc.pid, sig)
    except OSError:
        pass


def _note_progress(text):
    """The widget shows what a send is doing: the last line the CLI printed (its progress display redraws one line)."""
    for line in reversed(text.splitlines()):
        line = " ".join(line.split())
        if len(line) >= 3:
            state.cloud_progress = line[:90]
            return


def run_with_pty(command, cwd, timeout, stop_after_session_id=False, idle_timeout=None):
    """Runs a command as if in a real terminal (creating a cloud session
    shows a live progress display, and that is how the manual test that
    worked ran it). Returns (exit code, cleaned output, reason it ended,
    timeline).

    stop_after_session_id: `claude --cloud "task"` most likely stays open
    like a normal Claude after creating the session (Anthropic's wording:
    "the task runs in the cloud while you continue working locally"), so
    waiting for it to exit meant waiting out the whole timeout — reported
    live as the session taking far too long to appear compared with the
    manual test. Once a session id has appeared and the output has gone
    quiet for a few seconds, the session exists: stop the CLI."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 200, 0, 0))
    env = dict(os.environ)
    if env.get("TERM", "dumb") in ("", "dumb"):
        env["TERM"] = "xterm-256color"
    start = time.time()
    timeline = []

    def mark(what):
        timeline.append(f"{time.time() - start:5.1f}s {what}")

    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=slave, stdout=slave, stderr=slave, close_fds=True, start_new_session=True)
    os.close(slave)
    mark("started")
    chunks = []
    reason = "exited"
    found_at = None
    last_data = start
    try:
        while True:
            now = time.time()
            left = start + timeout - now
            if left <= 0:
                reason = "timeout"
                break
            if idle_timeout and now - last_data >= idle_timeout:
                reason = "idle"
                break
            if stop_after_session_id and found_at is not None and (now - last_data >= 4 or now - found_at >= 25):
                reason = "stopped after the session id appeared"
                break
            if stop_after_session_id and found_at is None and chunks and now - last_data >= config.PROMPT_STALL:
                if config.PROMPT_RE.search(github.clean(b"".join(chunks).decode("utf-8", "replace")).strip()[-400:]):
                    reason = "waiting for an answer"
                    break
            ready, _, _ = select.select([master], [], [], min(left, 1.0))
            if ready:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    break
                if not data:
                    break
                if not chunks:
                    mark("first output")
                chunks.append(data)
                last_data = time.time()
                if stop_after_session_id:
                    _note_progress(github.clean(data.decode("utf-8", "replace")))
                if stop_after_session_id and found_at is None:
                    if config.CLOUD_ID_RE.search(github.clean(b"".join(chunks).decode("utf-8", "replace"))):
                        found_at = last_data
                        mark("session id seen")
            elif proc.poll() is not None:
                break
    finally:
        if reason != "exited" and proc.poll() is None:
            _signal_group(proc, signal.SIGTERM)
        os.close(master)
    try:
        code = proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = proc.wait()
    if reason != "exited":
        # `script` may leave the CLI it started running. It was started in
        # its own session, so its whole group can be killed without
        # touching any other `claude` process (a follow-up running at the
        # same time, for instance).
        _signal_group(proc, signal.SIGKILL)
    mark(f"ended: {reason} (exit {code})")
    return code, github.clean(b"".join(chunks).decode("utf-8", "replace")), reason, timeline


def log_cloud(kind, command, code, output, timeline=()):
    try:
        config.CLOUD_LOG.write_text(
            f"[{state.ts()}] {kind} exit={code}\n$ {shlex.join(command)}\n" + "\n".join(timeline) + f"\n\n{output}\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def last_json_object(output):
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


def auth_status():
    """Whether the CLI is logged in (True / False), None when it can't be told."""
    try:
        done = subprocess.run(["claude", "auth", "status", "--json"], capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (done.stdout or "").strip()
    try:
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except ValueError:
        return None
    return data.get("loggedIn") is True if isinstance(data, dict) else None


def check_now():
    """A fresh answer to « is the CLI logged in », not the cached one (asked for by the app's set-up window)."""
    logged = auth_status()
    if logged is not None:
        set_login_state("ok" if logged else "needed")
    return {"accepted": True, "claude_login": login_state()}


def set_login_state(value):
    with state.login_lock:
        state.claude_login.update(state=value, at=time.time())


def note_login_problem(output):
    """A failed send whose text says "log in again" makes the widget ask for it."""
    if isinstance(output, str) and config.LOGIN_NEEDED_RE.search(output):
        set_login_state("needed")


def _login_probe():
    logged = auth_status()
    with state.login_lock:
        state.claude_login["busy"] = False
        state.claude_login.update(at=time.time(), **({"state": "ok" if logged else "needed"} if logged is not None else {}))


def login_state():
    """ok / needed / unknown. Looked up in the background — starting `claude` is not
    free on a phone — every ten minutes, every twenty seconds while it is 'needed'
    (so the widget clears soon after a login made somewhere else)."""
    with state.login_lock:
        known, age = state.claude_login["state"], time.time() - state.claude_login["at"]
        if not state.claude_login["busy"] and age > (20 if known == "needed" else 15 if known == "unknown" else 600):
            state.claude_login["busy"] = True
            threading.Thread(target=_login_probe, daemon=True).start()
        return known


def login_snapshot():
    with state.login_lock:
        return {"phase": state.login_flow["phase"], "url": state.login_flow["url"], "message": state.login_flow["message"]}


_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def _login_lines(text):
    """The readable lines of the CLI's screen (no escape codes, no login address)."""
    lines = [re.sub(r"^Paste code here if prompted\s*>\s*", "", l.strip()) for l in github.clean(_OSC_RE.sub("", text)).splitlines()]
    return [l for l in lines if l and "oauth/authorize" not in l]


def _login_reader(proc, master):
    """Reads what `claude auth login` prints: the address to open, then the outcome.
    A refused code makes the CLI print "Login failed" and exit (seen with the real
    CLI): a new login is then needed. Should it stay and ask again, the user may paste
    another code after a few seconds."""
    chunks = []
    refused_at = None
    while True:
        try:
            ready, _, _ = select.select([master], [], [], 1.0)
        except (OSError, ValueError):
            break
        if ready:
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            text = b"".join(chunks).decode("utf-8", "replace")
            with state.login_lock:
                if state.login_flow["proc"] is not proc:
                    return
                state.login_flow["text"] = text
                if state.login_flow["url"] is None:
                    found = config.LOGIN_URL_RE.search(text)
                    if found:
                        state.login_flow.update(url=found.group(0), phase="url")
                fresh = text[state.login_flow["mark"]:] if state.login_flow["phase"] == "checking" else ""
                if fresh and re.search(r"login successful|logged in as|successfully logged", fresh, re.I):
                    state.login_flow.update(phase="done", message="Connecté à Claude.")
                    state.claude_login.update(state="ok", at=time.time())
                elif fresh and re.search(r"invalid|expired|failed|error|denied|incorrect", fresh, re.I):
                    lines = _login_lines(fresh)
                    state.login_flow["message"] = (lines[-1] if lines else "Code refusé.")[:300]
                    refused_at = refused_at or time.time()
        elif proc.poll() is not None:
            break
        if refused_at is not None and proc.poll() is None and time.time() - refused_at > 3:
            with state.login_lock:
                if state.login_flow["proc"] is proc and state.login_flow["phase"] == "checking":
                    state.login_flow["phase"] = "url"
            refused_at = None
    code = proc.wait()
    with state.login_lock:
        if state.login_flow["proc"] is not proc:
            return
        if state.login_flow["phase"] != "done":
            if code == 0:
                state.login_flow.update(phase="done", message="Connecté à Claude.")
                state.claude_login.update(state="ok", at=time.time())
            else:
                lines = _login_lines(state.login_flow["text"])
                state.login_flow.update(phase="failed", message=state.login_flow["message"] or (lines[-1] if lines else f"le CLI s'est arrêté (code {code})")[:300])
        state.login_flow.update(proc=None, master=None)
    try:
        os.close(master)
    except OSError:
        pass


def login_cancel():
    with state.login_lock:
        proc = state.login_flow["proc"]
        state.login_flow.update(phase="idle", url=None, message="", proc=None, master=None, text="", mark=0)
    if proc is not None and proc.poll() is None:
        _signal_group(proc, signal.SIGTERM)


def login_start():
    """Starts `claude auth login` in a terminal of its own and waits for the address
    it prints. The user opens it in a browser, approves, and gets a CODE to paste
    (the redirect goes to platform.claude.com, not to the phone)."""
    login_cancel()
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 4000, 0, 0))  # wide: the address must not wrap
    # A token given in the environment would win over the login: not for this one.
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    env.update(TERM="xterm-256color", BROWSER="true")
    try:
        proc = subprocess.Popen(["claude", "auth", "login", "--claudeai"], env=env, stdin=slave, stdout=slave, stderr=slave, close_fds=True, start_new_session=True)
    except OSError as err:
        os.close(master)
        os.close(slave)
        with state.login_lock:
            state.login_flow.update(phase="failed", message=f"claude est introuvable : {err}")
        return login_snapshot()
    os.close(slave)
    with state.login_lock:
        state.login_flow.update(phase="starting", url=None, message="", proc=proc, master=master, text="", mark=0)
    threading.Thread(target=_login_reader, args=(proc, master), daemon=True).start()
    deadline = time.time() + 25
    while time.time() < deadline:
        snapshot = login_snapshot()
        if snapshot["phase"] in ("url", "failed", "done"):
            return snapshot
        time.sleep(0.2)
    return dict(login_snapshot(), message="Le CLI n'a pas donné d'adresse de connexion (25 s).")


def login_code(code):
    """Gives the code shown by the login page to the waiting CLI and waits for the verdict."""
    code = (code or "").strip()
    if not code or len(code) > 4000 or re.search(r"\s", code):
        return dict(login_snapshot(), message="Ce n'est pas un code de connexion (une seule suite de caractères, sans espace).")
    with state.login_lock:
        proc, master = state.login_flow["proc"], state.login_flow["master"]
        ready = proc is not None and proc.poll() is None and state.login_flow["phase"] == "url"
        if ready:
            state.login_flow.update(phase="checking", message="", mark=len(state.login_flow["text"]))
    if not ready:
        return dict(login_snapshot(), message="Aucune connexion en cours : ouvre d'abord la page de connexion.")
    try:
        os.write(master, code.encode() + b"\r")
    except OSError as err:
        with state.login_lock:
            state.login_flow.update(phase="failed", message=f"impossible de donner le code au CLI : {err}")
        return login_snapshot()
    deadline = time.time() + 45
    while time.time() < deadline:
        snapshot = login_snapshot()
        if snapshot["phase"] in ("done", "failed") or (snapshot["phase"] == "url" and snapshot["message"]):
            return snapshot
        time.sleep(0.25)
    return dict(login_snapshot(), message="Pas de réponse du CLI après 45 s.")