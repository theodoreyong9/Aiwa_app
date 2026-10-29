"""The person's profile: the repository whose `Profile/` folder is her page (the page itself is the work of a session), and the check of what falls short."""
import json
import re
import urllib.request

from . import github, profile_lib

PUB_FILE = "aiwa.json"     # in Profile/: {"v": 1, "pub": "<64 hex>"}, the key a coffee is sent to
PUB_RE = re.compile(r"[0-9a-f]{64}")


def profile_state():
    repo = profile_lib.repo()
    return {"ok": True, "repo": repo}


def profile_apply(data):
    """The repository of the profile (the phone's settings): the only thing Aiwa keeps; the page itself is the work of a session."""
    if "repo" in data and not profile_lib.set_repo(data.get("repo")):
        return {"ok": False, "error": "dépôt invalide"}
    return profile_state()


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
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/{PUB_FILE}", json.dumps({"v": 1, "pub": pub}).encode(), "Aiwa : la clé du wallet (pour recevoir un café)")
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    data["pub_sent"] = mark
    profile_lib.PROFILE_FILE.write_text(json.dumps(data), encoding="utf-8")
    return {"ok": True}


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