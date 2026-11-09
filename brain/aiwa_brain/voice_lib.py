"""The natural voice of the liaison agent: through sherpa-onnx, on the CPU of the phone's Linux (Termux). No account, no key, no network once installed. Two engines:
 - "piper" (the default): the Piper voice "siwis medium" (French), light (about 80 MB) and fast: a short sentence comes out almost at once;
 - "kokoro": the Kokoro voice (French "ff_siwis"), more natural, but heavy (about 350 MB) and several times slower. It is installed only when the person asks for it, and it speaks only while it is fast enough:
   when it takes longer than the sentence lasts, twice in a row, the voice goes back to Piper by itself and says why (`note`).
The app asks for a sentence and gets a WAV; if anything is missing it falls back on the phone's own voice.
Pure standard library apart from sherpa_onnx itself, which is imported only when a sentence is made."""
import os
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import wave

RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
ENGINES = {
    "piper": {"name": "vits-piper-fr_FR-siwis-medium", "file": "fr_FR-siwis-medium.onnx"},
    "kokoro": {"name": "kokoro-multi-lang-v1_0", "file": "model.onnx", "sid": 30, "lang": "fr"},      # sid 30 = ff_siwis, the French voice of this model
}
DEFAULT_ENGINE = "piper"
NAME = ENGINES["piper"]["name"]
URL = RELEASES + NAME + ".tar.bz2"
MAX_CHARS = 600
SLOW = 1.0                  # a sentence that takes longer to make than to say is too slow for a conversation


def model_dir(home=None, engine=DEFAULT_ENGINE):
    return os.path.join(home or os.path.expanduser("~"), ".cache", "aiwa-video", ENGINES[engine]["name"])


def model_present(home=None, engine=DEFAULT_ENGINE):
    return os.path.exists(os.path.join(model_dir(home, engine), ENGINES[engine]["file"]))


def _engine_file(home=None):
    return os.path.join(home or os.path.expanduser("~"), ".cache", "aiwa-video", "voice-engine.txt")


def read_engine(home=None):
    """The engine the person chose (piper when nothing was chosen or the file is unreadable)."""
    try:
        with open(_engine_file(home), encoding="utf-8") as f:
            name = f.read().strip()
        return name if name in ENGINES else DEFAULT_ENGINE
    except OSError:
        return DEFAULT_ENGINE


def write_engine(name, home=None):
    try:
        os.makedirs(os.path.dirname(_engine_file(home)), exist_ok=True)
        with open(_engine_file(home), "w", encoding="utf-8") as f:
            f.write(name)
    except OSError:
        pass


def to_wav(samples, rate):
    """Floats in [-1, 1] as a 16-bit mono WAV (bytes)."""
    import io
    pcm = bytearray()
    for x in samples:
        v = int(max(-1.0, min(1.0, float(x))) * 32767)
        pcm += v.to_bytes(2, "little", signed=True)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(bytes(pcm))
    return out.getvalue()


def _pip_available():
    try:
        return subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ensure_pip(timeout=900):
    """pip itself, when the Python of the phone's Linux has none (« No module named pip »: Debian ships it as a separate package): ensurepip, then the Debian package, then get-pip.py.
    Raises with the last words of what failed when none works."""
    if _pip_available():
        return
    last = ""
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    steps = [[sys.executable, "-m", "ensurepip", "--upgrade"], ["apt-get", "update", "-qq"], ["apt-get", "install", "-y", "-qq", "python3-pip"]]
    for cmd in steps:
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        except (OSError, subprocess.SubprocessError) as err:
            last = str(err)
            continue
        if done.returncode != 0:
            last = " ".join((done.stderr or done.stdout or "").split())[-200:]
        if _pip_available():
            return
    try:
        target = os.path.join(os.path.expanduser("~"), ".cache", "aiwa-video")
        os.makedirs(target, exist_ok=True)
        script = os.path.join(target, "get-pip.py")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", script)
        for extra in (["--break-system-packages"], []):
            done = subprocess.run([sys.executable, script, "-q"] + extra, capture_output=True, text=True, timeout=timeout)
            if done.returncode == 0 and _pip_available():
                return
            last = " ".join((done.stderr or done.stdout or "").split())[-200:] or last
    except (OSError, subprocess.SubprocessError) as err:
        last = str(err)
    raise RuntimeError("pip est absent et n'a pas pu être installé : " + (last or "?"))


def pip_install(package, timeout=1500):
    """pip install of one package. The Linux of the phone is a Debian whose Python refuses installs outside a virtualenv (« externally-managed-environment », PEP 668): then once more with
    --break-system-packages, the package going where the app's own Python looks for it. Raises with pip's own last words when it fails."""
    ensure_pip()
    base = [sys.executable, "-m", "pip", "install", "-q", "--no-input", package]
    done = subprocess.run(base, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0 and "externally-managed" in (done.stderr or ""):
        done = subprocess.run(base + ["--break-system-packages"], capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        tail = " ".join((done.stderr or done.stdout or "").split())[-300:]
        raise RuntimeError("pip " + package + " : " + (tail or f"code {done.returncode}"))


class Voice:
    """state: none (not installed) / installing / ready / error."""

    def __init__(self, home=None):
        self.home = home
        self.state = "ready" if model_present(home) and self._library() else "none"     # the light engine (Piper): what every state of the app has always meant
        self.kokoro = "ready" if model_present(home, "kokoro") and self._library() else "none"   # none / installing / ready / error
        self.engine = read_engine(home)      # the engine the person wants
        self.note = None                     # why the voice is not the one wanted (too slow, still downloading…)
        self.error = None
        self._tts = {}
        self._lock = threading.Lock()
        self._fails = 0            # sentences that failed in a row: one failure does not take the voice away
        self._slow = 0             # sentences in a row that took longer to make than to say (the heavy engine)
        self.attempt_at = 0.0      # when an installation was last started

    @staticmethod
    def _library():
        try:
            import sherpa_onnx  # noqa: F401
            return True
        except Exception:
            return False

    def install(self):
        """Starts the installation in the background (once); the state tells where it is."""
        with self._lock:
            if self.state in ("installing", "ready"):
                return
            self.state, self.error = "installing", None
            self.attempt_at = time.time()
        threading.Thread(target=self._install, daemon=True).start()

    def active(self):
        """The engine that speaks right now: the one wanted when it is ready, else Piper when it is, else none."""
        if self.engine == "kokoro" and self.kokoro == "ready":
            return "kokoro"
        return "piper" if self.state == "ready" else None

    def set_engine(self, name):
        """The person's choice. The heavy engine is downloaded in the background (the light one keeps speaking meanwhile) and takes over when it is ready."""
        if name not in ENGINES:
            return {"ok": False, "error": "moteur inconnu : " + str(name)}
        self.engine = name
        self.note = None
        self._slow = 0
        write_engine(name, self.home)
        if name == "kokoro" and self.kokoro in ("none", "error"):
            self.install_kokoro()
        return {"ok": True, "engine": self.engine, "active": self.active(), "kokoro": self.kokoro}

    def install_kokoro(self):
        with self._lock:
            if self.kokoro in ("installing", "ready"):
                return
            self.kokoro = "installing"
        threading.Thread(target=self._install_kokoro, daemon=True).start()

    def _install_kokoro(self):
        try:
            if not self._library():
                pip_install("sherpa-onnx")
            if not model_present(self.home, "kokoro"):
                self._download(ENGINES["kokoro"]["name"])
            if not (model_present(self.home, "kokoro") and self._library()):
                raise RuntimeError("installation incomplète")
            self.kokoro = "ready"
            self.note = None
        except Exception as err:
            self.kokoro = "error"
            self.note = "Le moteur « plus naturel » n'a pas pu être installé : " + str(err)[-200:]
            print("kokoro voice: installation failed: " + str(err)[-300:], flush=True)

    def _download(self, name):
        target = os.path.dirname(model_dir(self.home))
        os.makedirs(target, exist_ok=True)
        archive = os.path.join(target, name + ".tar.bz2")
        urllib.request.urlretrieve(RELEASES + name + ".tar.bz2", archive)
        with tarfile.open(archive, "r:bz2") as tar:
            for member in tar.getmembers():   # nothing may land outside the folder
                if os.path.isabs(member.name) or ".." in member.name.split("/"):
                    raise ValueError("archive refusée : " + member.name)
            tar.extractall(target)
        os.remove(archive)

    def view(self):
        """What the status of the brain shows."""
        return {"engine": self.engine, "active": self.active(), "kokoro": self.kokoro, "note": self.note}

    def retry_if_failed(self, wait=600):
        """A voice in error is installed again, at most every `wait` seconds (a network that was down, a download cut short): nobody has to find the button."""
        if self.state == "error" and time.time() - self.attempt_at > wait:
            self._tts = {}
            self.install()

    def _install(self):
        try:
            if not self._library():
                pip_install("sherpa-onnx")
            if not model_present(self.home):
                self._download(NAME)
            if not (model_present(self.home) and self._library()):
                raise RuntimeError("installation incomplète")
            self._fails = 0
            self.state = "ready"
        except Exception as err:
            self.state, self.error = "error", str(err)[-400:]
            print("natural voice: installation failed: " + self.error, flush=True)

    def _load(self, engine):
        import sherpa_onnx as so
        d = model_dir(self.home, engine)
        if engine == "kokoro":
            k = so.OfflineTtsKokoroModelConfig(model=os.path.join(d, "model.onnx"), voices=os.path.join(d, "voices.bin"), tokens=os.path.join(d, "tokens.txt"), data_dir=os.path.join(d, "espeak-ng-data"),
                                               dict_dir=os.path.join(d, "dict"), lexicon=os.path.join(d, "lexicon-us-en.txt") + "," + os.path.join(d, "lexicon-zh.txt"), lang=ENGINES["kokoro"]["lang"])
            cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(kokoro=k, num_threads=4), max_num_sentences=1)
        else:
            cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(
                model=os.path.join(d, ENGINES["piper"]["file"]), tokens=os.path.join(d, "tokens.txt"), data_dir=os.path.join(d, "espeak-ng-data")), num_threads=2), max_num_sentences=1)
        return so.OfflineTts(cfg)

    def say(self, text):
        """The sentence as WAV bytes, or None when the voice is not ready or fails."""
        text = " ".join(str(text or "").split())[:MAX_CHARS]
        engine = self.active()
        if not text or engine is None:
            return None
        try:
            with self._lock:
                if engine not in self._tts:
                    self._tts[engine] = self._load(engine)
                started = time.time()
                audio = self._tts[engine].generate(text, sid=ENGINES[engine].get("sid", 0), speed=1.0)
                took = time.time() - started
            self._fails = 0
            seconds = len(audio.samples) / float(audio.sample_rate or 1)
            if engine == "kokoro":
                # the heavy engine speaks only while it keeps up with the sentence: twice in a row too slow, and the light one takes over (the person is told, and can try again)
                self._slow = self._slow + 1 if seconds > 0.5 and took > SLOW * seconds else 0
                if self._slow >= 2:
                    self.engine, self.note, self._slow = "piper", "Le moteur « plus naturel » est trop lent sur ce téléphone : retour au moteur léger.", 0
                    write_engine("piper", self.home)
            return to_wav(audio.samples, audio.sample_rate)
        except Exception as err:
            # one sentence that fails (a text the voice cannot read, a memory shortage) does not stop the voice: it is made again from scratch at the next one; after three in a row it is in error
            self._tts.pop(engine, None)
            self._fails += 1
            self.error = str(err)[-400:]
            if self._fails >= 3:
                if engine == "kokoro":
                    self.engine, self.note, self._fails = "piper", "Le moteur « plus naturel » a échoué : retour au moteur léger.", 0
                    write_engine("piper", self.home)
                else:
                    self.state = "error"
            return None
