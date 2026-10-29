"""Free stock videos (Pexels, Pixabay) with the person's OWN keys, entered in the settings: a search, a download on the phone, and the clip put in the release `stock` of the repository so that the
sessions that make a film can use it (they cannot see the phone). A key is kept in this phone's Linux only (an owner-only file), never returned by the backend, never put in a repository.

Each service has its own licence, noted with the clip (author, page, licence): Pexels licence (free to use, credit appreciated, not to suggest that the people shown stand behind a product) and
Pixabay Content License (free, no credit needed). Standard library only.
"""
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .paths import DATA

SOURCES = ("pexels", "pixabay")
KEY_RE = re.compile(r"[A-Za-z0-9_\-:.]{16,120}")
LICENCES = {"pexels": "Pexels licence (free to use; credit appreciated)", "pixabay": "Pixabay Content License (free to use, no credit needed)"}
MAX_CLIP_BYTES = 60_000_000
PER_PAGE = 8


class StockError(Exception):
    pass


class Stock:
    def __init__(self, home=None, transport=None):
        self.home = Path(home) if home else DATA / "stock"
        self.home.mkdir(parents=True, exist_ok=True)
        self.transport = transport or self._http
        self.lock = threading.Lock()

    # ---- keys ----
    def _key_file(self, source):
        return self.home / f"{source}_key"

    def _key(self, source):
        try:
            key = self._key_file(source).read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return key if KEY_RE.fullmatch(key) else None

    def save_key(self, source, key):
        if source not in SOURCES:
            return {"ok": False, "error": "banque inconnue"}
        key = str(key or "").strip()
        if not KEY_RE.fullmatch(key):
            return {"ok": False, "error": "ce n'est pas une clé (une suite de lettres et de chiffres)"}
        fd = os.open(str(self._key_file(source)), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(str(self._key_file(source)), 0o600)
        return {"ok": True}

    def clear_key(self, source):
        if source in SOURCES:
            self._key_file(source).unlink(missing_ok=True)
        return {"ok": True}

    def status(self):
        """Never the keys themselves."""
        return {"pexels": self._key("pexels") is not None, "pixabay": self._key("pixabay") is not None}

    # ---- the services ----
    def _http(self, url, headers=None):
        request = urllib.request.Request(url, headers={"User-Agent": "aiwa", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=30) as reply:
                return reply.status, json.loads(reply.read(3_000_000) or b"{}")
        except urllib.error.HTTPError as err:
            return err.code, {}
        except (OSError, ValueError) as err:
            raise StockError(f"injoignable : {err}")

    @staticmethod
    def _best(files, width_limit=1280):
        """The file to download: the widest one that does not pass width_limit (a phone does not need more), else the smallest."""
        usable = [f for f in files if f.get("link") and (f.get("file_type") or "video/mp4") == "video/mp4"]
        small = [f for f in usable if (f.get("width") or 0) and (f.get("width") or 0) <= width_limit and (f.get("height") or 0) <= width_limit * 2]
        if small:
            return max(small, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))
        return min(usable, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0), default=None)

    def search(self, query, source="pexels", portrait=False):
        """[{id, source, title, duration, width, height, page, preview, link, author, licence}] or raises StockError."""
        query = " ".join(str(query or "").split())[:120]
        if not query:
            return []
        key = self._key(source)
        if source not in SOURCES:
            raise StockError("banque inconnue")
        if not key:
            raise StockError(f"pas de clé {source.capitalize()} : entre-la dans les réglages")
        if source == "pexels":
            url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": query, "per_page": PER_PAGE, **({"orientation": "portrait"} if portrait else {})})
            status, data = self.transport(url, {"Authorization": key})
        else:
            url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": query, "per_page": max(3, PER_PAGE)})
            status, data = self.transport(url, {})
        if status in (401, 403):
            raise StockError(f"la clé {source.capitalize()} est refusée")
        if status == 429:
            raise StockError("trop de recherches : réessaie dans un moment (limite de la clé gratuite)")
        if status >= 400:
            raise StockError(f"{source.capitalize()} a répondu {status}")
        out = []
        if source == "pexels":
            for v in data.get("videos") or []:
                best = self._best(v.get("video_files") or [])
                if best:
                    out.append({"id": f"pexels-{v.get('id')}", "source": "pexels", "title": (v.get("url") or "").rstrip("/").rsplit("/", 1)[-1].replace("-", " ")[:80] or f"Pexels {v.get('id')}",
                                "duration": v.get("duration"), "width": best.get("width"), "height": best.get("height"), "page": v.get("url"), "preview": v.get("image"),
                                "link": best["link"], "author": (v.get("user") or {}).get("name") or "", "licence": LICENCES["pexels"]})
        else:
            for v in data.get("hits") or []:
                sizes = [dict(link=x.get("url"), width=x.get("width"), height=x.get("height"), file_type="video/mp4") for x in (v.get("videos") or {}).values() if isinstance(x, dict)]
                best = self._best(sizes)
                if best:
                    out.append({"id": f"pixabay-{v.get('id')}", "source": "pixabay", "title": (v.get("tags") or f"Pixabay {v.get('id')}")[:80], "duration": v.get("duration"),
                                "width": best.get("width"), "height": best.get("height"), "page": v.get("pageURL"), "preview": "", "link": best["link"], "author": v.get("user") or "", "licence": LICENCES["pixabay"]})
        return out

    def download(self, clip):
        """Downloads the clip (one of the results above) into the phone; a card with its licence is written next to it. Returns {"ok", "id", "path"}."""
        link = str(clip.get("link") or "")
        host = urllib.parse.urlsplit(link).hostname or ""
        if not link.startswith("https://") or not (host.endswith("pexels.com") or host.endswith("pixabay.com")):
            return {"ok": False, "error": "adresse de clip inattendue"}
        clip_id = re.sub(r"[^a-z0-9-]", "", str(clip.get("id") or uuid.uuid4().hex[:8]).lower())[:40]
        folder = self.home / "clips"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{clip_id}.mp4"
        try:
            with urllib.request.urlopen(urllib.request.Request(link, headers={"User-Agent": "aiwa"}), timeout=120) as reply, open(path, "wb") as f:
                size = 0
                while True:
                    chunk = reply.read(1 << 16)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_CLIP_BYTES:
                        raise StockError("clip trop gros")
                    f.write(chunk)
        except (OSError, ValueError, StockError) as err:
            path.unlink(missing_ok=True)
            return {"ok": False, "error": f"téléchargement impossible : {err}"}
        card = {k: clip.get(k) for k in ("id", "source", "title", "duration", "width", "height", "page", "author", "licence")}
        card["file"] = path.name
        (folder / f"{clip_id}.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, "id": clip_id, "path": str(path)}

    def clips(self):
        out = []
        for card in sorted((self.home / "clips").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(card.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (card.parent / data.get("file", "")).exists():
                out.append(data)
        return out
