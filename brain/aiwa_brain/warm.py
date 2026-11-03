"""A Claude kept running for the super agent (the person's subscription, no key): the program starts cold ONCE (6 to 30 seconds), then every turn is only the model's time.
It keeps the conversation itself, so a turn sends the point and the sentence, and the history is sent again only when the process is new. Any failure kills it: the caller falls back to a fresh `claude -p`."""
import json
import queue
import subprocess
import threading
import time

from . import config

COMMAND = ["claude", "-p", "--model", "haiku", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
RECYCLE_AFTER = 12      # turns: the process keeps everything said, it is made again from time to time (and the history is sent again to the new one)
_lock = threading.Lock()
_proc = None
_lines = None
_turns = 0


def _kill():
    global _proc, _lines, _turns
    proc, _proc, _lines, _turns = _proc, None, None, 0
    if proc is not None:
        try:
            proc.kill()
            proc.wait(5)
        except Exception:
            pass


def _reader(proc, out):
    try:
        for line in proc.stdout:
            out.put(line)
    finally:
        out.put(None)      # the process is gone


def _start():
    global _proc, _lines, _turns
    _kill()
    try:
        proc = subprocess.Popen(COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, cwd=str(config.APP_DIR), start_new_session=True)
    except OSError:
        return False
    _proc, _lines, _turns = proc, queue.Queue(), 0
    threading.Thread(target=_reader, args=(proc, _lines), daemon=True).start()
    return True


def _turn(text, timeout):
    """One message in, the text of the result out (None on any failure)."""
    try:
        _proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n")
        _proc.stdin.flush()
    except Exception:
        return None
    deadline = time.time() + timeout
    while True:
        try:
            line = _lines.get(timeout=max(0.1, deadline - time.time()))
        except queue.Empty:
            return None
        if line is None:
            return None
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "result":
            return None if event.get("is_error") else (str(event.get("result") or "").strip() or None)


def ask(first, next_, timeout=120):
    """`first`: the whole prompt (with the history), used when the process is new; `next_`: the short one, when it already knows the conversation. The text, or None."""
    global _turns
    with _lock:
        new = _proc is None or _proc.poll() is not None or _turns >= RECYCLE_AFTER
        if new and not _start():
            return None
        out = _turn(first if new else next_, timeout)
        if out is None:
            _kill()
            return None
        _turns += 1
        return out


def prewarm():
    """Starts it in the background (the cold start is paid before the first sentence of the person)."""
    def go():
        with _lock:
            if (_proc is None or _proc.poll() is not None) and _start():
                if _turn("Réponds seulement : ok", 120) is None:
                    _kill()
    threading.Thread(target=go, daemon=True).start()
