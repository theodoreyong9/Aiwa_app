"""The super agent: it knows everything the brain knows (the point), answers the person by voice, proposes messages for the work sessions and settings for the phone, and sends them when the person confirms.
agent_lib has its words and its reading of the reply; this module holds the state and does the work."""
import json
import subprocess
import threading
import time

from . import agent_lib, asks, config, diagram, files, github, llm_lib, profile_lib, repos, scen_lib, sessions, state

_cache = {}      # ("age", repo, branch) / ("ci", repo) -> (time, value): GitHub is asked at most once in two minutes for the same thing
CACHE_SECONDS = 120


def _cached(key, fetch):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = fetch()
    _cache[key] = (now, value)
    return value


def _commit_age(repo, work):
    when = _cached(("age", repo, work), lambda: github.newest_commit_time(repo, work))
    return max(0, int((time.time() - when) // 60)) if when else None


def _ci_state(repo):
    run = _cached(("ci", repo), lambda: github.latest_run(repo))
    return (run or {}).get("state")


def point(report=False):
    """What the super agent is told before each turn, as (text, signature): the sessions with what GitHub shows of them, the repositories, the productions, the scenarios, the chamber, the questions
    that wait. For a report the workflows of the repositories are read too."""
    with state.lock:
        in_use, current_repo, direct = state.current_cloud, state.current_repo, state.push_main
    entries = sessions.load_all()[:agent_lib.DIGEST_SESSIONS]
    listed = []
    for i, e in enumerate(entries):
        repo, work = e.get("repo"), e.get("work")
        age = _commit_age(repo, work) if repo and work and i < 5 and github.REPO_RE.fullmatch(repo) else None
        listed.append({"id": e["id"], "title": e.get("title"), "repo": repo, "work": work, "commit_age_min": age, "current": e["id"] == in_use,
                       "ci": _ci_state(repo) if report and repo and github.REPO_RE.fullmatch(repo) else None})
    with state.lock:
        waiting = list(asks.pending_list())
    titles = [{"session": (sessions.entry_of(a.get("session")) or {}).get("title") if a.get("session") else None, "question": a["question"]} for a in waiting]
    with state.chamber_lock:
        name = state.chamber["name"] or "quelqu'un"
        chamber = f"en cours avec {name}" if state.chamber["active"] else None
    current = (sessions.entry_of(in_use) or {}).get("title") or in_use if in_use else None
    extra = []
    if report:
        failing = sorted({s["repo"] for s in listed if s.get("ci") == "failure"})
        extra.append("Rapport demandé. Workflows en échec : " + (", ".join(failing) if failing else "aucun") + ".")
    snap = {
        "pills": {"repo": current_repo, "session": current, "direct": direct, "profile": profile_lib.repo()},
        "sessions": listed, "repos": repos.names(), "productions": files.summary(), "scenarios": [scen_lib.public(s) for s in scen_lib.load(config.SCENARIOS_FILE)],
        "chamber": chamber, "asks": titles, "extra": extra,
    }
    return agent_lib.digest(snap)


def _model(system, history, user):
    """One turn through the person's own API key, else through the Claude of the phone (`claude -p`, her own login). The text, or None."""
    if state.llm.state == "ready":
        answer = state.llm.ask(system, history + [{"role": "user", "content": user}])
        if answer:
            return answer
    prompt = system + "\n\n" + "\n".join(("Toi : " if m["role"] == "assistant" else "Personne : ") + m["content"] for m in history[-6:]) + "\n\n" + user
    try:
        done = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "text"], input=prompt, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    out = github.clean(done.stdout or "").strip()
    return out if done.returncode == 0 and out else None


def converse(spoken=None, report=False):
    """One turn with the super agent, answered in the background: the reply (what it says, a proposal, a command) waits for the phone in `state.agent`. {"ok", "error"}."""
    with state.agent_lock:
        if state.agent["busy"]:
            return {"ok": False, "error": "le super agent répond encore"}
        state.agent["busy"] = True
        state.agent["error"] = None
    threading.Thread(target=_turn, args=(spoken, report), daemon=True).start()
    return {"ok": True}


def _turn(spoken, report):
    try:
        text, sig = point(report)
        if spoken and spoken != agent_lib.REPORT_REQUEST and not spoken.startswith("[Aiwa"):
            state.style.observe(spoken)
        user = agent_lib.user_turn(text, spoken=agent_lib.REPORT_REQUEST if report else spoken, stamp=time.strftime("%H:%M"))
        with state.agent_lock:
            history = list(state.agent_chat[-8:])
        answer = _model(agent_lib.system(state.style.note()) + ("\n\n" + diagram.note(live=False) if diagram.is_on() else ""), history, user)
        if answer is None:
            with state.agent_lock:
                state.agent["error"] = "Claude n'a pas répondu (clé, réseau ou quota)"
            return
        with state.agent_lock:
            state.agent_chat.extend([{"role": "user", "content": user}, {"role": "assistant", "content": answer}])
            del state.agent_chat[:-16]
            state.agent["sig"], state.agent["last"] = sig, time.time()
        reply = llm_lib.json_in(answer)
        if reply is not None:
            said(json.dumps(reply))
    except Exception as err:      # a bad turn must never leave the agent busy
        print(f"[{state.ts()}] agent: {err}", flush=True)
        with state.agent_lock:
            state.agent["error"] = str(err)[:200]
    finally:
        with state.agent_lock:
            state.agent["busy"] = False


def said(raw):
    """The agent's reply: what it says aloud, a proposal when it has one (never sent by itself), the settings it asks for."""
    known = {e["id"] for e in sessions.load_all() if e.get("id")}
    parsed = agent_lib.parse_message(raw, known)
    if parsed is None:
        print(f"[{state.ts()}] agent: a reply that is not one", flush=True)
        return False
    stamp = time.time()
    if parsed.get("diagram"):
        diagram.show(parsed["diagram"])
    with state.agent_lock:
        if parsed["say"]:
            state.agent["say"] = {"id": f"s{int(stamp * 1000)}", "text": parsed["say"], "ts": int(stamp), "spoken": False}
        if parsed["proposal"]:
            state.agent["proposal"] = {"id": f"p{int(stamp * 1000)}", "ts": int(stamp), **parsed["proposal"]}
        if parsed.get("command"):
            state.agent["command"] = {"id": f"c{int(stamp * 1000)}", "ts": int(stamp), "items": parsed["command"]}
    print(f"[{state.ts()}] agent: said {len(parsed['say'])} characters" + (", with a proposal" if parsed["proposal"] else ""), flush=True)
    return True


def _title_of(session_id):
    return (sessions.entry_of(session_id) or {}).get("title") or session_id


def _target(entry):
    """Where a proposal's message goes, in words: a session by its title, a repository by its name."""
    if entry.get("session"):
        return f"à la session {_title_of(entry['session'])}"
    return f"à la session du dépôt {entry['repo']}"


def snapshot():
    """What the phone takes: the words to say, the proposal to read back, the command to apply."""
    with state.agent_lock:
        say = state.agent["say"] if state.agent["say"] and not state.agent["say"]["spoken"] else None
        proposal = dict(state.agent["proposal"]) if state.agent["proposal"] else None
        command = dict(state.agent["command"]) if state.agent["command"] else None
        out = {"busy": state.agent["busy"], "error": state.agent["error"], "voice": state.voice.state, "llm": state.llm.state,
               "voice_error": (state.voice.error or "")[:200] if state.voice.state == "error" else None,
               "say": {k: say[k] for k in ("id", "text", "ts")} if say else None}
    if proposal:
        targets = [proposal] + proposal.get("more", [])
        proposal["read_back"] = agent_lib.read_back_all([(_target(t), t["message"]) for t in targets])
    out["proposal"] = proposal
    if command:
        items = command["items"]
        command = {"id": command["id"], "read_back": agent_lib.command_phrase(items, _title_of), "open": items.get("open"), "cast": items.get("cast"), "auto": command.get("auto") is True}
    out["command"] = command
    return out


def apply_command(command_id):
    """The person confirmed the settings (« vas-y »): the repository and the session are changed here, the phone does the rest (the screen to open, the cast). {"ok", "open", "cast"}."""
    with state.agent_lock:
        command = dict(state.agent["command"]) if state.agent["command"] else None
    if command is None or command["id"] != command_id:
        return {"ok": False, "error": "ces réglages ne sont plus d'actualité"}
    items = command["items"]
    if items.get("repo"):
        sessions.focus(items["repo"])
    session = items.get("session")
    if session:
        with state.lock:
            if session.lower() in ("nouvelle", "new"):
                state.current_cloud = None
            else:
                state.current_cloud = state.last_cloud = session
                repo = (sessions.entry_of(session) or {}).get("repo")
                if repo and not items.get("repo"):
                    state.current_repo = repo
            state.save()
    with state.agent_lock:
        if state.agent["command"] and state.agent["command"]["id"] == command_id:
            state.agent["command"] = None
    return {"ok": True, "open": items.get("open"), "cast": items.get("cast")}


def _deliver(targets):
    """Sends each message the way the person's own would go (her joined files and the instructions with it). The ids of the sessions reached."""
    reached = []
    for entry in targets:
        result = sessions.cloud_send(entry["message"], session=entry.get("session"), repo=entry.get("repo"))
        if not result["ok"]:
            return reached, result.get("error")
        reached.append(result["session_id"])
    return reached, None


def confirm(proposal_id):
    """The person confirmed (« c'est bon vas-y »): the messages go to their sessions, as the person's own."""
    with state.agent_lock:
        proposal = dict(state.agent["proposal"]) if state.agent["proposal"] else None
    if proposal is None or proposal["id"] != proposal_id:
        return {"ok": False, "error": "cette proposition n'est plus d'actualité"}
    sent, error = _deliver([proposal] + proposal.get("more", []))
    if error:
        return {"ok": False, "error": error, "sent": sent}
    with state.agent_lock:
        if state.agent["proposal"] and state.agent["proposal"]["id"] == proposal_id:
            state.agent["proposal"] = None
        recent = [(sid, at) for sid, at in state.agent["last_sent"] if sid not in sent and time.time() - at < config.AGENT_FORGET_WINDOW]
        state.agent["last_sent"] = recent + [(sid, time.time()) for sid in sent]      # « stop » asks these to forget the last comment
        state.agent["decisions"] = (state.agent["decisions"] + [f"proposition pour {', '.join(_title_of(sid) for sid in sent)} : CONFIRMÉE et envoyée — « {proposal['message'][:140]} »"])[-12:]
    return {"ok": True, "sent": sent}


def act(send, do):
    """What a master (a scenario's double, the live mode) asks for goes at once, with no read-back: the person launched it, which was her agreement. The messages are sent, the repository and the session
    are changed, and what is left for the phone (a screen to open, a cast) is marked to be applied without a question. True when the phone has something to apply."""
    if not (send or do):
        return False
    known = {e["id"] for e in sessions.load_all() if e.get("id")}
    parsed = agent_lib.parse_message({"send": send or [], "do": do or {}}, known)
    if parsed is None:
        return False
    if parsed["proposal"]:
        targets = [parsed["proposal"]] + parsed["proposal"].get("more", [])
        threading.Thread(target=_deliver, args=(targets,), daemon=True).start()
    command = parsed.get("command")
    if not command:
        return False
    stamp = time.time()
    with state.agent_lock:
        state.agent["command"] = {"id": f"c{int(stamp * 1000)}", "ts": int(stamp), "items": command}
    apply_command(f"c{int(stamp * 1000)}")
    if command.get("open") or command.get("cast"):
        with state.agent_lock:
            state.agent["command"] = {"id": f"c{int(stamp * 1000)}", "ts": int(stamp), "items": {k: command[k] for k in ("open", "cast") if k in command}, "auto": True}
        return True
    return False


def stop():
    """« stop »: the proposal and the settings that wait are dropped, and the sessions the super agent last spoke to are asked to forget its last comment. Returns how many were told."""
    with state.agent_lock:
        state.agent["proposal"] = None
        state.agent["command"] = None
        targets = [sid for sid, at in state.agent["last_sent"] if time.time() - at < config.AGENT_FORGET_WINDOW]
        state.agent["last_sent"] = []

    def run():
        for sid in targets:
            try:
                sessions.queue_followup(sid, "[Aiwa — stop] Oublie le dernier message du super agent : ne le traite pas, annule ce que tu en as commencé et ne fais rien à son sujet.")
            except (OSError, subprocess.SubprocessError):
                pass
    if targets:
        threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "told": len(targets)}


def cancel(proposal_id):
    """Drops the proposal, or the settings, that has this id (the phone also calls it once it has applied the settings: they are not applied twice)."""
    with state.agent_lock:
        if state.agent["proposal"] and state.agent["proposal"]["id"] == proposal_id:
            state.agent["decisions"] = (state.agent["decisions"] + [f"proposition « {state.agent['proposal']['message'][:140]} » : ANNULÉE"])[-12:]
            state.agent["proposal"] = None
        if state.agent["command"] and state.agent["command"]["id"] == proposal_id:
            state.agent["command"] = None
    return {"ok": True}


def spoken(say_id):
    with state.agent_lock:
        if state.agent["say"] and state.agent["say"]["id"] == say_id:
            state.agent["say"]["spoken"] = True
    return {"ok": True}
