"""GitHub, as far as Aiwa needs it.

Claude Code does the real work (clone, edit, commit, push) with its OWN GitHub access, which the person grants once at claude.ai/connect-github. What the brain does here is small:
 - find the repositories to talk about (public ones by owner, the person's own with a token);
 - start `claude --cloud` from a folder whose `origin` is the chosen repository (the cloud clones it itself);
 - read the productions of a repository (its releases) and delete one;
 - tell whether the last workflow of a repository passed.

The token is optional: the person gives it in the settings (« clés et plafonds »). Without it, public repositories are read and nothing is deleted.
"""
import base64
import calendar
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .paths import DATA

# The one folder every session starts from: the CLI asks "do you trust the files in this folder?" once per folder, and a single folder is a single answer.
SESSION_DIR = DATA / "chat"
# Overridable so that the lookups can be tested without the network.
GITHUB_API = os.environ.get("AIWA_GITHUB_API", "https://api.github.com")
GITHUB_BASE = os.environ.get("AIWA_GITHUB_BASE", "https://github.com")
TOKEN_FILE = DATA / "github_token"
OWNER_REPOS_FILE = DATA / "owner_repos.json"
USER_FILE = DATA / "github_user"        # the account the token belongs to (its login), found when the token is kept
# Runs nobody asked for, which say nothing about the person's work: the ones a workflow schedules for itself and GitHub's own dynamic ones.
NOT_NEWS_EVENTS = ("schedule", "dynamic")
OK_CONCLUSIONS = ("success", "skipped", "neutral")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
_URL_RE = re.compile(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/?#\s]|$)")
# Terminal escape sequences: CSI, OSC, and the two-byte kind (ESC 7 / ESC 8 save/restore the cursor).
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[ -/]*[0-~])")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
APK_TAG = "android-latest"


class GithubError(Exception):
    def __init__(self, message, limited=False):
        super().__init__(message)
        self.limited = limited      # GitHub's own limit was reached: it ends by itself


def clean(text):
    return CTRL_RE.sub("", ANSI_RE.sub("", text).replace("\r", "\n"))


def parse_repo(text):
    """owner/name from a GitHub link, a git remote or a bare owner/name."""
    text = text.strip()
    match = _URL_RE.search(text)
    if match:
        repo = f"{match.group(1)}/{match.group(2)}"
    else:
        repo = text[:-4] if text.endswith(".git") else text
    return repo if REPO_RE.fullmatch(repo) else None


def apk_url(repo):
    """Where the Android APK of a repository is published: a file of the one rolling release tagged android-latest, named after the repository."""
    owner, name = repo.split("/", 1)
    return f"{GITHUB_BASE}/{owner}/{name}/releases/download/{APK_TAG}/{name}.apk"


def _epoch(stamp):
    """Epoch seconds of a GitHub timestamp (2026-09-30T05:17:06Z); 0 when unreadable."""
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


# ---------- the token and the API ----------


def token_value():
    """The person's GitHub token, or None: the environment, then the file the settings write."""
    value = os.environ.get("AIWA_GITHUB_TOKEN", "").strip()
    if not value:
        try:
            value = TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    return value or None


def set_token(value):
    """Keeps (or, empty, forgets) the token. It stays in a file only the person can read."""
    value = str(value or "").strip()
    if value and not re.fullmatch(r"[A-Za-z0-9_\-]{20,255}", value):
        raise GithubError("jeton invalide")
    if not value:
        TOKEN_FILE.unlink(missing_ok=True)
        USER_FILE.unlink(missing_ok=True)
        return
    TOKEN_FILE.write_text(value, encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    # the account it belongs to: a token GitHub refuses is not kept; GitHub being unreachable keeps it (the account is looked up later)
    try:
        who = api("/user")
    except GithubError as err:
        if "401" in str(err) or "403" in str(err):
            TOKEN_FILE.unlink(missing_ok=True)
            raise GithubError("GitHub refuse ce jeton")
        return
    login = who.get("login") if isinstance(who, dict) else None
    if isinstance(login, str) and REPO_RE.fullmatch(login + "/x"):
        USER_FILE.write_text(login, encoding="utf-8")


def connected_user():
    """The GitHub account of the token, or None without a token."""
    if not token_value():
        return None
    try:
        return USER_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def api(path, method="GET", body=None, timeout=15):
    """One call to the GitHub API, with the token when there is one. Returns the JSON (None for an empty answer) or raises GithubError."""
    headers = {"User-Agent": "aiwa", "Accept": "application/vnd.github+json"}
    token = token_value()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{GITHUB_API}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as err:
        limited = err.code in (403, 429) and err.headers.get("X-RateLimit-Remaining") == "0"
        raise GithubError(f"GitHub {err.code}" + (" (limite atteinte)" if limited else "") + (" : jeton absent ou sans droit" if err.code in (401, 403, 404) and method != "GET" else ""), limited=limited)
    except (OSError, ValueError) as err:
        raise GithubError(f"GitHub injoignable : {err}")
    return json.loads(raw) if raw else None


def release_upload(repo, tag, title, notes, path, name, timeout=1800):
    """Puts a file in the release `tag` of a repository (made when it is not there), replacing a file of the same name. Needs the person's GitHub access. Raises GithubError."""
    if not token_value():
        raise GithubError("GitHub n'est pas connecté")
    try:
        release = api(f"/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}")
    except GithubError as err:
        if "404" not in str(err):
            raise
        release = api(f"/repos/{repo}/releases", "POST", {"tag_name": tag, "name": title, "body": notes})
    for old in (release or {}).get("assets", []):
        if old.get("name") == name:
            api(f"/repos/{repo}/releases/assets/{old['id']}", "DELETE")
    size = Path(path).stat().st_size
    with open(path, "rb") as handle:
        request = urllib.request.Request(
            f"https://uploads.github.com/repos/{repo}/releases/{release['id']}/assets?name={urllib.parse.quote(name)}", data=handle, method="POST",
            headers={"Authorization": f"Bearer {token_value()}", "Content-Type": "application/octet-stream", "Content-Length": str(size), "User-Agent": "aiwa", "Accept": "application/vnd.github+json"})
        try:
            urllib.request.urlopen(request, timeout=timeout).read()
        except urllib.error.HTTPError as err:
            raise GithubError(f"GitHub {err.code} : l'envoi est refusé (jeton sans le droit « repo » ?)")
        except OSError as err:
            raise GithubError(f"GitHub injoignable : {err}")


# ---------- the repositories ----------

_owner_cache = {}


def _owner_repos_saved():
    try:
        data = json.loads(OWNER_REPOS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def owner_repos(owner, max_age=600):
    """The public repositories of a GitHub user or organization, most recently pushed first. Cached ten minutes. When GitHub refuses (its limit without a token is 60 questions an hour) the last good list is kept, also across a restart."""
    cached = _owner_cache.get(owner)
    if cached and time.time() - cached[0] < max_age:
        return cached[1]
    try:
        data = api(f"/users/{urllib.parse.quote(owner)}/repos?per_page=100&sort=pushed")
        fetched_at, ok = time.time(), isinstance(data, list)
    except GithubError:
        data, fetched_at, ok = [], time.time() - max(0, max_age - 60), False   # retry in a minute
    repos = [{"name": r["full_name"], "private": False} for r in (data or []) if isinstance(r, dict) and r.get("full_name") and not r.get("archived")]
    if ok:
        saved = _owner_repos_saved()
        saved[owner] = repos
        try:
            OWNER_REPOS_FILE.write_text(json.dumps(saved), encoding="utf-8")
        except OSError:
            pass
    else:
        previous = cached[1] if cached and cached[1] else _owner_repos_saved().get(owner, [])
        if isinstance(previous, list) and previous:
            repos = previous
    _owner_cache[owner] = (fetched_at, repos)
    return repos


def my_repos():
    """The repositories the token can push to (private ones included); [] without a token."""
    if not token_value():
        return []
    try:
        data = api("/user/repos?per_page=100&sort=pushed&affiliation=owner,collaborator,organization_member", timeout=30)
    except GithubError:
        return []
    return [{"name": r["full_name"], "private": bool(r.get("private"))} for r in (data or []) if isinstance(r, dict) and r.get("full_name") and (r.get("permissions") or {}).get("push", True)]


def checkout_owner():
    """Whose repositories to offer first: the owner of the checkout Aiwa was installed from (its `origin` remote), or AIWA_GITHUB_OWNER."""
    override = os.environ.get("AIWA_GITHUB_OWNER", "").strip()
    if override:
        return override
    me = connected_user()
    if me:
        return me
    root = Path(__file__).resolve().parents[2]
    try:
        done = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    repo = parse_repo(done.stdout) if done.returncode == 0 else None
    return repo.split("/")[0] if repo else None


# ---------- the workflows ----------


def latest_run(repo):
    """The verdict on the most recent commit of a repository's GitHub Actions: {"state": "running" | "success" | "failure" | "none", "url", "detail"}, None when it can't be told.
    One push starts several runs: they are ONE verdict, "running" until the last has finished, "failure" when one did fail. Scheduled and dynamic runs are left out."""
    try:
        data = api(f"/repos/{repo}/actions/runs?per_page=20")
    except GithubError:
        return None
    runs = [r for r in ((data or {}).get("workflow_runs") or []) if r.get("event") not in NOT_NEWS_EVENTS]
    if not runs:
        return {"state": "none", "url": None, "detail": ""}
    head = runs[0]
    newest = {}
    for run in (r for r in runs if r.get("head_sha") == head.get("head_sha")):
        key = run.get("workflow_id") or run.get("name") or run.get("id")
        if key not in newest or (run.get("created_at") or "", run.get("id") or 0) > (newest[key].get("created_at") or "", newest[key].get("id") or 0):
            newest[key] = run
    same = list(newest.values())
    shown = head
    if any(r.get("status") != "completed" for r in same):
        verdict = "running"
    else:
        failed = next((r for r in same if r.get("conclusion") not in OK_CONCLUSIONS), None)
        verdict, shown = ("failure", failed) if failed else ("success", head)
    return {"state": verdict, "url": shown.get("html_url"), "detail": f"{shown.get('name') or '?'} — {shown.get('display_title') or '?'}"}


def newest_commit_time(repo, branch):
    """Epoch seconds of the last commit of a branch, 0 when it can't be read."""
    try:
        data = api(f"/repos/{repo}/commits/{urllib.parse.quote(branch, safe='')}")
    except GithubError:
        return 0
    return _epoch(((data or {}).get("commit") or {}).get("committer", {}).get("date"))


# ---------- the releases: where every production lives ----------


def releases(repo):
    """The releases of a repository, newest first, each as {id, tag, name, published, assets: [{id, name, size, url}]}."""
    try:
        data = api(f"/repos/{repo}/releases?per_page=100", timeout=20)
    except GithubError as err:
        raise GithubError(str(err))
    out = []
    for rel in data or []:
        if not isinstance(rel, dict) or not rel.get("tag_name"):
            continue
        out.append({
            "id": rel.get("id"), "tag": rel["tag_name"], "name": rel.get("name") or rel["tag_name"], "published": _epoch(rel.get("published_at")), "page": rel.get("html_url"),
            "assets": [{"id": a.get("id"), "name": a.get("name"), "size": a.get("size"), "url": a.get("browser_download_url")} for a in rel.get("assets") or [] if isinstance(a, dict)],
        })
    return out


def delete_release(repo, release_id, tag):
    """Deletes a release, and its tag so that the name can be used again."""
    api(f"/repos/{repo}/releases/{int(release_id)}", method="DELETE")
    try:
        api(f"/repos/{repo}/git/refs/tags/{urllib.parse.quote(tag, safe='')}", method="DELETE")
    except GithubError:
        pass     # the tag can be gone already (or never exist)


def put_file(repo, path, raw, message):
    """Puts a file in a repository (its default branch) with the token: the way a file reaches a cloud session when the relay is blocked from its network, since GitHub is always reachable.
    Replaces the file if it is already there. Returns the path."""
    if not token_value():
        raise GithubError("pas de jeton GitHub (réglages : clés et plafonds)")
    route = f"/repos/{repo}/contents/{urllib.parse.quote(path)}"
    body = {"message": message, "content": base64.b64encode(raw).decode()}
    try:
        old = api(route)
        if isinstance(old, dict) and old.get("sha"):
            body["sha"] = old["sha"]
    except GithubError:
        pass     # not there yet
    api(route, method="PUT", body=body, timeout=120)
    return path


def fetch(url, limit):
    """The bytes at an https address (a release's file: the redirect is followed), None when it is not a 200 or larger than `limit`."""
    if not url.startswith("https://"):
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "aiwa"})
        with urllib.request.urlopen(request, timeout=60) as reply:
            data = reply.read(limit + 1)
    except OSError:
        return None
    return data if len(data) <= limit else None


# ---------- the directory `claude --cloud` starts from ----------


def _env():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


SESSION_IN_TEXT = re.compile(r"(?:session|cse)_[A-Za-z0-9]+")


def _branch_session(repo, branch):
    """(repo, state, session id or None); state is "missing" (the repository
    answers and has no such branch), "unreachable" (it doesn't answer — a
    private repository without a login here, typically) or "found". A cloud
    session's commits carry a `Claude-Session: https://claude.ai/code/session_…`
    line, which is how a branch name leads back to its session. Only the
    commits that are on the branch and NOT on the default branch count: a
    brand-new branch is cut from a history that holds other sessions' links,
    and must not be mistaken for one of them (no commit of its own yet = no
    session known)."""
    url = f"{GITHUB_BASE}/{repo}.git"
    try:
        if not _git(["ls-remote", "--heads", url, f"refs/heads/{branch}"], timeout=15).strip():
            return (repo, "missing", None)
    except GithubError:
        return (repo, "unreachable", None)
    default = default_branch(repo)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _git(["init", "-q", "--bare", tmp])
            refs = [f"refs/heads/{branch}:refs/aiwa/branch", f"refs/heads/{default}:refs/aiwa/default"]
            try:
                _git(["fetch", "-q", "--depth", "50", "--filter=blob:none", url] + refs, cwd=tmp, timeout=30)
            except GithubError:
                _git(["fetch", "-q", "--depth", "50", url] + refs, cwd=tmp, timeout=45)
            log = _git(["log", "-30", "--format=%B", "refs/aiwa/branch", "^refs/aiwa/default"], cwd=tmp)
            # Nothing of its own: the work of this branch may already be in the default branch (pushed there straight from the session,
            # or merged), and then every commit of it is excluded above. The remote branch only exists because the session pushed to it
            # (a cloud session creates its branch locally), so its latest commits are the session's own.
            if not SESSION_IN_TEXT.search(log):
                log = _git(["log", "-5", "--first-parent", "--format=%B", "refs/aiwa/branch"], cwd=tmp)
        except GithubError:
            return (repo, "found", None)
    match = SESSION_IN_TEXT.search(log)
    return (repo, "found", match.group(0) if match else None)


def find_branch_session(repos, branch):
    """Looks for a branch in these repositories, in parallel, for at most
    ~35 s, and waits for all of them: one repository is not enough to say
    where a session works, a session can work on several with the same
    branch name. Returns (found, tried): found lists (repo, session id or
    None) for every repository that has the branch (empty when none does);
    tried lists (repo, state) for every repository, so a refusal can say
    what was looked at."""
    states = {repo: "trop lent" for repo in repos}
    pool = ThreadPoolExecutor(max_workers=6)
    futures = [pool.submit(_branch_session, repo, branch) for repo in repos]
    found = []
    try:
        for future in as_completed(futures, timeout=35):
            repo, verdict, session = future.result()
            states[repo] = verdict
            if verdict == "found":
                found.append((repo, session))
    except Exception:
        pass  # timed out: what has not answered stays "trop lent"
    pool.shutdown(wait=False, cancel_futures=True)
    found.sort(key=lambda item: repos.index(item[0]))
    return found, list(states.items())


def _git(args, cwd=None, timeout=300):
    command = ["git"]
    token = token_value()
    if token:
        # A token lets private repositories be read too.
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        command += ["-c", f"http.extraheader=Authorization: Basic {basic}"]
    try:
        done = subprocess.run(command + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=_env())
    except (OSError, subprocess.TimeoutExpired) as err:
        raise GithubError(f"git {args[0]} : {err}")
    if done.returncode != 0:
        raise GithubError(f"git {args[0]} : " + clean(done.stderr or done.stdout).strip()[-300:])
    return done.stdout


def default_branch_or_none(repo):
    """The repository's default branch as GitHub says it now, None when it cannot be read (empty repository, offline)."""
    try:
        out = _git(["ls-remote", "--symref", f"{GITHUB_BASE}/{repo}.git", "HEAD"], timeout=30)
        match = re.search(r"ref: refs/heads/(\S+)\s+HEAD", out)
        if match:
            return match.group(1)
    except GithubError:
        pass
    return None


def default_branch(repo):
    return default_branch_or_none(repo) or "main"


def trust_folder(path):
    """The CLI asks « do you trust the files in this folder? » the first time it is started from a folder, and nobody is there to answer in the terminal Aiwa gives it: the session would wait and never
    be made. The answer is kept in ~/.claude.json (projects[<folder>]); it is written here, once, for the folder the sessions start from."""
    config_file = Path.home() / ".claude.json"
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    projects = data.get("projects")
    if not isinstance(projects, dict):
        projects = data["projects"] = {}
    entry = projects.get(str(path))
    if not isinstance(entry, dict):
        entry = projects[str(path)] = {}
    if entry.get("hasTrustDialogAccepted") is True and entry.get("hasCompletedProjectOnboarding") is True:
        return
    entry.update(hasTrustDialogAccepted=True, hasCompletedProjectOnboarding=True)
    temp = config_file.with_name(config_file.name + ".aiwa")
    try:
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(config_file)
    except OSError:
        temp.unlink(missing_ok=True)


def prepare_repo_dir(repo):
    """The local directory `claude --cloud` is started from. The repository
    is only an address: this directory is an empty stub whose `origin` is
    the repository, which is all the CLI reads to tell the cloud session
    which repository to clone (with Claude's own GitHub access). Nothing of
    the repository is downloaded here, so nothing of it is uploaded from the
    phone either. It is always the same folder, kept as it is (only `origin`
    and the branch are set), so the CLI's one-time "trust this folder" answer
    stays valid from one repository to the next.
    Returns (directory, work branch, default branch): the work branch is
    the session's own branch, a fresh aiwa/<date> that Claude is asked to
    create from the default branch."""
    url = f"{GITHUB_BASE}/{repo}.git"
    branch = default_branch(repo)
    dest = SESSION_DIR
    dest.mkdir(parents=True, exist_ok=True)
    trust_folder(dest)
    if not (dest / ".git").exists():
        _git(["init", "-q", "-b", branch], cwd=dest)
    try:
        _git(["rev-parse", "--verify", "-q", "HEAD"], cwd=dest)
    except GithubError:
        _git(["-c", "user.name=aiwa", "-c", "user.email=aiwa@example.com", "commit", "-q", "--allow-empty", "-m", "stub"], cwd=dest)
    _git(["checkout", "-q", "-B", branch], cwd=dest)
    try:
        _git(["remote", "set-url", "origin", url], cwd=dest)
    except GithubError:
        _git(["remote", "add", "origin", url], cwd=dest)
    # Read from the CLI's code: before sending the repository's address, `claude --cloud` asks git whether the current branch is known on
    # the remote (`git show-ref --verify refs/remotes/origin/<branch>`). With no such ref it takes the folder for work that exists only here
    # and uploads the folder itself instead of naming the repository, and the cloud session gets an empty folder (no remote, one commit).
    # The ref is made here: it only says the branch exists on origin, which the cloud then clones by name.
    for ref in _git(["for-each-ref", "--format=%(refname)", "refs/remotes/origin/"], cwd=dest).split():
        _git(["update-ref", "-d", ref], cwd=dest)
    _git(["update-ref", f"refs/remotes/origin/{branch}", "HEAD"], cwd=dest)
    return dest, "aiwa/" + time.strftime("%Y%m%d-%H%M%S"), branch
