"""The diagram the super agent draws while it speaks (Mermaid): off until the person turns it on in the widget. The agent writes the code at the start of its answer (`@@DIAGRAM` … `@@END`, or the `diagram` field
of its JSON); the phone shows it at once and draws it again when it changes."""
import json
import re
import threading
import time

from .paths import DATA

FILE = DATA / "diagram.json"
MAX = 4000
MARK, END = "@@DIAGRAM", "@@END"
_lock = threading.Lock()
_state = {"on": None, "id": 0, "code": ""}


def _load_on():
    if _state["on"] is None:
        try:
            _state["on"] = json.loads(FILE.read_text(encoding="utf-8")).get("on") is True
        except (OSError, ValueError, AttributeError):
            _state["on"] = False
    return _state["on"]


def is_on():
    with _lock:
        return _load_on()


def set_on(value):
    with _lock:
        _state["on"] = value is True
        try:
            FILE.write_text(json.dumps({"on": _state["on"]}), encoding="utf-8")
        except OSError:
            pass
        return _state["on"]


def clean(code):
    """The Mermaid text alone: no fence around it, a reasonable size; '' when there is nothing to draw."""
    text = str(code or "").strip()
    text = re.sub(r"^```(?:mermaid)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    return text[:MAX]


def show(code):
    """Keeps a new diagram for the phone to draw. False when the setting is off or there is nothing."""
    text = clean(code)
    with _lock:
        if not _load_on() or not text:
            return False
        _state["id"], _state["code"] = int(time.time() * 1000), text
        return True


def snapshot():
    with _lock:
        return {"on": _load_on(), "id": _state["id"], "code": _state["code"]}


def note(live):
    """What the agent is told when the setting is on (nothing otherwise)."""
    if not is_on():
        return ""
    how = (f"Écris TOUT AU DÉBUT de ta réponse une ligne `{MARK}`, puis le code Mermaid, puis une ligne `{END}`, puis seulement après tes phrases parlées." if live
           else "Mets le code Mermaid dans le champ `diagram` du JSON (avant `say` si possible).")
    return ("SCHÉMAS : la personne a activé l'affichage. Quand un schéma aide à expliquer (étapes, liens, architecture, comparaison), dessine-le en Mermaid : flowchart, sequenceDiagram ou mindmap, court, "
            "étiquettes brèves sans caractères spéciaux. " + how + " Il s'affiche pendant que tu parles ; n'en fais pas quand ce n'est pas utile, et ne lis jamais le code à voix haute.")
