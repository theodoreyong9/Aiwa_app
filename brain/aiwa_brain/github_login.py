"""GitHub's device flow: the phone shows a short code, the person types it once on github.com, and the brain waits for the token (no token to copy, nothing to paste). It is how the first Aiwa did it.
The application is the one of deployment.json (github.clientId); a device-flow application has no secret. The token it hands over is kept like any other (github.set_token), after GitHub has named the account."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, files, github

SCOPE = "repo"      # all the repositories (the private ones too), and the releases a production is deleted from
BASE = "https://github.com"

lock = threading.Lock()
flow = {"phase": "idle", "user_code": None, "uri": None, "message": "", "id": 0}


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
        reply = post("/login/oauth/access_token", {"client_id": client_id(), "device_code": code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        token = reply.get("access_token")
        if isinstance(token, str):
            try:
                github.set_token(token)
            except github.GithubError as err:
                _fail(str(err), mine)
                return
            files.forget()
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
    args = (mine, reply["device_code"], int(reply.get("interval") or 5), int(reply.get("expires_in") or 900), post)
    if background:
        threading.Thread(target=_wait, args=args, daemon=True).start()
    return {"ok": True, **snapshot()}


def cancel():
    with lock:
        flow["id"] += 1
        flow.update(phase="idle", user_code=None, uri=None, message="")
    return {"ok": True}


def snapshot():
    with lock:
        return {"phase": flow["phase"], "user_code": flow["user_code"], "uri": flow["uri"], "message": flow["message"]}
