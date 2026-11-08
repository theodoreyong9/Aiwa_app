"""Film 13 (the punch): the timeline (one source of truth) from the durations of the voices; fills the page (ui13.built.html).  python3 build13.py [durations.json]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/os13/voice/durations.json')); r2 = lambda x: round(x, 2)
V = {}; T = {'fps': 24, 'width': 1920, 'height': 1080}
V['q1'] = 1.0; V['q2'] = V['q1'] + D['q1'] + .3; V['q3'] = V['q2'] + D['q2'] + .3
T['hook'] = {'q1': [V['q1'], V['q1'] + D['q1']], 'q2': [V['q2'], V['q2'] + D['q2']], 'q3': [V['q3'], V['q3'] + D['q3']]}
slam = V['q3'] + D['q3'] + .15                                   # the title « imposer vos règles » is struck here
T['slam'] = r2(slam)
EXTRA = {'b2': 4.2, 'b3': 3.9, 'b4': 3.9}
t = slam + 1.0; beats = []
for k in ('b2', 'b3', 'b4'):
    V[k] = t + .7; end = V[k] + D[k] + EXTRA[k]
    beats.append({'k': k, 's0': r2(t), 'voice': [r2(V[k]), r2(V[k] + D[k])], 'work': [r2(V[k] + D[k] * .5), r2(V[k] + D[k] + 2.2)], 'end': r2(end)}); t = end
T['beats'] = beats
V['e1'] = t + .9; V['e2'] = V['e1'] + D['e1'] + .5
T['end'] = {'black': r2(t), 'logo': r2(V['e1'] - .1), 'promise': r2(V['e2'])}
T['voice'] = {k: r2(v) for k, v in V.items()}; T['total'] = r2(V['e2'] + D['e2'] + 3.2)
json.dump(T, open(os.path.join(HERE, 'timeline13.json'), 'w'), indent=1)
ui = open(os.path.join(HERE, 'ui13.html')).read() if os.path.exists(os.path.join(HERE, 'ui13.html')) else ''
open(os.path.join(HERE, 'ui13.built.html'), 'w').write(ui.replace('__TIMELINE__', json.dumps(T)).replace('__DURATIONS__', json.dumps(D)))
print('total', T['total'], [(b['k'], b['s0'], b['end']) for b in beats], T['slam'])
