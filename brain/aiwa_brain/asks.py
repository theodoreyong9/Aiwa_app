"""The questions Claude asks through the widget (a session writes a question and its choices to the relay) and the answers they take."""
import hashlib
import json
import time

from . import config, sessions, state


def ask_set(raw, event_id=None):
    """A question from Claude: JSON {"question": "...", "options": ["...", ...]}. Kept (one at a time; a newer one replaces the older), and
    shown by the widget until it is answered. The same event twice is one question. True if it was kept."""
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("question"), str) or not data["question"].strip():
        print(f"[{state.ts()}] ask not kept: not a question", flush=True)
        return False
    options = [o.strip()[:config.ASK_OPTION_MAX] for o in data.get("options", []) if isinstance(o, str) and o.strip()][:config.ASK_OPTIONS] if isinstance(data.get("options"), list) else []
    identifier = str(event_id or data.get("id") or hashlib.sha1((data["question"] + str(time.time())).encode()).hexdigest()[:12])
    text = data["question"].strip()[:config.ASK_QUESTION_MAX]
    with state.lock:
        if any(a["id"] == identifier for a in state.ask_list):
            return False
        # The same question that came by the other road (the relay AND GitHub are both used), in the same session: one question, not two
        if any(a["question"] == text and a.get("session") == state.current_cloud and time.time() - a["ts"] < 1200 for a in state.ask_list):
            return False
        # The question belongs to the session being used when it came (the relay and the branch watched are the current session's); questions of several sessions wait together
        state.ask_list = (state.ask_list + [{"id": identifier, "question": text, "options": options, "ts": int(time.time()), "answered": False, "session": state.current_cloud}])[-config.ASK_PENDING_MAX:]
        state.save()
    print(f"[{state.ts()}] question from Claude kept ({len(options)} choices)", flush=True)
    return True


def pending_list():
    """The questions nobody answered yet, oldest first. Call with `lock` held."""
    return [a for a in state.ask_list if not a["answered"]]


def to_show():
    """The question the widget shows: the one of the session in use when there is one, else the oldest of the others. Call with `lock` held."""
    waiting = pending_list()
    return next((a for a in waiting if a.get("session") == state.current_cloud), waiting[0] if waiting else None)


def snapshot():
    with state.lock:
        shown = to_show()
        count = len(pending_list())
        session = shown.get("session") if shown else None
        snapshot = {k: shown[k] for k in ("id", "question", "options", "ts")} if shown is not None else None
    if snapshot is None:
        return None
    entry = sessions.entry_of(session) if session else {}
    snapshot.update(session=(entry or {}).get("title") or session, count=count)
    return snapshot


def answer(body):
    """The answer typed or chosen in the widget: sent to the session the question came from (not necessarily the one in use), with the question it answers."""
    try:
        data = json.loads(body)
    except ValueError:
        return {"ok": False, "error": "réponse illisible"}
    text = str(data.get("answer", "")).strip()[:2000] if isinstance(data, dict) else ""
    with state.lock:
        found = next((dict(a) for a in pending_list() if a["id"] == str(data.get("id") if isinstance(data, dict) else "")), None)
        in_use = state.current_cloud
    if found is None:
        return {"ok": False, "error": "cette question n'est plus d'actualité"}
    if not text:
        return {"ok": False, "error": "réponse vide"}
    message = f"Ma réponse à ta demande « {found['question']} » : {text}"
    if found.get("session") in (None, in_use):
        result = sessions.cloud_send(message)
    else:
        sent = sessions.queue_followup(found["session"], message)
        result = {"ok": bool(sent.get("ok")), "error": sent.get("error")}
    if result.get("ok"):
        with state.lock:
            for a in state.ask_list:
                if a["id"] == found["id"]:
                    a["answered"] = True
            state.save()
    return result