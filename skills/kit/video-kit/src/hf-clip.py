#!/usr/bin/env python3
"""A clip from a free video generator hosted on Hugging Face (a ZeroGPU « Space »: Wan 2.2, LTX-Video…), called like any program through `gradio_client`.

  python3 hf-clip.py "<prompt>" out.mp4 --space owner/name [--api-name /generate] [--prompt-arg prompt] [--arg key=value …] [--image first.jpg --image-arg image]
  python3 hf-clip.py --space owner/name --show-api          what the Space asks for (the names of its parameters change from one Space to another)

  HF_TOKEN (environment): a free Hugging Face token (huggingface.co/settings/tokens). Without it the daily ZeroGPU quota is only a few minutes of computing, that is a few shots; with a free account it is a
  little more, with the paid plan much more. The quota is of computing time, not of video: a 5 s shot of Wan 2.2 takes minutes of it, LTX-Video far less.
  Honest limits: the Spaces change, move or queue, and their parameters are not the same: nothing here is tied to one Space. Exit codes: 0 done, 2 gradio_client missing or bad call, 3 quota reached, 4 failed."""
import json
import os
import shutil
import subprocess
import sys

QUOTA_WORDS = ("quota", "zerogpu", "exceeded", "too many requests", "429", "no gpu")


def parse(argv):
    opts = {"space": None, "api": None, "prompt_arg": "prompt", "args": {}, "image": None, "image_arg": "image", "show": False}
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--space", "--api-name", "--prompt-arg", "--image", "--image-arg", "--arg") and i + 1 < len(argv):
            v = argv[i + 1]
            i += 2
            if a == "--space": opts["space"] = v
            elif a == "--api-name": opts["api"] = v
            elif a == "--prompt-arg": opts["prompt_arg"] = v
            elif a == "--image": opts["image"] = v
            elif a == "--image-arg": opts["image_arg"] = v
            else:
                k, _, val = v.partition("=")
                opts["args"][k] = _typed(val)
        elif a == "--show-api":
            opts["show"] = True
            i += 1
        else:
            pos.append(a)
            i += 1
    return opts, pos


def _typed(text):
    """A number or a boolean when it looks like one, otherwise the text."""
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(text.lower(), text)


def find_video(result):
    """The first file named like a video in whatever the Space returned (a path, a tuple, a dict with a `video` or a `value`)."""
    if isinstance(result, str):
        return result if result.lower().endswith((".mp4", ".webm", ".mov")) else None
    if isinstance(result, dict):
        for key in ("video", "value", "path", "name"):
            found = find_video(result.get(key))
            if found:
                return found
        for value in result.values():
            found = find_video(value)
            if found:
                return found
        return None
    if isinstance(result, (list, tuple)):
        for item in result:
            found = find_video(item)
            if found:
                return found
    return None


def seconds_of(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def main(argv):
    opts, pos = parse(argv)
    if not opts["space"]:
        print(__doc__)
        return 2
    try:
        from gradio_client import Client, handle_file
    except ImportError:
        print("gradio_client manque : python3 -m pip install gradio_client", file=sys.stderr)
        return 2
    token = os.environ.get("HF_TOKEN") or None
    try:
        try:
            client = Client(opts["space"], hf_token=token)
        except TypeError:
            client = Client(opts["space"], token=token)
        if opts["show"]:
            client.view_api()
            return 0
        if len(pos) < 2:
            print("il faut un texte et un fichier de sortie : hf-clip.py \"<prompt>\" out.mp4 --space owner/name", file=sys.stderr)
            return 2
        prompt, out = pos[0], pos[1]
        kwargs = {opts["prompt_arg"]: prompt, **opts["args"]}
        if opts["image"]:
            kwargs[opts["image_arg"]] = handle_file(opts["image"])
        result = client.predict(api_name=opts["api"], **kwargs) if opts["api"] else client.predict(**kwargs)
    except Exception as err:
        text = str(err)
        if any(w in text.lower() for w in QUOTA_WORDS):
            print(json.dumps({"ok": False, "quota": True, "message": "Le quota gratuit de calcul du jour est atteint" + ("" if token else " (sans clé Hugging Face il n'est que de quelques minutes par jour : une clé gratuite sur huggingface.co/settings/tokens en donne plus)") + ". Réessaie demain" + (" ou prends l'abonnement." if token else "."), "detail": text[-200:]}, ensure_ascii=False))
            return 3
        print(json.dumps({"ok": False, "message": text[-300:]}, ensure_ascii=False))
        return 4
    video = find_video(result)
    if not video or not os.path.exists(video):
        print(json.dumps({"ok": False, "message": "le Space n'a rendu aucun fichier vidéo", "got": str(result)[:200]}, ensure_ascii=False))
        return 4
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    shutil.copyfile(video, out)
    print(json.dumps({"ok": True, "out": out, "seconds": seconds_of(out), "space": opts["space"], "token": bool(token)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
