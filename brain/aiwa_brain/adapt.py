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
