"""Film 13, the sound: the voices on the timeline, then the effects (synthesised, each on something the picture does), with a drone that tightens during the rules and a glass break.
   python3 sound11.py <voices dir> <out dir>     -> <out>/vo.wav  <out>/sfx.wav"""
import json, os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); SR = 44100
TL = json.load(open(os.path.join(HERE, 'timeline13.json'))); V = TL['voice']; HK = TL['hook']; BT = TL['beats']; EN = TL['end']
CUES = json.load(open(os.path.join(HERE, 'cues13.json'))); WHO = {c['id']: c['who'] for c in CUES}
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

# ---- the voices (the narrator, in the middle)
vo = np.zeros((N, 2))
for cid, t0 in V.items():
    p = os.path.join(vdir, cid + '.wav')
    if os.path.exists(p): put(vo, read(p), t0, 1.0, 0)
write(os.path.join(odir, 'vo.wav'), vo)

# ---- the effects: every cut is a blow
fx = np.zeros((N, 2))
def hit(t, g=1.0):
    put(fx, sub(46, 1.6, .25), t, .95 * g); put(fx, lp(whoosh(.5, 600, 6000), .35), t - .12, .5 * g)
    n = tt(.4); c = rng.standard_normal(len(n)) * np.exp(-n / .05); put(fx, c - lp(c, .1), t, .35 * g)
put(fx, sub(40, 2.0, .15), 0.15, .7)
# Q1: speed, then the lines stop dead
q1 = HK['q1']; put(fx, riser(q1[1] - q1[0] + .1, 200, 5200), q1[0] - .05, .42); hit(q1[0] - .02, .9)
put(fx, bell(1480, 1.6), q1[1] + .02, .0)
# Q2: the points tick, then snap into a line
q2 = HK['q2']; hit(q2[0] - .02, .8)
for k in range(30): put(fx, tick(.025, 2200 + 55 * k), q2[0] + 1.0 + k * .018, .12, (k - 15) / 20)
put(fx, bell(1318, 1.6), q2[0] + 1.62, .35); put(fx, sub(70, 1.0), q2[0] + 1.62, .5)
# Q3: the rules close in, then the blow
q3 = HK['q3']; hit(q3[0] - .02, .8)
put(fx, riser(TL['slam'] - q3[0] + .1, 80, 4200), q3[0], .5)
for k in range(9): put(fx, tick(.04, 1700 + 120 * (k % 4)), q3[0] + k * .35, .16, (k % 3 - 1) / 2)
put(fx, np.zeros(10), 0, 0)
sl = TL['slam']; hit(sl, 1.7); put(fx, sub(34, 3.0, .1), sl - .02, 1.1); put(fx, bell(220, 3.0), sl, .3)
# the beats
for i, B in enumerate(BT):
    s0 = B['s0']; v0, v1 = B['voice']; w0, w1 = B['work']
    hit(s0 - .02, 1.0); put(fx, lp(whoosh(.7, 300, 5200), .25), s0 - .35, .6)
    if i == 0:
        put(fx, lp(whoosh(1.1, 300, 4200), .12), w0 - .5, .4); put(fx, bell(1568, 1.4), w0 + .6, .28, .3)           # the page is read, then rewritten
        for k in range(26): put(fx, tick(.02, 3300), w0 + .2 + k * .06, .06, .4)
    if i == 1:
        for k in range(8): put(fx, tick(.04, 2500 + 90 * k), s0 + 1.2 + k * .34, .2, (k % 2) - .5); put(fx, blip(660 + 70 * k, .2), s0 + 1.2 + k * .34, .12, (k % 2) - .5)
        put(fx, tick(.05, 3200), w1 - .9, .4); put(fx, lp(whoosh(1.0, 400, 5200), .15), w1 - .7, .65); put(fx, sub(52, 1.2, .3), w1 - .2, .7); put(fx, bell(1568, 1.8), w1 + .2, .35)
    if i == 2:
        for k in range(5): put(fx, bell(1100 + 140 * k, 1.1), s0 + .7 + k * .5, .13, np.sin(k)); put(fx, blip(2200, .06), s0 + .7 + k * .5, .1)
        for k in range(10): put(fx, tick(.02, 3000 + 60 * k), s0 + 1.2 + k * .22, .07)
        put(fx, bell(1318, 2.0), w1 - .9, .3); put(fx, bell(1760, 2.0), w1 - .7, .22, .3)
# the end
e = EN; put(fx, sub(52, 3.0, .15), e['logo'] - .05, .9); put(fx, pad([130.8, 196, 261.6, 329.6, 392], 7.0, 1.6), e['logo'] - .3, .26); put(fx, bell(784, 4.5), e['logo'] + .05, .32)
put(fx, bell(1318, 4.0), e['promise'] + .15, .22, .2); put(fx, bell(1046, 5.0), e['promise'] + .7, .2, -.2)
write(os.path.join(odir, 'sfx.wav'), fx); print('vo.wav, sfx.wav ->', odir)
