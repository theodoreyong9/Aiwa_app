"""Claude straight from the backend, with the person's own Anthropic API key (optional): the agent answers in a second or two instead of going through a cloud session, and
the chamber speaks with it. Without a key the super agent falls back on the Claude of the phone. A daily ceiling (tokens) keeps the bill where the person wants it.

The key is saved only in this phone's Linux (a file readable by its owner alone), is never returned by the backend (the status says only none / installing / ready / error), never goes
into a repository, and is sent to Anthropic only. The `anthropic` package is installed from PyPI the first time a key is saved.
"""
import json
import os
import re
import threading
import time
from pathlib import Path

KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")
MODEL = "claude-haiku-5-5"   # fast and cheap; the answer of a voice assistant must not wait
MAX_TOKENS = 700


class Llm:
    """state: none (no key) / capped (the day's ceiling is reached) / installing (the package is being installed) / ready / error."""

    def __init__(self, key_file=None, client_factory=None, usage_file=None):
        self.key_file = Path(key_file) if key_file else Path.home() / ".aiwa_anthropic_key"
        self.usage_file = Path(usage_file) if usage_file else Path.home() / ".aiwa_llm_usage.json"
        self._factory = client_factory
        self._client = None
        self.error = None
        self._installing = False
        self._lock = threading.Lock()

    # ---- the key ----
    def _key(self):
        try:
            key = self.key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return key if KEY_RE.fullmatch(key) else None

    def save_key(self, key):
        """Saves the key (owner-only file) and prepares the package. {"ok", "error"}."""
        key = str(key or "").strip()
        if not KEY_RE.fullmatch(key):
            return {"ok": False, "error": "ce n'est pas une clé Anthropic (elle commence par sk-ant-)"}
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(key)
        os.chmod(str(self.key_file), 0o600)
        self._client, self.error = None, None
        self.prepare()
        return {"ok": True}

    def clear_key(self):
        try:
            self.key_file.unlink()
        except OSError:
            pass
        self._client, self.error = None, None
        return {"ok": True}

    # ---- the package ----
    def _have_sdk(self):
        if self._factory:
            return True
        try:
            import anthropic  # noqa: F401
            return True
        except Exception:
            return False

    def prepare(self):
        """Installs the package in the background when a key is there and it is missing."""
        with self._lock:
            if self._installing or not self._key() or self._have_sdk():
                return
            self._installing = True
        threading.Thread(target=self._install, daemon=True).start()

    def _install(self):
        try:
            from .voice_lib import pip_install
            pip_install("anthropic", timeout=900)
            self.error = None
        except Exception as err:
            detail = getattr(err, "stderr", b"") or b""
            self.error = (str(err) + " " + detail.decode("utf-8", "replace")[-200:]).strip()
        finally:
            self._installing = False

    @property
    def state(self):
        if not self._key():
            return "none"
        if self.capped():
            return "capped"
        if self._installing:
            return "installing"
        if self.error:
            return "error"
        return "ready" if self._have_sdk() else "installing"

    # ---- the ceiling: tokens per day (0 = none) ----
    def _usage(self):
        try:
            data = json.loads(self.usage_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data = data if isinstance(data, dict) else {}
        today = time.strftime("%Y-%m-%d")
        if data.get("day") != today:
            data = {"day": today, "used": 0, "cap": int(data.get("cap") or 0)}
        return {"day": today, "used": int(data.get("used") or 0), "cap": int(data.get("cap") or 0)}

    def _write_usage(self, data):
        try:
            self.usage_file.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def set_cap(self, tokens):
        """The most tokens Aiwa may spend per day with the key; 0 = no ceiling. {"ok", "cap"}."""
        try:
            cap = max(0, min(int(tokens), 100_000_000))
        except (TypeError, ValueError):
            return {"ok": False, "error": "plafond invalide"}
        with self._lock:
            data = self._usage()
            data["cap"] = cap
            self._write_usage(data)
        return {"ok": True, "cap": cap}

    def usage(self):
        with self._lock:
            return self._usage()

    def capped(self):
        data = self.usage()
        return bool(data["cap"]) and data["used"] >= data["cap"]

    # ---- a question ----
    def ask(self, system, messages, max_tokens=MAX_TOKENS, model=MODEL):
        """The text of Claude's answer, or None (no key, package missing, network, refusal). Never raises: the callers fall back on what they did before."""
        key = self._key()
        if not key or not self._have_sdk() or self.capped():
            return None
        try:
            if self._client is None:
                if self._factory:
                    self._client = self._factory(key)
                else:
                    import anthropic
                    self._client = anthropic.Anthropic(api_key=key, timeout=30.0, max_retries=1)
            try:
                response = self._client.messages.create(
                    model=model, max_tokens=max_tokens, system=system, messages=messages,
                    thinking={"type": "disabled"}, output_config={"effort": "low"},
                )
            except TypeError:   # an older package that does not know these parameters
                response = self._client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages)
            usage = getattr(response, "usage", None)
            spent = int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "output_tokens", 0) or 0)
            if spent:
                with self._lock:
                    data = self._usage()
                    data["used"] += spent
                    self._write_usage(data)
            if getattr(response, "stop_reason", None) == "refusal":
                return None
            parts = [getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"]
            return "".join(parts).strip() or None
        except Exception as err:
            self.error = str(err)[:200]
            return None


def json_in(text):
    """The first JSON object found in a model's answer (it may be wrapped in a fence or in words), or None."""
    import json
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:i + 1])
                        if isinstance(value, dict):
                            return value
                    except ValueError:
                        pass
                    break
        start = text.find("{", start + 1)
    return None
