"""What the super agent keeps between two conversations: short notes the person asked it to remember. Written on the phone only (never in a public repository), readable and erasable."""
import json
import re
import threading
import time
import uuid

from . import config

MAX_NOTES = 100
MAX_CHARS = 300
CONDENSE_AT = 60      # beyond this many notes, the oldest ones are condensed
CONDENSE_TAKE = 30    # how many of the oldest are condensed at once
CONDENSE_INTO = 6     # and what they become, at most
FILE = config.APP_DIR / "memory.json"
_lock = threading.Lock()

REMEMBER_RE = re.compile(r"\b(retiens|retenir|souviens|souvenir|n'oublie pas|n’oublie pas|note que|note bien|mémorise|memorise|garde en mémoire|rappelle-toi)\b", re.I)
FORGET_RE = re.compile(r"\b(oublie|oublier|efface|effacer|supprime|supprimer|enl[eè]ve)\b", re.I)


def _load():
    try:
        data = json.loads(FILE.read_text("utf-8"))
        return [n for n in data if isinstance(n, dict) and isinstance(n.get("text"), str)] if isinstance(data, list) else []
    except Exception:
        return []


def _save(notes):
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes, ensure_ascii=False), "utf-8")
    tmp.replace(FILE)


def notes():
    with _lock:
        return _load()


def add(text):
    """Keep one note. The note, or None when it is empty or already there."""
    text = " ".join(str(text or "").split())[:MAX_CHARS]
    if not text:
        return None
    with _lock:
        all_ = _load()
        if any(n["text"].lower() == text.lower() for n in all_):
            return None
        note = {"id": "m" + uuid.uuid4().hex[:12], "text": text, "ts": int(time.time())}
        all_.append(note)
        _save(all_[-MAX_NOTES:])
        return note


def forget(what):
    """`what`: a note id, "all", or words found in the notes. How many were erased."""
    what = str(what or "").strip()
    if not what:
        return 0
    with _lock:
        all_ = _load()
        if what.lower() == "all":
            kept = []
        else:
            low = what.lower()
            kept = [n for n in all_ if n.get("id") != what and low not in n["text"].lower()]
        _save(kept)
        return len(all_) - len(kept)


def digest():
    """The notes as the agent reads them, newest last, within a limit."""
    lines = [n["text"] for n in notes()]
    out, size = [], 0
    for line in reversed(lines):
        size += len(line) + 3
        if size > 1800:
            break
        out.append(line)
    return list(reversed(out))


def apply(spoken, reply):
    """The `remember` / `forget` of a reply, kept only when the person's own sentence asked for it. Returns what was done."""
    done = []
    if not isinstance(reply, dict) or not spoken:
        return done
    spoken = str(spoken)
    if spoken.startswith("[Aiwa"):
        return done
    if reply.get("remember") and REMEMBER_RE.search(spoken):
        items = reply["remember"] if isinstance(reply["remember"], list) else [reply["remember"]]
        for item in items[:3]:
            if add(item):
                done.append("remember")
    if reply.get("forget") and FORGET_RE.search(spoken):
        what = reply["forget"]
        if forget(what if isinstance(what, str) else str(what)):
            done.append("forget")
    return done


def to_condense():
    """The oldest notes to condense (a list of notes), or [] while the memory is small enough."""
    all_ = notes()
    return all_[:CONDENSE_TAKE] if len(all_) > CONDENSE_AT else []


def condense_prompt(old):
    return ("Voici des notes anciennes qu'une personne t'a demandé de retenir. Regroupe-les en au plus " + str(CONDENSE_INTO) + " notes courtes (chacune sous " + str(MAX_CHARS) + " caractères) "
            "sans perdre un fait durable (préférences, projets, noms, dates) ; supprime les doublons et ce qui est périmé. Réponds seulement par du JSON : {\"notes\":[\"…\"]}.\n\n"
            + "\n".join("- " + n["text"] for n in old))


def replace(old, texts):
    """The old notes are replaced by the condensed ones (placed first, as the oldest). False when the answer is unusable."""
    texts = [" ".join(str(t).split())[:MAX_CHARS] for t in (texts if isinstance(texts, list) else []) if str(t).strip()][:CONDENSE_INTO]
    if not texts:
        return False
    gone = {n["id"] for n in old}
    with _lock:
        rest = [n for n in _load() if n.get("id") not in gone]
        base = int(old[0].get("ts") or time.time())
        made = [{"id": "c" + uuid.uuid4().hex[:12], "text": t, "ts": base} for i, t in enumerate(texts)]
        _save((made + rest)[-MAX_NOTES:])
    return True
