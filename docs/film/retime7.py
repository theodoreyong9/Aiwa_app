"""Film 7 = film 6 with the passage of the phone screen sent to the television cut out (80 frames, a short dissolve over the cut) and the pause on the television changed (the own application, the matches, the super agents: no more scenarios and scoring of other profiles).
   python3 retime7.py OUT_DIR   writes OUT_DIR/00000.jpg … and OUT_DIR/anchors.json
Sources: /tmp/os3/f6 (the frames of film 6, without the overlay), /tmp/os3/b28w (the pause, redone)."""
import json, os, subprocess, sys
OUT = sys.argv[1]; F6, WINDIR = '/tmp/os3/f6', '/tmp/os3/b28w'
INS0, INSN = 400, 96                       # film 7: 2 s more (the phone idle, slowed to half speed over film-6 frames 400..448) so that the voice has the time to say that it draws schemas
CUT0, CUTN = 474, 80                       # film 6: the phone is dark at 474, the television shows the stream until 554: the 80 frames in between go
FADE = 8                                   # the dissolve starts 8 frames before the cut
W0, W1 = 1068, 1476                        # the pause in film 6 (it keeps its 17 s)
TOTAL = 1884 - CUTN + INSN // 2
os.makedirs(OUT, exist_ok=True)
anchors6 = json.load(open(os.path.join(F6, 'anchors.json')))
anchors = {}
def src6(n): return os.path.realpath(os.path.join(F6, '%05d.jpg' % n))
def pos(m):                                  # the film-6 frame (a real number) that frame m of film 7 shows
    if m < INS0: return float(m)
    if m < INS0 + INSN: return INS0 + (m - INS0) / 2
    return float(m - INSN // 2 + (CUTN if m - INSN // 2 >= CUT0 else 0))
for m in range(TOTAL):
    dst = os.path.join(OUT, '%05d.jpg' % m)
    if os.path.lexists(dst): os.remove(dst)
    p = pos(m); n = int(p)
    if W0 <= n < W1:
        src = os.path.join(WINDIR, '%05d.jpg' % (n - W0)); anchors[str(m)] = {}
    elif p != n:                                                   # half a frame: the two around are mixed
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src6(n), '-i', src6(n + 1), '-filter_complex', 'blend=all_expr=(A+B)/2', '-q:v', '2', dst], check=True)
        anchors[str(m)] = anchors6.get(str(n), {}); continue
    elif m >= INS0 + INSN and CUT0 - FADE <= m - INSN // 2 < CUT0:
        k = (m - INSN // 2 - (CUT0 - FADE) + 1) / (FADE + 1)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src6(n), '-i', src6(n + CUTN), '-filter_complex', f'blend=all_expr=A*(1-{k:.4f})+B*{k:.4f}', '-q:v', '2', dst], check=True)
        anchors[str(m)] = anchors6.get(str(n + CUTN if k > .5 else n), {}); continue
    else:
        src = src6(n); anchors[str(m)] = anchors6.get(str(n), {})
    assert os.path.getsize(src) > 2000, src
    os.symlink(src, dst)
json.dump(anchors, open(os.path.join(OUT, 'anchors.json'), 'w'))
print('frames', TOTAL)
