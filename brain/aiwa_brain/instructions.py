"""What a session is told when it works for the person: the repository, how to push, how to ask and warn, and the skills that say how to make each kind of production.
The long how-to of each kind lives in the skills (skills/<kind>/SKILL.md of the product's repository): the first message holds one line per skill, with a short mark so that a changed skill is told again."""
import hashlib

from . import config, profile_lib, relay, sessions, state, studio

KIND_LABELS = {
    "docs": "Documents (lettre, CV, rapport, contrat, présentation, tableur…)",
    "image": "Images (affiche, illustration, visuel, logo…)",
    "video": "Vidéos (promo, tutoriel, animation, film…)",
    "app": "Apps (une application qui s'installe ou s'ouvre sur le téléphone)",
    "page": "Pages (une page web d'un seul fichier HTML)",
}
LABELS = {"repo": "dépôt", "push": "push", "ask": "questions", "alert": "alerte", "release": "productions en release", "profile": "profil", "stock": "clips libres", **{f"skill_{k}": k for k in config.KINDS}}


def mailbox_signal(kind, work):
    """The words of a fallback signal: one line in aiwa-out/SIGNAL, committed to Claude's own branch."""
    return (
        f"`mkdir -p aiwa-out && echo \"{kind} $(date +%s)\" > aiwa-out/SIGNAL`, commite ce fichier sur ta branche {work} et pousse-la "
        f"(`git push origin {work}`), jamais sur la branche principale"
    )


def ask_line(repo, work):
    """How Claude asks something: through the widget, because the widget never sees what is said in the conversation."""
    fallback = (
        f" Envoie-la TOUJOURS par les DEUX voies, sans attendre que la première échoue (le relais peut être bloqué sans que la commande te le dise) : en plus de la commande, écris le même JSON dans `aiwa-out/ask.json`, puis `echo \"ask $(date +%s)\" > aiwa-out/SIGNAL`, commite les deux sur ta branche {work} "
        f"et pousse-la (`git push origin {work}`), jamais sur la branche principale."
        if repo and work else ""
    )
    return (
        "Questions : ne me pose JAMAIS de question dans ta conversation, je ne la vois pas (je ne vois que le widget). Produis toujours quelque chose de concret, "
        "sur des hypothèses raisonnables que tu me dis en une phrase. Si une décision m'appartient vraiment et change le résultat, envoie-la comme demande : "
        "`curl -s -m 10 -d '{\"question\":\"…\",\"options\":[\"…\",\"…\"]}' -H 'Title: aiwa-ask' " + relay.relay_url() + "` "
        "(une seule question, de trois à quatre choix courts : je choisis ou j'écris ma réponse dans le widget, et elle te revient comme mon message suivant). "
        "Ne t'arrête pas pour l'attendre : continue sur ton hypothèse, et ajuste quand ma réponse arrive." + fallback
    )


def alert_line(repo, work):
    """Mandatory: it is how the widget learns that Claude is waiting (the CLI can't read a cloud reply back)."""
    return (
        "Alerte (obligatoire) : à la fin de CHAQUE réponse — quand tu as terminé, ou que tu attends une réponse, "
        f"une décision ou une validation de ma part — exécute cette commande shell pour me prévenir : `curl -s -m 5 -d attend {relay.relay_url()}` "
        + (
            f"(si elle échoue parce que le réseau la bloque, repli, SEULEMENT quand tu attends une réponse ou une décision de ma part : {mailbox_signal('attend', work)} ; "
            "sinon ignore l'erreur et continue). "
            if repo and work else "(si le réseau la bloque, ignore l'erreur et continue). "
        )
        + "Termine ensuite ta réponse par ta question s'il y en a une."
    )


def repo_line(repo, origin):
    """The repository the session works on; `origin` is the one it was started on, when it now works on another (the person talked about another repository: the session stays)."""
    access = f"Claude n'a pas accès à {repo} : sur github.com/settings/installations, ouvre Claude, choisis All repositories, enregistre."
    if origin is not None and origin != repo:
        began = f"Ta session a démarré sur {origin}, mais à partir" if origin else "À partir"
        return (
            f"Dépôt : {repo}. {began} de ce message c'est sur {repo} que tu travailles (la conversation continue, seul le dépôt change). "
            f"Rattache-le avec l'outil `add_repo` (accès `push`) s'il n'est pas déjà attaché à ta session. Ne modifie plus {origin or 'les autres dépôts'} sauf si je te le demande. "
            f"Sans cet outil, ou si l'accès est refusé, réponds en UNE phrase : « {access} » Puis arrête-toi."
        )
    return (
        f"Dépôt : {repo}. Ton répertoire de travail doit être ce dépôt GitHub (vérifie `git remote -v`) ; si ce n'est pas le cas, dis-le-moi et arrête-toi. "
        "Si le répertoire ne contient qu'un commit « stub » (le dépôt n'a pas été cloné), rattache le dépôt avec l'outil `add_repo` ; sans cet outil, ou si l'accès est refusé, "
        f"réponds en UNE phrase, sans rien construire ni proposer d'autre repli : « {access} Puis relance une session. » Puis arrête-toi."
    )


def push_line(work, base, direct):
    if direct:
        return (
            f"Push : travaille sur ta propre branche ({work}) : commits-y et pousse-la. Quand un changement est terminé, intègre TOUTE ta branche dans {base} et pousse {base}, "
            "sans pull request à relire : par push direct si ta session le permet, sinon en ouvrant une pull request que tu fusionnes aussitôt. "
            f"Avant d'intégrer : récupère {base} et vérifie qu'il n'a pas reçu de modification parallèle qui entre en conflit avec les tiennes. "
            "Si la fusion se fait sans conflit, intègre et pousse sans me demander ; les fichiers `aiwa-out/` de ta branche sont normaux. Un vrai conflit mécanique, résous-le toi-même ; "
            "s'il ne l'est pas, n'intègre rien et pose-moi la question par la consigne Questions. Ne me demande jamais de changer un réglage du dépôt. "
            "Jamais de force-push, jamais d'écrasement du travail de quelqu'un d'autre."
        )
    return (
        f"Push : travaille sur ta propre branche ({work}) (crée-la depuis {base} si elle n'existe pas) : commits-y et pousse-la. N'intègre RIEN dans {base} et n'ouvre aucune pull request "
        "sauf si je te le demande. Jamais de force-push."
    )


def release_line(repo):
    """Everything made for the person leaves as a release: that is what the Files page lists."""
    return (
        f"Productions : tout ce que tu fabriques pour moi (un document, une image, une vidéo, une app, une page) part en RELEASE du dépôt {repo}, jamais commité dans le code. "
        "L'étiquette (tag) dit le genre : `docs-…`, `image-…`, `video-…`, `app-…` ou `page-…`, suivie d'un nom court en minuscules sans espace et de la date (par exemple `video-promo-20260701`). "
        "Le fichier est la pièce jointe de la release ; son titre est une phrase courte que je comprends. Comment faire et à quelle qualité : les skills ci-dessous."
    )


def skill_text(kind):
    try:
        return (config.SKILLS_DIR / kind / "SKILL.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def skill_line(kind):
    """The one line that replaces a long how-to in the message; it carries a short mark so that a changed skill is told again."""
    mark = hashlib.sha1(skill_text(kind).encode()).hexdigest()[:6]
    base = f"{config.RAW_BASE}/{config.APP_REPO}/{config.APP_BRANCH}/skills"
    return f"{KIND_LABELS[kind]} : quand ma demande en est une, lis {base}/{kind}/SKILL.md avant de t'y mettre, et suis-le [v{mark}]."


def lines(repo, work, base, direct, origin=None):
    """What the person's settings ask of the session, in words, as (key, text) pairs."""
    out = []
    if repo:
        out.append(("repo", repo_line(repo, origin)))
        out.append(("push", push_line(work, base, direct)))
        out.append(("release", release_line(repo)))
        out.extend((f"skill_{kind}", skill_line(kind)) for kind in config.KINDS)
        out.append(("release_how", skill_line_release()))
        if studio.published():
            out.append(("stock", studio.stock_line(repo)))
        mine = profile_lib.repo()
        if mine:
            out.append(("profile", profile_lib.instruction(mine)))
    out.append(("ask", ask_line(repo, work)))
    out.append(("alert", alert_line(repo, work)))
    return out


def skill_line_release():
    mark = hashlib.sha1(skill_text("release").encode()).hexdigest()[:6]
    return f"Publier une release (le geste commun à tous les genres) : lis {config.RAW_BASE}/{config.APP_REPO}/{config.APP_BRANCH}/skills/release/SKILL.md [v{mark}]."


# A long conversation gets summarised by Claude Code and the first message can fade; a file at the root of the session is read again every time. It stays out of git (it holds the person's private channel).
FILE_NOTE = (
    "- Mémoire des consignes : écris ce bloc de consignes, tel quel, dans `CLAUDE.local.md` à la racine de ton répertoire de travail (il est relu à chaque reprise de la conversation) "
    "et ajoute cette ligne à `.git/info/exclude` pour qu'il ne soit JAMAIS commité ni poussé (il contient mon canal privé). "
    "Si tu l'as déjà fait, mets-le à jour avec les changements."
)
# A session lives in a container that stops when nothing happens in it: a long job that runs in the background stops with it, and nobody is told.
LONG_WORK_NOTE = (
    "- Travail long : quand tu lances un calcul qui dure (un rendu de plusieurs minutes), programme tout de suite un contrôle avec l'outil `send_later` (toutes les 20 minutes) : "
    "à chaque réveil, regarde si ton calcul tourne encore, relance-le s'il s'est arrêté (ce qui est déjà fait est gardé), reprogramme le contrôle suivant tant que ce n'est pas fini, "
    "annule-le (`delete_trigger`) quand c'est fini, et dis-le-moi en une phrase."
)


def compose(entry, repo, work, base, direct, origin=None):
    """The instructions added to a message, and what was told (a hash per instruction, kept with the session). Everything goes with a session's FIRST message; after that only what changed
    since, and nothing at all when nothing changed, so that the conversation isn't buried in repeats."""
    pairs = lines(repo, work, base, direct, origin)
    told = {key: hashlib.sha1(text.encode()).hexdigest()[:8] for key, text in pairs}
    previous = (entry or {}).get("instr")
    if not isinstance(previous, dict) or not previous:
        return "\n\n[Aiwa — consignes de cette conversation]\n" + "\n".join(f"- {text}" for _, text in pairs) + "\n" + FILE_NOTE + "\n" + LONG_WORK_NOTE, told
    parts = [f"- {text}" for key, text in pairs if previous.get(key) != told[key]]
    parts += [f"- Consigne retirée : {LABELS.get(key, key)}." for key in previous if key not in told]
    if not parts:
        return "", told
    return "\n\n[Aiwa — consignes mises à jour]\n" + "\n".join(parts) + "\n- Mets aussi à jour `CLAUDE.local.md` avec ces changements.", told


def preview():
    """The full block the current settings would add, for the app to show."""
    with state.lock:
        repo, direct, session = state.current_repo, state.push_main, state.current_cloud
    entry = sessions.entry_of(session) if session else {}
    text, _ = compose({}, repo, entry.get("work") or "aiwa/<date>", entry.get("base") or "main", direct, entry.get("origin"))
    return text.strip()


def resend():
    """« renvoie les instructions »: the session in use forgets what it was told, so that its next message carries the instructions in full again."""
    with state.lock:
        session = state.current_cloud
    if not session:
        return {"ok": False, "error": "pas de session en cours : le prochain message les portera en entier"}
    sessions.update_session(session, instr={})
    return {"ok": True}
