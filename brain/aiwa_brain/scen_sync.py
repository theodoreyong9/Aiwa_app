"""The scenarios of the person kept in her GitHub too: one file each in the `Profile/scenarios/` folder of her profile repository (the one she chose for her profile: private or public is her choice on GitHub,
not Aiwa's). Written after each change, read at the start of the brain: a reinstallation finds them again. Local first: nothing is lost when GitHub or the repository is missing, and the scenarios that Aiwa
offers by itself (the defaults, unchanged) are not written. Standard library only."""
import hashlib
import json
import threading
import time

from . import config, github, profile_lib, scen_lib
from .paths import DATA

FOLDER = f"{profile_lib.FOLDER}/scenarios"
STATE = DATA / "scen_sync.json"        # {scenario id: hash of what was written} : what is on GitHub, so that a scenario deleted here is deleted there
_lock = threading.Lock()
_timer = None


def _known():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _remember(known):
    STATE.write_text(json.dumps(known), encoding="utf-8")


def _raw(sc):
    return json.dumps(sc, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")


def _is_default(sc):
    return any(d["id"] == sc["id"] and scen_lib.clean(d) == sc for d in scen_lib.DEFAULTS)


def push_all():
    """Writes what changed, deletes what was deleted here. {"ok", "written", "deleted"} or {"ok": False, "error"}."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    if not github.token_value():
        return {"ok": False, "error": "GitHub n'est pas connecté"}
    with _lock:
        local = scen_lib.load(config.SCENARIOS_FILE)
        known = _known()
        written = deleted = 0
        try:
            for sc in local:
                if _is_default(sc):
                    continue
                raw = _raw(sc)
                mark = hashlib.sha256(raw).hexdigest()
                if known.get(sc["id"]) != mark:
                    github.put_file(repo, f"{FOLDER}/{sc['id']}.json", raw, f"Aiwa : le scénario « {sc['name']} »")
                    known[sc["id"]] = mark
                    written += 1
            ids = {sc["id"] for sc in local}
            for gone in [i for i in known if i not in ids]:
                github.delete_file(repo, f"{FOLDER}/{gone}.json", "Aiwa : scénario supprimé")
                known.pop(gone)
                deleted += 1
        except github.GithubError as err:
            _remember(known)
            return {"ok": False, "error": str(err)}
        _remember(known)
    return {"ok": True, "written": written, "deleted": deleted}


def pull():
    """Adds the scenarios found on GitHub that are not here (a reinstallation, a second phone). What is here is never replaced. {"ok", "added"}."""
    repo = profile_lib.repo()
    if not repo or not github.token_value():
        return {"ok": False, "added": 0}
    try:
        listed = github.api(f"/repos/{repo}/contents/{FOLDER.replace(' ', '%20')}")
    except github.GithubError:
        return {"ok": True, "added": 0}
    added = 0
    with _lock:
        local = scen_lib.load(config.SCENARIOS_FILE)
        known = _known()
        have = {sc["id"] for sc in local}
        for node in listed if isinstance(listed, list) else []:
            name = str(node.get("name") or "")
            if not name.endswith(".json") or not node.get("download_url"):
                continue
            raw = github.fetch(node["download_url"], 20000)
            try:
                sc = scen_lib.clean(json.loads(raw.decode("utf-8"))) if raw else None
            except ValueError:
                sc = None
            if sc is None or sc["id"] in have or any(scen_lib.plain(o["word"]) == scen_lib.plain(sc["word"]) for o in local):
                continue
            local.append(sc)
            have.add(sc["id"])
            known[sc["id"]] = hashlib.sha256(_raw(sc)).hexdigest()
            added += 1
        if added:
            scen_lib.save(config.SCENARIOS_FILE, local)
            _remember(known)
    return {"ok": True, "added": added}


def sync_soon(delay=5.0):
    """After a change: one write a few seconds later, whatever the number of changes (the person edits a scenario in several steps)."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay, lambda: push_all())
        _timer.daemon = True
        _timer.start()


def startup():
    """At the start of the brain, once the network is there: scenarios found on GitHub are added, then what is here and not there goes up."""
    time.sleep(20)
    try:
        pull()
        push_all()
    except Exception as err:      # never a reason to stop the brain
        print(f"scénarios : {err}", flush=True)
