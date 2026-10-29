"""The Claude Code sessions: which session belongs to which repository, creating one, sending it a message."""
import json
import re
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import attachments, claude_cli, config, github, instructions, relay, repos, state


def load_all():
    try:
        data = json.loads(config.CLOUD_STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def save_cloud_session(session_id, title, url, repo=None, work=None, base=None, direct=None, instr=None, model=None, effort=None, imported=None):
    """The CLI has no non-interactive way to LIST cloud sessions, so the
    ones Aiwa created or was given a link to are remembered here, with the
    repository (and branch) a session was started on and a fingerprint of
    the instructions it was last given."""
    with state.store_lock:
        entries = load_all()
        existing = next((e for e in entries if e.get("id") == session_id), None) or {}
        entries = [e for e in entries if e.get("id") != session_id]
        # Everything already known is kept, whatever this call is about;
        # only what is given changes. work: the session's own branch; base:
        # the repository's default branch; direct: integrate into base.
        entry = dict(existing)
        entry.update({
            "id": session_id,
            "title": existing.get("title") or title,
            "url": url or existing.get("url") or f"https://claude.ai/code/{session_id}",
        })
        # model / effort: "" = automatic, absent = unknown.
        for key, value in (("repo", repo), ("work", work), ("base", base), ("direct", direct), ("instr", instr), ("model", model), ("effort", effort), ("imported", imported)):
            if value is not None:
                entry[key] = value
        entries.insert(0, entry)
        config.CLOUD_STORE.write_text(json.dumps(entries[:30]), encoding="utf-8")


def update_session(session_id, **fields):
    """Changes fields of a remembered session in place (its rank is kept)."""
    with state.store_lock:
        entries = load_all()
        for entry in entries:
            if entry.get("id") == session_id:
                entry.update(fields)
                config.CLOUD_STORE.write_text(json.dumps(entries), encoding="utf-8")
                return


def entry_of(session_id):
    return next((e for e in load_all() if e.get("id") == session_id), {})


def session_for_repo(repo):
    """The session linked to a repository: the most recent one that works on it (the list is kept newest first), or None when there is none yet."""
    return next((e["id"] for e in load_all() if e.get("id") and e.get("repo") == repo), None)


def focus(repo):
    """The person talks about this repository: it becomes the one in use, with the session linked to it (none yet: the next message makes one)."""
    linked = session_for_repo(repo)
    with state.lock:
        state.current_repo = repo
        state.current_cloud = linked
        if linked:
            state.last_cloud = linked
        state.save()
    repos.remember(repo)
    return linked


def _session_targets(session_id, entry):
    """(work, base) of a repository session: its own branch, and the default branch it integrates into. Filled in once when missing (an imported session)."""
    work, base = entry.get("work"), entry.get("base")
    if not work or not base:
        base = base or "main"
        work = work or "aiwa/" + time.strftime("%Y%m%d-%H%M%S")
        update_session(session_id, work=work, base=base)
    return work, base


def _branch_candidates():
    """Repositories to look a branch up in: the current one, the ones of
    remembered sessions, then the discovered list (see choices)."""
    with state.lock:
        current = state.current_repo
    names = [current] + [e.get("repo") for e in load_all()] + [c["name"] for c in repos.choices()]
    seen, out = set(), []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out[:10]


def cloud_add(text):
    """Adds an EXISTING cloud session and selects it, from the name of its
    branch (claude/…): the repository is looked up among the ones Aiwa knows
    (a session's commits carry its link), and the branch is the one Claude
    pushes to. A link alone is refused: it names neither the repository nor
    the branch, so nothing could be read back from GitHub. If the text also holds the
    link or id of the session, that is the one used. Returns (session id,
    None), or (None, why not)."""
    branch_match = re.search(r"claude/[A-Za-z0-9._/-]+", text)
    link_only = config.CLOUD_ID_RE.search(text)
    if branch_match is None and link_only is not None and state.current_repo:
        # A session whose link is all there is (one just made in Claude, with no branch yet): it is added on the repository in use,
        # and given its own work branch (aiwa/…) like the sessions Aiwa makes; the alert by GitHub follows once it has pushed there.
        session_id = link_only.group(0)
        url_match = config.CLOUD_URL_RE.search(text)
        save_cloud_session(
            session_id, "Session " + session_id[-6:], url_match.group(0) if url_match else None,
            repo=state.current_repo, base=github.default_branch(state.current_repo), direct=False, imported=True,
        )
        with state.lock:
            state.current_cloud = state.last_cloud = session_id
            state.save()
        print(f"[{state.ts()}] import by link {session_id} on {state.current_repo}", flush=True)
        return session_id, None
    if branch_match is None:
        return None, (
            "Une session s'ajoute par son lien (claude.ai/code/session_…) quand on a dit de quel dépôt on parle, ou par le nom de sa branche (claude/…)."
        )
    branch = branch_match.group(0).rstrip("/.")
    found, tried = github.find_branch_session(_branch_candidates(), branch)
    print(f"[{state.ts()}] import by branch {branch}: tried {tried}", flush=True)
    if not found:
        wording = {"missing": "branche absente", "unreachable": "privé ou inaccessible", "trop lent": "trop lent"}
        detail = ", ".join(f"{name} ({wording.get(why, why)})" for name, why in tried) or "aucun dépôt candidat"
        return None, (
            f"Branche {branch} introuvable. Dépôts essayés : {detail}. "
            "Un dépôt privé ne peut pas être lu par Aiwa : le dépôt de la session doit être public, "
            "ou déjà utilisé une fois (il est alors essayé en premier)."
        )
    given = config.CLOUD_ID_RE.search(text)
    session_id = given.group(0) if given else next((found_id for _, found_id in found if found_id), None)
    if session_id is None:
        where = ", ".join(name for name, _ in found)
        return None, (
            f"Aiwa cherche la branche dans tes dépôts : elle existe dans {where}, mais aucun de ses derniers commits ne porte le lien de la session. "
            "Copie aussi le lien de la session (claude.ai/code/session_…) avec le nom de la branche."
        )
    # The repository is only known when the branch is in ONE of them. A session can work on several repositories with the same branch
    # name, and taking the first that answers is a guess about where Claude is going to push: none is taken then, and the person chooses.
    repo = found[0][0] if len(found) == 1 else None
    title = branch
    url_match = config.CLOUD_URL_RE.search(text)
    # An imported session works on its own branch: that is the only one Claude can push to.
    save_cloud_session(
        session_id, title, url_match.group(0) if url_match else None,
        repo=repo, work=branch, base=github.default_branch(repo) if repo else None, direct=True, imported=True,
    )
    with state.lock:
        state.current_cloud = state.last_cloud = session_id
        state.current_repo = entry_of(session_id).get("repo")
        state.save()
    return session_id, None


def queue_followup(session_id, text):
    """Queues one message into an existing cloud session
    (`claude -p --cloud <id>`). Returns {"ok", "url", "error"}."""
    command = ["claude", "-p", *config.CLOUD_ALLOWED_TOOLS_ARGS, "--cloud", session_id, "--output-format", "json"]
    with state.followup_lock:
        done = subprocess.run(command, input=text, capture_output=True, text=True, timeout=90)
    output = github.clean((done.stdout or "") + (done.stderr or ""))
    claude_cli.log_cloud("follow-up", command, done.returncode, output)
    data = claude_cli.last_json_object(output)
    if data is not None:
        ok, url, error = data.get("ok") is True, data.get("url"), data.get("error")
    else:
        ok, url, error = done.returncode == 0, None, None
    if not ok:
        error = error or output.strip()[-600:] or f"code {done.returncode}"
    return {"ok": ok, "url": url, "error": error}


def session_rename(session_id, title):
    """The person renames a session: the name Aiwa shows changes (the store keeps the title it was given at the start, so it is set here), and the session is told with /rename."""
    title = " ".join(str(title or "").split())[:60]
    if not config.CLOUD_ID_RE.fullmatch(str(session_id or "")) or not title:
        return {"ok": False, "error": "nom ou session invalide"}
    with state.store_lock:
        entries = load_all()
        entry = next((e for e in entries if e.get("id") == session_id), None)
        if entry is None:
            return {"ok": False, "error": "session inconnue d'Aiwa"}
        entry["title"] = title
        try:
            config.CLOUD_STORE.write_text(json.dumps(entries[:30]), encoding="utf-8")
        except OSError as err:
            return {"ok": False, "error": str(err)}
    threading.Thread(target=_rename_session, args=(session_id, title), daemon=True).start()
    return {"ok": True}


def _rename_session(session_id, title):
    """Claude names a cloud session itself, and the CLI can't read that name
    back — so Aiwa imposes its own: the name Aiwa shows is sent to the
    session with `/rename`, which cloud sessions document as taking its
    value as an argument. Best effort, in the background."""
    try:
        result = queue_followup(session_id, f"/rename {title}")
        print(f"[{state.ts()}] rename {session_id[:16]}: ok={result['ok']} {result['error'] or ''}", flush=True)
    except (OSError, subprocess.SubprocessError) as err:
        print(f"[{state.ts()}] rename failed: {err}", flush=True)


def _keep_cli_repo_lines(log):
    """What the CLI said about the repository when it created the session (its debug log is deleted, and holds the message): only the lines
    that speak of GitHub, the repository or the bundling, kept in a file and in the backend's log, so that "the session started empty" can be
    explained afterwards instead of guessed."""
    try:
        lines = [ln[:300] for ln in log.splitlines() if re.search(r"github|repo|bundl|preflight|source|clone|debug file", ln, re.I)][-40:]
        if not lines:
            lines = [f"(the CLI's debug log has {len(log)} characters and none speaks of GitHub, the repository or the bundling)"]
        config.CLI_REPO_LOG.write_text(f"[{state.ts()}]\n" + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"[{state.ts()}] cloud_send: the CLI's lines on the repository: {len(lines)} kept in {config.CLI_REPO_LOG.name}", flush=True)
    except OSError:
        pass


def _cli_repo_verdict(repo):
    """Why the CLI took the folder for the repository's content instead of naming the repository, from its debug log (which is then deleted:
    it holds the message): "no_app" (Claude's GitHub app is not installed on it), another reason of the CLI's own words, or None when it named
    the repository."""
    try:
        log = config.CLI_DEBUG.read_text(encoding="utf-8", errors="replace")[-400_000:]
    except OSError:
        _keep_cli_repo_lines("(the CLI wrote no debug file: nothing to read about the repository)")
        return None
    finally:
        config.CLI_DEBUG.unlink(missing_ok=True)
    _keep_cli_repo_lines(log)
    reason = config.CLI_BUNDLING_RE.search(log)
    if reason is None:
        return None
    if config.CLI_NO_APP_RE.search(log) or reason.group(1) == "github_preflight_failed":
        return "no_app"
    return reason.group(1)


def cloud_send(text, command=False, session=None, repo=None):
    """Sends one message to the current cloud session — creating a new
    one when none is selected. Synchronous: creating a session can take a
    while, the cloud machine has to start.

    command=True: `text` is a slash command for the CURRENT session (e.g.
    `/model opus`); it never creates a session and leaves the session's
    name and rank in the list alone.

    session: a session to send to INSTEAD of the one in use (the super agent's confirmed proposals): the message then goes the same way as my own —
    with the files I joined and the instructions of the pills — and the widget's session stays as it is.

    repo: the repository the message is about, when the session is not named: the session linked to that repository is used (it is made when there is none), and it becomes the one in use."""
    if repo and not session and not command:
        focus(repo)
    with state.lock:
        if state.cloud_busy:
            return {"ok": False, "error": "busy"}
        session_id = session or state.current_cloud
        model = state.current_model
        repo, direct_now = state.current_repo, state.push_main
        if command and not session_id:
            return {"ok": False, "error": "aucune session en cours"}
        state.cloud_busy = True
        state.cloud_busy_since = time.time()
        state.cloud_progress = ""
    title = " ".join(text.split())[:50]
    with state.attach_lock:
        sent_files = [] if command else list(state.attachments)
    text += attachments.block(sent_files)
    if not command:
        relay.clear_waiting()  # the user answered: whatever Claude was waiting for is over
    try:
        if session_id:
            sent, fingerprint = text, None
            if not command:
                entry = entry_of(session_id)
                work = base = None
                if entry.get("repo"):
                    work, base = _session_targets(session_id, entry)
                    # The default branch can change after the session started (the first branch pushed into an empty repository becomes it):
                    # the instructions follow it, so Claude never has to ask which branch to integrate into.
                    fresh = github.default_branch_or_none(entry["repo"])
                    if fresh and fresh != base:
                        update_session(session_id, base=fresh)
                        base = fresh
                    entry = entry_of(session_id)
                extra_text, fingerprint = instructions.compose(entry, entry.get("repo"), work, base, entry.get("direct", True), entry.get("origin"))
                sent += extra_text
            result = queue_followup(session_id, sent)
            if not result["ok"]:
                claude_cli.note_login_problem(result["error"])
                return {"ok": False, "error": result["error"]}
            claude_cli.set_login_state("ok")
            if sent_files:
                with state.attach_lock:
                    del state.attachments[:len(sent_files)]
            if not command:
                relay.note_message_sent()
                save_cloud_session(session_id, title, result["url"], instr=fingerprint)
                relay.mailbox_watch(entry.get("repo"), work)
            return {"ok": True, "session_id": session_id, "url": result["url"]}
        if not repo:
            # Every session starts on a repository: there is no free conversation.
            return {"ok": False, "error": "Dis de quel dépôt on parle : chaque session démarre sur un dépôt."}
        # The session starts on the chosen repository, which is only an address:
        # the directory is an empty stub whose origin is that repository, and the
        # cloud clones it itself, with Claude's own access (the user grants it at
        # claude.ai/connect-github). Nothing of the repository goes through the phone.
        with state.lock:
            state.repo_access_missing = None
        state.cloud_progress = f"préparation de la session sur {repo}…"
        try:
            directory, work, base = github.prepare_repo_dir(repo)
        except github.GithubError as err:
            state.github_error = f"dépôt {repo} : {err}"
            return {"ok": False, "error": state.github_error}
        state.github_error = None
        extra_text, fingerprint = instructions.compose({}, repo, work, base, direct_now)
        with state.lock:
            asked_before = state.relay_cloud["asked"]
        check_text = relay.check_text(repo=repo, work=work)
        task = text + extra_text + check_text
        # Claude's own title for the session is made from this first message: the
        # name Aiwa shows is written in it, besides the /rename queued after the
        # creation (which the CLI accepts but whose execution can't be checked).
        task += f"\n\n[Aiwa] Nom de cette session, tel qu'Aiwa l'affiche : « {title} ». Utilise exactement ce nom comme titre de la session."
        if task.lstrip().startswith("-"):
            task = "Message : " + task
        with state.lock:
            effort = state.current_effort
        config.CLI_DEBUG.unlink(missing_ok=True)
        command_line = ["claude"] + (["--model", model] if model else []) + (["--effort", effort] if effort else []) + config.CLOUD_ALLOWED_TOOLS_ARGS + ["--debug-file", str(config.CLI_DEBUG), "--cloud", task]
        # Under `script` the CLI gets a full terminal including a
        # controlling one (a bare pty has none, and a program that opens
        # /dev/tty then fails); without `script` it just gets the pty.
        run = ["script", "-q", "-e", "-c", shlex.join(command_line), "/dev/null"] if shutil.which("script") else command_line
        state.cloud_progress = "création de la session (le CLI de Claude démarre)…"
        code, output, reason, timeline = claude_cli.run_with_pty(run, directory, config.CLOUD_HARD, stop_after_session_id=True, idle_timeout=config.CLOUD_IDLE)
        timed_out = reason in ("timeout", "idle")
        claude_cli.log_cloud("create", run, code, output, timeline)
        ids = config.CLOUD_ID_RE.findall(output)
        found = next((i for i in ids if i.startswith("session_")), ids[0] if ids else None)
        url_match = config.CLOUD_URL_RE.search(output)
        url = url_match.group(0) if url_match else None
        if found is None and url:
            from_url = config.CLOUD_ID_RE.search(url)
            found = from_url.group(0) if from_url else None
        print(f"[{state.ts()}] cloud_send: created={found!r} code={code} {timeline[-1]}", flush=True)
        if found and sent_files:
            with state.attach_lock:
                del state.attachments[:len(sent_files)]
        verdict = _cli_repo_verdict(repo)
        if repo and found and verdict == "no_app":
            state.github_error = (
                f"Claude n'a pas accès à {repo} : son app GitHub n'y est pas installée, donc la session est partie avec un dossier vide. "
                "Une fois pour tous tes dépôts, présents et futurs : github.com/settings/installations, Claude, All repositories, Enregistrer."
            )
            with state.lock:
                state.repo_access_missing = repo
        elif repo and found and verdict:
            # The CLI sent the folder for another reason: said as it said it, without guessing at the cause.
            state.github_error = f"La session est partie avec un dossier vide au lieu de cloner {repo} (raison du CLI : {verdict})."
            with state.lock:
                state.repo_access_missing = None
                state.save()
        elif repo and found:
            with state.lock:
                if state.repo_access_missing == repo:
                    state.repo_access_missing = None
                    state.save()
        if found is None:
            prompted = reason == "waiting for an answer"
            if prompted:
                where = str(directory).replace(str(Path.home()), "~")
                asked = " ".join(output.strip().split())[-240:]
                reason = (
                    f"le CLI de Claude attend une réponse dans {where} : « {asked} ». Dans Termux : "
                    f"proot-distro login ubuntu -- bash -c 'cd {where} && claude' — réponds une fois (par exemple faire confiance au dossier), quitte, puis renvoie le message"
                )
            elif timed_out:
                reason = ("délai dépassé : le CLI n'a rien affiché depuis " + str(config.CLOUD_IDLE) if reason == "idle" else "délai dépassé : plus de " + str(config.CLOUD_HARD)) + " s (" + " ; ".join(timeline) + ")"
            else:
                reason = f"aucun identifiant de session trouvé (code {code})"
            claude_cli.note_login_problem(output)
            if check_text:
                with state.lock:  # no session was created: the relay test was not asked after all
                    state.relay_cloud["asked"] = asked_before
                    state.save()
            return {"ok": False, "error": reason if prompted else reason + " — sortie : " + output.strip()[-600:]}
        claude_cli.set_login_state("ok")
        relay.note_message_sent()
        state.last_request.update(text=" ".join(str(text).split())[:300], at=int(time.time()))
        with state.lock:
            state.current_cloud = state.last_cloud = found
            state.save()
        save_cloud_session(found, title, url, repo=repo, work=work, base=base, direct=direct_now if repo else None, instr=fingerprint, model=model or "", effort=effort or "")
        relay.mailbox_watch(repo, work)
        threading.Thread(target=_rename_session, args=(found, title), daemon=True).start()
        return {"ok": True, "session_id": found, "url": url}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "délai dépassé"}
    except (OSError, subprocess.CalledProcessError) as err:
        return {"ok": False, "error": str(err)}
    finally:
        with state.lock:
            state.cloud_busy = False
            state.cloud_busy_since = None
            state.cloud_progress = ""