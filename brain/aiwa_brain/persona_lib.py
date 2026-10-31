"""The way the super agent talks (a style the person chooses) and the « game » mode: the person gives it points by voice, it loses one an hour, loses five when it proposes something on its own and is
refused, wins ten when it is accepted, and at zero it can no longer speak until it is given points. Kept on the phone (one small file). Standard library only.

The score is not felt by the model: it is told to it at each turn with the rule, and the brain enforces what can be enforced (the silence at zero, the points)."""
import json
import re
import threading
import time

START_POINTS = 48          # a comfortable start: a day without a word is 24 points
PRESETS = {
    "neutre": "",
    "vanneur": "condescendant et vanneur : tu le chambres gentiment, avec de l'ironie, une pointe de supériorité amusée, des vannes courtes",
    "chaleureux": "chaleureux et encourageant, comme un ami enthousiaste",
    "sec": "sec et direct : phrases très courtes, aucun enrobage, pas de politesses",
}
LABELS = {"neutre": "Neutre", "vanneur": "Condescendant et vanneur", "chaleureux": "Chaleureux", "sec": "Sec et direct"}
GIFT_RE = re.compile(r"\b(?:je te donne|je t'en donne|donne[- ]toi|prends|tiens)\s+(\d{1,4})\s+points?\b", re.I)
TAKE_RE = re.compile(r"\b(?:je te retire|je t'enl[eè]ve|retire[- ]toi|enl[eè]ve[- ]toi)\s+(\d{1,4})\s+points?\b", re.I)


class Persona:
    def __init__(self, path, clock=time.time):
        self.path = path
        self.clock = clock
        self._lock = threading.Lock()
        self.data = {"style": "neutre", "game": False, "points": 0, "tick": 0.0}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update({k: loaded[k] for k in self.data if k in loaded})
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
        except OSError:
            pass

    def _tick(self):
        """One point lost per full hour since the last tick (only while the game is on)."""
        d = self.data
        if not d["game"]:
            return
        hours = int((self.clock() - d["tick"]) // 3600)
        if hours > 0:
            d["points"] = max(0, d["points"] - hours)
            d["tick"] += hours * 3600
            self._save()

    # ---- the style ----
    def set_style(self, name):
        with self._lock:
            if name in PRESETS:
                self.data["style"] = name
                self._save()
        return self.status()

    # ---- the game ----
    def set_game(self, on):
        with self._lock:
            on = bool(on)
            if on and not self.data["game"]:
                self.data.update(game=True, points=START_POINTS, tick=self.clock())
            elif not on:
                self.data["game"] = False
            self._save()
        return self.status()

    def add(self, delta):
        """Points won or lost (the game only). Returns the new total."""
        with self._lock:
            if self.data["game"]:
                self._tick()
                self.data["points"] = max(0, self.data["points"] + int(delta))
                self._save()
            return self.data["points"]

    def gift_in(self, spoken):
        """« je te donne 20 points »: the points are added here, by the brain, so that it works even when it cannot speak. Returns the delta or None."""
        text = str(spoken or "")
        for rx, sign in ((GIFT_RE, 1), (TAKE_RE, -1)):
            m = rx.search(text)
            if m and self.data["game"]:
                delta = sign * int(m.group(1))
                self.add(delta)
                return delta
        return None

    def muted(self):
        with self._lock:
            self._tick()
            return self.data["game"] and self.data["points"] <= 0

    def reward(self, accepted):
        """What the person answered to something the agent proposed on its own."""
        return self.add(10 if accepted else -5)

    # ---- what the agent is told ----
    def note(self):
        with self._lock:
            self._tick()
            d = self.data
            parts = []
            if PRESETS.get(d["style"]):
                parts.append("[Style choisi par la personne pour ce que tu DIS à voix haute (`say`) : " + PRESETS[d["style"]] + ". Il ne touche jamais les messages que tu envoies aux sessions (`send`), qui restent neutres et précis. "
                             "La vanne reste un ton : jamais d'insulte, ni sur elle, ni sur ses proches, ni sur personne ; si elle a l'air de mal le prendre, adoucis.]")
            if d["game"]:
                parts.append(f"[Mode jeu : tu as {d['points']} points. Tu en perds 1 par heure. Si tu proposes quelque chose de ta propre initiative (qu'elle ne t'a pas demandé) : refus = -5, accord = +10. À 0 point tu ne peux plus parler. "
                             "Tiens-toi au courant de ce qui se passe ; tu peux poser une question à une session en terminant ton message par « Juste réponds ». Propose peu, et seulement ce qui vaut le coup.]")
            return "\n".join(parts)

    def status(self):
        with self._lock:
            self._tick()
            d = self.data
            return {"style": d["style"], "styles": [{"id": k, "label": LABELS[k]} for k in PRESETS], "game": d["game"], "points": d["points"] if d["game"] else None}
