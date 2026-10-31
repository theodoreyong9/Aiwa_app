"""Free generated shots on Hugging Face (ZeroGPU Spaces: Wan 2.2, LTX-Video…), called by the brain with the person's OWN token (Réglages), so no session needs it. A shot is made in the background (it queues,
it takes minutes), kept in the phone like a stock clip (card: made by an AI, the Space, the prompt) and put in the release `stock` by the same step as the stock clips, which is how the sessions get it.

Honest limits: the Spaces change, move or queue and their parameters differ; the defaults below are guesses to check (`api()` shows what a Space really asks for), and `spaces.json` in the data folder replaces
them without any update. Without a token the daily ZeroGPU quota is only a few minutes. `gradio_client` is installed on first use."""
import json
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

DEFAULTS = {
    "text": {"space": "Lightricks/LTX-Video-Distilled", "api_name": "/text_to_video", "prompt_arg": "prompt", "args": {}},
    "image": {"space": "Lightricks/LTX-Video-Distilled", "api_name": "/image_to_video", "prompt_arg": "prompt", "image_arg": "input_image_filepath", "args": {}},
}
QUOTA_WORDS = ("quota", "zerogpu", "exceeded", "too many requests", "429", "no gpu")


def find_video(result):
    if isinstance(result, str):
        return result if result.lower().endswith((".mp4", ".webm", ".mov")) else None
    if isinstance(result, dict):
        for key in ("video", "value", "path", "name"):
            found = find_video(result.get(key))
            if found:
                return found
        for value in result.values():
            found = find_video(value)
            if found:
                return found
    if isinstance(result, (list, tuple)):
        for item in result:
            found = find_video(item)
            if found:
                return found
    return None


class Hf:
    def __init__(self, stock, runner=None):
        self.stock = stock
        self.runner = runner or self._predict
        self.jobs = {}
        self.lock = threading.Lock()

    def config(self, mode):
        try:
            data = json.loads((self.stock.home / "spaces.json").read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get(mode), dict):
                return {**DEFAULTS[mode], **data[mode]}
        except (OSError, ValueError):
            pass
        return DEFAULTS[mode]

    @staticmethod
    def _client(space, token):
        try:
            from gradio_client import Client
        except ImportError:
            from . import voice_lib
            voice_lib.ensure_pip()
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "gradio_client"], capture_output=True, text=True, timeout=900)
            from gradio_client import Client
        try:
            return Client(space, hf_token=token)
        except TypeError:
            return Client(space, token=token)

    def _predict(self, cfg, prompt, image, token):
        """The path of the video the Space made (raises with the Space's own words)."""
        from gradio_client import handle_file
        client = self._client(cfg["space"], token)
        kwargs = {cfg.get("prompt_arg", "prompt"): prompt, **(cfg.get("args") or {})}
        if image:
            kwargs[cfg.get("image_arg", "image")] = handle_file(str(image))
        result = client.predict(api_name=cfg["api_name"], **kwargs)
        video = find_video(result)
        if not video or not Path(video).exists():
            raise RuntimeError("le Space n'a rendu aucun fichier vidéo")
        return video

    def api(self, mode="text"):
        """What the Space asks for, as text (to correct `spaces.json`)."""
        cfg = self.config(mode)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                self._client(cfg["space"], self.stock.key_of("hf")).view_api()
        except Exception as err:
            return {"ok": False, "error": str(err)[-300:]}
        return {"ok": True, "space": cfg["space"], "api": buf.getvalue()[-4000:]}

    def start(self, prompt, image=None):
        """Starts a shot in the background: {"ok", "id"}; poll `job(id)`."""
        prompt = " ".join(str(prompt or "").split())[:600]
        if not prompt:
            return {"ok": False, "error": "décris le plan"}
        token = self.stock.key_of("hf")
        job_id = uuid.uuid4().hex[:8]
        mode = "image" if image else "text"
        with self.lock:
            self.jobs[job_id] = {"state": "running", "error": "", "quota": False, "clip": "", "token": token is not None, "ts": int(time.time())}
        threading.Thread(target=self._run, args=(job_id, mode, prompt, image, token), daemon=True).start()
        return {"ok": True, "id": job_id, "token": token is not None}

    def _run(self, job_id, mode, prompt, image, token):
        cfg = self.config(mode)
        job = self.jobs[job_id]
        try:
            video = self.runner(cfg, prompt, image, token)
            folder = self.stock.home / "clips"
            folder.mkdir(parents=True, exist_ok=True)
            clip_id = f"hf-{job_id}"
            shutil.copyfile(video, folder / f"{clip_id}.mp4")
            card = {"id": clip_id, "source": "hf", "title": prompt[:80], "duration": None, "width": None, "height": None, "page": "https://huggingface.co/spaces/" + cfg["space"], "author": cfg["space"],
                    "licence": "Généré par IA (Hugging Face, " + cfg["space"] + ") : à présenter comme tel", "file": f"{clip_id}.mp4"}
            (folder / f"{clip_id}.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            job.update(state="done", clip=clip_id)
        except Exception as err:
            text = str(err)
            quota = any(w in text.lower() for w in QUOTA_WORDS)
            job.update(state="failed", quota=quota, error=("Le quota gratuit de calcul du jour est atteint" + ("" if token else " (sans clé Hugging Face il n'est que de quelques minutes par jour : une clé gratuite en donne plus)")) if quota else text[-300:])

    def job(self, job_id):
        data = self.jobs.get(str(job_id))
        return {"ok": True, **data} if data else {"ok": False, "error": "plan inconnu"}
