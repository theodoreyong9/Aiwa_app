"""Cast to the television: « envoie la vidéo sur la TV quand c'est fini ». The wish waits for a video that did not exist when it was made."""
import time

from . import config, files, state


def cast_register(tv):
    """The person asked for the video to go to the television (named `tv`, or empty) as soon as Claude has made it: the videos that exist now are not the ones."""
    marks = files.newest_video_marks()
    with state.lock:
        state.cast_pending.update(on=True, tv=str(tv or "").strip()[:60], since=time.time(), known=marks)
    return {"ok": True}


def cast_clear():
    with state.lock:
        state.cast_pending.update(on=False)
    return {"ok": True}


def ready(now=None):
    """{tv, name, url} when a video that was not there at the request now is, else None. The phone then casts it and clears the wish."""
    now = time.time() if now is None else now
    with state.lock:
        pending = dict(state.cast_pending)
    if not pending["on"]:
        return None
    if now - pending["since"] > config.CAST_WAIT_SECONDS:
        cast_clear()
        return None
    files.forget()
    known = {(k[0], k[1]) for k in pending["known"]}
    for video in files.listing(None)["items"]["video"]:
        if (video["file"], video["ts"]) not in known and video["url"].startswith("https://"):
            return {"tv": pending["tv"], "name": video["title"], "url": video["url"]}
    return None
