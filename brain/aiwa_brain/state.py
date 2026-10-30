"""What the brain knows and remembers. One module holds all the shared state, so that every domain module reads and writes the same names (`state.current_repo`, `state.agent`…).
The settings are saved (`save`) and come back at the start (`load`); the rest lives as long as the brain does."""
import json
import re
import secrets
import threading
import time

from . import config, github, llm_lib, style_lib, voice_lib


def ts():
    return time.strftime("%H:%M:%S")


# ---------- the settings (saved) ----------
lock = threading.Lock()   # guards the settings below
current_model = None      # None = the CLI's own default model
current_effort = None     # None = the CLI's own default effort
# The cloud session messages go to; None = the next message creates one. `last_cloud` is the session most recently in use: kept when the next message starts a NEW one, so that the app can still open the conversation you were in.
current_cloud = None
last_cloud = None
# The repository the session works on, and new sessions start on ("owner/name"; None = none yet). The super agent changes it by itself when the person talks about another one.
current_repo = None
push_main = True          # push straight to the default branch (otherwise to a work branch of the session)
repo_access_missing = None  # the repository whose last session started without it: Claude's GitHub app is not installed there
# The relay topic (a random secret) and whether Claude has pinged it since the person last sent a message or opened the session.
waiting_topic = None
waiting_lock = threading.Lock()
waiting = {"since": None, "last_ping": None}
# Whether a command Claude runs in the cloud reaches the relay (the environment's network access must allow ntfy.sh): when the test was asked, and when its answer came. Saved: a relay seen working stays confirmed.
relay_cloud = {"asked": None, "ok": None}
# The questions Claude asked through the widget (`Title: aiwa-ask`, or aiwa-out/ask.json) and nobody answered yet, of every session: [{id, question, options, ts, answered, session}].
ask_list = []
relay_seen = {"id": None, "time": None}     # the last relay event handled, to resume after a restart
last_message_at = 0       # when the person last sent a message through Aiwa (epoch seconds)

# ---------- the running state (not saved) ----------
github_error = None       # the last GitHub problem worth showing in the app
session_error = None      # why the last session made on a repository could not be made (None: it was, or none was asked)
cloud_busy = False
last_send = None   # {at, seconds, ok, error} of the last message sent to a session
cloud_busy_since = None   # when the running send began (epoch seconds): the widget says how long it has lasted
cloud_progress = ""       # what the running send is doing right now (a step of ours, then the last line the CLI printed)
store_lock = threading.Lock()
followup_lock = threading.Lock()   # two `claude -p --cloud <id>` runs never overlap (a send and the /rename that follows a creation, for instance)
# The account the CLI is logged in to: state is unknown / ok / needed, looked up in the background. `login_flow` is the `claude auth login` run the app drives from its « Connecter Claude » window: phase idle / starting / url / checking / done / failed.
login_lock = threading.Lock()
claude_login = {"state": "unknown", "at": 0.0, "busy": False}
login_flow = {"phase": "idle", "url": None, "message": "", "proc": None, "master": None, "text": "", "mark": 0}
conversation = []         # the talk with the super agent, [(time, who, text)]: it forgets after ten quiet minutes, and keeps the last eight turns
last_request = {"text": "", "at": 0}      # the last thing the person asked a session to do (for « t'en es où » and for the answers)
attachments = []          # what the person attached with the paperclip: it leaves with the next message
attach_lock = threading.Lock()
mailbox = {"key": None, "until": 0.0, "running": False, "seen": None}
mailbox_lock = threading.Lock()
silence = {"acked_for": 0, "commit_key": None, "commit_at": 0.0, "commit_time": None}
cast_pending = {"on": False, "tv": "", "since": 0.0, "known": []}
self_update_last = {"at": 0.0, "result": "pas encore vérifié"}

# The super agent: what it said and proposed, waiting for the phone (agent_lib has its text), and the talk with it. It answers through the person's own API key, or else through the Claude of the phone.
agent_lock = threading.Lock()
agent = {"decisions": [], "sig": None, "last": 0.0, "say": None, "proposal": None, "command": None, "last_sent": [], "busy": False, "error": None}
agent_chat = []
voice = voice_lib.Voice()
llm = llm_lib.Llm()
style = style_lib.Style(config.APP_DIR / "style.json")      # the person's way of speaking (counts only), so that the agent talks like her

# The chamber: the super agent meets the one of someone else, in a room they both pressed the button of (chamber_lib has the rules). A super agent is in ONE chamber at a time; the lines are what was said.
chamber_lock = threading.Lock()
chamber_offers = []       # what the others proposed with something attached (a slide, a video…): the person sees it and opens it or not
chamber = {"active": False, "peer": None, "name": None, "lines": []}
match_cache = {}

# The scenarios: a prompt under a launch word of the person's own, each one a super agent of its own.
scenario_lock = threading.Lock()
scenario_run = {}         # scenario id -> {"creating": bool, "error": str|None, "said": [{"id", "say", "note", "ts"}]}   (in memory: only what is in flight)
# « Création à la volée »: the super agent in a fluid conversation while the person builds.
live = {"on": False, "events": [], "recent": [], "snap": {}}
live_lock = threading.Lock()


def _repo_or_none(value):
    return value if isinstance(value, str) and github.REPO_RE.fullmatch(value) else None


def load():
    global current_model, current_cloud, current_repo, push_main, current_effort, waiting_topic, last_cloud, ask_list, last_message_at, repo_access_missing
    try:
        data = json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        data = {}
    model, cloud = data.get("model"), data.get("cloud")
    current_model = model if isinstance(model, str) and config.MODEL_RE.fullmatch(model) else None
    current_cloud = cloud if isinstance(cloud, str) and config.CLOUD_ID_RE.fullmatch(cloud) else None
    last = data.get("last_cloud")
    last_cloud = last if isinstance(last, str) and config.CLOUD_ID_RE.fullmatch(last) else current_cloud
    current_repo = _repo_or_none(data.get("repo"))
    repo_access_missing = _repo_or_none(data.get("repo_access_missing"))
    push_main = data.get("push_main") is not False
    effort = data.get("effort")
    current_effort = effort if effort in config.EFFORT_LEVELS else None
    sent = data.get("last_message")
    last_message_at = sent if isinstance(sent, int) else 0
    checked = data.get("relay_cloud")
    if isinstance(checked, dict):
        relay_cloud.update({k: checked.get(k) if isinstance(checked.get(k), (int, float)) else None for k in ("asked", "ok")})
    pending_list = data.get("ask_list")
    if not isinstance(pending_list, list):
        pending_list = [data.get("ask")] if isinstance(data.get("ask"), dict) else []
    ask_list = []
    for pending in pending_list:
        if isinstance(pending, dict) and isinstance(pending.get("question"), str) and isinstance(pending.get("id"), str):
            ask_list.append({"id": pending["id"], "question": pending["question"], "options": [o for o in pending.get("options", []) if isinstance(o, str)][:config.ASK_OPTIONS],
                             "ts": int(pending.get("ts") or 0), "answered": pending.get("answered") is True,
                             "session": pending.get("session") if isinstance(pending.get("session"), str) else None})
    ask_list = ask_list[-config.ASK_PENDING_MAX:]
    handled = data.get("relay_seen")
    if isinstance(handled, dict):
        relay_seen.update(id=handled.get("id") if isinstance(handled.get("id"), str) else None,
                          time=handled.get("time") if isinstance(handled.get("time"), int) else None)
    topic = data.get("topic")
    valid = isinstance(topic, str) and re.fullmatch(r"aiwa-[a-f0-9]{24}", topic)
    waiting_topic = topic if valid else "aiwa-" + secrets.token_hex(12)
    if not valid:
        save()  # the topic must survive a restart: sessions were told it


def save():
    """Survives a brain restart (the app restarts it when it updates): without this, the next message after a restart would silently start a brand-new cloud session instead of continuing the current one."""
    try:
        config.STATE_FILE.write_text(json.dumps({
            "model": current_model, "cloud": current_cloud, "repo": current_repo, "push_main": push_main,
            "effort": current_effort, "topic": waiting_topic, "last_cloud": last_cloud,
            "relay_cloud": relay_cloud, "ask_list": ask_list, "relay_seen": relay_seen, "last_message": last_message_at,
            "repo_access_missing": repo_access_missing,
        }), encoding="utf-8")
    except OSError as err:
        print(f"[{ts()}] could not save state: {err}", flush=True)
