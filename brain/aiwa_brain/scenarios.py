"""The scenarios: a prompt the person would repeat by hand, kept under a launch word of her own. Each one is a double of her (a session of its own) that she talks to; the report is a scenario too."""
import json
import re
import threading
import time

from . import agent, config, github, live, relay, scen_lib, sessions, state


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
    with state.scenario_lock:
        watch = state.scenario_watch.get(sc["id"]) or {}
    return {**scen_lib.public(sc), "session": mine.get("current"), "creating": run["creating"], "error": run["error"], "repo": mine.get("repo"), "watching": bool(watch.get("on")), "turns": int(watch.get("turns") or 0),
            "sessions": [{"id": x["id"], "title": str(titles.get(x["id"]) or sc["name"])[:60], "current": x["id"] == mine.get("current")} for x in mine.get("list", []) if isinstance(x, dict) and x.get("id")]}


def _dedicated_repo(sc):
    """The repository that is the home of the scenario's double (private, made once with the person's GitHub account: `aiwa-<scenario>`), or None when it cannot be made."""
    mine = _scen_sessions().get(sc["id"]) or {}
    if mine.get("repo"):
        return mine["repo"]
    owner = github.connected_user()
    if not owner:
        return None
    name = "aiwa-" + re.sub(r"[^a-z0-9-]+", "-", str(sc["id"]).lower()).strip("-")[:60]
    repo = f"{owner}/{name}"
    try:
        github.api("/user/repos", method="POST", body={"name": name, "private": True, "auto_init": True, "description": f"Le dépôt du double du scénario Aiwa « {sc['name']} » : ses notes."}, timeout=30)
    except github.GithubError as err:
        # already there: it is the one to use; anything else: the double lives on the repository in use
        try:
            github.api(f"/repos/{repo}")
        except github.GithubError:
            print(f"[{state.ts()}] scenario {sc['id']}: no dedicated repository ({str(err)[:120]})", flush=True)
            return None
    data = _scen_sessions()
    data.setdefault(sc["id"], {"current": None, "list": []})["repo"] = repo
    _scen_sessions_save(data)
    return repo


def scenario_create(sc, fresh=False):
    """The session of the scenario (a super agent of its own, in a repository of its own), made in the background. With `fresh`, a new one even if there is one. {"ok", "error"}."""
    with state.scenario_lock:
        run = _scen_run(sc["id"])
        if run["creating"]:
            return {"ok": True, "creating": True}
        if _scen_sessions().get(sc["id"], {}).get("current") and not fresh:
            return {"ok": True, "creating": False}
        run.update(creating=True, error=None)

    def work():
        dedicated = _dedicated_repo(sc)
        with state.lock:
            previous = (state.current_cloud, state.last_cloud, state.current_repo)
            state.current_cloud = None            # a new session is made, and the one in use stays the one in use
            if dedicated:
                state.current_repo = dedicated
        try:
            result = sessions.cloud_send(scen_lib.charter(sc, relay.relay_url(), dedicated))
            if not result.get("ok") and dedicated:
                # the cloud cannot reach the new repository (Claude's access to it): the double lives on the repository in use, as before
                with state.lock:
                    state.current_cloud, state.current_repo = None, previous[2]
                result = sessions.cloud_send(scen_lib.charter(sc, relay.relay_url()))
        except Exception as err:
            result = {"ok": False, "error": str(err)}
        finally:
            with state.lock:
                state.current_cloud, state.last_cloud, state.current_repo = previous
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


# ---------- the watch: a double that criticises what a session did, again and again, until the person says stop ----------

WATCH_EVERY = 45            # seconds between two looks at the watched branches
WATCH_BUSY_MAX = 20 * 60    # a double that does not answer in twenty minutes is asked again at the next change
WATCH_IDLE_STOP = 3 * 3600  # nothing from the watched sessions for three hours: the loop ends and says so


def _resolve_targets(send):
    """[{session, repo, work, title}] of the sessions a double sent to (by session, or by repository: the session linked to it)."""
    entries = sessions.load_all()
    out = []
    for item in (send if isinstance(send, list) else [send]):
        if not isinstance(item, dict):
            continue
        sid, repo = str(item.get("session") or ""), str(item.get("repo") or "")
        entry = next((e for e in entries if sid and e.get("id") == sid), None) or next((e for e in entries if repo and e.get("repo") == repo and e.get("work")), None)
        if entry and entry.get("id") and entry.get("repo") and entry.get("work") and github.REPO_RE.fullmatch(str(entry["repo"])):
            out.append({"session": entry["id"], "repo": entry["repo"], "work": entry["work"], "title": str(entry.get("title") or entry["id"])[:40]})
    return out


def watch_start(scenario_id, send):
    """The double asked to watch (`watch: true`): the sessions it sent to are looked at from now on, and it is woken at each turn they finish."""
    targets = _resolve_targets(send)
    baseline = {}
    for t in targets:
        try:
            baseline[t["session"]] = live.look_branch(t["repo"], t["work"])
        except github.GithubError:
            baseline[t["session"]] = None
    with state.scenario_lock:
        w = state.scenario_watch.setdefault(scenario_id, {"on": True, "busy": False, "turns": 0, "targets": {}})
        w["on"], w["busy"] = True, False
        for t in targets:
            w["targets"][t["session"]] = {**t, "snap": baseline.get(t["session"]), "pending": False, "changed": time.time()}


def _say_to_phone(scenario_id, text):
    with state.scenario_lock:
        items = _scen_run(scenario_id)["said"]
        items.append({"id": f"{int(time.time() * 1000)}", "say": text, "note": "", "ts": int(time.time()), "do": False})
        del items[:-20]


def watch_stop(scenario_id, why=None):
    with state.scenario_lock:
        w = state.scenario_watch.get(scenario_id)
        if not w:
            return
        w["on"] = False
    if why:
        _say_to_phone(scenario_id, why)


def watch_stop_all():
    """« stop »: every double stops watching and is told to launch nothing more."""
    with state.scenario_lock:
        stopped = [sid for sid, w in state.scenario_watch.items() if w.get("on")]
        for sid in stopped:
            state.scenario_watch[sid]["on"] = False
    for sid in stopped:
        double = _scen_sessions().get(sid, {}).get("current")
        if double:
            threading.Thread(target=_scenario_send, args=(double, "[Aiwa — stop scénario] La personne a dit stop : tu ne lances plus rien et tu ne veilles plus."), daemon=True).start()


def _wake_message(fired, turn):
    parts = []
    for t, now in fired:
        ci = {"success": "réussi", "failure": "ÉCHOUÉ", "running": "en cours", None: "aucun"}.get(now.get("ci"), "?")
        parts.append(f"La session « {t['title']} » [{t['session']}] vient de finir un tour. Dernier commit : « {str(now.get('message') or '')[:120]} ». Workflow : {ci}. "
                     f"Regarde le résultat : dépôt {t['repo']}, branche {t['work']} (fais un `git fetch` de cette branche et lis ce qui a changé).")
    return ("[Aiwa — veille, tour " + str(turn) + "] " + " ".join(parts) + " Critique ce résultat et envoie ta critique à cette session avec `send` (session : l'identifiant ci-dessus), "
            "en gardant `\"watch\":true` dans ta commande pour continuer de veiller. Si le résultat te satisfait, dis-le et mets `\"watch\":false`.")


def _wake(scenario_id, double, text):
    ok = False
    try:
        result = sessions.queue_followup(double, text)
        ok = result.get("ok") is True
    except Exception as err:
        print(f"[{state.ts()}] scenario watch: {err}", flush=True)
    with state.scenario_lock:
        w = state.scenario_watch.get(scenario_id)
        if not w:
            return
        if ok:
            w["fails"] = 0
        else:
            w["busy"] = False
            w["fails"] = int(w.get("fails") or 0) + 1
            stop = w["fails"] >= 3
    if not ok and stop:
        watch_stop(scenario_id, "La veille s'arrête : je n'arrive pas à joindre le double du scénario.")


def watch_once():
    with state.scenario_lock:
        ids = [sid for sid, w in state.scenario_watch.items() if w.get("on")]
    for sid in ids:
        with state.scenario_lock:
            w = state.scenario_watch.get(sid)
            if not w or not w.get("on"):
                continue
            if w.get("busy") and time.time() - float(w.get("busy_since") or 0) > WATCH_BUSY_MAX:
                w["busy"] = False
            targets = list(w["targets"].values())
        double = _scen_sessions().get(sid, {}).get("current")
        if not double or not targets:
            continue
        fired = []
        for t in targets:
            try:
                now = live.look_branch(t["repo"], t["work"])
            except github.GithubError:
                continue
            prev = t["snap"]
            t["snap"] = now
            if prev is None:
                t["changed"] = time.time()
                continue
            if (now["sha"] and now["sha"] != prev.get("sha")) or now["ci"] != prev.get("ci"):
                t["changed"], t["pending"] = time.time(), True
            if t["pending"] and now["ci"] != "running":
                t["pending"] = False
                fired.append((t, now))
        with state.scenario_lock:
            w = state.scenario_watch.get(sid)
            if not w or not w.get("on"):
                continue
            if fired and not w.get("busy"):
                w["busy"], w["busy_since"] = True, time.time()
                w["turns"] = int(w.get("turns") or 0) + 1
                turn = w["turns"]
                message = _wake_message(fired, turn)
            else:
                turn = None
            idle = time.time() - max(t["changed"] for t in targets) > WATCH_IDLE_STOP and not w.get("busy")
        if turn:
            threading.Thread(target=_wake, args=(sid, double, message), daemon=True).start()
        elif idle:
            watch_stop(sid, "La veille s'arrête : plus rien de la session depuis trois heures.")


def watch_loop():
    time.sleep(90)
    while True:
        try:
            watch_once()
        except Exception as err:
            print(f"[{state.ts()}] scenario watch: {err}", flush=True)
        time.sleep(WATCH_EVERY)


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
    sid_ = data["scenario"]
    if data.get("watch") is True and data.get("send"):
        watch_start(sid_, data.get("send"))
    elif data.get("watch") is False:
        watch_stop(sid_)
    with state.scenario_lock:
        w_ = state.scenario_watch.get(sid_)
        if w_:
            w_["busy"] = False           # the double answered: it can be woken again at the next turn
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