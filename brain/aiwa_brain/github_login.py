"""GitHub's device flow: the phone shows a short code, the person types it once on github.com, and the brain waits for the token (no token to copy, nothing to paste). It is how the first Aiwa did it.
The application is the one of deployment.json (github.clientId); a device-flow application has no secret. The token it hands over is kept like any other (github.set_token), after GitHub has named the account."""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, files, github
from .paths import DATA

SCOPE = "repo"      # all the repositories (the private ones too), and the releases a production is deleted from
BASE = "https://github.com"

lock = threading.Lock()
flow = {"phase": "idle", "user_code": None, "uri": None, "message": "", "id": 0}
PENDING = DATA / "github_device.json"       # the code being waited for: a brain that restarts while the person is on github.com goes on waiting for it


def client_id():
    try:
        value = json.loads((config.REPO_ROOT / "deployment.json").read_text(encoding="utf-8")).get("github", {}).get("clientId", "")
    except (OSError, ValueError):
        return ""
    return value if isinstance(value, str) else ""


def _post(path, form):
    """One POST of a form; GitHub's login endpoints answer 200 even for « not yet »."""
    data = urllib.parse.urlencode(form).encode()
    request = urllib.request.Request(BASE + path, data=data, headers={"Accept": "application/json", "User-Agent": "aiwa"})
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return json.loads(reply.read())
    except urllib.error.HTTPError as err:
        try:
            return json.loads(err.read())
        except ValueError:
            return {"error": f"http_{err.code}"}


def _fail(text, mine):
    with lock:
        if flow["id"] == mine:
            flow.update(phase="failed", message=text)


ERRORS = {
    "access_denied": "Tu as refusé l'accès sur GitHub.",
    "expired_token": "Le code a expiré avant d'être tapé sur GitHub. Recommence.",
    "device_flow_disabled": "L'application GitHub d'Aiwa n'a pas le « device flow » activé (case dans ses réglages sur GitHub).",
    "incorrect_client_credentials": "GitHub ne connaît pas cette application (deployment.json, github.clientId).",
}


def _wait(mine, code, interval, expires, post):
    deadline = time.time() + expires
    while time.time() < deadline:
        time.sleep(interval)
        with lock:
            if flow["id"] != mine or flow["phase"] != "code":
                return
        try:
            reply = post("/login/oauth/access_token", {"client_id": client_id(), "device_code": code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        except (OSError, ValueError):
            continue      # the network blinked: GitHub is asked again at the next turn
        token = reply.get("access_token")
        if isinstance(token, str):
            try:
                github.set_token(token)
                files.forget()
            except Exception as err:      # whatever went wrong is told to the person, never lost in a thread
                _fail(str(err) or "la connexion n'a pas abouti", mine)
                return
            PENDING.unlink(missing_ok=True)
            with lock:
                if flow["id"] == mine:
                    flow.update(phase="done", message="")
            return
        error = reply.get("error")
        if error == "slow_down":
            interval = int(reply.get("interval") or interval + 5)
        elif error and error != "authorization_pending":
            _fail(ERRORS.get(error) or reply.get("error_description") or str(error), mine)
            return
    _fail(ERRORS["expired_token"], mine)


def start(post=_post, background=True):
    """Asks GitHub for a code and waits for it in the background. Returns what to show."""
    cid = client_id()
    if not cid:
        return {"ok": False, "error": "pas d'application GitHub dans deployment.json"}
    reply = post("/login/device/code", {"client_id": cid, "scope": SCOPE})
    if reply.get("error") or not reply.get("device_code"):
        return {"ok": False, "error": ERRORS.get(reply.get("error")) or reply.get("error_description") or "GitHub n'a pas répondu"}
    with lock:
        flow["id"] += 1
        mine = flow["id"]
        flow.update(phase="code", user_code=reply["user_code"], uri=reply["verification_uri"], message="")
    expires = int(reply.get("expires_in") or 900)
    try:
        PENDING.write_text(json.dumps({"device_code": reply["device_code"], "user_code": reply["user_code"], "uri": reply["verification_uri"], "interval": int(reply.get("interval") or 5),
                                       "until": time.time() + expires}), encoding="utf-8")
        PENDING.chmod(0o600)
    except OSError:
        pass
    args = (mine, reply["device_code"], int(reply.get("interval") or 5), expires, post)
    if background:
        threading.Thread(target=_wait, args=args, daemon=True).start()
    return {"ok": True, **snapshot()}


def resume(post=_post, background=True):
    """After a restart of the brain: a code that was shown and has not expired is waited for again."""
    try:
        saved = json.loads(PENDING.read_text(encoding="utf-8"))
        left = int(saved["until"] - time.time())
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if left <= 5 or github.token_value():
        PENDING.unlink(missing_ok=True)
        return False
    with lock:
        flow["id"] += 1
        mine = flow["id"]
        flow.update(phase="code", user_code=saved.get("user_code"), uri=saved.get("uri"), message="")
    args = (mine, saved["device_code"], int(saved.get("interval") or 5), left, post)
    if background:
        threading.Thread(target=_wait, args=args, daemon=True).start()
    return True


def cancel():
    PENDING.unlink(missing_ok=True)
    with lock:
        flow["id"] += 1
        flow.update(phase="idle", user_code=None, uri=None, message="")
    return {"ok": True}


def snapshot():
    with lock:
        return {"phase": flow["phase"], "user_code": flow["user_code"], "uri": flow["uri"], "message": flow["message"]}
