"""The person's profile: the repository whose `Profile/` folder is her page (the page itself is the work of a session), and the check of what falls short."""
import base64
import hashlib
import json
import re
import time
import urllib.request

from . import github, profile_lib

PUB_FILE = "aiwa.json"     # in Profile/: {"v": 1, "pub": "<64 hex>"}, the key a coffee is sent to
PUB_RE = re.compile(r"[0-9a-f]{64}")
SEEN_FILE = "aiwa-seen.json"   # in Profile/: {"v": 1, "seen": ["owner/name", …]}, the profiles this person crossed in the last week: names only, no place, no distance, no time (public)
SEEN_MAX = 5000
SEEN_EVERY = 3600             # at most one write an hour
FAVS_FILE = "aiwa-favorites.json"      # in Profile/: {"v": 1, "favs": ["owner/name", …]}, the profiles this person keeps as favourites (names only, public)
JUMPS_FILE = "aiwa-jumps.json"         # in Profile/: {"v": 1, "jumps": ["owner/name", …]}, the profiles this person jumped into, the latest first (names only, public)
LISTS = {"favs": FAVS_FILE, "jumps": JUMPS_FILE}
LIST_EVERY = 300              # these two change by hand: written within five minutes
NETWORK_MAX = 100
NETWORK_FAVORITES = 25


def profile_state():
    repo = profile_lib.repo()
    return {"ok": True, "repo": repo}


def profile_apply(data):
    """The repository of the profile (the phone's settings): the only thing Aiwa keeps; the page itself is the work of a session."""
    if "repo" in data and not profile_lib.set_repo(data.get("repo")):
        return {"ok": False, "error": "dépôt invalide"}
    return profile_state()


def read_aiwa(repo):
    """The `Profile/aiwa.json` of a repository as it is now (read through the API: a copy a few minutes old would erase a recent change), {} when there is none."""
    try:
        old = github.api(f"/repos/{repo}/contents/{profile_lib.FOLDER}/{PUB_FILE}")
        data = json.loads(base64.b64decode(old["content"]).decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (github.GithubError, KeyError, TypeError, ValueError):
        return {}


def update_aiwa(changes, message):
    """Changes some keys of `Profile/aiwa.json` and keeps all the others (the key of the wallet, the traits, the zones, the switch of adaptation): one file, several writers. {"ok", "unchanged"?, "error"?}."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    current = read_aiwa(repo)
    merged = {**current, **changes}
    if merged == current:
        return {"ok": True, "unchanged": True}
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/{PUB_FILE}", json.dumps(merged, ensure_ascii=False, indent=1).encode("utf-8"), message)
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    return {"ok": True}


def publish_pub(pub):
    """Leaves the public key of the wallet in `Profile/aiwa.json` of her profile repository (public by nature), once: nothing is written again while it is the same."""
    pub = str(pub or "").strip().lower()
    repo = profile_lib.repo()
    if not PUB_RE.fullmatch(pub):
        return {"ok": False, "error": "clé invalide"}
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    data = profile_lib.load()
    mark = f"{repo.lower()}:{pub}"
    if data.get("pub_sent") == mark:
        return {"ok": True, "unchanged": True}
    done = update_aiwa({"v": 1, "pub": pub}, "Aiwa : la clé du wallet (pour recevoir un café)")
    if not done["ok"]:
        return done
    data["pub_sent"] = mark
    profile_lib.PROFILE_FILE.write_text(json.dumps(data), encoding="utf-8")
    return {"ok": True}


def publish_contracts(events):
    """Leaves the person's own `contract-spec` events in `Profile/aiwa-contracts.json` (public, each event signed: whoever reads it checks them), once for the same content."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    if not isinstance(events, list) or not events or len(events) > 200:
        return {"ok": False, "error": "rien à publier"}
    clean = [e for e in events if isinstance(e, dict) and e.get("type") == "contract-spec" and isinstance(e.get("author"), str) and isinstance(e.get("payload"), dict)]
    creators = {e["author"] for e in clean}
    if not clean or len(creators) != 1:
        return {"ok": False, "error": "des contrats d'une seule personne"}
    raw = json.dumps({"v": 1, "creator": creators.pop(), "events": clean}, sort_keys=True, separators=(",", ":")).encode()
    if len(raw) > 400_000:
        return {"ok": False, "error": "trop gros"}
    data = profile_lib.load()
    mark = f"{repo.lower()}:{hashlib.sha256(raw).hexdigest()}"
    if data.get("contracts_sent") == mark:
        return {"ok": True, "unchanged": True}
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/aiwa-contracts.json", raw, "Aiwa : mes contrats (événements signés)")
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    data["contracts_sent"] = mark
    profile_lib.PROFILE_FILE.write_text(json.dumps(data), encoding="utf-8")
    return {"ok": True}


def publish_seen(repos):
    """Leaves the list of the profiles the person crossed this week in `Profile/aiwa-seen.json` of her profile repository (names of public repositories only): whoever takes her place in « Swipe » reads it
    from GitHub. Written when it changed, and at most once an hour."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    clean = [r for r in dict.fromkeys(str(x) for x in (repos if isinstance(repos, list) else [])) if profile_lib.REPO_RE.fullmatch(r) and r.lower() != repo.lower()][:SEEN_MAX]
    if not clean:
        return {"ok": False, "error": "rien à publier"}
    raw = json.dumps({"v": 1, "seen": clean}, separators=(",", ":")).encode()
    data = profile_lib.load()
    mark = f"{repo.lower()}:{hashlib.sha256(raw).hexdigest()}"
    if data.get("seen_sent") == mark:
        return {"ok": True, "unchanged": True}
    if time.time() - float(data.get("seen_at") or 0) < SEEN_EVERY:
        return {"ok": True, "waiting": True}
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/{SEEN_FILE}", raw, "Aiwa : les profils croisés cette semaine")
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    data["seen_sent"] = mark
    data["seen_at"] = time.time()
    profile_lib.PROFILE_FILE.write_text(json.dumps(data), encoding="utf-8")
    return {"ok": True}


def seen_of(repo):
    """The profiles a person crossed this week, as she left them in her `Profile/aiwa-seen.json` (GitHub's raw files: no question against the API's limit); an empty list when there is none."""
    if not isinstance(repo, str) or not profile_lib.REPO_RE.fullmatch(repo):
        return {"ok": False, "seen": []}
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{profile_lib.FOLDER}/{SEEN_FILE}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aiwa"}), timeout=15) as resp:
            listed = (json.loads(resp.read(1_000_000)) or {}).get("seen")
    except (OSError, ValueError, AttributeError):
        return {"ok": True, "seen": []}
    names = [r for r in dict.fromkeys(str(x) for x in (listed if isinstance(listed, list) else [])) if profile_lib.REPO_RE.fullmatch(r) and r.lower() != repo.lower()]
    return {"ok": True, "seen": names[:SEEN_MAX]}


def publish_list(kind, repos):
    """The favourites (`favs`) or the jumps (`jumps`) of the person, in her own profile repository, so that her friends can swipe what she keeps and where she went. Written when it changed, at most every five minutes."""
    if kind not in LISTS:
        return {"ok": False, "error": "liste inconnue"}
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    clean = [r for r in dict.fromkeys(str(x) for x in (repos if isinstance(repos, list) else [])) if profile_lib.REPO_RE.fullmatch(r) and r.lower() != repo.lower()][:SEEN_MAX]
    raw = json.dumps({"v": 1, kind: clean}, separators=(",", ":")).encode()
    data = profile_lib.load()
    mark = f"{repo.lower()}:{hashlib.sha256(raw).hexdigest()}"
    if data.get(f"{kind}_sent") == mark:
        return {"ok": True, "unchanged": True}
    if time.time() - float(data.get(f"{kind}_at") or 0) < LIST_EVERY:
        return {"ok": True, "waiting": True}
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/{LISTS[kind]}", raw, "Aiwa : " + ("mes favoris" if kind == "favs" else "mes jumps"))
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    data[f"{kind}_sent"] = mark
    data[f"{kind}_at"] = time.time()
    profile_lib.PROFILE_FILE.write_text(json.dumps(data), encoding="utf-8")
    return {"ok": True}


def list_of(repo, kind):
    """A person's favourites or jumps as she left them (GitHub's raw files); [] when there is none."""
    if kind not in LISTS or not isinstance(repo, str) or not profile_lib.REPO_RE.fullmatch(repo):
        return []
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{profile_lib.FOLDER}/{LISTS[kind]}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aiwa"}), timeout=10) as resp:
            listed = (json.loads(resp.read(1_000_000)) or {}).get(kind)
    except (OSError, ValueError, AttributeError):
        return []
    return [r for r in dict.fromkeys(str(x) for x in (listed if isinstance(listed, list) else [])) if profile_lib.REPO_RE.fullmatch(r) and r.lower() != repo.lower()][:SEEN_MAX]


def network(favorites):
    """The deck to swipe from the « Réseau » key: the profiles my favourites jumped into and the favourites of my favourites, the most mentioned first, without me, without my own favourites. {"ok", "deck", "read"}."""
    from concurrent.futures import ThreadPoolExecutor
    mine = {r.lower() for r in (favorites if isinstance(favorites, list) else []) if isinstance(r, str)}
    mine_repo = (profile_lib.repo() or "").lower()
    chosen = [r for r in dict.fromkeys(str(x) for x in (favorites if isinstance(favorites, list) else [])) if profile_lib.REPO_RE.fullmatch(r)][:NETWORK_FAVORITES]
    count = {}
    names = {}

    def read(friend):
        return list_of(friend, "jumps") + list_of(friend, "favs")
    with ThreadPoolExecutor(max_workers=6) as pool:
        lists = list(pool.map(read, chosen))
    for found in lists:
        for r in dict.fromkeys(found):
            key = r.lower()
            if key in mine or key == mine_repo:
                continue
            count[key] = count.get(key, 0) + 1
            names.setdefault(key, r)
    deck = [names[k] for k in sorted(count, key=lambda k: (-count[k], k))][:NETWORK_MAX]
    return {"ok": True, "deck": deck, "read": sum(1 for found in lists if found), "of": len(chosen)}


def pub_of(repo):
    """The key a person left in the `Profile/aiwa.json` of her repository (read from GitHub's raw files: no question against the API's limit), or None."""
    if not isinstance(repo, str) or not profile_lib.REPO_RE.fullmatch(repo):
        return {"ok": False, "pub": None}
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{profile_lib.FOLDER}/{PUB_FILE}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aiwa"}), timeout=15) as resp:
            pub = str((json.loads(resp.read(2000)) or {}).get("pub") or "").lower()
    except (OSError, ValueError, AttributeError):
        return {"ok": True, "pub": None}
    return {"ok": True, "pub": pub if PUB_RE.fullmatch(pub) else None}


def profile_check():
    """Reads the profile of the repository chosen (the file `Profile/index.html` and the sizes of the media it names, from GitHub as they are) and says what falls short of the minimum."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "Aucun dépôt choisi pour le profil (Réglages)."}
    base = f"https://raw.githubusercontent.com/{repo}/HEAD/{profile_lib.FOLDER}/"
    try:
        with urllib.request.urlopen(urllib.request.Request(base + "index.html", headers={"User-Agent": "aiwa"}), timeout=15) as resp:
            html = resp.read(profile_lib.READ_MAX).decode("utf-8", "replace")
    except (OSError, ValueError):
        return {"ok": False, "error": f"Pas de profil lisible dans {repo} : un dossier Profile/ public avec un index.html."}
    media = {}
    names = {a or b for a, b in re.findall(r"""(?:src|poster|href)\s*=\s*["'](media/[^"'?#]{1,120})|url\(\s*["']?(media/[^"')?#]{1,120})""", html)}
    for path in sorted(names)[:20]:
        try:
            with urllib.request.urlopen(urllib.request.Request(base + path, method="HEAD", headers={"User-Agent": "aiwa"}), timeout=15) as resp:
                media[path] = int(resp.headers.get("Content-Length") or 0)
        except (OSError, ValueError):
            media[path] = 0
    problems = profile_lib.check(html, media)
    return {"ok": True, "repo": repo, "problems": problems}