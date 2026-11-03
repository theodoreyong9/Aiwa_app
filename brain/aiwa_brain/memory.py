"""What the super agent keeps between two conversations: short notes the person asked it to remember. Written on the phone only (never in a public repository), readable and erasable."""
import json
import re
import threading
import time
import uuid

from . import config

MAX_NOTES = 2000
MAX_CHARS = 2000
CONDENSE_AT = 1000    # beyond this many notes, the oldest ones are condensed
CONDENSE_TAKE = 100   # how many of the oldest are condensed at once
CONDENSE_INTO = 10    # and what they become, at most
RECENT = 5            # the notes always in front of the agent; the others are found when the person asks
FOUND = 15            # the notes found for a question, at most
PROMPT_NOTE = 600     # a note, cut to this in the condensing prompt
FILE = config.APP_DIR / "memory.json"
_lock = threading.Lock()

REMEMBER_RE = re.compile(r"\b(retiens|retenir|souviens[- ]toi|n'oublie pas|n’oublie pas|note que|note bien|mémorise|memorise|garde en mémoire|rappelle[- ]toi)\b", re.I)
RECALL_RE = re.compile(r"\b(te rappelles?|te souviens?|rappelle[- ]moi|ce que je t'ai (dit|demandé|raconté)|qu'est[- ]ce que (tu sais|j'ai dit|je t'ai)|tu retiens|dans ta mémoire|de ma mémoire)\b", re.I)
WORD_RE = re.compile(r"[a-zà-ÿ0-9]{4,}")
STOP = {"tout", "tous", "cette", "dans", "pour", "avec", "sans", "elle", "elles", "nous", "vous", "mais", "donc", "quoi", "comme", "plus", "moins", "tres", "bien", "dire", "dit", "demande", "demandé", "rappelles", "rappelle", "souviens", "souvient", "retiens", "t'ai", "sais", "mémoire", "memoire", "ce que", "quand", "alors", "aussi", "fait", "faire", "veux", "peux", "sont", "etait", "était"}
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


def _plain(text):
    import unicodedata
    text = str(text).lower().replace("œ", "oe").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def recent():
    """The last notes: always in front of the agent."""
    return [n["text"] for n in notes()[-RECENT:]]


def search(sentence):
    """The notes that answer a sentence like « tu te rappelles de mon vélo ? »: the ones that share its words (the best first), or the newest when it asks for everything.
    [] when the sentence does not ask the agent to remember."""
    sentence = str(sentence or "")
    if not RECALL_RE.search(sentence):
        return []
    all_ = notes()
    words = {_plain(w) for w in WORD_RE.findall(sentence.lower())} - {_plain(w) for w in STOP}
    scored = []
    for i, n in enumerate(all_):
        low = _plain(n["text"])
        hits = sum(1 for w in words if w in low)
        if hits:
            scored.append((hits, i, n["text"]))
    if scored:
        scored.sort(key=lambda t: (-t[0], -t[1]))
        return [t[2] for t in scored[:FOUND]]
    return [n["text"] for n in all_[-FOUND:]]      # no word to look for: what was kept last


def count():
    return len(notes())


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
            + "\n".join("- " + n["text"][:PROMPT_NOTE] for n in old))


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
