"""The productions: everything a session makes for the person is a file in a release of a repository, and the tag says the kind (`docs-…`, `image-…`, `video-…`, `app-…`, `page-…`).
This module lists them (for one repository, or all), deletes one, and says how to share one."""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, github, repos, sessions, state

PAGE_MAX = 3_000_000       # bytes of a page the brain hands to the app
CACHE_SECONDS = 45
ALL_REPOS_MAX = 12         # « Tous » reads at most this many repositories, those with a session first
_cache = {}                # repo -> (time, items)
_lock = threading.Lock()


def kind_of(tag):
    """docs / image / video / app / page from a release tag, or None for a release that is not a production."""
    prefix = str(tag or "").split("-", 1)[0].lower()
    return prefix if prefix in config.KINDS else None


def _title(release, asset):
    name = release["name"]
    if name and name != release["tag"]:
        return name
    return re.sub(r"[-_]+", " ", re.sub(r"\.[A-Za-z0-9]{1,5}$", "", asset["name"] or release["tag"])).strip() or release["tag"]


def _items_of(repo):
    """The productions of one repository, newest first: one item per file of a production release."""
    with _lock:
        cached = _cache.get(repo)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    items = []
    for release in github.releases(repo):
        kind = kind_of(release["tag"])
        if kind is None:
            continue
        for asset in release["assets"]:
            items.append({
                "repo": repo, "kind": kind, "tag": release["tag"], "release": release["id"], "title": _title(release, asset), "file": asset["name"], "size": asset["size"],
                "url": asset["url"], "ts": release["published"], "page": release["page"],
            })
    with _lock:
        _cache[repo] = (time.time(), items)
    return items


def forget(repo=None):
    with _lock:
        if repo:
            _cache.pop(repo, None)
        else:
            _cache.clear()


def worked_on():
    """« Tous »: the repositories that have a session (the most recent first), and the one in use. Not every repository of the account: that would be dozens of questions to GitHub for nothing."""
    with state.lock:
        names = [state.current_repo] if state.current_repo else []
    for entry in sessions.load_all():
        name = entry.get("repo")
        if isinstance(name, str) and github.REPO_RE.fullmatch(name) and name not in names:
            names.append(name)
    return names


def listing(repo=None):
    """{"repo": the repository asked or None for all, "repos": [names], "error": str|None, "items": {kind: [item…]}} with the newest first inside each kind."""
    wanted = repo if repo and github.REPO_RE.fullmatch(repo) else None
    names = [wanted] if wanted else worked_on()[:ALL_REPOS_MAX]
    items, errors = [], []

    def one(name):
        try:
            return _items_of(name)
        except github.GithubError as err:
            errors.append(f"{name} : {err}")
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        for found in pool.map(one, names):
            items.extend(found)
    by_kind = {kind: sorted((i for i in items if i["kind"] == kind), key=lambda i: -i["ts"]) for kind in config.KINDS}
    return {"repo": wanted, "repos": repos.names()[:30], "error": "; ".join(errors[:2]) or None, "items": by_kind}


def find(repo, tag, name=None):
    if not github.REPO_RE.fullmatch(str(repo or "")):
        return None
    for item in _items_of(repo):
        if item["tag"] == tag and (name is None or item["file"] == name):
            return item
    return None


def delete(repo, tag):
    """Deletes the release (and its tag): the production is gone from the list. Needs the GitHub token of the settings."""
    item = find(repo, tag)
    if item is None:
        return {"ok": False, "error": "cette production n'existe plus"}
    if not github.token_value():
        return {"ok": False, "error": "pour supprimer, il faut un jeton GitHub (réglages : clés et plafonds)"}
    try:
        github.delete_release(repo, item["release"], tag)
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    forget(repo)
    return {"ok": True}


def share(repo, tag, name=None):
    """What the phone shares: the address of the file (a page shares its file too), with a title."""
    item = find(repo, tag, name)
    if item is None:
        return {"ok": False, "error": "cette production n'existe plus"}
    return {"ok": True, "title": item["title"], "url": item["url"], "page": item["page"], "kind": item["kind"], "file": item["file"]}


def page_html(repo, tag):
    """The HTML of a page production, read here and handed to the app's own window (a release file is served as a download, not as a page)."""
    item = find(repo, tag)
    if item is None or item["kind"] != "page":
        return None
    raw = github.fetch(item["url"], PAGE_MAX)
    return raw.decode("utf-8", "replace") if raw else None


def newest_video_marks(repo=None):
    """[[file, ts]] of the videos that exist now: the cast of « la vidéo qui va arriver » waits for one that is not in this list."""
    return [[i["file"], i["ts"]] for i in listing(repo)["items"]["video"]]


def summary(limit=3):
    """For the super agent: per kind, how many productions there are over the known repositories and the newest titles. Reads the cache only (it never waits on GitHub)."""
    out = {kind: [] for kind in config.KINDS}
    with _lock:
        cached = [(repo, items) for repo, (_t, items) in _cache.items()]
    for repo, items in cached:
        for item in items:
            out[item["kind"]].append(item)
    return {kind: {"count": len(found), "newest": [f"{i['title']} ({i['repo'].split('/')[-1]})" for i in sorted(found, key=lambda i: -i["ts"])[:limit]]} for kind, found in out.items()}


def warm():
    """Reads the releases of the known repositories in the background, so that the super agent knows the productions without waiting."""
    def run():
        try:
            listing(None)
        except Exception as err:      # a bad round must never end the thread
            print(f"[{state.ts()}] files: {err}", flush=True)
    threading.Thread(target=run, daemon=True).start()
