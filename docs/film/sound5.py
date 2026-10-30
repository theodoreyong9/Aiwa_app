"""Sound effects of the film, synthesised and placed on the timeline (each one sits on something the picture does). The music is a real track from the catalog, mixed under by make.sh.
   python3 sound.py timeline.json out.wav"""
import json, sys, wave
import numpy as np
SR = 44100
tl = json.load(open(sys.argv[1])); T = tl['T']
TOTAL = tl['T'].get('E', tl.get('E'))['total'] if False else tl['E']['total']
out = np.zeros((int(TOTAL * SR) + SR, 2)); rng = np.random.default_rng(11)

# the times written below are the times of the scene (old film time); the edit slows nothing but compresses the voice section, shows the campaign again and holds a pause of 17 s on the television
PTS = [(0, 0), (379, 379), (420, 408), (552, 466), (672, 540), (686, 554), (1200, 1068)]
def N(t, after=False):
    if after or t >= 50.0 and t > 1200 / 24 - 1e-9 and False: pass
    f = t * 24
    if t >= 50.0: return t + 11.5
    for (o0, n0), (o1, n1) in zip(PTS, PTS[1:]):
        if f <= o1: return (n0 + (f - o0) * (n1 - n0) / (o1 - o0)) / 24
    return t - 132 / 24
def put(sig, t, pan=0.0, gain=1.0): return putn(sig, N(t), pan, gain)

def putn(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR); n = min(len(sig), len(out) - i)
    if i < 0 or n <= 0: return
    out[i:i + n, 0] += sig[:n] * gain * (1 - max(0, pan)); out[i:i + n, 1] += sig[:n] * gain * (1 + min(0, pan))

def tt(d): return np.arange(int(d * SR)) / SR
def blip(f, d=.25, a=.004):                     # a soft sine with a quick attack and a round decay
    t = tt(d); return np.sin(2 * np.pi * f * t) * np.minimum(1, t / a) * np.exp(-t / (d * .3))
def bell(f, d=1.2):                              # inharmonic partials: glass
    t = tt(d); return sum(np.sin(2 * np.pi * f * k * t) * np.exp(-t / (d * .25 / k ** .6)) * a for k, a in ((1, 1), (2.76, .35), (5.4, .15))) * np.minimum(1, t / .003)
def noise_sweep(d, f0, f1, q=.9):               # air that opens (a whoosh), filtered white noise
    t = tt(d); n = rng.standard_normal(len(t)); f = np.geomspace(f0, f1, len(t)); ph = np.cumsum(2 * np.pi * f / SR)
    mod = np.sin(ph) * .5 + .5
    x = np.convolve(n, np.ones(24) / 24, 'same') * mod
    e = np.sin(np.pi * np.linspace(0, 1, len(t))) ** 2; return x * e
def sub(f, d, drop=.5):
    t = tt(d); ff = f * (1 - drop * (1 - np.exp(-t * 3))); return np.sin(np.cumsum(2 * np.pi * ff / SR)) * np.exp(-t / (d * .35)) * np.minimum(1, t / .01)
def tick(d=.05, f=2400):
    t = tt(d); return rng.standard_normal(len(t)) * np.exp(-t / .006) * .6 + np.sin(2 * np.pi * f * t) * np.exp(-t / .01) * .4
def lp(x, k):                                    # a one-pole low-pass, to take the edge off
    y = np.zeros_like(x); s = 0.0
    for i, v in enumerate(x): s += k * (v - s); y[i] = s
    return y

# the dot in the dark: ONE blip, then the room is there, with a low hit
put(blip(1040, .35), T['dotBlink'][0], 0, .4)
put(sub(52, 2.6, .25), T['reveal'][0] - .04, 0, .9); put(bell(1318, 1.8), T['reveal'][0] + .02, .3, .3)
put(lp(noise_sweep(.9, 200, 4200), .2), T['reveal'][0] - .5, 0, .35)
put(bell(987, 1.4), T['unlock'], 0, .3); put(bell(1480, 1.2), T['unlock'] + .14, .2, .2)             # "j'écoute"
put(lp(noise_sweep(2.4, 150, 1500), .1), T['pullBack'][0], 0, .45)                                    # the camera goes back to the room
s0, s1 = T['tvShapes']
for k, f in enumerate((523, 659, 784, 988)):                                                         # each shape that becomes the next one
    t0 = s0 + k * (s1 - s0) / 4
    put(blip(f, .5), t0 + .5, -.2, .26); put(lp(noise_sweep(.7, 300, 2600), .2), t0 + .2, -.2, .3)
k0 = T['tvContract'][0]
for i in range(16): put(tick(), k0 + .4 + i * .11 + rng.random() * .03, -.1, .12)                    # the contract is typed
put(sub(70, 1.2), k0 + 2.2, 0, .45); put(bell(1568, 1.4), k0 + 2.2, .2, .25)                         # and sealed
put(lp(noise_sweep(2.8, 150, 1600), .1), T['rise'][0], .2, .55); put(sub(90, 2.6, .2), T['rise'][0], 0, .4)   # the phone rises
for t0 in T['tapTimes']: put(tick(.06, 3200), t0, .3, .24); put(blip(1100, .08), t0, .3, .14)         # the buttons of the widget
put(blip(740, .18), 15.8, .2, .22); put(blip(988, .18), 15.98, .2, .22)                              # "il parle avec toi"
put(blip(520, .6) * np.linspace(1, 0, int(.6 * SR)), T['screenOff'], 0, .4); put(sub(55, .8, .6), T['screenOff'], 0, .4)   # the screen goes dark
put(bell(1760, 1.5), T['cast'][0], 0, .25)
for k in range(3): put(lp(noise_sweep(1.6, 400, 4200), .25), T['cast'][0] + .1 + k * .3, .1 + k * .1, .22)   # the stream goes to the television
put(sub(60, 1.6, .3), T['cast'][0] + 1.0, -.3, .3)
for i, t0 in enumerate((29.0, 29.6, 30.2, 32.2, 33.4)): put(bell(660 * 2 ** (i * 3 / 12), .8), t0 + .3, .5 - i * .25, .18)   # the nodes arrive
import campaign as CP
for p_ in CP.schedule():                                                                                  # a pair leaves, falls, lands: a wave goes out
    n_ = p_['n']; put(lp(noise_sweep(.3, 3200, 700), .3), p_['t0'], .2 - (n_ % 3) * .2, .12)
    put(blip(440 * 2 ** ((n_ % 7) * 2 / 12), .25), p_['t1'], .1, .2); put(sub(80 + (n_ % 4) * 6, .5, .4), p_['t1'], 0, .22)
    put(lp(noise_sweep(1.1, 500, 3800), .2), p_['t1'] + .02, -.2 + (n_ % 3) * .2, .16)
put(lp(noise_sweep(3.5, 150, 2500), .1), T['world'][0] - .2, -.3, .5)   # the view travels to the world
for i, t0 in enumerate(np.arange(T['world'][0] + 1.0, T['world'][0] + 3.0, .35)): put(bell(1175 * (1 + (i % 3) * .25), .9), t0, -.5 + (i % 4) * .3, .14)  # the pins
put(sub(46, 2.5, .2), T['profileTV'][0] - .2, 0, .3); put(bell(784, 1.8), T['profileTV'][0] + .1, 0, .22)
put(lp(noise_sweep(4.5, 1800, 120), .06), T['closed'][0] + 2.0, 0, .5)    # the room dims
put(blip(55, 4.0), 56.0, 0, .4)
put(sub(36, 3.8, .4), T['end'][0], 0, .85); put(bell(1568, 3.0), T['end'][0] + .05, 0, .3)    # "Aiwa."
put(bell(784, 3.0), 60.6, 0, .18)
W0 = 44.5                                                                                              # the pause: new film time
putn(sub(50, 1.4, .3), W0 + .55, 0, .3); putn(bell(880, 1.4), W0 + .75, .2, .2)
for t_ in (1.2, 3.0): putn(bell(1047 * (1 + (t_ > 2) * .25), 1.0), W0 + t_ + .1, .1, .16); putn(blip(880, .12), W0 + t_ - .6, -.2, .12)   # the application is restyled by voice
putn(lp(noise_sweep(1.0, 300, 2600), .2), W0 + 5.0, 0, .3); putn(bell(1047, 1.4), W0 + 5.1, -.2, .2)
for dt in (5.3, 5.9, 6.5): putn(blip(988, .15), W0 + dt, -.3, .14)                                                                   # the three profiles arrive
for dt in (7.7, 8.5): putn(blip(1175, .15), W0 + dt, .3, .2); putn(bell(1568, .9), W0 + dt + .05, .3, .14)               # the match pro, the match perso
putn(lp(noise_sweep(1.2, 400, 3000), .2), W0 + 9.6, 0, .3); putn(sub(60, 1.6, .3), W0 + 9.65, 0, .25)
for i, t_ in enumerate((10.1, 11.1, 12.2, 13.3)): putn(blip(660 + (i % 2) * 220, .2), W0 + t_, -.2 + (i % 2) * .4, .16)                            # the agents speak
putn(lp(noise_sweep(1.8, 200, 2400), .12), W0 + 13.2, 0, .3); putn(bell(1760, 1.2), W0 + 14.9, .2, .16)                                      # the intimacy rises
putn(lp(noise_sweep(.9, 1500, 200), .1), W0 + 16.2, 0, .3)
m = np.max(np.abs(out)) or 1; out = out / m * .85
with wave.open(sys.argv[2], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(out, -1, 1) * 32767).astype('<i2').tobytes())
print('sfx ok', round(len(out) / SR, 1), 's')
