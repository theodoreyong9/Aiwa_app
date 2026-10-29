"""The brain updates itself from its repository (the product's `main`), once an hour, and restarts when the files moved."""
import os
import re
import sys
import subprocess
import time
from pathlib import Path

from . import config, state


def update_once(run=subprocess.run, root=config.REPO_ROOT):
    """Fetches the install's repository; when main moved and the tree is untouched, fast-forwards it. Returns 'updated', 'current' or why nothing happened."""
    def git(*args):
        # safe.directory: the brain runs in proot, where the folder (bound from Termux) belongs to another user, and git then refuses it
        return run(["git", "-c", "safe.directory=*", "-C", str(root), *args], capture_output=True, text=True, timeout=120)
    try:
        if not (Path(root) / ".git").exists():
            return "not a git install"
        if git("status", "--porcelain").stdout.strip():
            return "local changes"
        fetched = git("fetch", "--quiet", "origin", "main")
        if fetched.returncode != 0:
            return "offline : " + " ".join((fetched.stderr or "").split())[-160:]
        here = git("rev-parse", "HEAD").stdout.strip()
        there = git("rev-parse", "FETCH_HEAD").stdout.strip()
        if not here or not there or here == there:
            return "current"
        return "updated" if git("merge", "--ff-only", "FETCH_HEAD").returncode == 0 else "cannot fast-forward"
    except (OSError, subprocess.SubprocessError) as err:
        return f"failed: {err}"


def disk_version():
    """The BACKEND_VERSION written in this file on disk now (None when it cannot be read)."""
    try:
        found = re.search(r"^BACKEND_VERSION = (\d+)", Path(config.__file__).read_text(encoding="utf-8"), re.M)
        return int(found.group(1)) if found else None
    except OSError:
        return None


def update_loop():
    time.sleep(120)
    while True:
        result = update_once()
        state.self_update_last.update(at=time.time(), result=result)
        if result == "current" and disk_version() not in (None, config.BACKEND_VERSION):
            result = "updated"      # the files were moved forward by something else (Termux's script) and this process still runs the old code
        if result == "updated":
            print(f"{time.strftime('%H:%M:%S')} Aiwa backend updated itself, restarting", flush=True)
            state.save()
            os.execv(sys.executable, [sys.executable, *sys.argv])
        time.sleep(config.SELF_UPDATE_EVERY)