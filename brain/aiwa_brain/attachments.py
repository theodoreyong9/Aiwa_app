"""What the person joins to the next message (the « Ajouter » button): a small text goes inside the message, anything else goes to the repository or to the relay."""
import base64
import json
import re
import secrets
import urllib.request

from . import config, github, state


def attach_add(body):
    """body = JSON {name, data (base64)}. Returns {"ok", "count"} or {"ok": False, "error"}."""
    try:
        req = json.loads(body)
        name = re.sub(r"[^\w.\- ]", "_", str(req.get("name") or "fichier"))[:80].strip() or "fichier"
        raw = base64.b64decode(req.get("data") or "", validate=False)
    except (ValueError, TypeError):
        return {"ok": False, "error": "fichier illisible"}
    if not raw:
        return {"ok": False, "error": "fichier vide"}
    if len(raw) > config.ATTACH_MAX:
        return {"ok": False, "error": f"fichier trop gros ({len(raw) // 1048576} Mo, maximum {config.ATTACH_MAX // 1048576} Mo)"}
    entry = {"name": name, "size": len(raw)}
    text = None
    if len(raw) <= config.ATTACH_INLINE and b"\0" not in raw:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
    if text is not None:
        entry["text"] = text
    else:
        # GitHub first: the file goes into the repository (aiwa-inputs/), which the session always reaches, whereas the relay may be closed to its network
        with state.lock:
            repo_now = state.current_repo
        if repo_now:
            try:
                entry["path"] = github.put_file(repo_now, f"{config.INPUTS_DIR}/{name}", raw, f"Aiwa : pièce jointe {name}")
                entry["repo"] = repo_now
            except github.GithubError as err:
                print(f"[{state.ts()}] attach: dépôt de {name} dans {repo_now} impossible ({err}); le relais prendra le relais", flush=True)
        topic = "aiwa-att-" + secrets.token_hex(10)
        if not entry.get("path"):
            put = urllib.request.Request(f"{config.NTFY_SERVER}/{topic}", data=raw, method="PUT", headers={"Filename": name})
            try:
                with urllib.request.urlopen(put, timeout=120) as answer:
                    info = json.loads(answer.read().decode("utf-8", "replace"))
                entry["url"] = (info.get("attachment") or {}).get("url") or ""
            except (OSError, ValueError) as err:
                return {"ok": False, "error": f"envoi du fichier impossible ({err})"}
            if not entry["url"]:
                return {"ok": False, "error": "le relais n'a pas gardé le fichier"}
    with state.attach_lock:
        state.attachments.append(entry)
        return {"ok": True, "count": len(state.attachments)}


def attach_list():
    """The files joined and not sent yet, in order: what the widget shows one by one."""
    with state.attach_lock:
        return [{"name": a["name"], "size": a["size"]} for a in state.attachments]


def attach_remove(body):
    """body = JSON {index}: takes back ONE of the files joined and not sent yet."""
    try:
        index = int(json.loads(body).get("index"))
    except (ValueError, TypeError, AttributeError):
        return {"ok": False, "error": "numéro de fichier illisible"}
    with state.attach_lock:
        if not 0 <= index < len(state.attachments):
            return {"ok": False, "error": "ce fichier n'est plus en attente"}
        del state.attachments[index]
        return {"ok": True, "count": len(state.attachments)}


def attach_clear():
    with state.attach_lock:
        state.attachments.clear()
    return {"ok": True, "count": 0}


def block(items):
    if not items:
        return ""
    out = "\n\n[Aiwa] Pièces jointes de ma part :"
    for it in items:
        if "text" in it:
            out += f"\n--- {it['name']} ---\n{it['text']}\n--- fin de {it['name']} ---"
        elif it.get("path"):
            out += f"\n- {it['name']} ({it['size']} octets) : déposé dans le dépôt `{it['repo']}` sous `{it['path']}` (branche par défaut) : lis-le là, par exemple avec `git pull` ou `curl -sL https://raw.githubusercontent.com/{it['repo']}/HEAD/{it['path']}` ; un PDF se lit avec `pdftotext`."
        else:
            out += f"\n- {it['name']} ({it['size']} octets) : récupère-le avec `curl -sL -o '{it['name']}' '{it['url']}'` (disponible quelques heures)."
    return out