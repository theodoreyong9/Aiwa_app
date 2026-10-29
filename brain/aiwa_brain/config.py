"""The brain's constants: where it listens, where it keeps things, what it accepts, how long it waits. Nothing here changes while the brain runs."""
import os
import re
from pathlib import Path

from .paths import DATA

HOST = "127.0.0.1"
PORT = int(os.environ.get("AIWA_PORT", "8788"))

# Bumped whenever the app starts depending on a new brain feature; the app compares it (via /api/status) with the version it expects.
BACKEND_VERSION = 202

HOME = Path.home()
# The brain's own folder (scenarios, style, the voice) and its files: all under ~/.aiwa_app, so that another Aiwa on the same phone (the first one, on port 8787) is never touched.
APP_DIR = DATA / "apps"
APP_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = DATA / "state.json"
CLOUD_STORE = DATA / "cloud_sessions.json"
REPOS_STORE = DATA / "repos.json"
SCENARIOS_FILE = APP_DIR / "scenarios.json"
SCEN_SESSIONS_FILE = APP_DIR / "scenario-sessions.json"
# The full output of the last `claude --cloud` run, for diagnosing a failure (`cat` it from Termux): the error shown in the app is only the tail.
CLOUD_LOG = DATA / "cloud_last.log"
CLI_REPO_LOG = DATA / "cli_repo_last.log"
# What the CLI says it decided about the repository, written where Aiwa can read it (its debug log: the terminal is not touched). With no Claude GitHub app on the repository it uploads
# the (empty) folder instead of naming the repository, and the session starts empty.
CLI_DEBUG = DATA / "cli_debug.log"
# The brain's own folder when it is a git checkout (the brain updates itself from it).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Passed to `claude --model` when a new cloud session is created, and to `/model` in an existing one. Kept restrictive: it ends up as a command-line argument.
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\[\]-]{0,63}")
# The effort levels `/effort` and `claude --effort` accept (None = automatic).
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

# A public relay Claude pings when it waits for an answer. It is also how a reply comes back to the phone: Claude's replies cannot be read by a program, but a command it runs in the cloud can reach the relay.
NTFY_SERVER = "https://ntfy.sh"
# The mailbox: when the cloud environment blocks the relay, what Claude has to say can still leave the session through GitHub, the one road a session always has (the GitHub proxy), on a repository
# attached to it: Claude pushes aiwa-out/SIGNAL to its own branch, and the phone reads it from raw.githubusercontent.com (public repositories) for a while after a message. Overridable for the tests.
RAW_BASE = os.environ.get("AIWA_RAW_BASE", "https://raw.githubusercontent.com")
MAILBOX_WAIT = 45 * 60
MAILBOX_EVERY = 20

# The page the CLI prints to log in with a Claude account (inside terminal escape codes).
LOGIN_URL_RE = re.compile(r"https://claude\.(?:com|ai)/[^\s\x07\x1b]*oauth/authorize[^\s\x07\x1b]*")
# What the CLI says when it is not (or no longer) logged in.
LOGIN_NEEDED_RE = re.compile(
    r"not logged in|run /login|login expired|unable to get organization uuid|api key authentication|not authenticated|authentication (?:failed|required|error)",
    re.I,
)
# How long Claude gets to answer the relay test before the widget says it is missing.
CLOUD_CHECK_WAIT = 240
# Creating a cloud session may legitimately take minutes (a repository the Claude GitHub App is not installed on is bundled and uploaded from the phone): it is given up when the CLI says nothing
# for CLOUD_IDLE seconds, or after CLOUD_HARD in all, not at a fixed 3 minutes.
CLOUD_HARD = 600
CLOUD_IDLE = 150
# A CLI that has said nothing for this long while its last words are a question (trust this folder? press Enter…) is waiting for someone who is not there: better to say so than to wait out the whole timeout.
PROMPT_STALL = 30
PROMPT_RE = re.compile(r"(?i)(do you trust|trust (this|the) (folder|files|directory|project)|safety check|\(y/n\)|\[y/n\]|press enter|enter to confirm|esc to cancel|\?\s*$)")
CLI_NO_APP_RE = re.compile(r"GitHub app is not installed on (\S+)")
CLI_BUNDLING_RE = re.compile(r"Bundling \(reason: (\w+)\)")
CLOUD_ID_RE = re.compile(r"(?:session|cse)_[A-Za-z0-9]+")
CLOUD_URL_RE = re.compile(r"https://claude\.ai/code/[^\s\"')>\]]+")
BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,100}")

# The tools Aiwa's own instructions ask a session to use: allowed from the start, so that the session does not stop to ask for them (a permission prompt in the Claude conversation, which the widget cannot
# see and the person has to find). The session names them "mcp__claude-code-remote__…" (hyphens, lower case), the local CLI "mcp__Claude_Code_Remote__…": the list carries both, because with one spelling only
# the permission question « Add Repo » came back every time and stayed in Claude, out of the widget's reach.
CLOUD_ALLOWED_TOOLS = [
    f"mcp__{server}__{tool}"
    for server in ("claude-code-remote", "Claude_Code_Remote")
    for tool in ("add_repo", "register_repo_root", "subscribe_pr_activity", "unsubscribe_pr_activity", "send_later", "delete_trigger")      # the last two: a scenario that watches a pull request must be able to set up and remove its own check-ins
]
CLOUD_ALLOWED_TOOLS_ARGS = ["--allowedTools", ",".join(CLOUD_ALLOWED_TOOLS)]

# Files the person attached with the widget's paperclip: they leave with the NEXT message to the session. A small text file goes inside the message; anything else is put on the relay (ntfy keeps it a few hours)
# and the session fetches it by its address.
ATTACH_MAX = 12 * 1024 * 1024
ATTACH_INLINE = 24000

# The questions Claude asks through the widget, and the answers it takes.
ASK_PENDING_MAX = 10
ASK_OPTIONS = 6
ASK_QUESTION_MAX = 600
ASK_OPTION_MAX = 80

# « envoie la vidéo sur la TV quand c'est fini »: a cast asked together with a message waits for the video to exist, and after three hours the wish is forgotten.
CAST_WAIT_SECONDS = 3 * 3600

# The talk with the super agent: it forgets after ten quiet minutes.
CONVERSATION_QUIET = 600
AGENT_FORGET_WINDOW = 1800      # seconds: a stop reaches the sessions spoken to in the last half hour

# Nothing seen after a message (no commit, no workflow that ran): it is said between SILENCE_AFTER and SILENCE_UNTIL seconds after the message; after an hour the message is taken as done or given up.
SILENCE_AFTER = 600
SILENCE_UNTIL = 3600

# The brain updates itself from its repository, once an hour.
SELF_UPDATE_EVERY = 3600

# The product's own repository: the brain updates itself from it, and the sessions read the skills there.
APP_REPO = "theodoreyong9/Aiwa_app"
APP_BRANCH = "main"
SKILLS_DIR = REPO_ROOT / "skills"
# What a session produces is published as a release of the repository; its tag says what kind it is.
KINDS = ("docs", "image", "video", "app", "page")
INPUTS_DIR = "aiwa-inputs"      # where a joined file goes in the repository (a session reaches GitHub even when the relay is closed to it)
# Where the person installs Claude's GitHub app for all her repositories (a session on a repository it is not installed on starts with an empty folder).
GITHUB_APP_URL = "https://github.com/settings/installations"
