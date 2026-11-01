"""The files tied to a recipient: for one file and one of its recipients (« cibles »), the other files the person ticked as going with it (the CV and the letter for this journal, the CV alone for that one).
A label only: no file is moved, and the link goes one way, from the recipient to its files. Kept on the phone and also written next to the file, in its release, as `<file>.pj.json` (separate from the card
of recipients that a session writes, so that neither overwrites the other); read from there when the phone has nothing, after a reinstallation. Standard library only."""
import json
import tempfile
import threading
from pathlib import Path

from . import github
from .paths import DATA

FILE = DATA / "links.json"
MAX_FILES = 30
_lock = threading.Lock()


def _load():
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def key(repo, tag, file):
    return f"{repo}|{tag}|{file}"


def _remote(repo, tag, file):
    """What was written next to the file in its release (when the phone has nothing: a reinstallation). {} when there is nothing or GitHub cannot be asked."""
    if not github.REPO_RE.fullmatch(str(repo or "")):
        return {}
    try:
        for release in github.releases(repo):
            if release["tag"] != tag:
                continue
            asset = next((a for a in release["assets"] if a["name"] == f"{file}.pj.json"), None)
            raw = github.fetch(asset["url"], 20000) if asset else None
            data = json.loads(raw.decode("utf-8")) if raw else {}
            found = data.get("pj") if isinstance(data, dict) else None
            return {c: [f for f in fs if isinstance(f, dict)] for c, fs in found.items() if isinstance(fs, list)} if isinstance(found, dict) else {}
    except (github.GithubError, ValueError, AttributeError):
        return {}
    return {}


def get(repo, tag, file):
    """{recipient value: [{"repo", "tag", "file"}]} for this file: the phone's, else the one written in the release."""
    with _lock:
        found = _load().get(key(repo, tag, file))
    if isinstance(found, dict) and found:
        return found
    remote = _remote(repo, tag, file) if github.token_value() else {}
    if remote:
        with _lock:
            data = _load()
            data[key(repo, tag, file)] = remote
            FILE.write_text(json.dumps(data), encoding="utf-8")
    return remote


def _publish(repo, tag, file):
    """Writes the links of this file next to it, in its release. Never raises: the phone keeps them anyway."""
    try:
        with _lock:
            mine = _load().get(key(repo, tag, file)) or {}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{file}.pj.json"
            path.write_text(json.dumps({"v": 1, "pj": mine}, ensure_ascii=False), encoding="utf-8")
            github.release_upload(repo, tag, tag, "", path, f"{file}.pj.json", timeout=120)
    except (github.GithubError, OSError):
        pass


def set_links(repo, tag, file, cible, files):
    """Remembers the files ticked for a recipient of a file; an empty list forgets them. {"ok", "count"}."""
    cible = " ".join(str(cible or "").split())[:200]
    if not (github.REPO_RE.fullmatch(str(repo or "")) and tag and file and cible):
        return {"ok": False, "error": "lien illisible"}
    clean, seen = [], set()
    for f in files if isinstance(files, list) else []:
        if not isinstance(f, dict) or not github.REPO_RE.fullmatch(str(f.get("repo") or "")) or not f.get("tag") or not f.get("file"):
            continue
        ident = (f["repo"], str(f["tag"]), str(f["file"]))
        if ident in seen or ident == (repo, tag, file):
            continue
        seen.add(ident)
        clean.append({"repo": ident[0], "tag": ident[1][:120], "file": ident[2][:200]})
        if len(clean) >= MAX_FILES:
            break
    with _lock:
        data = _load()
        mine = data.get(key(repo, tag, file))
        mine = mine if isinstance(mine, dict) else {}
        if clean:
            mine[cible] = clean
        else:
            mine.pop(cible, None)
        if mine:
            data[key(repo, tag, file)] = mine
        else:
            data.pop(key(repo, tag, file), None)
        FILE.write_text(json.dumps(data), encoding="utf-8")
    if github.token_value():
        threading.Thread(target=_publish, args=(repo, tag, file), daemon=True).start()
    return {"ok": True, "count": len(clean)}
