"""The person's way of speaking, learned from what she dictates to the agent, so that the agent talks to her in a way that looks like hers. Only COUNTS are kept (words per utterance, the register, a few
little words), never the sentences themselves: the file holds no content. A short note built from the counts is added to what the agent is told; nothing else of this file leaves the phone.
Pure standard library."""
import json
import os
import re
import threading
import unicodedata

ENOUGH = 8            # utterances before the note is given
CAP = 3000            # the counts are halved past this many utterances: the style follows the person, it does not freeze
FILLERS = ("du coup", "en fait", "alors", "bon", "ben", "bah", "genre", "voilà", "écoute", "franchement", "quoi", "enfin", "bref", "carrément", "tiens", "dis donc")
INFORMAL = ("t'as", "t'es", "y'a", "j'sais", "j'suis", "chuis", "faut", "t'inquiète", "ouais", "nan", "j'vais", "j'peux", "j'veux", "c'pas", "ça va", "grave")
TU = ("tu", "toi", "ton", "ta", "tes", "t'")
VOUS = ("vous", "votre", "vos")


def _plain(text):
    s = unicodedata.normalize("NFC", str(text or "").lower()).replace("’", "'")
    return " " + " ".join(re.sub(r"[^\w' ]+", " ", s).split()) + " "


def _count(words_text, items):
    return {w: words_text.count(f" {w} ") for w in items if words_text.count(f" {w} ")}


class Style:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        raw = raw if isinstance(raw, dict) else {}
        return {"enabled": raw.get("enabled") is not False, "utt": int(raw.get("utt") or 0), "words": int(raw.get("words") or 0),
                "tu": int(raw.get("tu") or 0), "vous": int(raw.get("vous") or 0), "polite": int(raw.get("polite") or 0),
                "fillers": raw.get("fillers") if isinstance(raw.get("fillers"), dict) else {}, "informal": raw.get("informal") if isinstance(raw.get("informal"), dict) else {}}

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
        except OSError:
            pass

    def observe(self, text):
        """One thing the person said (a dictation to the agent): only its counts are kept."""
        t = _plain(text)
        n = len(t.split())
        if not self.data["enabled"] or n < 2 or n > 120:
            return
        with self._lock:
            d = self.data
            d["utt"] += 1
            d["words"] += n
            d["tu"] += sum(t.count(f" {w} ") if not w.endswith("'") else t.count(f" {w}") for w in TU)
            d["vous"] += sum(t.count(f" {w} ") for w in VOUS)
            d["polite"] += t.count(" s'il te plait ") + t.count(" s'il vous plait ") + t.count(" merci ")
            for key, items in (("fillers", FILLERS), ("informal", INFORMAL)):
                for w, c in _count(t, [_plain(x).strip() for x in items]).items():
                    d[key][w] = d[key].get(w, 0) + c
            if d["utt"] > CAP:
                for k in ("utt", "words", "tu", "vous", "polite"):
                    d[k] //= 2
                for key in ("fillers", "informal"):
                    d[key] = {w: c // 2 for w, c in d[key].items() if c // 2}
            self._save()

    def note(self):
        """What the agent is told about her way of speaking ('' when it is off or there is not enough yet)."""
        d = self.data
        if not d["enabled"] or d["utt"] < ENOUGH:
            return ""
        avg = d["words"] / d["utt"]
        parts = ["phrases " + ("très courtes" if avg < 8 else "courtes" if avg < 16 else "de longueur moyenne" if avg < 30 else "longues et développées") + f" (environ {round(avg)} mots par fois)"]
        if d["tu"] > d["vous"]:
            parts.append("tutoiement")
        elif d["vous"] > d["tu"]:
            parts.append("vouvoiement")
        per100 = lambda c: 100.0 * c / max(1, d["words"])
        informal = sorted(d["informal"].items(), key=lambda kv: -kv[1])
        if per100(sum(c for _, c in informal)) >= 1.5:
            parts.append("oral familier, avec des contractions (" + ", ".join("« " + w + " »" for w, _ in informal[:3]) + ")")
        else:
            parts.append("registre soigné, peu de contractions")
        fillers = [w for w, c in sorted(d["fillers"].items(), key=lambda kv: -kv[1]) if per100(c) >= 0.8][:3]
        if fillers:
            parts.append("petits mots fréquents : " + ", ".join("« " + w + " »" for w in fillers))
        if per100(d["polite"]) >= 1.0:
            parts.append("poli, remercie volontiers")
        return ("[Façon de parler de la personne, apprise de ses dictées (des comptes, jamais ses phrases) : " + " ; ".join(parts) + ". Quand tu parles à voix haute, parle comme elle : même longueur de phrases, même registre, "
                "ses petits mots avec mesure. Ne la singe pas et ne la caricature pas.]")

    def status(self):
        d = self.data
        return {"enabled": d["enabled"], "count": d["utt"], "ready": d["utt"] >= ENOUGH, "note": self.note()}

    def set_enabled(self, on):
        with self._lock:
            self.data["enabled"] = bool(on)
            self._save()

    def clear(self):
        with self._lock:
            enabled = self.data["enabled"]
            self.data = {"enabled": enabled, "utt": 0, "words": 0, "tu": 0, "vous": 0, "polite": 0, "fillers": {}, "informal": {}}
            self._save()
