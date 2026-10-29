"""The scenarios: a prompt the person would repeat by hand, kept under a launch word of her own. Each one is a double of her (a session of its own) that she talks to; the report is a scenario too."""
import json
import threading
import time

from . import agent, config, relay, scen_lib, sessions, state


def _scen_sessions():
    try:
        raw = json.loads(config.SCEN_SESSIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    return raw if isinstance(raw, dict) else {}


def _scen_sessions_save(data):
    try:
        config.SCEN_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.SCEN_SESSIONS_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _scen_run(sid):
    return state.scenario_run.setdefault(sid, {"creating": False, "error": None, "said": []})


def _scenario_view(sc):
    mine = _scen_sessions().get(sc["id"]) or {}
    with state.scenario_lock:
        run = dict(_scen_run(sc["id"]))
    titles = {e.get("id"): e.get("title") for e in sessions.load_all() if e.get("id")}
    return {**scen_lib.public(sc), "session": mine.get("current"), "creating": run["creating"], "error": run["error"],
            "sessions": [{"id": x["id"], "title": str(titles.get(x["id"]) or sc["name"])[:60], "current": x["id"] == mine.get("current")} for x in mine.get("list", []) if isinstance(x, dict) and x.get("id")]}


def scenario_create(sc, fresh=False):
    """The session of the scenario (a super agent of its own, on the repository in use), made in the background. With `fresh`, a new one even if there is one. {"ok", "error"}."""
    with state.scenario_lock:
        run = _scen_run(sc["id"])
        if run["creating"]:
            return {"ok": True, "creating": True}
        if _scen_sessions().get(sc["id"], {}).get("current") and not fresh:
            return {"ok": True, "creating": False}
        run.update(creating=True, error=None)

    def work():
        with state.lock:
            previous = (state.current_cloud, state.last_cloud)
            state.current_cloud = None            # a new session is made, and the one in use stays the one in use
        try:
            result = sessions.cloud_send(scen_lib.charter(sc, relay.relay_url()))
        except Exception as err:
            result = {"ok": False, "error": str(err)}
        finally:
            with state.lock:
                state.current_cloud, state.last_cloud = previous
                state.save()
        with state.scenario_lock:
            run = _scen_run(sc["id"])
            run["creating"] = False
            if result.get("ok"):
                data = _scen_sessions()
                entry = data.setdefault(sc["id"], {"current": None, "list": []})
                entry["current"] = result["session_id"]
                entry["list"] = [{"id": result["session_id"], "ts": int(time.time())}] + [x for x in entry.get("list", []) if x.get("id") != result["session_id"]][:9]
                _scen_sessions_save(data)
            else:
                run["error"] = str(result.get("error"))[:300]
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "creating": True}


def said(raw):
    """What the session of a scenario says through the relay (title aiwa-scenario): {"scenario", "say", "note"}, kept until the phone comes to take it."""
    try:
        data = json.loads(str(raw or ""))
    except ValueError:
        return False
    if not isinstance(data, dict) or not any(s["id"] == data.get("scenario") for s in scen_lib.load(config.SCENARIOS_FILE)):
        return False
    say, note = " ".join(str(data.get("say") or "").split())[:scen_lib.SAY_MAX], " ".join(str(data.get("note") or "").split())[:scen_lib.NOTE_MAX]
    # what it proposes for the other sessions (`send`, `do`) goes the way the super agent's proposals go: read back by the phone, confirmed by the person, never sent by itself
    # A scenario is its own master: launching it was the person's agreement, so what it sends to the sessions goes at once, and what it asks the phone to do (open, cast) is applied at once.
    did = agent.act(data.get("send"), data.get("do"))
    if not say and not note:
        return bool(data.get("send") or data.get("do"))
    with state.scenario_lock:
        items = _scen_run(data["scenario"])["said"]
        items.append({"id": f"{int(time.time() * 1000)}", "say": say, "note": note, "ts": int(time.time()), "do": did})
        del items[:-20]
    return True


def _scenario_send(session, text):
    result = sessions.queue_followup(session, text)
    if not result["ok"]:
        print(f"[{state.ts()}] scenario: message not sent: {str(result.get('error'))[:200]}", flush=True)


def scenario_api(path, body):
    try:
        data = json.loads(body) if body.strip() else {}
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    sid = str(data.get("id") or "")
    scenarios = scen_lib.load(config.SCENARIOS_FILE)

    def listing():
        return {"ok": True, "scenarios": [_scenario_view(s) for s in scenarios]}
    with state.scenario_lock:
        if path == "/api/scenarios/save":
            scenarios, _sc, error = scen_lib.upsert(scenarios, data)
            if error:
                return {"ok": False, "error": error}
            scen_lib.save(config.SCENARIOS_FILE, scenarios)
        elif path == "/api/scenarios/delete":
            scenarios = [s for s in scenarios if s["id"] != sid]
            scen_lib.save(config.SCENARIOS_FILE, scenarios)
            state.scenario_run.pop(sid, None)
    if path in ("/api/scenarios", "/api/scenarios/save", "/api/scenarios/delete"):
        return listing()
    sc = next((s for s in scenarios if s["id"] == sid), None) if sid else scen_lib.match(str(data.get("text") or ""), scenarios)
    if sc is None:
        return {"ok": False, "error": "aucun scénario avec ce mot" if not sid else "scénario inconnu"}
    if path == "/api/scenarios/create":
        return {**scenario_create(sc, fresh=data.get("fresh") is True), "scenarios": [_scenario_view(s) for s in scen_lib.load(config.SCENARIOS_FILE)]}
    if path == "/api/scenarios/use":
        with state.scenario_lock:
            all_mine = _scen_sessions()
            entry = all_mine.get(sc["id"]) or {}
            target = data.get("session")
            known = any(x.get("id") == target for x in entry.get("list", []))
            if not known:
                # a session the person already has (any of her sessions): the scenario is sent to it, and it becomes the scenario's session
                if not config.CLOUD_ID_RE.fullmatch(str(target or "")) or not any(e.get("id") == target for e in sessions.load_all()):
                    return {"ok": False, "error": "session inconnue"}
                entry["list"] = [{"id": target, "ts": int(time.time())}] + entry.get("list", [])[:9]
            entry["current"] = target
            all_mine[sc["id"]] = entry
            _scen_sessions_save(all_mine)
        if not known:
            threading.Thread(target=_scenario_send, args=(target, scen_lib.charter(sc, relay.relay_url())), daemon=True).start()
        return listing()
    if path == "/api/scenarios/launch":
        # the report asks the super agent; any other scenario has its session made now if it has none, then the phone talks to it
        if sc["kind"] == "report":
            sent = agent.converse(report=True)
            return {"ok": sent.get("ok") is True, "error": sent.get("error"), "scenario": scen_lib.public(sc), "created": False}
        had = bool(_scen_sessions().get(sc["id"], {}).get("current"))
        made = scenario_create(sc)
        return {"ok": True, "created": not had, "creating": made.get("creating", False), "scenario": scen_lib.public(sc)}
    if path == "/api/scenarios/say":
        session = _scen_sessions().get(sc["id"], {}).get("current")
        with state.scenario_lock:
            creating = _scen_run(sc["id"])["creating"]
        if creating or not session:
            return {"ok": False, "pending": True, "error": "la session du scénario se crée : un instant"}
        listed = "\n".join(f"- {str(e.get('title') or e['id'])[:50]} [{e['id']}]" for e in sessions.load_all() if e.get("id") and e.get("id") != session)[:6 * 90]
        threading.Thread(target=_scenario_send, args=(session, scen_lib.user_turn(sc, str(data.get("text") or ""), listed)), daemon=True).start()
        return {"ok": True}
    if path == "/api/scenarios/said":
        with state.scenario_lock:
            run = _scen_run(sc["id"])
            items, run["said"] = list(run["said"]), []
            return {"ok": True, "says": items, "creating": run["creating"], "error": run["error"]}
    return {"ok": False, "error": "?"}