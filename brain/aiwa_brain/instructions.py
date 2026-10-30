"""What a session is told when it works for the person. The rules live in ONE file of the product's public repository (skills/instructions/SKILL.md); every message carries its link and, in a few
words, what belongs to this session alone (the private relay, the repository, the branch, the way of integrating, the profile, the person's own instruction). When the file (or a skill it points to)
has changed since the session last heard of it, the message says so: « modifiées »."""
import hashlib
import json

from . import config, profile_lib, sessions, state, studio
from .paths import DATA

FILE = "skills/instructions/SKILL.md"
EXTRA_FILE = DATA / "extra_instruction.json"
EXTRA_MAX = 600
# What the instructions file points to: a change in any of these is a change of the instructions.
POINTED = tuple(f"skills/{kind}/SKILL.md" for kind in (*config.KINDS, "release", "profile"))


def mailbox_signal(kind, work):
    """The words of a fallback signal: one line in aiwa-out/SIGNAL, committed to Claude's own branch."""
    return (
        f"`mkdir -p aiwa-out && echo \"{kind} $(date +%s)\" > aiwa-out/SIGNAL`, commite ce fichier sur ta branche {work} et pousse-la "
        f"(`git push origin {work}`), jamais sur la branche principale"
    )


def file_url():
    return f"{config.RAW_BASE}/{config.APP_REPO}/{config.APP_BRANCH}/{FILE}"


def mark():
    """A short mark of the instructions as they are now: the file and the skills it points to."""
    digest = hashlib.sha1()
    for path in (FILE, *POINTED):
        try:
            digest.update((config.REPO_ROOT / path).read_bytes())
        except OSError:
            digest.update(path.encode())
    return digest.hexdigest()[:6]


def extra():
    """The person's own instruction (« consigne perso »), said aloud to the super agent: kept until she changes it."""
    try:
        text = json.loads(EXTRA_FILE.read_text(encoding="utf-8")).get("text")
    except (OSError, ValueError, AttributeError):
        return ""
    return text if isinstance(text, str) else ""


def set_extra(text):
    text = " ".join(str(text or "").split())[:EXTRA_MAX]
    if text:
        EXTRA_FILE.write_text(json.dumps({"text": text}), encoding="utf-8")
    else:
        EXTRA_FILE.unlink(missing_ok=True)
    return text


def personal(repo, work, base, direct, origin=None):
    """What belongs to this session alone, in a few lines: the values the file speaks of."""
    from . import relay
    parts = [f"RELAIS = {relay.relay_url()}"]
    if repo:
        parts += [f"dépôt = {repo}", f"ta branche = {work}", f"base = {base} (la branche par défaut du dépôt : si elle a changé depuis, lis-la toi-même avec `git remote show origin` et intègre dans celle-là)", "intégration = " + ("directe" if direct else "non")]
        if origin is not None and origin != repo:
            parts.append(f"ta session a démarré sur {origin or 'aucun dépôt'} : tu travailles maintenant sur {repo} (rattache-le avec add_repo)")
        if studio.published():
            parts.append("clips libres = release stock du dépôt")
        mine = profile_lib.repo()
        if mine:
            parts.append(f"profil = {mine}")
    if work:
        parts.append("REPLI = " + mailbox_signal("<mot>", work))
    text = (extra() or "").strip()
    if text:
        parts.append(f"consigne perso = {text}")
    return "; ".join(parts) + "."


def compose(entry, repo, work, base, direct, origin=None):
    """The instructions added to a message, and what was told (kept with the session). Every message carries the link of the file and the session's own values; the first one says it is the first,
    and a later one says « modifiées » when the file or a skill has changed since the session last heard."""
    now = mark()
    told = {"mark": now}
    previous = (entry or {}).get("instr")
    link = f"Lis {file_url()} [v{now}] : ces consignes valent pour ce message et pour la suite."
    if not isinstance(previous, dict) or not previous:
        lead = "\n\n[Aiwa — consignes de cette conversation] " + link + " Tu ne les as jamais lues : lis-le en entier avant de commencer, puis les skills qu'il cite quand ma demande en est une."
    elif previous.get("mark") != now:
        lead = "\n\n[Aiwa — consignes MODIFIÉES depuis ton dernier message] " + link + " Relis le fichier en entier avant de continuer."
    else:
        lead = "\n\n[Aiwa — consignes] " + link
    return lead + " Cette session : " + personal(repo, work, base, direct, origin), told


def preview():
    """The full text the current settings would add, for the app to show: the message part, then the file."""
    with state.lock:
        repo, direct, session = state.current_repo, state.push_main, state.current_cloud
    entry = sessions.entry_of(session) if session else {}
    text, _ = compose({}, repo, entry.get("work") or "aiwa/<date>", entry.get("base") or "main", direct, entry.get("origin"))
    try:
        body = (config.REPO_ROOT / FILE).read_text(encoding="utf-8")
    except OSError:
        body = ""
    return (text.strip() + ("\n\n" + body.strip() if body else "")).strip()


def resend():
    """« renvoie les instructions »: the session in use forgets what it was told, so that its next message says again that it has never read them."""
    with state.lock:
        session = state.current_cloud
    if not session:
        return {"ok": False, "error": "pas de session en cours : le prochain message les portera en entier"}
    sessions.update_session(session, instr={})
    return {"ok": True}
