"""The files tied to a recipient: for one file and one of its recipients (« cibles »), the other files the person ticked as going with it (the CV and the letter for this journal, the CV alone for that one).
Only a label kept on the phone: nothing is moved or written in a repository, and the link goes one way, from the recipient to its files. Standard library only."""
import json
import threading

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


def get(repo, tag, file):
    """{recipient value: [{"repo", "tag", "file"}]} for this file."""
    with _lock:
        found = _load().get(key(repo, tag, file))
    return found if isinstance(found, dict) else {}


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
    return {"ok": True, "count": len(clean)}
