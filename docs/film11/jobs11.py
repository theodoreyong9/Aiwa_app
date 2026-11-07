"""The list of the jobs that draw the pages of the screens frame by frame (one line = one command): python3 jobs11.py > jobs.txt ; xargs -P4 -I{} sh -c '{}' < jobs.txt"""
import json, os
T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timeline11.json')))
OUT = os.environ.get('UI', '/tmp/os11/ui'); SZ = {'1920x1080': (1920, 1080), 'p': (1080, 2400)}
jobs = []
def add(mode, w, h, t0, t1, chunks=4, png=False):
    n = max(1, chunks); step = (t1 - t0) / n
    for k in range(n):
        a = round(t0 + k * step, 4); b = round(t0 + (k + 1) * step, 4)
        jobs.append(f"{'PNG=1 ' if png else ''}node render_ui11.cjs {mode} {w} {h} {a} {b} {OUT}/{mode} 0 1")
S = T['scenes']; V = T['voice']
add('act1', 1920, 1080, 0, S[0]['s0'] + 0.6, 3)
for s in S:
    i = s['i']; a, b = s['s0'] + 0.9, s['out'][1] + 0.05
    if i in (1, 3): add('s%d' % i, 1080, 2400, a, b, 3)
    elif i == 5:
        for m in ('s5a', 's5b', 's5c'): add(m, 1080, 2400, a, b, 3)
    else: add('s%d' % i, 1920, 1080, a, b, 3)
add('act3a', 1920, 1080, T['act3']['rules'][0] - .1, T['act3']['shatter'] + .1, 2)
add('act3b', 1920, 1080, T['act3']['logo'][0] - .3, T['total'], 2)
D = json.load(open('/tmp/os11/voice/durations.json'))
for i in range(1, 7):
    t0 = V['n_s%d' % i]; add('ov', 1920, 1080, t0 - .25, t0 + D['n_s%d' % i] + 2.0, 1, png=True)
print('\n'.join(jobs))
