"""The repositories the person works on: the ones used or named, the ones of their sessions, the public ones of their owner, and with a token all of theirs."""
import json

from . import config, github, sessions, state


def remember(repo):
    """A repository that was used or named comes first next time."""
    with state.store_lock:
        known = known_repos()
        known = [repo] + [r for r in known if r != repo]
        try:
            config.REPOS_STORE.write_text(json.dumps(known[:30]), encoding="utf-8")
        except OSError:
            pass


def known_repos():
    try:
        known = json.loads(config.REPOS_STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = []
    return [r for r in known if isinstance(r, str) and github.REPO_RE.fullmatch(r)]


def choices():
    """[{name, private}]: the known repositories first (most recently used), then those of the sessions, then the owner's public ones, then everything the token can push to."""
    seen, found = set(), []

    def offer(item):
        if item["name"] not in seen:
            seen.add(item["name"])
            found.append(item)

    known = known_repos()
    for name in known:
        offer({"name": name, "private": False})
    for entry in sessions.load_all():
        name = entry.get("repo")
        if isinstance(name, str) and github.REPO_RE.fullmatch(name):
            offer({"name": name, "private": False})
            if name not in known:
                known = known + [name]
    owners = []
    for owner in [github.checkout_owner()] + [name.split("/")[0] for name in known]:
        if owner and owner not in owners:
            owners.append(owner)
    for owner in owners[:3]:
        for item in github.owner_repos(owner):
            offer(item)
    for item in github.my_repos():
        offer(item)
    return found


def names():
    return [c["name"] for c in choices()]


def resolve(text):
    """The repository a person means by `text` (« aiwa app », « theodoreyong9/sgd », a link), or None. Whole names first, then the name part alone when it points to one repository only."""
    wanted = " ".join(str(text or "").lower().replace("_", " ").replace("-", " ").split())
    if not wanted:
        return None
    parsed = github.parse_repo(str(text))
    if parsed:
        return parsed
    flat = lambda value: value.lower().replace("_", " ").replace("-", " ")
    found = [n for n in names() if flat(n.split("/", 1)[1]) == wanted or flat(n) == wanted]
    return found[0] if len(found) == 1 else None
