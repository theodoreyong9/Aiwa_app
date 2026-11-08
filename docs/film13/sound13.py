"""Film 13, the sound: the voice on the timeline, then the effects made with sfxlib (layered impacts, moving air, designed interface sounds, one room for all).
   python3 sound13.py <voices dir> <out dir>     -> <out>/vo.wav  <out>/sfx.wav"""
import json, os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sfxlib as L
SR = L.SR
TL = json.load(open(os.path.join(HERE, 'timeline13.json'))); V = TL['voice']; HK = TL['hook']; BT = TL['beats']; EN = TL['end']; SL = TL['slam']
vdir, odir = sys.argv[1], sys.argv[2]; os.makedirs(odir, exist_ok=True)
N = TL['total'] + 1.5
def read(p):
    w = wave.open(p); n = w.getnframes(); x = np.frombuffer(w.readframes(n), np.int16).astype(float) / 32768
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(1)
    if w.getframerate() != SR: k = SR / w.getframerate(); x = np.interp(np.arange(int(len(x) * k)) / k, np.arange(len(x)), x)
    return x
def write(p, st):
    st = np.clip(st, -1, 1); w = wave.open(p, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()

# ---- the voice: dry, a short room (a voice that is too wet is lost under the music)
vo = L.Mix(N)
for cid, t0 in V.items():
    p = os.path.join(vdir, cid + '.wav')
    if os.path.exists(p): vo.put(read(p), t0, 1.0, 0, .0)
write(os.path.join(odir, 'vo.wav'), vo.render())

# ---- the effects
m = L.Mix(N); P = m.put
def hit(t, g=1.0, room=.32):
    P(L.impact(power=g), t, .95, 0, room); P(L.whoosh(.55, 500, 6500, 2.0), t - .5, .35 * g, 0, .2)           # air that rushes in, then the blow
def pitched(base, n, k): return base * 2 ** (k / 12.0)
# opening: a heartbeat, then the first blow
P(L.impact(.45), .22, .6, 0, .25); P(L.impact(.35), .72, .45, 0, .25); P(L.drone(HK['q1'][1] - 0.1, 55), .1, .22, 0, .3)
# Q1: speed (air passes, faster and faster), then the tape stops
q1 = HK['q1']; hit(q1[0] - .05, .9)
for k in range(5): P(L.whoosh(.45, 500 + 300 * k, 7500, 1.8), q1[0] + .12 + k * .32, .45, -.7 + .35 * k, .15)
P(L.riser(q1[1] - q1[0], 150, 2600), q1[0], .38, 0, .25)
P(L.whoosh(.4, 4500, 160, 1.6), q1[1] - .12, .6, 0, .2)                                                     # it falls away: everything stops
# Q2: the points tick, faster and higher, then lock
q2 = HK['q2']; hit(q2[0] - .05, .75)
tk = q2[0] + .9; k = 0
while tk < q2[0] + 1.6:
    P(L.click(2800 + 70 * k), tk, .32, np.sin(k) * .6, .12); tk += max(.014, .075 * (.9 ** k)); k += 1
P(L.impact(.5), q2[0] + 1.62, .8, 0, .3); P(L.chord([1318, 1760, 2093], 2.4, tau=.9), q2[0] + 1.63, .36, 0, .4); P(L.shimmer(1.4), q2[0] + 1.62, .25, 0, .4)
# Q3: the rules close in, then the blow
q3 = HK['q3']; hit(q3[0] - .05, .75)
P(L.riser(SL - q3[0], 70, 3600), q3[0], .52, 0, .3)
for k in range(9): P(L.click(1400 + 100 * (k % 4), body=700), q3[0] + k * .35, .32, (k % 3 - 1) * .6, .15)
hit(SL, 1.75, .45); P(L.shimmer(2.2, 4200), SL, .3, 0, .5); P(L.chord([220, 330, 440], 3.2, tau=1.4, ratio=2.0), SL + .05, .28, 0, .5)
# the beats
for i, B in enumerate(BT):
    s0 = B['s0']; v0, v1 = B['voice']; w0, w1 = B['work']
    hit(s0 - .02, .9)
    if i == 0:
        P(L.whoosh(1.0, 300, 7000, 2.0), w0 - .2, .5, -.5, .2); P(L.whoosh(1.0, 300, 7000, 2.0), w0 - .2, .5, .5, .2)
        for j in range(5):
            tj = w0 + 2.2 * (.22 + .13 * j)
            P(L.pop(pitched(360, 0, j * 2), .18), tj, .5, -.6, .2); P(L.pop(pitched(300, 0, j * 2 + 3), .18), tj + .01, .5, .6, .2)
        P(L.chord([784, 988, 1175], 2.0, tau=.8), w0 + 2.0, .25, -.5, .35); P(L.chord([1046, 1318, 1568], 2.0, tau=.8), w0 + 2.15, .25, .5, .35)
    if i == 1:
        for j in range(26): P(L.click(2500 + 40 * j, body=1100), s0 + .5 + j * .05, .12, .0, .1)                       # the creation is read
        t0 = s0 + 1.9
        for j in range(6):
            P(L.pop(pitched(330, 0, j * 2), .2), t0 + j * .36, .5, (j % 2) * 1.2 - .6, .25)
            for q in range(10): P(L.click(3000 + 90 * q, body=1400), t0 + j * .36 + .35 + q * .02, .06, (j % 2) * 1.2 - .6, .05)
        sent = w1 - 1.0
        P(L.pop(520, .22), sent - .5, .55, 0, .2); P(L.click(4200), sent, .7, 0, .1)
        P(L.whoosh(.9, 400, 8000, 1.6, tone=.25), sent + .2, .8, 0, .25); P(L.riser(.4, 400, 3000), sent - .2, .25, 0, .2)
        P(L.impact(.9), sent + .95, .9, 0, .35); P(L.chord([1046, 1318, 1568, 2093], 2.6, gap=.06, tau=1.0), sent + 1.0, .38, 0, .4); P(L.shimmer(1.8), sent + 1.0, .28, 0, .45)
    if i == 2:
        for j in range(5):
            a0 = s0 + .7 + j * .5
            P(L.fm_bell(1320 + 90 * j, 1.8, ratio=3.0, index=1.6, tau=.55), a0 + .4, .26, np.sin(j * 1.7) * .7, .55)             # a ping for each profile
        for q in range(34): P(L.click(2600 + 55 * q, body=1300), s0 + 1.2 + q * .06, .1, 0, .08)                            # the scores climb
        sel = w1 - .8
        P(L.whoosh(.6, 400, 5000, 2.0), sel - .2, .4, 0, .2); P(L.chord([784, 988, 1175], 2.0, tau=.9), sel, .3, 0, .4)
        for j in range(3): P(L.blip(1568 + 220 * j, .14), sel + .2 + j * .25, .3, 0, .3)
        P(L.pop(440, .2), sel + 1.0, .45, -.3, .2)
# the end: a breath, then the name
e = EN; P(L.riser(.9, 100, 1200), e['black'] - .1, .5, 0, .3)
P(L.impact(1.0), e['logo'] + .02, .95, 0, .5); P(L.pad([130.8, 196, 261.6, 329.6, 392, 493.9], 8.0, 1.6), e['logo'] - .2, .42, 0, .5)
P(L.chord([784, 1046, 1318, 1568], 4.0, gap=.08, tau=1.4), e['logo'] + .1, .34, 0, .5); P(L.shimmer(2.6), e['logo'] + .05, .25, 0, .5)
P(L.fm_bell(1318, 4.0, tau=1.2), e['promise'] + .12, .26, .2, .55); P(L.fm_bell(1046, 5.0, tau=1.5), e['promise'] + .62, .24, -.2, .55)
write(os.path.join(odir, 'sfx.wav'), m.render()); print('vo.wav, sfx.wav ->', odir)
