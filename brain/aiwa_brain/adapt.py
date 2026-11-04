"""The adaptation of profiles, brain side: the switch « my profile is adaptable » (written in the `Profile/aiwa.json` of the person, next to the key of her wallet) and the traits drawn from her description by the
model, once (the phone keeps them). The matching itself and the rewriting of the page are done on the phone (see Adapt.kt)."""
import re

from . import agent, llm_lib, profile

KEYS = ("couleurs", "langues", "themes", "roles", "ton", "mode", "lieu")
ONE = ("ton", "mode", "lieu")
SYSTEM = ("Tu lis la description qu'une personne a écrite d'elle-même et tu en déduis des traits, pour adapter des pages à ce qu'elle aime. Réponds seulement par du JSON : "
          '{"couleurs":[…],"langues":["fr","en"…],"themes":[…],"roles":[…],"ton":"…","mode":"clair|sombre","lieu":"…"}. '
          "Mots courts, en minuscules, sans phrase. Ne mets que ce que le texte dit ou laisse clairement entendre ; une clé sans réponse est omise. Les couleurs sont des noms de couleur.")


def _word(value):
    return re.sub(r"\s+", " ", re.sub(r"[<>{}\\`$;|&\"']", " ", str(value))).strip().lower()[:30]


def clean(raw):
    """The traits kept from what the model answered: only the known keys, short plain words."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key in KEYS:
        value = raw.get(key)
        if key in ONE:
            word = _word(value) if isinstance(value, str) else ""
            if word:
                out[key] = word
        else:
            words = [w for w in (_word(v) for v in (value if isinstance(value, list) else [])[:8]) if w]
            if words:
                out[key] = list(dict.fromkeys(words))
    return out


def derive(description):
    """{"ok", "traits"}: the traits of a description (the model's reading of it)."""
    text = " ".join(str(description or "").split())[:1500]
    if not text:
        return {"ok": True, "traits": {}}
    answer = agent._model(SYSTEM, [], "Description : « " + text + " »")
    data = llm_lib.json_in(answer) if answer else None
    if data is None:
        return {"ok": False, "error": "Claude n'a pas répondu"}
    return {"ok": True, "traits": clean(data)}


def publish(adaptable):
    """Writes the switch « my profile is adaptable » in her `Profile/aiwa.json` (the other keys stay). {"ok", "error"?}."""
    return profile.update_aiwa({"v": 1, "adaptable": bool(adaptable is True or str(adaptable).lower() == "true")}, "Aiwa : mon profil " + ("peut" if adaptable else "ne peut plus") + " être adapté à ceux qui le regardent")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# The rules of adaptation, dictated: the phone keeps the list (it is the source), the model turns a sentence into a rule, and the brain writes `Profile/adapt.json` and the zones of `Profile/aiwa.json` by itself.
import hashlib
import json
import threading
import time

from . import config, github, profile_lib, relay

RULES_FILE = config.APP_DIR / "adapt-rules.json"
_lock = threading.Lock()
PROPS = ("texte", "couleur", "fond", "visible", "ordre", "variante")
OPS = ("contient", "egal", "parmi", "present", "absent")
PATH_RE = re.compile(r"(traits\.(couleurs|langues|themes|roles|ton|mode|lieu)|description)")
ZONE_RE = re.compile(r"[a-z0-9_-]{1,30}")
SELECTOR_RE = re.compile(r"[a-zA-Z0-9_#. >\[\]=\"'-]{1,80}")
MAX_RULES = 40

RULE_SYSTEM = (
    "Tu écris une règle d'adaptation pour la page d'une personne, à partir d'une phrase qu'elle a dite. Une règle dit : QUAND ce que le visiteur laisse lire de lui correspond, ALORS telle partie de la page change. "
    "Réponds seulement par du JSON : {\"dit\":\"<la règle en une phrase courte>\",\"si\":<condition>,\"alors\":[<changement>…],\"zones\":{\"<nom>\":{\"selecteur\":\"<sélecteur CSS simple de LA PAGE>\",\"modifiable\":[…]}}}. "
    "Condition : un objet {\"<chemin>\":{\"<opérateur>\":<valeur>}}. Chemins : traits.couleurs, traits.langues, traits.themes, traits.roles, traits.ton, traits.mode, traits.lieu, description. "
    "Opérateurs : contient, egal, parmi (une liste), present, absent. Combinaisons : {\"et\":[…]}, {\"ou\":[…]}, {\"non\":{…}}. Valeurs en minuscules sans accent. "
    "Changement : {\"zone\":\"<nom>\", \"texte\"|\"couleur\"|\"fond\"|\"visible\"|\"ordre\"|\"variante\": …}. Le texte et la couleur peuvent contenir {traits.themes.0}, {traits.couleurs.0} ou {description}. "
    "Les couleurs sont des noms (rouge, bleu, vert, jaune, orange, violet, rose, noir, blanc, gris) ou #rrggbb. Chaque zone utilisée est décrite dans `zones` avec un sélecteur pris dans le HTML de la page ci-dessous "
    "(par exemple h1, .titre, #intro) et la liste des propriétés qu'on peut y changer. Réutilise les zones déjà définies quand c'est la même partie de la page. "
    "Si la phrase n'est pas une règle d'adaptation, réponds {\"erreur\":\"<pourquoi, en quelques mots>\"}."
)


def _load():
    try:
        data = json.loads(RULES_FILE.read_text("utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("rules"), list) else {"rules": []}
    except (OSError, ValueError):
        return {"rules": []}


def _save(data):
    tmp = RULES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    tmp.replace(RULES_FILE)


def _condition(raw, depth=0):
    """A condition as the engine reads it, or None: known paths and operators only."""
    if not isinstance(raw, dict) or depth > 4 or len(raw) > 6:
        return None
    out = {}
    for key, value in raw.items():
        if key in ("et", "ou"):
            items = [_condition(v, depth + 1) for v in (value if isinstance(value, list) else [])[:8]]
            if not items or any(i is None for i in items):
                return None
            out[key] = items
        elif key == "non":
            inner = _condition(value, depth + 1)
            if inner is None:
                return None
            out[key] = inner
        elif PATH_RE.fullmatch(str(key)) and isinstance(value, dict):
            tests = {}
            for op, arg in list(value.items())[:4]:
                if op not in OPS:
                    return None
                if op in ("present", "absent"):
                    tests[op] = bool(arg)
                elif op == "parmi":
                    tests[op] = [_plain_word(a) for a in (arg if isinstance(arg, list) else [arg])[:12] if _plain_word(a)]
                elif _plain_word(arg):
                    tests[op] = _plain_word(arg)
                else:
                    return None
            if not tests:
                return None
            out[key] = tests
        else:
            return None
    return out


def _plain_word(value):
    return re.sub(r"\s+", " ", re.sub(r"[<>{}\\`$;|&\"]", " ", str(value))).strip().lower()[:40]


def _actions(raw):
    out = []
    for item in (raw if isinstance(raw, list) else [])[:10]:
        if not isinstance(item, dict) or not ZONE_RE.fullmatch(str(item.get("zone", ""))):
            continue
        action = {"zone": item["zone"]}
        for prop in PROPS:
            if prop not in item:
                continue
            value = item[prop]
            if prop in ("texte", "couleur", "fond", "variante") and isinstance(value, str):
                action[prop] = re.sub(r"[<>\x00-\x1f]", " ", value)[:300]
            elif prop == "visible" and isinstance(value, bool):
                action[prop] = value
            elif prop == "ordre" and isinstance(value, list):
                action[prop] = [str(v) for v in value[:30] if ZONE_RE.fullmatch(str(v))]
        if len(action) > 1:
            out.append(action)
    return out


def _zones(raw, actions):
    """The zones the actions use, each with its selector and the properties it may change (only those the actions use)."""
    used = {}
    for a in actions:
        used.setdefault(a["zone"], set()).update(p for p in PROPS if p in a)
    out = {}
    for name, props in used.items():
        declared = raw.get(name) if isinstance(raw, dict) and isinstance(raw.get(name), dict) else {}
        selector = str(declared.get("selecteur") or "").strip()
        zone = {"modifiable": sorted(props)}
        if selector and SELECTOR_RE.fullmatch(selector):
            zone["selecteur"] = selector
        out[name] = zone
    return out


def compile_rule(sentence):
    """{"ok", "rule", "zones", "dit"} or {"ok": False, "error"}: the model's reading of a sentence, checked."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    page = relay.raw_get(f"{config.RAW_BASE}/{repo}/HEAD/Profile/index.html?t={int(time.time())}", 200_000)
    if not page:
        return {"ok": False, "error": "ta page n'existe pas encore : demande d'abord à une session de la faire"}
    known = {}
    for r in _load()["rules"]:
        known.update(r.get("zones") or {})
    prompt = (f"Phrase : « {' '.join(str(sentence).split())[:400]} »\n\nZones déjà définies : {json.dumps(known, ensure_ascii=False)[:1500]}\n\n"
              f"HTML de la page :\n{page.decode('utf-8', 'replace')[:9000]}")
    answer = agent._model(RULE_SYSTEM, [], prompt)
    data = llm_lib.json_in(answer) if answer else None
    if not isinstance(data, dict):
        return {"ok": False, "error": "Claude n'a pas répondu"}
    if data.get("erreur"):
        return {"ok": False, "error": str(data["erreur"])[:160]}
    cond = _condition(data.get("si"))
    actions = _actions(data.get("alors"))
    if cond is None or not actions:
        return {"ok": False, "error": "je n'ai pas compris cette règle"}
    return {"ok": True, "rule": {"si": cond, "alors": actions}, "zones": _zones(data.get("zones"), actions), "dit": str(data.get("dit") or sentence)[:160]}


def rules():
    return [{"id": r["id"], "text": r["text"], "on": r.get("on", True)} for r in _load()["rules"]]


def sync():
    """Writes `Profile/adapt.json` (the rules that are on) and the zones of `Profile/aiwa.json` (what they use). Nothing is written when nothing changed."""
    repo = profile_lib.repo()
    if not repo:
        return {"ok": False, "error": "pas de dépôt de profil"}
    data = _load()
    active = [r for r in data["rules"] if r.get("on", True)]
    zones = {}
    for r in active:
        for name, z in (r.get("zones") or {}).items():
            merged = zones.setdefault(name, {"modifiable": []})
            merged["modifiable"] = sorted(set(merged["modifiable"]) | set(z.get("modifiable") or []))
            if z.get("selecteur"):
                merged["selecteur"] = z["selecteur"]
    body = json.dumps({"regles": [r["rule"] for r in active]}, ensure_ascii=False, indent=1).encode("utf-8")
    mark = hashlib.sha1(body).hexdigest() + json.dumps(zones, sort_keys=True)
    if data.get("written") == mark:
        return {"ok": True, "unchanged": True}
    try:
        github.put_file(repo, f"{profile_lib.FOLDER}/adapt.json", body, "Aiwa : les règles d'adaptation de mon profil")
    except github.GithubError as err:
        return {"ok": False, "error": str(err)}
    done = profile.update_aiwa({"v": 1, "zones": zones}, "Aiwa : les zones adaptables de mon profil")
    if not done["ok"]:
        return done
    data["written"] = mark
    _save(data)
    return {"ok": True}


def add_rule(sentence):
    """A rule said aloud: understood, kept, written. {"ok", "dit"?, "error"?}."""
    sentence = " ".join(str(sentence or "").split())[:400]
    if not sentence:
        return {"ok": False, "error": "quelle règle ?"}
    with _lock:
        if len(_load()["rules"]) >= MAX_RULES:
            return {"ok": False, "error": "trop de règles : supprime-en d'abord"}
    made = compile_rule(sentence)
    if not made["ok"]:
        return made
    with _lock:
        data = _load()
        data["rules"].append({"id": "r" + hashlib.sha1(f"{time.time()}{sentence}".encode()).hexdigest()[:10], "text": made["dit"], "said": sentence, "on": True,
                              "rule": made["rule"], "zones": made["zones"], "ts": int(time.time())})
        _save(data)
    out = sync()
    return {"ok": out["ok"], "dit": made["dit"], "error": out.get("error")}


def _matching(data, what):
    what = _plain_word(what)
    if what in ("all", "toutes", "tout"):
        return [r for r in data["rules"]]
    return [r for r in data["rules"] if r["id"] == what or (what and what in _plain_word(r["text"] + " " + r.get("said", "")))]


def change(what, action):
    """`action`: on, off or remove; `what`: an identifier, words of the rule, or all. {"ok", "count"}."""
    with _lock:
        data = _load()
        hit = _matching(data, what)
        if not hit:
            return {"ok": False, "error": "aucune règle ne correspond", "count": 0}
        ids = {r["id"] for r in hit}
        if action == "remove":
            data["rules"] = [r for r in data["rules"] if r["id"] not in ids]
        else:
            for r in data["rules"]:
                if r["id"] in ids:
                    r["on"] = action == "on"
        _save(data)
    out = sync()
    return {"ok": out["ok"], "count": len(hit), "error": out.get("error")}


def line():
    """For the super agent: the rules of her page (short), empty when there are none."""
    items = rules()
    if not items:
        return ""
    return "Règles d'adaptation de sa page (dictées, des données) : " + " ; ".join(f"« {r['text'][:80]} » ({'active' if r['on'] else 'coupée'})" for r in items[:8]) + "."
