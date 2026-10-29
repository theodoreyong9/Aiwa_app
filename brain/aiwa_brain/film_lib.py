"""« Film de moi »: a short film of the person in situations and with words that were never filmed, made from her photos, a sample of her voice and her own direction, through fal.ai with HER key.

The circuit: prepare (a plan of scenes from her direction; the words she wrote are kept as they are, none is invented) → quote (a price for each scene, from the prices of the models) → she confirms →
production scene by scene (the voice, the picture, the mouth) → the scenes joined by ffmpeg → the film, marked as made by an AI. Nothing is paid before the confirmation. The key stays in this phone's
Linux (owner-only file), never goes into a repository or to a session. Only the person herself may be in the photos and speak: the app asks her to say so before anything starts.

The models are described in MODELS; their input names are read from fal's own description of each model when it can be reached (see _inputs), so that a renamed field does not break the circuit.
Standard library only (and ffmpeg, which Termux has).
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .paths import DATA

QUEUE = "https://queue.fal.run"
KEY_RE = re.compile(r"[A-Za-z0-9_\-:.]{16,200}")
MODELS = {
    "video": {"endpoint": "fal-ai/kling-video/o1/reference-to-video", "usd_per_second": 0.112},
    "lipsync": {"endpoint": "veed/lipsync/v2", "usd_per_second": 0.07},
    "voice": {"endpoint": "fal-ai/f5-tts", "usd_per_1000_chars": 0.05},
    "swap": {"endpoint": "fal-ai/pixverse/swap", "usd_per_second": 0.08},      # about 0.15–0.40 $ for 5 s on fal's page: the upper end is quoted
}
KINDS = ("me", "product", "both", "swap")
MAX_SWAP_SECONDS = 30
SCENE_SECONDS = (5, 10)
MAX_SCENES = 12
DEFAULT_CAP_USD = 20.0
SAMPLE_TEXT = "Bonjour, c'est moi. Je lis cette phrase pour que mon film me ressemble, avec ma voix, de la première à la dernière image."
AI_LABEL = "Généré par IA"


class FilmError(Exception):
    pass


def _safe(text, limit=300):
    return " ".join(str(text or "").split())[:limit]


class Film:
    def __init__(self, home=None, transport=None, planner=None, sleep=time.sleep, voiceover=None):
        self.home = Path(home) if home else DATA / "film"
        self.key_file = self.home / "fal_key"
        self.voice_file = self.home / "voice_sample"
        self.transport = transport or self._http
        self.planner = planner            # (direction, says, seconds, kind) -> {"scenes": [...]} or None; None = the fallback plan
        self.sleep = sleep
        self.voiceover = voiceover        # text -> WAV bytes (the phone's natural voice, free) or None: the voice-over of a product film
        self.lock = threading.Lock()
        self.jobs = {}
        self._schemas = {}
        self.home.mkdir(parents=True, exist_ok=True)
        self._load_jobs()

    # ---------------- jobs kept on disk: a film can be retouched after Termux restarts ----------------
    def _save(self, job):
        data = {k: v for k, v in job.items() if k != "dir"}
        try:
            (job["dir"] / "job.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _load_jobs(self):
        for path in self.home.glob("*/job.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["dir"] = path.parent
                if data.get("state") == "running":       # the brain stopped while it ran: what was made is kept, the rest can be started again
                    data.update(state="quoted", step="", error="interrompu : relance pour terminer")
                self.jobs[data["id"]] = data
            except (OSError, ValueError, KeyError):
                continue

    # ---------------- the key, the voice, the cap ----------------
    def _key(self):
        try:
            key = self.key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return key if KEY_RE.fullmatch(key) else None

    def save_key(self, key):
        key = str(key or "").strip()
        if key.lower().startswith("key "):
            key = key[4:].strip()
        if not KEY_RE.fullmatch(key):
            return {"ok": False, "error": "ce n'est pas une clé fal (une suite de lettres, chiffres et « : »)"}
        fd = os.open(str(self.key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(str(self.key_file), 0o600)
        return {"ok": True}

    def clear_key(self):
        try:
            self.key_file.unlink()
        except OSError:
            pass
        return {"ok": True}

    def save_voice(self, data, ext="m4a"):
        ext = re.sub(r"[^a-z0-9]", "", str(ext).lower())[:5] or "m4a"
        if not data or len(data) > 20_000_000:
            return {"ok": False, "error": "échantillon vide ou trop gros"}
        for old in self.home.glob("voice_sample*"):
            old.unlink(missing_ok=True)
        (self.home / f"voice_sample.{ext}").write_bytes(data)
        return {"ok": True}

    def _voice_path(self):
        found = sorted(self.home.glob("voice_sample.*"))
        return found[0] if found else None

    def cap(self):
        try:
            return float((self.home / "cap").read_text().strip())
        except (OSError, ValueError):
            return DEFAULT_CAP_USD

    def set_cap(self, usd):
        try:
            usd = max(1.0, min(500.0, float(usd)))
        except (TypeError, ValueError):
            return {"ok": False, "error": "montant invalide"}
        (self.home / "cap").write_text(str(usd))
        return {"ok": True, "cap": usd}

    def status(self):
        """What the settings show: never the key itself."""
        return {"key": self._key() is not None, "voice": self._voice_path() is not None, "cap": self.cap(), "sample_text": SAMPLE_TEXT,
                "per_minute": round(MODELS["video"]["usd_per_second"] * 60 + MODELS["lipsync"]["usd_per_second"] * 60 * 0.6, 2)}

    # ---------------- fal ----------------
    def _http(self, method, url, payload=None, key=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Key {key}" if key else "", "Content-Type": "application/json", "User-Agent": "aiwa"})
        try:
            with urllib.request.urlopen(request, timeout=60) as reply:
                body = reply.read(20_000_000)
                return reply.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as err:
            try:
                detail = json.loads(err.read(20_000) or b"{}")
            except ValueError:
                detail = {}
            return err.code, detail
        except (OSError, ValueError) as err:
            raise FilmError(f"fal injoignable : {err}")

    def _call(self, method, url, payload=None):
        key = self._key()
        if not key:
            raise FilmError("pas de clé fal")
        status, body = self.transport(method, url, payload, key)
        if status >= 400:
            raise FilmError(f"fal a refusé (HTTP {status}) : {_safe(json.dumps(body, ensure_ascii=False))}")
        return body

    def run(self, role, inputs, timeout=1500):
        """Submits to fal's queue and waits for the result. Returns the result JSON."""
        endpoint = MODELS[role]["endpoint"]
        job = self._call("POST", f"{QUEUE}/{endpoint}", inputs)
        status_url, response_url = job.get("status_url"), job.get("response_url")
        if not status_url or not response_url:
            raise FilmError(f"réponse inattendue de fal pour {endpoint} : {_safe(json.dumps(job))}")
        waited = 0
        while True:
            state = str(self._call("GET", status_url).get("status", "")).upper()
            if state == "COMPLETED":
                return self._call("GET", response_url)
            if state in ("FAILED", "ERROR", "CANCELLED"):
                raise FilmError(f"{endpoint} a échoué ({state})")
            if waited > timeout:
                raise FilmError(f"{endpoint} : trop long (plus de {timeout // 60} min)")
            self.sleep(3)
            waited += 3

    def _inputs(self, role):
        """The names of the input fields of a model, from fal's description of it ({name: schema}), or None when it cannot be read (then the usual names are used)."""
        endpoint = MODELS[role]["endpoint"]
        if endpoint in self._schemas:
            return self._schemas[endpoint]
        props = None
        try:
            status, body = self.transport("GET", "https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=" + urllib.parse.quote(endpoint, safe="/"), None, None)
            if status == 200 and isinstance(body, dict):
                schemas = (body.get("components") or {}).get("schemas") or {}
                for name, schema in schemas.items():
                    if name.lower().endswith("input") and isinstance(schema.get("properties"), dict):
                        props = schema["properties"]
                        break
        except (FilmError, OSError, ValueError):
            props = None
        self._schemas[endpoint] = props
        return props

    @staticmethod
    def _pick(props, candidates, default):
        if props:
            for name in candidates:
                if name in props:
                    return name
            return None
        return default

    def _video_inputs(self, scene, photos, aspect, kind="me"):
        props = self._inputs("video")
        prompt = scene["situation"]
        if kind == "product":
            prompt += ". Le produit des images de référence reste strictement identique : forme, couleurs, matière, logo et texte inchangés."
        elif kind == "both":
            prompt += ". La personne des premières images de référence et le produit des dernières restent strictement identiques : visage, silhouette, forme, couleurs, logo et texte du produit inchangés."
        out = {}
        pname = self._pick(props, ["prompt"], "prompt")
        many = self._pick(props, ["image_urls", "reference_image_urls", "images", "input_image_urls"], "image_urls")
        one = self._pick(props, ["image_url", "start_image_url", "input_image_url"], None)
        if many:
            out[many] = photos[:7]
        elif one:
            out[one] = photos[0]
        elif props and "elements" in props:
            out["elements"] = [{"frontal_image_url": photos[0], "reference_image_urls": photos[1:7] or photos[:1]}]
            prompt = "@Element1 " + prompt
        else:
            out["image_urls"] = photos[:7]
        out[pname or "prompt"] = prompt
        dur = self._pick(props, ["duration"], "duration")
        if dur:
            kind = (props or {}).get(dur, {}).get("type") if props else "string"
            out[dur] = str(scene["seconds"]) if kind != "integer" else int(scene["seconds"])
        ar = self._pick(props, ["aspect_ratio"], "aspect_ratio")
        if ar:
            out[ar] = aspect
        return out

    def _voice_inputs(self, text, sample_url):
        props = self._inputs("voice")
        out = {self._pick(props, ["gen_text", "text", "prompt"], "gen_text") or "gen_text": text}
        out[self._pick(props, ["ref_audio_url", "audio_url", "reference_audio_url"], "ref_audio_url") or "ref_audio_url"] = sample_url
        rt = self._pick(props, ["ref_text"], "ref_text")
        if rt:
            out[rt] = SAMPLE_TEXT
        return out

    def _lipsync_inputs(self, video_url, audio_url):
        props = self._inputs("lipsync")
        return {self._pick(props, ["video_url"], "video_url") or "video_url": video_url, self._pick(props, ["audio_url"], "audio_url") or "audio_url": audio_url}

    @staticmethod
    def _find_url(result, kinds):
        """The first URL in a result whose file name ends with one of `kinds`, wherever it sits in the JSON."""
        stack = [result]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.lower().split("?")[0].endswith(kinds):
                    return url
                stack += list(item.values())
            elif isinstance(item, list):
                stack += item
            elif isinstance(item, str) and item.startswith("http") and item.lower().split("?")[0].endswith(kinds):
                return item
        return None

    def _download(self, url, path):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aiwa"}), timeout=120) as reply, open(path, "wb") as f:
                shutil.copyfileobj(reply, f)
        except (OSError, ValueError) as err:
            raise FilmError(f"téléchargement impossible : {err}")

    # ---------------- plan and quote ----------------
    def _plan(self, direction, says, seconds, kind="me"):
        """Scenes from the person's direction. Her own words (`says`) are kept as they are."""
        plan = None
        if self.planner:
            try:
                plan = self.planner(direction, says, seconds, kind)
            except Exception:
                plan = None
        scenes = []
        for raw in ((plan or {}).get("scenes") or [])[:MAX_SCENES]:
            if not isinstance(raw, dict) or not str(raw.get("situation") or "").strip():
                continue
            sec = 10 if int(raw.get("seconds") or 5) > 7 else 5
            scenes.append({"situation": _safe(raw["situation"], 500), "seconds": sec, "says": _safe(raw.get("says"), 400)})
        if not scenes:
            scenes = [{"situation": _safe(direction, 500), "seconds": 10 if (seconds or 5) > 7 else 5, "says": _safe(says, 400)}]
        # the words she gave are never changed or added to: a scene may only say words that are in `says`
        given = " ".join(str(says or "").lower().split())
        for scene in scenes:
            if scene["says"] and " ".join(scene["says"].lower().split()) not in given:
                scene["says"] = ""
        return scenes

    @staticmethod
    def scene_key(scene, aspect, kind="me"):
        return hashlib.sha1(json.dumps([scene["situation"], scene["seconds"], scene["says"], aspect, kind], ensure_ascii=False).encode()).hexdigest()[:12]

    def _price(self, scene, kind="me"):
        if kind == "swap":
            return round(MODELS["swap"]["usd_per_second"] * scene["seconds"], 3)
        video = MODELS["video"]["usd_per_second"] * scene["seconds"]
        mouth = voice = 0.0
        if scene["says"] and kind in ("me", "both"):
            mouth = MODELS["lipsync"]["usd_per_second"] * scene["seconds"]
            voice = MODELS["voice"]["usd_per_1000_chars"] * max(1, len(scene["says"])) / 1000
        return round(video + mouth + voice, 3)

    def quote(self, job):
        total = 0.0
        for index, scene in enumerate(job["scenes"]):
            done = (job["dir"] / f"scene_{self.scene_key(scene, job['aspect'], job['kind'])}.mp4").exists()
            scene["price"] = 0.0 if done else self._price(scene, job["kind"])
            scene["done"] = done
            total += scene["price"]
        job["total"] = round(total, 2)
        job["over_cap"] = job["total"] > self.cap()
        return job

    def prepare(self, direction, says="", seconds=None, aspect="9:16", photos=None, consent=False, kind="me", photos_product=None, swap="product"):
        """photos: [bytes], the main references (the person; or the product for a product film; or what replaces something in the person's own video). photos_product: the product, for « moi + produit ».
        kind: me | product | both | swap (the person's own video, in which the product or the person is replaced: the video comes next, see set_source). Returns the quote; nothing is sent to fal yet."""
        if not self._key():
            return {"ok": False, "error": "pas de clé fal : colle-la dans les réglages"}
        kind = kind if kind in KINDS else "me"
        swap = "person" if swap == "person" else "product"
        if not consent:
            return {"ok": False, "error": {"product": "il faut dire que c'est ton produit, ou que tu as le droit de l'utiliser", "both": "il faut dire que c'est toi, et que le produit est à toi ou que tu as le droit de l'utiliser",
                    "swap": "il faut dire que la vidéo est à toi (ou que tu as le droit de l'utiliser)" + (" et que la personne remplacée est d'accord" if swap == "person" else "")}.get(kind, "il faut dire que c'est toi sur les photos (et ta voix), ou que la personne est d'accord")}
        if not photos:
            return {"ok": False, "error": "il faut au moins une photo"}
        if kind == "both" and not photos_product:
            return {"ok": False, "error": "il faut au moins une photo du produit"}
        if not str(direction or "").strip() and kind != "swap":
            return {"ok": False, "error": "dis ce que tu veux dans le film"}
        if says and kind in ("me", "both") and not self._voice_path():
            return {"ok": False, "error": "pour parler dans le film, enregistre d'abord ta voix dans les réglages"}
        job_id = uuid.uuid4().hex[:10]
        folder = self.home / job_id
        folder.mkdir(parents=True, exist_ok=True)

        def keep(items, prefix, limit):
            names = []
            for i, data in enumerate((items or [])[:limit]):
                if not data or len(data) > 12_000_000:
                    continue
                path = folder / f"{prefix}{i}.jpg"
                path.write_bytes(data)
                names.append(path.name)
            return names
        paths = keep(photos, "photo", 4 if kind == "both" else 7)
        product = keep(photos_product, "prod", 3) if kind == "both" else []
        if not paths or (kind == "both" and not product):
            return {"ok": False, "error": "photos vides ou trop grosses"}
        (folder / "kind.txt").write_text(kind)
        if kind == "swap":
            what = "la personne" if swap == "person" else "le produit"
            scenes = [{"situation": _safe(direction, 500) or f"Remplacer {what} dans la vidéo", "seconds": 0, "says": ""}]
            state = "needs_video"
        else:
            scenes, state = self._plan(direction, says, seconds, kind), "quoted"
        job = {"id": job_id, "dir": folder, "direction": _safe(direction, 1500), "says": _safe(says, 1500), "aspect": aspect if aspect in ("9:16", "16:9", "1:1") else "9:16",
               "photos": paths, "photos_product": product, "kind": kind, "swap": swap, "scenes": scenes, "state": state, "step": "", "error": None, "film": None, "confirmed": False}
        self.quote(job)
        with self.lock:
            self.jobs[job_id] = job
        self._save(job)
        return {"ok": True, **self.view(job)}

    def set_source(self, job_id, data):
        """The person's own video, for a swap: kept, its length read (it is what the quote is made from)."""
        job = self.jobs.get(job_id)
        if not job or job.get("kind") != "swap" or job["state"] == "running":
            return {"ok": False, "error": "film inconnu ou pas un remplacement"}
        if not data or len(data) > 200_000_000:
            return {"ok": False, "error": "vidéo vide ou trop grosse (200 Mo au plus)"}
        path = job["dir"] / "source.mp4"
        path.write_bytes(data)
        try:
            seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60).stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            seconds = 0.0
        if seconds <= 0:
            path.unlink(missing_ok=True)
            return {"ok": False, "error": "je n'arrive pas à lire cette vidéo (ffmpeg est-il installé : pkg install ffmpeg ?)"}
        if seconds > MAX_SWAP_SECONDS:
            path.unlink(missing_ok=True)
            return {"ok": False, "error": f"la vidéo dure {int(seconds)} s : {MAX_SWAP_SECONDS} s au plus pour un remplacement"}
        job["scenes"][0]["seconds"] = max(1, int(seconds + 0.999))
        job["state"], job["error"] = "quoted", None
        self.quote(job)
        self._save(job)
        return {"ok": True, **self.view(job)}

    def edit(self, job_id, index, situation=None, says=None, seconds=None, remove=False):
        job = self.jobs.get(job_id)
        if not job or job["state"] == "running":
            return {"ok": False, "error": "film inconnu ou en cours"}
        if not 0 <= index < len(job["scenes"]):
            return {"ok": False, "error": "scène inconnue"}
        if remove:
            job["scenes"].pop(index)
            if not job["scenes"]:
                return {"ok": False, "error": "il faut au moins une scène"}
        else:
            scene = job["scenes"][index]
            if situation:
                scene["situation"] = _safe(situation, 500)
            if says is not None:
                scene["says"] = _safe(says, 400)
            if seconds:
                scene["seconds"] = 10 if int(seconds) > 7 else 5
        job["state"], job["error"] = "quoted", None
        self.quote(job)
        self._save(job)
        return {"ok": True, **self.view(job)}

    @staticmethod
    def view(job):
        return {"id": job["id"], "state": job["state"], "step": job["step"], "error": job["error"], "total": job.get("total", 0), "over_cap": job.get("over_cap", False),
                "aspect": job["aspect"], "film": job["film"], "label": AI_LABEL, "kind": job["kind"], "swap": job.get("swap", ""), "saved": job.get("saved", "none"), "saved_error": job.get("saved_error", ""),
                "scenes": [{"situation": s["situation"], "seconds": s["seconds"], "says": s["says"], "price": s.get("price", 0), "done": s.get("done", False)} for s in job["scenes"]]}

    def get(self, job_id):
        job = self.jobs.get(job_id)
        return {"ok": True, **self.view(job)} if job else {"ok": False, "error": "film inconnu"}

    # ---------------- production ----------------
    def start(self, job_id, confirmed=False):
        """Starts the production, only after the person's confirmation of THIS quote."""
        job = self.jobs.get(job_id)
        if not job:
            return {"ok": False, "error": "film inconnu"}
        if not confirmed:
            return {"ok": False, "error": "devis non confirmé"}
        if job["state"] == "needs_video":
            return {"ok": False, "error": "il manque ta vidéo"}
        if job["state"] == "running":
            return {"ok": True, **self.view(job)}
        self.quote(job)
        if job["over_cap"]:
            return {"ok": False, "error": f"le devis ({job['total']} $) dépasse ton plafond ({self.cap()} $) : monte-le dans les réglages ou enlève des scènes"}
        job.update(state="running", error=None, step="départ", confirmed=True)
        threading.Thread(target=self._produce, args=(job,), daemon=True).start()
        return {"ok": True, **self.view(job)}

    def _data_uri(self, path, mime=None):
        mime = mime or "audio/mp4" if path.suffix in (".m4a", ".mp4", ".aac") else "audio/wav" if path.suffix == ".wav" else "audio/mpeg" if path.suffix == ".mp3" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()

    def _produce(self, job):
        try:
            folder = job["dir"]
            if job["kind"] == "swap":
                self._produce_swap(job)
                return
            photos = [self._data_uri(folder / name) for name in job["photos"]] + [self._data_uri(folder / name) for name in job.get("photos_product", [])]
            sample = None
            clips = []
            total = len(job["scenes"])
            for i, scene in enumerate(job["scenes"], 1):
                clip = folder / f"scene_{self.scene_key(scene, job['aspect'], job['kind'])}.mp4"
                if not clip.exists():
                    audio_url = None
                    if scene["says"] and job["kind"] in ("me", "both"):
                        if sample is None:
                            sample = self._data_uri(self._voice_path())
                        job["step"] = f"scène {i}/{total} : ta voix"
                        voice = self.run("voice", self._voice_inputs(scene["says"], sample))
                        audio_url = self._find_url(voice, (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"))
                        if not audio_url:
                            raise FilmError("la voix n'a rien rendu : " + _safe(json.dumps(voice)))
                    job["step"] = f"scène {i}/{total} : l'image"
                    video = self.run("video", self._video_inputs(scene, photos, job["aspect"], job["kind"]))
                    video_url = self._find_url(video, (".mp4", ".mov", ".webm"))
                    if not video_url:
                        raise FilmError("l'image n'a rien rendu : " + _safe(json.dumps(video)))
                    if audio_url and job["kind"] in ("me", "both"):
                        job["step"] = f"scène {i}/{total} : la bouche"
                        mouth = self.run("lipsync", self._lipsync_inputs(video_url, audio_url))
                        video_url = self._find_url(mouth, (".mp4", ".mov", ".webm")) or video_url
                    job["step"] = f"scène {i}/{total} : téléchargement"
                    if job["kind"] == "product" and scene["says"] and self.voiceover:
                        raw = folder / f"raw_{clip.name}"
                        self._download(video_url, raw)
                        job["step"] = f"scène {i}/{total} : voix off"
                        self._add_voiceover(raw, scene["says"], clip)
                    else:
                        self._download(video_url, clip)
                clips.append(clip)
            job["step"] = "assemblage"
            job["film"] = self._assemble(job, clips)
            job.update(state="done", step="terminé")
            self._save(job)
        except FilmError as err:
            job.update(state="error", error=str(err))
        except Exception as err:      # never silent: the person sees why
            job.update(state="error", error=f"erreur inattendue : {_safe(err)}")

    def _fal_file(self, path, content_type):
        """A file for fal: small ones travel inside the request, bigger ones are put in fal's storage first (an address is asked for, the bytes are sent there)."""
        if path.stat().st_size <= 4_000_000:
            return self._data_uri(path, content_type)
        info = self._call("POST", "https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=gcs", {"content_type": content_type, "file_name": path.name})
        upload_url, file_url = info.get("upload_url"), info.get("file_url")
        if not upload_url or not file_url:
            raise FilmError("fal n'a pas donné d'adresse d'envoi pour la vidéo : " + _safe(json.dumps(info)))
        try:
            urllib.request.urlopen(urllib.request.Request(upload_url, data=path.read_bytes(), method="PUT", headers={"Content-Type": content_type}), timeout=900)
        except (OSError, ValueError) as err:
            raise FilmError(f"l'envoi de la vidéo à fal a échoué : {err}")
        return file_url

    def _swap_inputs(self, video_url, image_url, target, prompt):
        props = self._inputs("swap")
        out = {self._pick(props, ["video_url"], "video_url") or "video_url": video_url}
        out[self._pick(props, ["image_url", "reference_image_url", "reference_image", "swap_image_url"], "image_url") or "image_url"] = image_url
        mode = self._pick(props, ["mode", "swap_mode", "type"], "mode")
        if mode:
            out[mode] = "person" if target == "person" else "object"
        pname = self._pick(props, ["prompt"], None)
        if pname and prompt:
            out[pname] = prompt
        return out

    def _produce_swap(self, job):
        folder = job["dir"]
        scene = job["scenes"][0]
        clip = folder / f"scene_{self.scene_key(scene, job['aspect'], job['kind'])}.mp4"
        if not clip.exists():
            source = folder / "source.mp4"
            if not source.exists():
                raise FilmError("il manque ta vidéo")
            job["step"] = "envoi de ta vidéo"
            video = self._fal_file(source, "video/mp4")
            image = self._data_uri(folder / job["photos"][0])
            job["step"] = "remplacement"
            result = self.run("swap", self._swap_inputs(video, image, job.get("swap", "product"), scene["situation"]))
            url = self._find_url(result, (".mp4", ".mov", ".webm"))
            if not url:
                raise FilmError("le remplacement n'a rien rendu : " + _safe(json.dumps(result)))
            job["step"] = "téléchargement"
            self._download(url, clip)
        job["step"] = "assemblage"
        job["film"] = self._assemble(job, [clip])
        job.update(state="done", step="terminé")
        self._save(job)

    def _add_voiceover(self, raw, text, out):
        """The voice-over (the phone's natural voice) laid on the generated clip; the clip's length wins (a text longer than the scene is cut)."""
        wav = None
        try:
            wav = self.voiceover(text)
        except Exception:
            wav = None
        if not wav:
            shutil.copy(raw, out)        # no voice available: the scene stays silent, the film goes on
            return
        audio = raw.with_suffix(".vo.wav")
        audio.write_bytes(wav)
        done = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-i", str(audio), "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)],
                              capture_output=True, text=True, timeout=300)
        if done.returncode != 0:
            raise FilmError("la voix off n'a pas pu être posée : " + _safe(done.stderr, 200))

    def _assemble(self, job, clips):
        """The scenes joined (same size and sound for all), marked as made by an AI in the picture when ffmpeg can write text, always in the file's metadata."""
        if not shutil.which("ffmpeg"):
            raise FilmError("ffmpeg manque : pkg install ffmpeg")
        w, h = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (960, 960)}[job["aspect"]]
        out = job["dir"] / "film.mp4"
        inputs, parts = [], []
        for i, clip in enumerate(clips):
            inputs += ["-i", str(clip)]
            parts.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{i}];[{i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        concat = "".join(f"[v{i}][a{i}]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
        # a clip without sound gets a silent track first
        for i, clip in enumerate(clips):
            if not self._has_audio(clip):
                silent = clip.with_name(clip.stem + "_s.mp4")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:v", "copy", "-c:a", "aac", str(silent)], check=True, timeout=300)
                inputs[2 * i + 1] = str(silent)
        meta = ["-metadata", f"comment={AI_LABEL}", "-metadata", f"title={AI_LABEL}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(out)]
        label = f"drawtext=text='{AI_LABEL}':fontcolor=white@0.8:fontsize={max(14, h // 55)}:x=w-tw-12:y=h-th-12:box=1:boxcolor=black@0.35:boxborderw=4"
        with_label = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts) + ";" + concat + f";[v]{label}[vl]", "-map", "[vl]", "-map", "[a]", *meta]
        plain = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts) + ";" + concat, "-map", "[v]", "-map", "[a]", *meta]
        for command in (with_label, plain):
            done = subprocess.run(command, capture_output=True, text=True, timeout=1800)
            if done.returncode == 0 and out.exists():
                return out.name
        raise FilmError("l'assemblage a échoué : " + _safe(done.stderr, 300))

    @staticmethod
    def _has_audio(path):
        done = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60)
        return bool(done.stdout.strip())

    @staticmethod
    def asset_name(job_id, kind):
        """The file name in the release (plain ASCII: GitHub rewrites spaces and accents)."""
        return f"film-de-{ {'product': 'produit', 'both': 'moi-produit', 'swap': 'remplacement'}.get(kind, 'moi') }-{job_id}.mp4"

    def mark_saved(self, job_id, state, error=""):
        """state: none | pending (a session was asked to save it) | saved | failed."""
        job = self.jobs.get(job_id)
        if job:
            job["saved"], job["saved_error"] = state, error
            self._save(job)

    def delete(self, job_id, drafts):
        """Deletes the film made on this phone. drafts=True: its photos, plan and scene clips too (it can no longer be retouched); False: only the final film, the drafts stay."""
        job = self.jobs.get(job_id)
        folder = self.home / job_id
        if not (folder / "film.mp4").exists() and not job:
            return {"ok": False, "error": "film introuvable"}
        if drafts:
            shutil.rmtree(folder, ignore_errors=True)
            self.jobs.pop(job_id, None)
        else:
            (folder / "film.mp4").unlink(missing_ok=True)
            if job:
                job.update(film=None, state="quoted", saved="none", saved_error="")
                self._save(job)
        return {"ok": True}

    # ---------------- the films made ----------------
    def films(self):
        """The finished films for the Média list: [{name, path, ts}], newest first."""
        out = []
        for folder in self.home.glob("*/film.mp4"):
            try:
                kind = (folder.parent / "kind.txt").read_text().strip()
            except OSError:
                kind = "me"
            job = self.jobs.get(folder.parent.name) or {}
            out.append({"id": folder.parent.name, "path": folder, "ts": int(folder.stat().st_mtime), "kind": kind, "saved": job.get("saved", "none")})
        return sorted(out, key=lambda f: f["ts"], reverse=True)
