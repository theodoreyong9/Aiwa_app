"""The list of the jobs that draw the pages of the screens frame by frame (one line = one command): python3 jobs12.py > jobs.txt ; xargs -P4 -I{} sh -c '{}' < jobs.txt"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'timeline12.json'))); D = json.load(open(os.environ.get('DURATIONS', '/tmp/os11/voice/durations.json')))
OUT = os.environ.get('UI', '/tmp/os12/ui'); jobs = []
def add(mode, w, h, t0, t1, chunks=1, png=False):
    step = (t1 - t0) / chunks
    for k in range(chunks):
        a = round(t0 + k * step, 4); b = round(t0 + (k + 1) * step, 4)
        jobs.append(f"{'PNG=1 ' if png else ''}node render_ui12.cjs {mode} {w} {h} {a} {b} {OUT}/{mode}")
S = T['scenes']; V = T['voice']
add('act1', 1920, 1080, 0, S[0]['s0'] + .7, 3)
for s in S:
    i = s['i']; a, b = max(0, s['s0'] - .45), s['out'][1] + .1
    if i == 1: add('s1', 1080, 2400, a, b, 3)
    elif i == 2: add('s2', 1920, 1080, a, b, 3)
    elif i == 3: add('s3', 1080, 2400, a, b, 1)                       # the real profile page: one run, so that its liquid moves without a break
    elif i == 4: add('s4', 1920, 1080, a, b, 3)
    elif i == 5: add('s5a', 1080, 2400, a, b, 3); add('s5b', 1080, 2400, a, b, 1); add('s5c', 1080, 2400, a, b, 1)
    else: add('s6', 1920, 1080, a, b, 3)
add('act3a', 1920, 1080, T['act3']['rules'][0] - .1, T['act3']['shatter'] + .1, 2)
add('logo', 1920, 1080, T['act3']['logo'][0] - .2, T['total'], 2, png=True)
for i in range(1, 7):
    t0 = V['n_s%d' % i]; add('ov', 1920, 1080, t0 - .3, t0 + D['n_s%d' % i] + 2.0, 1, png=True)
print('\n'.join(jobs))
