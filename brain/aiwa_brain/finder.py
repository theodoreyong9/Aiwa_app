"""Looking for profiles on GitHub from a sentence (« des vidéastes qui font du produit »): the model turns it into a few short searches (the words, their synonyms, in French and in English), the brain asks the code search of GitHub for the
`Profile/index.html` files that contain them (that is the shape of a profile of Aiwa), and the repositories are ranked by how many of the searches found them. Needs the GitHub account of the person (the code search is closed to anonymous callers)."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import agent_lib, creators, github, llm_lib

MAX_TERMS = 5
MAX_REPOS = 30
STOP = {"des", "les", "une", "qui", "que", "pour", "avec", "dans", "sur", "sont", "font", "fait", "cherche", "trouve", "profils", "profil", "gens", "personnes", "quelqu", "comme"}

TERMS_SYSTEM = ("Tu prépares une recherche de profils sur GitHub. Tâche ponctuelle, hors de toute conversation : à partir de la demande, donne au plus 5 recherches COURTES (un à trois mots chacune : le mot de la demande, "
                "ses synonymes, sa traduction anglaise ou française). Réponds seulement par du JSON : {\"terms\":[\"…\"]}.")


def fallback_terms(query):
    words = [w for w in agent_lib.plain(query).split() if len(w) >= 4 and w not in STOP]
    return words[:MAX_TERMS]


def terms(query):
    """The searches to make for a sentence (the model's, else the words of the sentence)."""
    try:
        from . import agent
        answer = agent._model(TERMS_SYSTEM, [], "Demande : « " + " ".join(str(query).split())[:200] + " »")
        data = llm_lib.json_in(answer) if answer else None
        found = data.get("terms") if isinstance(data, dict) else None
        clean = []
        for item in (found if isinstance(found, list) else []):
            text = " ".join(re.sub(r"[^\w' -]", " ", str(item), flags=re.UNICODE).split())[:40]
            if text and text.lower() not in [c.lower() for c in clean]:
                clean.append(text)
        if clean:
            return clean[:MAX_TERMS]
    except Exception:
        pass
    return fallback_terms(query)


def _search(term):
    """The repositories whose Profile/index.html contains `term` (a list of full names). Raises GithubError-like RuntimeError with a sentence to say."""
    token = github.token_value()
    if not token:
        raise RuntimeError("Connecte ton compte GitHub dans les réglages : la recherche de GitHub est fermée sans lui.")
    query = (f'"{term}"' if " " in term else term) + " path:Profile filename:index.html"
    url = f"{github.GITHUB_API}/search/code?per_page=30&q=" + urllib.parse.quote(query)
    request = urllib.request.Request(url, headers={"User-Agent": "aiwa", "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            data = json.loads(reply.read() or b"{}")
    except urllib.error.HTTPError as err:
        if err.code in (403, 429):
            raise RuntimeError("GitHub limite les recherches : réessaie dans une minute.")
        if err.code == 401:
            raise RuntimeError("Le jeton GitHub n'est plus valide : reconnecte ton compte.")
        raise RuntimeError(f"GitHub a refusé la recherche ({err.code}).")
    except (OSError, ValueError):
        raise RuntimeError("GitHub ne répond pas.")
    out = []
    for item in data.get("items") or []:
        repo = ((item.get("repository") or {}).get("full_name")) or ""
        if item.get("path") == "Profile/index.html" and github.REPO_RE.fullmatch(repo) and repo not in out:
            out.append(repo)
    return out


FILTERS = ("creators", "network")


def _network(favorites):
    """The people this person is connected to: her favourites and what her favourites keep and jumped into."""
    from . import profile
    mine = [r for r in (favorites if isinstance(favorites, list) else []) if isinstance(r, str)]
    try:
        reached = profile.network(mine).get("deck") or []
    except Exception:
        reached = []
    return list(dict.fromkeys(mine + list(reached)))


def find(query, creator_filter="", favorites=None):
    """{"ok", "repos", "terms", "error", "contracts"}: the profiles found for a sentence, the best first. `creator_filter` keeps only the creators (profiles whose wallet distributed at least one contract, checked):
    "creators" among everything found, "network" among the people she is connected to. Without a sentence the filter alone lists them."""
    query = " ".join(str(query or "").split())[:200]
    mode = creator_filter if creator_filter in FILTERS else ""
    if not query and not mode:
        return {"ok": False, "error": "cherche quoi ?", "repos": [], "terms": []}
    wanted, failure, repos = [], None, []
    if query:
        wanted = terms(query)
        score, order = {}, []
        for term in wanted:
            try:
                for repo in _search(term):
                    if repo not in score:
                        order.append(repo)
                    score[repo] = score.get(repo, 0) + 1
            except RuntimeError as err:
                failure = str(err)
                break
        repos = sorted(order, key=lambda r: (-score[r], order.index(r)))[:MAX_REPOS]
    if not mode:
        if not repos and failure:
            return {"ok": False, "error": failure, "repos": [], "terms": wanted}
        return {"ok": True, "repos": repos, "terms": wanted, "error": None if repos else "aucun profil trouvé"}
    try:
        if mode == "network":
            net = {r.lower() for r in _network(favorites)}
            pool = [r for r in repos if r.lower() in net] if query else _network(favorites)
            pairs = creators.creators_among(pool)
        elif query:
            pairs = creators.creators_among(repos)
        else:
            pairs = creators.listed()
    except RuntimeError as err:
        return {"ok": False, "error": str(err), "repos": [], "terms": wanted}
    out = [r for r, _ in pairs][:MAX_REPOS]
    counts = {r: len(c) for r, c in pairs if r in out}
    if not out:
        why = failure or ("aucun créateur dans ton réseau" if mode == "network" else "aucun créateur trouvé")
        return {"ok": bool(not failure), "error": why, "repos": [], "terms": wanted, "contracts": {}}
    return {"ok": True, "repos": out, "terms": wanted, "error": None, "contracts": counts}
