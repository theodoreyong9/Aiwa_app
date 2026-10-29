"""The chamber: the super agent meets the one of someone else, in a room they both pressed the button of. One chamber at a time; the rules and the words are in chamber_lib."""
import json
import time
import urllib.parse
import urllib.request

from . import agent, agent_lib, chamber_lib, profile_lib, state


def chamber_active():
    """While a super agent is in a chamber it takes part in no other conversation (another chamber)."""
    with state.chamber_lock:
        return state.chamber["active"]


def _chamber_view(after=0):
    with state.chamber_lock:
        return {"ok": True, "active": state.chamber["active"], "peer": state.chamber["peer"], "name": state.chamber["name"], "lines": [dict(l) for l in state.chamber["lines"] if l["n"] > after][-chamber_lib.KEEP:], "offers": [dict(o) for o in state.chamber_offers if o["state"] == "new"]}


def _match(repo):
    """The score of a visited profile for the person (pro, perso), made by her own super agent from the public page; nothing leaves for the other person. Kept while the page and she do not change."""
    if not chamber_lib.REPO_RE.fullmatch(repo):
        return {"ok": False, "error": "profil ?"}
    if repo == profile_lib.repo():
        return {"ok": False, "error": "c'est ton profil"}
    if state.llm.state != "ready":
        return {"ok": False, "error": "il faut ta clé Anthropic pour noter un profil"}
    try:
        request = urllib.request.Request(f"https://raw.githubusercontent.com/{repo}/HEAD/Profile/index.html", headers={"User-Agent": "aiwa", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=15) as reply:
            theirs = chamber_lib.page_text(reply.read(profile_lib.READ_MAX).decode("utf-8", "replace"))
    except Exception:
        return {"ok": False, "error": "page illisible"}
    mine_repo = profile_lib.repo()
    mine = profile_lib.note()
    if mine_repo:
        try:
            request = urllib.request.Request(f"https://raw.githubusercontent.com/{mine_repo}/HEAD/Profile/index.html", headers={"User-Agent": "aiwa"})
            with urllib.request.urlopen(request, timeout=15) as reply:
                mine = (mine + " " + chamber_lib.page_text(reply.read(profile_lib.READ_MAX).decode("utf-8", "replace"), 1500)).strip()
        except Exception:
            pass
    key = (repo, hash(theirs), hash(mine))
    if key in state.match_cache:
        return {"ok": True, **state.match_cache[key]}
    score = chamber_lib.parse_match(state.llm.ask(chamber_lib.match_system(), [{"role": "user", "content": chamber_lib.match_user(mine, theirs)}], max_tokens=60))
    if score is None:
        return {"ok": False, "error": "pas de note"}
    state.match_cache[key] = score
    return {"ok": True, **score}


def chamber_api(path, body):
    try:
        data = json.loads(body) if body.strip() else {}
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    if path == "/api/chamber":
        return _chamber_view(int(data.get("after") or 0) if str(data.get("after") or "0").isdigit() else 0)
    if path == "/api/chamber/note":
        if "text" in data:
            profile_lib.set_note(data.get("text"))
        return {"ok": True, "text": profile_lib.note()}
    if path == "/api/chamber/offer":
        with state.chamber_lock:
            for o in state.chamber_offers:
                if o["id"] == str(data.get("id")):
                    o["state"] = "opened" if data.get("do") == "open" else "dismissed"
        return _chamber_view()
    if path == "/api/match":
        return _match(str(data.get("repo") or ""))
    peer = str(data.get("peer") or "")
    if path == "/api/chamber/active":
        with state.chamber_lock:
            if data.get("on") is True:
                if not chamber_lib.REPO_RE.fullmatch(peer):
                    return {"ok": False, "error": "chambre : il faut le dépôt du profil de l'autre (owner/nom)"}
                if state.chamber["active"] and state.chamber["peer"] != peer:
                    return {"ok": False, "busy": True, "error": "ce super agent est déjà dans une chambre"}
                if not state.chamber["active"]:
                    state.chamber.update(active=True, peer=peer, name=chamber_lib.name_of(data.get("name"), peer.split("/")[0]), lines=[])
            else:
                state.chamber.update(active=False, peer=None, name=None)
        return _chamber_view()
    with state.chamber_lock:
        if not state.chamber["active"] or state.chamber["peer"] != peer:
            return {"ok": False, "error": "pas de chambre avec cette personne"}
        their = state.chamber["name"]
    danger = data.get("danger") is True
    if path == "/api/chamber/deliver":
        item = chamber_lib.incoming(data.get("kind"), data.get("text"))
        if item is None or item["kind"] == "say":
            return {"ok": False, "error": "rien à remettre"}
        if not danger:
            return {"ok": False, "error": "le danger n'est pas activé des deux côtés"}
        attach = chamber_lib.clean_attach(data.get("attach")) if item["kind"] == "proposal" else None
        with state.chamber_lock:
            chamber_lib.add_line(state.chamber["lines"], "them", their, item["kind"], item["text"], time.time(), attach)
            if attach:
                state.chamber_offers.append({"id": f"o{int(time.time() * 1000)}", "from": their, "text": item["text"], "attach": attach, "ts": int(time.time()), "state": "new"})
                del state.chamber_offers[:-20]
        if item["kind"] == "message":
            agent.converse(spoken=f"[Aiwa · chambre] Le super agent de {their} te dit : « {item['text']} »")
        else:
            stamp = time.time()
            with state.agent_lock:
                state.agent["say"] = {"id": f"s{int(stamp * 1000)}", "text": f"{their} te propose : {item['text']}" + (f" ({attach['title']}, à voir dans la chambre)" if attach else ""), "ts": int(stamp), "spoken": False}
        return {"ok": True}
    if path == "/api/chamber/turn":
        if state.llm.state != "ready":
            return {"ok": False, "error": "il faut ta clé Anthropic (Réglages) pour que ton super agent parle dans la chambre"}
        item = chamber_lib.incoming("say", (data.get("incoming") or {}).get("text") if isinstance(data.get("incoming"), dict) else "")
        with state.chamber_lock:
            if item:
                chamber_lib.add_line(state.chamber["lines"], "them", their, "say", item["text"], time.time())
            lines = [dict(l) for l in state.chamber["lines"]]
        # the SAME super agent as in the rest of Aiwa: its system text and its point on the person's work (what it knows is not cut down), plus the way of answering in a chamber
        point, _sig = agent.point()
        system = agent_lib.system() + chamber_lib.room_note(data.get("me"), their, danger, data.get("peer_note") or "") + "\n\n[Point Aiwa " + time.strftime("%H:%M") + "]\n" + str(point)[:3500]
        answer = state.llm.ask(system, chamber_lib.messages(lines), max_tokens=400)
        parsed = chamber_lib.parse(answer, danger)
        if parsed is None:
            return {"ok": False, "error": "Claude n'a pas répondu (clé, réseau ou quota)"}
        with state.chamber_lock:
            if parsed["say"]:
                chamber_lib.add_line(state.chamber["lines"], "me", data.get("me"), "say", parsed["say"], time.time())
            for kind in ("message", "proposal"):
                if parsed[kind]:
                    chamber_lib.add_line(state.chamber["lines"], "me", data.get("me"), kind, parsed[kind], time.time(), parsed.get("attach") if kind == "proposal" else None)
        return {"ok": True, **parsed}
    return {"ok": False, "error": "?"}