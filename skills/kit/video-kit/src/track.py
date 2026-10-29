#!/usr/bin/env python3
"""Follows one thing in a real footage (a person, a face of a pair of glasses, a table) from a box drawn on one frame, and writes where it is at each frame. The film's page then places
an element (a profile, a halo, a label) on that position, as a function of time. OpenCV only (pip install opencv-python-headless numpy): no model to download.

  track.py footage.mp4 out.json --bbox=x,y,w,h [--at=0.0] [--smooth=0.35] [--every=1]

  --bbox     the thing to follow, in pixels of the footage, at the frame --at (seconds). Look at a frame first (ffmpeg -ss 2 -i footage.mp4 -frames:v 1 f.png), then draw the box.
  out.json   { fps, width, height, frames: [ { t, x, y, w, h, ok } … ] }  ok=false when the tracker lost it (the last good box is kept, never invented)
Honest limit: this follows a box, it does not recognise anyone. A fast turn, an occlusion or a cut loses it; the file says where (ok=false) so that the element can fade out there.
"""
import json, sys
import cv2


def arg(name, default=None):
    for a in sys.argv[1:]:
        if a.startswith(f'--{name}='):
            return a.split('=', 1)[1]
    return default


def make_tracker():
    for name in ('TrackerMIL_create', 'TrackerNano_create'):
        if hasattr(cv2, name):
            try:
                return getattr(cv2, name)()
            except Exception:
                continue
    if hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerCSRT_create'):
        return cv2.legacy.TrackerCSRT_create()
    raise SystemExit('no OpenCV tracker available in this build: pip install opencv-python-headless')


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith('--')]
    src, out = pos[0], pos[1]
    try:
        box = [float(v) for v in (arg('bbox') or '').split(',')]
    except ValueError:
        box = []
    if len(box) != 4:
        raise SystemExit('give --bbox=x,y,w,h (the thing to follow, in pixels, at the frame --at)')
    at, smooth, every = float(arg('at', 0)), float(arg('smooth', 0.35)), int(arg('every', 1))
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f'cannot read {src}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    start = int(round(at * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f'no frame at {at} s')
    tracker = make_tracker()
    tracker.init(frame, tuple(int(v) for v in box))
    rows = [{'t': round(start / fps, 3), 'x': box[0], 'y': box[1], 'w': box[2], 'h': box[3], 'ok': True}]
    last = list(box)
    i = start
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if (i - start) % every:
            continue
        found, b = tracker.update(frame)
        if found and b[2] > 4 and b[3] > 4:
            last = [smooth * last[k] + (1 - smooth) * b[k] for k in range(4)] if smooth else list(b)
            rows.append({'t': round(i / fps, 3), 'x': round(last[0], 1), 'y': round(last[1], 1), 'w': round(last[2], 1), 'h': round(last[3], 1), 'ok': True})
        else:
            rows.append({'t': round(i / fps, 3), 'x': round(last[0], 1), 'y': round(last[1], 1), 'w': round(last[2], 1), 'h': round(last[3], 1), 'ok': False})
    json.dump({'fps': fps, 'width': width, 'height': height, 'frames': rows}, open(out, 'w'))
    lost = sum(1 for r in rows if not r['ok'])
    print(json.dumps({'ok': True, 'frames': len(rows), 'lost': lost, 'out': out}))


main()
