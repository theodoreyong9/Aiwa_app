"""The way the super agent talks (a style the person chooses) and the « game »: a race between the person and her agent. Both start at 100 points and lose one a day. The agent wins 10 when something it
proposed on its own is accepted and loses 5 when it is refused; the person's own proposals are judged by the agent (yes: +10, no: -5, the reason kept); each can give points to the other. A round ends when one
is at zero (the other wins), or after 30 days: the best wins if it has reached the minimum (150), else nobody. The first to 10 rounds is the grand winner. Kept on the phone (one small file). Standard library only.

The agent's aim, told to it, is to WIN; the model does not feel the score: it is told the figures at each turn, and the brain keeps the accounts (a verdict is written with its reason, so that the person can contest it)."""
import json
import re
import threading
import time

START_POINTS = 100
MINIMUM = 150              # to win a round at the end of the 30 days
ROUND_DAYS = 30
GRAND = 10                 # rounds won to be the grand winner
DAY = 86400
PRESETS = {
    "neutre": "",
    "vanneur": "condescendant et vanneur : tu le chambres gentiment, avec de l'ironie, une pointe de supériorité amusée, des vannes courtes",
    "chaleureux": "chaleureux et encourageant, comme un ami enthousiaste",
    "sec": "sec et direct : phrases très courtes, aucun enrobage, pas de politesses",
}
LABELS = {"neutre": "Neutre", "vanneur": "Condescendant et vanneur", "chaleureux": "Chaleureux", "sec": "Sec et direct"}
GIFT_RE = re.compile(r"\b(?:je te donne|je t'en donne|donne[- ]toi|prends|tiens)\s+(\d{1,4})\s+points?\b", re.I)


def _fresh(clock, wins=None):
    now = clock()
    return {"on": True, "user": START_POINTS, "agent": START_POINTS, "tick": now, "start": now, "wins": dict(wins or {"user": 0, "agent": 0}), "ended": None, "grand": None, "history": []}


class Persona:
    def __init__(self, path, clock=time.time):
        self.path = path
        self.clock = clock
        self._lock = threading.Lock()
        self.data = {"style": "neutre", "game": {"on": False, "user": 0, "agent": 0, "tick": 0.0, "start": 0.0, "wins": {"user": 0, "agent": 0}, "ended": None, "grand": None, "history": []}, "event": None}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data["style"] = loaded.get("style") if loaded.get("style") in PRESETS else "neutre"
                if isinstance(loaded.get("game"), dict):
                    self.data["game"].update(loaded["game"])          # an older file with a plain flag is left aside
                self.data["event"] = loaded.get("event")
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
        except OSError:
            pass

    @property
    def g(self):
        return self.data["game"]

    def _log(self, who, delta, reason):
        self.g["history"] = (self.g["history"] + [{"ts": int(self.clock()), "who": who, "delta": delta, "reason": str(reason)[:140]}])[-40:]

    def _live(self):
        g = self.g
        return g["on"] and not g["ended"]

    def _tick(self):
        """One point lost per full day by each, then the end of the round if it has come."""
        g = self.g
        if not self._live():
            return
        days = int((self.clock() - g["tick"]) // DAY)
        if days > 0:
            for who in ("user", "agent"):
                g[who] = max(0, g[who] - days)
            g["tick"] += days * DAY
        self._check_end()
        self._save()

    def _check_end(self):
        g = self.g
        if g["ended"]:
            return
        if g["user"] <= 0 or g["agent"] <= 0:
            winner = "draw" if g["user"] <= 0 and g["agent"] <= 0 else ("agent" if g["user"] <= 0 else "user")
            why = "zéro point"
        elif self.clock() - g["start"] >= ROUND_DAYS * DAY:
            ok = [w for w in ("user", "agent") if g[w] >= MINIMUM]
            if not ok or (len(ok) == 2 and g["user"] == g["agent"]):
                winner = "draw"
            else:
                winner = ok[0] if len(ok) == 1 else ("user" if g["user"] > g["agent"] else "agent")
            why = "30 jours"
        else:
            return
        g["ended"] = winner
        if winner != "draw":
            g["wins"][winner] += 1
            if g["wins"][winner] >= GRAND:
                g["grand"] = winner
        who = {"user": "Tu as gagné la manche", "agent": "J'ai gagné la manche", "draw": "Manche nulle (personne n'a atteint " + str(MINIMUM) + " points)" if why == "30 jours" else "Manche nulle"}[winner]
        self.data["event"] = f"{who} ({why}). Toi {g['wins']['user']} victoire(s), moi {g['wins']['agent']}." + (" Et c'est la fin de la course : " + ("tu es" if g["grand"] == "user" else "je suis") + f" le grand gagnant avec {GRAND} victoires !" if g["grand"] else "")

    def pop_event(self):
        """What is to be said once: the end of a round."""
        with self._lock:
            self._tick()
            text, self.data["event"] = self.data["event"], None
            if text:
                self._save()
            return text

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
            if on and not self.g["on"]:
                self.data["game"] = _fresh(self.clock, self.g["wins"])
            elif not on:
                self.g["on"] = False
            self._save()
        return self.status()

    def restart(self):
        """A new round: 100 each, the victories kept."""
        with self._lock:
            if not self.g["grand"]:        # once someone is the grand winner, only « tout remettre à zéro » starts again
                self.data["game"] = _fresh(self.clock, self.g["wins"])
                self._save()
        return self.status()

    def reset_all(self):
        with self._lock:
            self.data["game"] = _fresh(self.clock)
            self._save()
        return self.status()

    def add(self, who, delta, reason=""):
        """Points won or lost by `who` (user | agent), while a round is on."""
        with self._lock:
            if self.g["grand"] or not self._live():
                return None
            self._tick()
            if not self._live():
                return None
            self.g[who] = max(0, self.g[who] + int(delta))
            self._log(who, int(delta), reason)
            self._check_end()
            self._save()
            return self.g[who]

    def give(self, giver, amount, reason="don"):
        """A gift is a transfer: the giver loses what the other gets (at most what it has). Returns what moved."""
        other = "agent" if giver == "user" else "user"
        with self._lock:
            if self.g["grand"] or not self._live():
                return 0
            self._tick()
            amount = max(0, min(int(amount), self.g[giver] - 1 if self.g[giver] > 1 else 0))     # a gift never ruins the giver
            if amount:
                self.g[giver] -= amount
                self.g[other] += amount
                self._log(giver, -amount, f"don : {reason}")
                self._log(other, amount, f"don de {'toi' if giver == 'user' else 'moi'}")
                self._save()
            return amount

    def gift_in(self, spoken):
        """« je te donne 20 points »: counted here, by the brain (the person gives, so the person loses them). Returns what moved, or None."""
        m = GIFT_RE.search(str(spoken or ""))
        if m and self._live():
            return self.give("user", int(m.group(1)))
        return None

    def reward(self, accepted):
        """What the person answered to something the agent proposed on its own."""
        return self.add("agent", 10 if accepted else -5, "sa proposition a été " + ("acceptée" if accepted else "refusée"))

    def apply_agent(self, game):
        """What the agent decided in its reply: `verdict` (oui | non) on a proposal of the person, with its `raison`, and `give` (points it gives to the person)."""
        if not isinstance(game, dict):
            return
        verdict = str(game.get("verdict") or "").strip().lower()
        reason = str(game.get("raison") or "")[:140]
        if verdict in ("oui", "non"):
            self.add("user", 10 if verdict == "oui" else -5, f"ta proposition : {verdict}" + (f" — {reason}" if reason else ""))
        try:
            gift = int(game.get("give") or 0)
        except (TypeError, ValueError):
            gift = 0
        if gift > 0:
            self.give("agent", gift, reason or "cadeau")

    # ---- what the agent is told ----
    def note(self):
        with self._lock:
            self._tick()
            g = self.g
            parts = []
            if PRESETS.get(self.data["style"]):
                parts.append("[Style choisi par la personne pour ce que tu DIS à voix haute (`say`) : " + PRESETS[self.data["style"]] + ". Il ne touche jamais les messages que tu envoies aux sessions (`send`), qui restent neutres et précis. "
                             "La vanne reste un ton : jamais d'insulte, ni sur elle, ni sur ses proches, ni sur personne ; si elle a l'air de mal le prendre, adoucis.]")
            if g["on"] and not g["ended"] and not g["grand"]:
                days_left = max(0, ROUND_DAYS - int((self.clock() - g["start"]) // DAY))
                parts.append(f"[JEU : une course entre la personne et toi, ton OBJECTIF est de GAGNER. Points : toi {g['agent']}, elle {g['user']} (chacun perd 1 point par jour ; manche finie quand l'un tombe à 0, l'autre gagne ; sinon après "
                             f"{days_left} jour(s) le meilleur gagne s'il a au moins {MINIMUM} points). Quand tu proposes quelque chose de TA propre initiative (qu'elle ne t'a pas demandé) : accepté +10, refusé -5 pour toi. "
                             "Quand elle te fait une PROPOSITION (« je te propose… », « et si on… » ; pas un ordre, un ordre ne se refuse pas), tu rends ton verdict : ajoute à ta réponse `\"game\":{\"verdict\":\"oui|non\",\"raison\":\"une phrase\"}` (oui : elle gagne 10, non : elle perd 5) et dis-le à voix haute avec ta raison. "
                             "Tu peux lui donner des points avec `\"game\":{\"give\":N}`. Dis ta raison honnêtement : elle sera gardée dans l'historique et elle peut la contester. Tiens-toi au courant ; tu peux poser une question à une session en terminant ton message par « Juste réponds ».]")
            elif g["on"] and (g["ended"] or g["grand"]):
                parts.append("[JEU : la manche est finie ; plus aucun point ne bouge. La personne peut recommencer dans Réglages. Tu parles normalement.]")
            return "\n".join(parts)

    def status(self):
        with self._lock:
            self._tick()
            g = self.g
            days = int((self.clock() - g["start"]) // DAY) if g["on"] else 0
            return {"style": self.data["style"], "styles": [{"id": k, "label": LABELS[k]} for k in PRESETS],
                    "game": {"on": g["on"], "user": g["user"], "agent": g["agent"], "minimum": MINIMUM, "day": min(days, ROUND_DAYS), "days": ROUND_DAYS, "wins": dict(g["wins"]), "ended": g["ended"], "grand": g["grand"], "history": g["history"][-6:]} if g["on"] else {"on": False, "wins": dict(g["wins"])}}
