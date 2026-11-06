"""Film 10, the sound: the voices (placed on the timeline), the effects (synthesised, each on something the picture does).
   python3 sound10.py <voices dir> <out dir>      -> <out>/vo.wav  <out>/sfx.wav"""
import json, os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SR = 44100
TL = json.load(open(os.path.join(HERE, 'timeline10.json'))); V = TL['voice']; 
vdir, odir = sys.argv[1], sys.argv[2]; os.makedirs(odir, exist_ok=True)
N = int((TL['total'] + 1) * SR); rng = np.random.default_rng(10)

def read(p):
    w = wave.open(p); n = w.getnframes(); x = np.frombuffer(w.readframes(n), np.int16).astype(float) / 32768
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
    if w.getframerate() != SR:
        k = SR / w.getframerate(); x = np.interp(np.arange(int(len(x) * k)) / k, np.arange(len(x)), x)
    return x
def write(p, st):
    st = np.clip(st, -1, 1); w = wave.open(p, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()
def put(buf, sig, t, gain=1.0, pan=0.0):
    i = int(t * SR); n = min(len(sig), len(buf) - i)
    if i < 0 or n <= 0: return
    buf[i:i + n, 0] += sig[:n] * gain * (1 - max(0, pan)); buf[i:i + n, 1] += sig[:n] * gain * (1 + min(0, pan))
tt = lambda d: np.arange(int(d * SR)) / SR
def blip(f, d=.25, a=.004): t = tt(d); return np.sin(2 * np.pi * f * t) * np.minimum(1, t / a) * np.exp(-t / (d * .3))
def bell(f, d=1.2): t = tt(d); return sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t / (d * .25 / k ** .6)) * a for k, a in ((1, 1), (2.76, .35), (5.4, .15))) * np.minimum(1, t / .003)
def lp(x, k):
    y = np.zeros_like(x); s = 0.0
    for i, v in enumerate(x): s += k * (v - s); y[i] = s
    return y
def whoosh(d, f0, f1):  # air that opens
    t = tt(d); n = rng.standard_normal(len(t)); f = np.geomspace(f0, f1, len(t)); mod = np.sin(np.cumsum(2 * np.pi * f / SR)) * .5 + .5
    x = np.convolve(n, np.ones(24) / 24, 'same') * mod; return x * np.sin(np.pi * np.linspace(0, 1, len(t))) ** 2
def sub(f, d, drop=.5): t = tt(d); ff = f * (1 - drop * (1 - np.exp(-t * 3))); return np.sin(np.cumsum(2 * np.pi * ff / SR)) * np.exp(-t / (d * .35)) * np.minimum(1, t / .01)
def tick(d=.05, f=2400): t = tt(d); return rng.standard_normal(len(t)) * np.exp(-t / .006) * .6 + np.sin(2 * np.pi * f * t) * np.exp(-t / .01) * .4
def hum(d, f=60): t = tt(d); return (np.sin(2 * np.pi * f * t) + .4 * np.sin(2 * np.pi * f * 2 * t)) * np.minimum(1, t / .6) * np.minimum(1, (d - t) / .8)

# ---- the voices: the user a little lower and at the side, the agent brighter and in front
vo = np.zeros((N, 2)); AG = {c['id'] for c in json.load(open(os.path.join(HERE, 'cues10.json'))) if c['who'] == 'A'}
for cid, t0 in V.items():
    p = os.path.join(vdir, cid + '.wav')
    if not os.path.exists(p): print('no voice', cid); continue
    x = read(p); agent = cid in AG
    if agent: put(vo, x, t0, 1.0, .1)
    else: put(vo, lp(x, .55) * .9 + x * .15, t0, .95, -.12)
write(os.path.join(odir, 'vo.wav'), vo)

# ---- the effects
fx = np.zeros((N, 2)); P1, P2, P3, R0, R1, R2, R3 = (TL[k] for k in ('P1', 'P2', 'P3', 'R0', 'R1', 'R2', 'R3'))
put(fx, bell(1318, 1.6), V['wake'] - .15, .35, .2); put(fx, blip(880, .2), V['wake'], .3, .2)                    # the phone wakes
put(fx, bell(987, 1.2), V['listen'] - .1, .25, .2)
put(fx, lp(whoosh(R0['push'][1] - R0['push'][0], 120, 1200), .08), R0['push'][0], .5, 0)                     # the camera goes to the television
put(fx, sub(55, 2.2, .3), R0['tvOn'][0], .8); put(fx, hum(3.6, 58), R0['tvOn'][0], .06)                       # the television comes on
put(fx, bell(1480, 1.4), TL['TV0']['splash'][0] + .2, .22, -.2)
for i in range(12): put(fx, tick(.04, 3000 + 130 * i), TL['TV0']['work'][0] + .8 + i * (TL['TV0']['work'][1] - TL['TV0']['work'][0] - 1.4) / 12, .12, -.1)   # the documents appear
put(fx, bell(1568, 1.2), TL['TV0']['ready'], .3, 0)                                                            # « c'est fait »
def zoom(a, b, g=.5, lo=150, hi=1500, pan=0): put(fx, lp(whoosh(b - a, lo, hi), .1), a, g, pan)
zoom(*R1['back'], .55); zoom(*R1['dive'], .4, 200, 2400); put(fx, sub(70, 1.2), R1['dive'][1] - .3, .4)
put(fx, tick(.07, 3200), P1['list'], .2); put(fx, blip(740, .14), P1['open'], .18, .2); put(fx, blip(988, .14), P1['next'], .18, .2)
zoom(*R1['out'], .5); zoom(*R2['out'], .55, 120, 1800)
put(fx, lp(whoosh(R2['pick'][1] - R2['pick'][0], 300, 3000), .15), R2['pick'][0], .35); put(fx, sub(80, 1.4), R2['pick'][0] + .2, .35)   # the phone is taken
zoom(*R2['toNative'], .4, 200, 2400)
put(fx, tick(.06, 3300), P2['tapTargets'], .3, .3); put(fx, blip(1100, .08), P2['tapTargets'], .15, .3)
put(fx, tick(.06, 3100), P2['openTarget'], .3, .3); put(fx, bell(1318, 1.0), P2['mail'], .22, .2)
zoom(*P2['back'], .35, 200, 1800); put(fx, tick(.06, 3300), P2['tapAttach'], .3, .3); put(fx, blip(1200, .1), P2['tapAttach'], .15, .3)
zoom(*P2['out'], .55, 120, 1800); zoom(*R3['out'], .55, 120, 1800); put(fx, sub(60, 2.4, .3), R3['out'][0] + .4, .5)
zoom(*P3['toNative'], .4, 200, 2400); put(fx, bell(1480, 1.2), P3['improve'][0] + 1.6, .2, .2)
for i in range(4): put(fx, blip(660 + 110 * i, .3), P3['tracker'][0] + .5 + i * .25, .16, -.1)                  # the figures of the follow-up
zoom(*P3['back'], .5, 150, 2000); zoom(*P3['dive'], .4, 200, 2400)
for i in range(5): put(fx, blip(523 + 80 * i, .25), P3['scenario'][0] + 1.8 + i * .55, .14, .1)                # the steps of the scenario
for i in range(4): put(fx, lp(whoosh(.5, 400, 2800), .2), P3['swipe'][0] + i * .55 + .3, .3, -.2 if i % 2 else .2)  # the cards pass
put(fx, bell(1046, 1.4), P3['match'], .35, 0); put(fx, bell(1568, 1.4), P3['match'] + .14, .25, .2)             # match
put(fx, lp(whoosh(P3['scan'][1] - P3['scan'][0], 300, 3500), .12), P3['scan'][0], .35)                          # scan
put(fx, lp(whoosh(1.0, 400, 3000), .15), P3['send'], .4); put(fx, bell(1760, 1.2), P3['send'] + .5, .2, .2)    # the aiwa are sent
put(fx, sub(50, 3.0, .2), P3['door'] - .2, .8); put(fx, lp(whoosh(P3['passage'][1] - P3['passage'][0], 100, 2600), .06), P3['passage'][0], .7, 0)   # the passage opens
put(fx, bell(784, 3.4), P3['door'] + .3, .3, 0); put(fx, bell(1175, 3.0), P3['door'] + .6, .22, .2)
put(fx, sub(40, 3.2, .1), P3['stop'], .9)                                                                      # the video stops
put(fx, bell(880, 3.0), TL['end']['card'][0] + .2, .3, 0); put(fx, bell(1318, 3.0), TL['end']['card'][0] + .5, .2, .2)
write(os.path.join(odir, 'sfx.wav'), fx); print('vo.wav, sfx.wav ->', odir)
