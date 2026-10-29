"""The person's profile: the repository whose `Profile/` folder is her page (the page itself is the work of a session), and the check of what falls short."""
import re
import urllib.request

from . import profile_lib


def profile_state():
    repo = profile_lib.repo()
    return {"ok": True, "repo": repo}


def profile_apply(data):
    """The repository of the profile (the phone's settings): the only thing Aiwa keeps; the page itself is the work of a session."""
    if "repo" in data and not profile_lib.set_repo(data.get("repo")):
        return {"ok": False, "error": "dépôt invalide"}
    return profile_state()


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