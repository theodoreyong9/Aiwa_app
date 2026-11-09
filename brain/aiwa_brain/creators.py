"""« Créateurs »: the profiles whose wallet has distributed at least one contract. In Aiwa that is not a deployment on a chain: it is a `contract-spec` event, signed by the key of the wallet, that the person leaves in the
`Profile/aiwa-contracts.json` of her profile repository (the full source travels in the event). Each event is checked here like the wallet checks it (the key derives the author, the id is the hash of the content, the
signature holds, the source matches its hash) and must be signed by the key the profile names in its `Profile/aiwa.json`: a copied or forged file counts for nothing. Anyone can publish a contract: what a contract may
do is the business of the permissions and of the scoring, not of this list."""
import hashlib
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import ed25519_lib, github, profile_lib

FILE = "aiwa-contracts.json"
PUB_FILE = "aiwa.json"
MAX_EVENTS = 200
READ_MAX = 600_000
KEEP_SECONDS = 600
WORKERS = 6
HEX = re.compile(r"[0-9a-f]+")
_cache = {}


def _canon(value):
    if isinstance(value, list):
        return [_canon(v) for v in value]
    if isinstance(value, dict):
        return {k: _canon(value[k]) for k in sorted(value)}
    return value


def event_valid(event):
    """True for a genuine `contract-spec` event: the same three checks as `verifyEvent` (core/event.js), plus the source against its hash."""
    try:
        if not isinstance(event, dict) or event.get("type") != "contract-spec":
            return False
        payload = event.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("sourceCode"), str):
            return False
        if hashlib.sha256(payload["sourceCode"].encode("utf-8")).hexdigest() != payload.get("sourceHash"):
            return False
        key, sig = str(event.get("authorPublicKey") or ""), str(event.get("signature") or "")
        if not HEX.fullmatch(key) or len(key) != 64 or not HEX.fullmatch(sig) or len(sig) != 128:
            return False
        if hashlib.sha256(bytes.fromhex(key)).hexdigest() != event.get("author"):
            return False
        core = {"domain": event.get("domain"), "author": event.get("author"), "authorPublicKey": key, "parents": sorted(event.get("parents") or []),
                "type": "contract-spec", "payload": _canon(payload), "createdAt": event.get("createdAt")}
        raw = json.dumps(core, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest() == event.get("id") and ed25519_lib.verify(bytes.fromhex(sig), raw, bytes.fromhex(key))
    except Exception:
        return False


def contracts_in(data, pub):
    """The verified contracts of a file read from a profile: [{"name", "version", "hash"}], only those signed by `pub` (the key the profile names). Forged, altered or foreign events are dropped."""
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("events"), list) or not isinstance(pub, str):
        return []
    author = hashlib.sha256(bytes.fromhex(pub)).hexdigest() if HEX.fullmatch(pub) and len(pub) == 64 else None
    out, seen = [], set()
    for event in data["events"][:MAX_EVENTS]:
        if not isinstance(event, dict) or event.get("authorPublicKey") != pub or event.get("author") != author or not event_valid(event):
            continue
        h = event["payload"]["sourceHash"]
        if h in seen:
            continue
        seen.add(h)
        out.append({"name": str(event["payload"].get("name") or "")[:80], "version": str(event["payload"].get("version") or "")[:20], "hash": h})
    return out


def _raw(repo, name, limit):
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{profile_lib.FOLDER}/{name}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aiwa"}), timeout=15) as resp:
            return json.loads(resp.read(limit))
    except (OSError, ValueError):
        return None


def of(repo):
    """{"ok", "creator", "contracts"}: what a profile has distributed, checked (read from GitHub's raw files, kept ten minutes)."""
    if not isinstance(repo, str) or not profile_lib.REPO_RE.fullmatch(repo):
        return {"ok": False, "creator": False, "contracts": []}
    key = repo.lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < KEEP_SECONDS:
        return hit[1]
    wallet = _raw(repo, PUB_FILE, 2000)
    pub = str((wallet or {}).get("pub") or "").lower() if isinstance(wallet, dict) else ""
    contracts = []
    if pub:
        contracts = contracts_in(_raw(repo, FILE, READ_MAX), pub)
    out = {"ok": True, "creator": bool(contracts), "contracts": contracts}
    _cache[key] = (time.time(), out)
    return out


def creators_among(repos):
    """The repositories among `repos` that are creators, the one with the most contracts first (the order of `repos` otherwise): [(repo, contracts)]."""
    names = [r for r in dict.fromkeys(repos) if isinstance(r, str) and profile_lib.REPO_RE.fullmatch(r)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        found = list(pool.map(of, names))
    kept = [(r, f["contracts"]) for r, f in zip(names, found) if f.get("creator")]
    return sorted(kept, key=lambda item: -len(item[1]))


def _search():
    """Profiles that left a contracts file (GitHub code search; needs the account of the person)."""
    token = github.token_value()
    if not token:
        raise RuntimeError("Connecte ton compte GitHub dans les réglages : la recherche de GitHub est fermée sans lui.")
    import urllib.error
    import urllib.parse
    out = []
    for page in (1, 2):
        url = f"{github.GITHUB_API}/search/code?per_page=30&page={page}&q=" + urllib.parse.quote(f"path:Profile filename:{FILE}")
        request = urllib.request.Request(url, headers={"User-Agent": "aiwa", "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=20) as reply:
                data = json.loads(reply.read() or b"{}")
        except urllib.error.HTTPError as err:
            if out:
                break
            raise RuntimeError("GitHub limite les recherches : réessaie dans une minute." if err.code in (403, 429) else f"GitHub a refusé la recherche ({err.code}).")
        except (OSError, ValueError):
            if out:
                break
            raise RuntimeError("GitHub ne répond pas.")
        items = data.get("items") or []
        for item in items:
            repo = ((item.get("repository") or {}).get("full_name")) or ""
            if item.get("path") == f"{profile_lib.FOLDER}/{FILE}" and profile_lib.REPO_RE.fullmatch(repo) and repo not in out:
                out.append(repo)
        if len(items) < 30:
            break
    return out


def listed():
    """Every creator GitHub knows of, checked: [(repo, contracts)]."""
    return creators_among(_search())
