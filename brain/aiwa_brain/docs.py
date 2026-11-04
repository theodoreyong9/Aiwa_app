"""What the super agent reads of the code of Aiwa when the person asks about the application itself (« comment je crée un scénario ? », « qu'est-ce que tu sais faire ? »): the brain fetches the right files of the public
repository, keeps them an hour on the phone, and puts excerpts in the point. The agent answers from the real code, which is always the current one: there is no manual to keep up to date. Data, never orders."""
import re
import time

from . import agent_lib, config, relay

REPO = "theodoreyong9/Aiwa_app"
TTL = 3600
PER_FILE = 5000
TOTAL = 12000
GENERAL = "ARCHITECTURE.md"

# a question about the application (in plain letters: no accent, no apostrophe)
ASKS = re.compile(
    r"\bcomment (je |on |puis je |peut on |fait on |ca )?(cree|creer|fais|faire|utilise|utiliser|marche|fonctionne|configure|regle|ajoute|ajouter|change|changer|modifie|modifier|active|activer)"
    r"|\b(qu est ce que|que) (je peux|tu peux|tu sais|peut on)|\btu peux faire quoi|\ba quoi (ca )?sert|\bc est quoi\b|\bqu est ce que c est\b|\bpourquoi (tu|il|ca) (ne |n )?(comprend|marche|fonctionne|repond)"
    r"|\bexplique(s| moi)?\b|\baide moi (a|avec)\b")

# what to read for which subject (a word of the question, in plain letters -> files of the repository)
SUBJECTS = [
    (("scenario",), ["skills/profile/SKILL.md", "brain/aiwa_brain/scen_lib.py"]),
    (("page", "profil", "swipe", "bouton", "slot"), ["skills/profile/SKILL.md", "skills/page/SKILL.md"]),
    (("mot", "vocabulaire", "comprend", "commande", "dire", "voix", "vocal"), ["brain/aiwa_brain/agent_lib.py"]),
    (("instruction", "consigne"), ["skills/instructions/SKILL.md"]),
    (("film", "video", "plan", "clip"), ["skills/video/SKILL.md"]),
    (("document", "docs", "cv", "lettre"), ["skills/docs/SKILL.md"]),
    (("image", "photo"), ["skills/image/SKILL.md"]),
    (("application", "app"), ["skills/app/SKILL.md"]),
    (("memoire", "souvenir", "retenir"), ["brain/aiwa_brain/memory.py"]),
]


def _cache():
    folder = config.APP_DIR / "docs-cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def fetch(path):
    """A file of the repository as text (kept an hour), or None."""
    file = _cache() / re.sub(r"[^A-Za-z0-9_.-]", "_", path)
    try:
        if file.is_file() and time.time() - file.stat().st_mtime < TTL:
            return file.read_text("utf-8")
    except OSError:
        pass
    raw = relay.raw_get(f"{config.RAW_BASE}/{REPO}/HEAD/{path}", 400_000)
    if raw is None:
        try:
            return file.read_text("utf-8") if file.is_file() else None      # offline: the older copy is better than nothing
        except OSError:
            return None
    text = raw.decode("utf-8", "replace")
    try:
        file.write_text(text, "utf-8")
    except OSError:
        pass
    return text


def wanted(spoken):
    """The files to read for this sentence ([] when it is not a question about the application)."""
    text = agent_lib.plain(spoken)
    if not text or not ASKS.search(text):
        return []
    words = set(text.split())
    paths = []
    for keys, files in SUBJECTS:
        if any(k in words or any(w.startswith(k) for w in words) for k in keys):
            paths += [f for f in files if f not in paths]
    return (paths[:3] or []) + ([GENERAL] if GENERAL not in paths[:3] else [])


def lookup(spoken):
    """[(path, excerpt)] for the point; empty for any sentence that is not about the application."""
    out, size = [], 0
    for path in wanted(spoken):
        text = fetch(path)
        if not text:
            continue
        piece = text[:PER_FILE]
        if size + len(piece) > TOTAL:
            break
        size += len(piece)
        out.append((path, piece))
    return out
