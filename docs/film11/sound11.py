"""Film 11, the sound: the voices on the timeline, then the effects (synthesised, each on something the picture does), with a drone that tightens during the rules and a glass break.
   python3 sound11.py <voices dir> <out dir>     -> <out>/vo.wav  <out>/sfx.wav"""
import json, os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SR = 44100
TL = json.load(open(os.path.join(HERE, 'timeline11.json'))); V = TL['voice']; S = TL['scenes']; A1 = TL['act1']; A3 = TL['act3']
CUES = json.load(open(os.path.join(HERE, 'cues11.json'))); WHO = {c['id']: c['who'] for c in CUES}
vdir, odir = sys.argv[1], sys.argv[2]; os.makedirs(odir, exist_ok=True)
N = int((TL['total'] + 2) * SR); rng = np.random.default_rng(11)

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
def whoosh(d, f0, f1):
    t = tt(d); n = rng.standard_normal(len(t)); f = np.geomspace(f0, f1, len(t)); mod = np.sin(np.cumsum(2 * np.pi * f / SR)) * .5 + .5
    x = np.convolve(n, np.ones(24) / 24, 'same') * mod; return x * np.sin(np.pi * np.linspace(0, 1, len(t))) ** 2
def sub(f, d, drop=.5): t = tt(d); ff = f * (1 - drop * (1 - np.exp(-t * 3))); return np.sin(np.cumsum(2 * np.pi * ff / SR)) * np.exp(-t / (d * .35)) * np.minimum(1, t / .01)
def tick(d=.05, f=2400): t = tt(d); return rng.standard_normal(len(t)) * np.exp(-t / .006) * .6 + np.sin(2 * np.pi * f * t) * np.exp(-t / .01) * .4
def riser(d, f0=200, f1=3200): t = tt(d); f = np.geomspace(f0, f1, len(t)); ph = np.cumsum(2 * np.pi * f / SR); return (np.sin(ph) + .5 * np.sin(ph * 1.5) + .3 * rng.standard_normal(len(t)) * np.linspace(0, 1, len(t))) * np.linspace(0, 1, len(t)) ** 2
def pad(freqs, d, a=1.2):
    t = tt(d); x = sum(np.sin(2 * np.pi * f * t + i) + .4 * np.sin(2 * np.pi * f * 2.003 * t) for i, f in enumerate(freqs)); return x / len(freqs) * np.minimum(1, t / a) * np.minimum(1, (d - t) / 1.5)
def glass(d=3.0):
    t = tt(d); x = rng.standard_normal(len(t)) * np.exp(-t / .25)
    x = x - lp(x, .08)                                         # high-pass: the sharp part
    for _ in range(90):
        f = 2500 + rng.random() * 7000; t0 = rng.random() * .5; i = int(t0 * SR); k = tt(d - t0)[:len(t) - i]; x[i:i + len(k)] += np.sin(2 * np.pi * f * k) * np.exp(-k / (.04 + rng.random() * .25)) * (.04 + .1 * rng.random())
    return x

# ---- the voices: the narrator in the middle, the person at the left (a little closer), the agent at the right
vo = np.zeros((N, 2))
for cid, t0 in V.items():
    p = os.path.join(vdir, cid + '.wav')
    if not os.path.exists(p): print('no voice', cid); continue
    w = WHO[cid]; put(vo, read(p), t0, 1.0 if w == 'N' else .95, {'N': 0, 'U': -.16, 'A': .16}[w])
write(os.path.join(odir, 'vo.wav'), vo)

# ---- the effects
fx = np.zeros((N, 2))
# act 1: a pulse in the dark, a tick for each thing the assistant does, the question, the liquid that takes a shape
put(fx, sub(48, 3.0, .2), 0.15, .7)
c0, cd = A1['cards']
for r in (.10, .26, .40, .54, .70): put(fx, tick(.05, 2600), c0 + cd * r - .05, .18, (r - .4)); put(fx, blip(660 + r * 500, .25), c0 + cd * r - .05, .12, (r - .4))
put(fx, riser(A1['ask'][0] - c0 - cd + .4, 150, 2200), c0 + cd - .2, .35)
put(fx, sub(55, 2.4), A1['ask'][0] - .05, .8); put(fx, bell(784, 2.4), A1['ask'][0] + .6, .22)
y0, y1 = A1['you']
put(fx, lp(whoosh(1.2, 300, 2000), .1), y0 + (y1 - y0) * .34, .45); put(fx, pad([196, 247, 294, 370], 5.0, 1.8), y0 + (y1 - y0) * .34, .22)
for i in range(8): put(fx, blip(880 + 110 * i, .3), y0 + (y1 - y0) * (.62 + .04 * i), .1, (i - 4) / 6)
put(fx, bell(1046, 2.0), A1['imagine'][0], .3); put(fx, sub(60, 2.0), A1['imagine'][0] - .05, .6)
# the worlds
for s in S:
    i = s['i']; b0, b1 = s['back']; d0, d1 = s['dive']; o0, o1 = s['out']; c0_, c1_ = s['cmd']; w0, w1 = s['work']; a0, a1 = s['agent']
    put(fx, lp(whoosh(b1 - b0, 150, 1800), .1), b0, .5, 0); put(fx, sub(62, 1.6, .3), b0, .45)                 # the camera goes back
    put(fx, lp(whoosh(d1 - d0, 200, 2600), .1), d0, .4, 0)                                                      # and into the screen
    put(fx, bell(1318, 1.4), c0_ - .15, .22, .2); put(fx, blip(880, .16), c0_ - .15, .22)                         # the ear opens
    for k in range(int((c1_ - c0_) * 7)): put(fx, tick(.025, 3500 + (k * 137) % 900), c0_ + k / 7.0, .05, -.1)   # the words as they are heard
    put(fx, bell(1568, 1.2), c1_ + .1, .18, .2)                                                                    # understood
    n = int((w1 - w0) / .22)
    for k in range(n): put(fx, tick(.03, 2800 + 90 * (k % 7)), w0 + k * .22, .07, ((k % 5) - 2) / 8)               # the work
    put(fx, bell(1046, 1.6), a0 - .02, .3, .1); put(fx, bell(1568, 1.8), a0 + .1, .2, .25)                         # done
    put(fx, lp(whoosh(o1 - o0, 130, 1900), .1), o0, .5, 0)                                                      # back to the room
    if i == 2: put(fx, riser(w1 - w0, 300, 2800), w0, .22); put(fx, sub(50, 1.2), w1, .4)
    if i == 4:
        for k in range(8): put(fx, bell(1400 + 70 * k, 1.1), w0 + .4 + k * .4, .09, np.sin(k))
    if i == 5:
        for k in range(14): put(fx, bell(2000 + 110 * (k % 6), 1.6), a0 + .2 + k * .15, .05, np.sin(k * 1.3))      # snow
    if i == 6:
        put(fx, lp(whoosh(w1 - w0, 300, 4200), .1), w0, .35); put(fx, pad([261, 329, 392, 523], 3.0, .3), w1 - .6, .12)
# act 3: the cold dialogs, a drone that tightens, the break
r0, r1 = A3['rules']; sp = (r1 - r0 - .3) / 24
dr = r1 - r0 + .4; t = tt(dr); drone = (np.sin(2 * np.pi * 55 * t) + .6 * np.sin(2 * np.pi * 58.3 * t) + .3 * np.sin(2 * np.pi * 110.7 * t)) * np.linspace(.2, 1, len(t)) ** 2 * .5
put(fx, drone, r0 - .2, .55)
put(fx, riser(dr, 120, 5000), r0 - .1, .3)
for k in range(24): put(fx, tick(.04, 1800 + 140 * (k % 5)), r0 + .06 + k * sp * .9, .22, (rng.random() - .5) * .8); (put(fx, blip(220 + 30 * (k % 4), .18), r0 + .06 + k * sp * .9, .12) if k % 3 == 0 else None)
put(fx, sub(44, 1.6, .1), r0 + .02, .5)
sh = A3['shatter']
put(fx, glass(3.2), sh, .9); put(fx, sub(36, 3.2, .1), sh - .02, 1.0); put(fx, lp(whoosh(1.4, 200, 6000), .2), sh - .1, .6)
n7 = V['n7']
put(fx, pad([130.8, 196, 261.6, 329.6, 392], 7.0, 1.8), n7 - .5, .26); put(fx, bell(784, 4.5), n7 + .05, .3, 0); put(fx, sub(52, 3.0, .15), n7 - .05, .8)
put(fx, bell(1318, 4.0), V['n8'] + .2, .22, .2); put(fx, bell(1046, 5.0), V['n8'] + .8, .2, -.2)
write(os.path.join(odir, 'sfx.wav'), fx); print('vo.wav, sfx.wav ->', odir)
