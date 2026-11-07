"""Film 12: the timeline (one source of truth) from the durations of the voices; fills the page of the screens (ui12.built.html).  python3 build11.py [durations.json]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/os11/voice/durations.json'))
r2 = lambda x: round(x, 2)
V, T = {}, {'fps': 24, 'width': 1920, 'height': 1080}
# act 1: the question
V['n1'] = .6; V['n2'] = V['n1'] + D['n1'] + .55; V['n3'] = V['n2'] + D['n2'] + .85; V['n4'] = V['n3'] + D['n3'] + .9
T['act1'] = {'cards': [V['n1'], V['n1'] + D['n1']], 'ask': [V['n2'], V['n2'] + D['n2']], 'you': [V['n3'], V['n3'] + D['n3']], 'imagine': [V['n4'], V['n4'] + D['n4']]}
# the six worlds: each one is a room with a screen, the previous world is on that screen, the camera goes back, dives into the screen, the voice asks, the screen does it
WORK = [2.1, 3.3, 3.1, 3.1, 2.3, 3.3]
ENV = [('R1', 'phone'), ('R2', 'tv'), ('R4', 'phone'), ('R0', 'tv'), ('R5', 'phones'), ('R3', 'tv')]
s0 = V['n4'] + 1.6; S = []
for i, (env, kind) in enumerate(ENV, 1):
    n, u, a = 'n_s%d' % i, 'u_s%d' % i, 'a_s%d' % i
    V[n] = s0 + .55
    V[u] = max(V[n] + D[n] + .35, s0 + 3.4)
    ue = V[u] + D[u]
    V[a] = ue + .1 + WORK[i - 1]
    ae = V[a] + D[a]
    out0 = ae + .55
    sc = {'i': i, 'env': env, 'kind': kind, 's0': r2(s0), 'dive': [r2(V[u] - 1.45), r2(V[u] - .1)],
          'cmd': [r2(V[u]), r2(ue)], 'work': [r2(ue + .1), r2(V[a])], 'agent': [r2(V[a]), r2(ae)], 'out': [r2(out0), r2(out0 + 1.8)]}
    S.append(sc); s0 = out0 + 1.8 - .25
T['scenes'] = S
e6 = S[-1]['out'][1] - .2
V['n5'] = e6 + .35; V['n6'] = V['n5'] + D['n5'] + 1.0
T['act3'] = {'rules': [e6, V['n6']], 'shatter': r2(V['n6'] + .12)}
V['n7'] = V['n6'] + 1.95; V['n8'] = V['n7'] + D['n7'] + .35
T['act3']['logo'] = [r2(V['n7'] - .2), r2(V['n8'] + D['n8'] + 2.6)]; T['act3']['universe'] = [r2(V['n6'] + .12), r2(V['n8'] + D['n8'] + 3.0)]
T['voice'] = {k: r2(v) for k, v in V.items()}
T['total'] = r2(V['n8'] + D['n8'] + 3.4)
json.dump(T, open(os.path.join(HERE, 'timeline12.json'), 'w'), indent=1)
ui = open(os.path.join(HERE, 'ui12.html')).read() if os.path.exists(os.path.join(HERE, 'ui12.html')) else ''
open(os.path.join(HERE, 'ui12.built.html'), 'w').write(ui.replace('__TIMELINE__', json.dumps(T)).replace('__DURATIONS__', json.dumps(D)))
print('total', T['total'], 'scenes', [(s['i'], s['s0'], s['out'][1]) for s in S])
