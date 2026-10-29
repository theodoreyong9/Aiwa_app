"""Puts the frames of film 5 in order (the film of v4 re-cut: the voice section is faster, the campaign is new, a pause of 17 s on the television shows what comes after the profile).
   python3 retime.py OUT_DIR     writes OUT_DIR/00000.jpg … (links, or blends where the old time is played faster) and OUT_DIR/anchors.json
Sources: /tmp/os3/f4 (the old film, frame by frame: b26 where it was redone, b24 elsewhere), /tmp/os3/b27 (the new campaign), /tmp/os3/b27w (the pause)."""
import json, os, subprocess, sys
OUT = sys.argv[1]; F4, CAMP, WINDIR = '/tmp/os3/f4', '/tmp/os3/b27', '/tmp/os3/b27w6'
PTS = [(0, 0), (379, 379), (408, 420), (466, 552), (540, 672), (554, 686)]            # (new frame, old frame): the old time is played faster between them
SHIFT, W0, WN, W1, OLD_AFTER = 132, 1068, 408, 1476, 1200                               # new n = old n - 132 up to the pause; the pause; then the old film goes on from old frame 1200
TOTAL = W1 + (1608 - OLD_AFTER)
os.makedirs(OUT, exist_ok=True)

def old_src(i):                                              # a frame of the old film, the campaign being the new one
    i = max(0, min(1607, int(round(i))))
    return os.path.join(CAMP if 860 <= i < 992 else F4, '%05d.jpg' % i)

def old_pos(n):                                              # the old frame (a real number) that new frame n shows, or None in the pause
    if n < PTS[-1][0]:
        for (n0, o0), (n1, o1) in zip(PTS, PTS[1:]):
            if n <= n1: return o0 + (n - n0) * (o1 - o0) / (n1 - n0)
    if n < W0: return n + SHIFT
    if n < W1: return None
    return n - W1 + OLD_AFTER

anchors_old = json.load(open('/tmp/os3/anchors4.json'))
camp_a = '/tmp/os3/b27/anchors.00860.json'
if os.path.exists(camp_a):
    for k, v in json.load(open(camp_a)).items():
        if 860 <= int(k) < 992: anchors_old[k] = v
    for k in range(860, 992): anchors_old.setdefault(str(k), {})
anchors = {}
for n in range(TOTAL):
    dst = os.path.join(OUT, '%05d.jpg' % n)
    p = old_pos(n)
    if p is None:
        k = n - W0; src = os.path.join(WINDIR, '%05d.jpg' % k); anchors[str(n)] = {}
    else:
        anchors[str(n)] = anchors_old.get(str(int(round(p))), {})
        nxt = old_pos(n + 1) if n + 1 < TOTAL else None
        rate = (nxt - p) if nxt is not None else 1.0
        if abs(rate - 1.0) < .05: src = old_src(p)
        else:                                                # played faster: a short shutter, the frames around the position are mixed
            if os.path.exists(dst) and not os.path.islink(dst) and os.path.getsize(dst) > 2000: continue
            h = max(1, int(round(rate / 2))); ps = sorted({p - rate / 4 * 1.0, p, p + rate / 4 * 1.0}); files = list(dict.fromkeys(old_src(x) for x in ps))
            if len(files) == 1:
                if os.path.lexists(dst): os.remove(dst)
                os.symlink(files[0], dst); continue
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y'] + sum((['-i', f] for f in files), []) + ['-filter_complex', f'mix=inputs={len(files)}', '-q:v', '2', dst], check=True)
            continue
    if os.path.lexists(dst): os.remove(dst)
    assert os.path.getsize(src) > 2000, src
    os.symlink(src, dst)
json.dump(anchors, open(os.path.join(OUT, 'anchors.json'), 'w'))
print('frames', TOTAL)
