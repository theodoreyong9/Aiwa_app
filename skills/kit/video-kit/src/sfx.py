"""The sound design of the film: whooshes under the camera moves, soft plucks on the six kinds, sonar pings on the lock screen, a room tone under the real shot, a riser and a low boom
for the last card. All of it is SYNTHESISED here (numpy), from nothing: no sample, no licence to carry. Writes a stereo 44.1 kHz wav; the film mixes it under the voice with the music.
  python3 sfx.py sched.json out.wav"""
import json, sys, wave
import numpy as np

SR = 44100
sched = json.load(open(sys.argv[1]))
total = sched['total']
T = {x['o'] if isinstance(x['o'], str) else None: x['t'] for x in sched['scn']}
out = np.zeros((int(total * SR) + SR, 2))
rng = np.random.default_rng(7)

def put(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i < 0 or i >= len(out): return
    n = min(len(sig), len(out) - i)
    l, r = (1 - max(0, pan)) * gain, (1 + min(0, pan)) * gain
    out[i:i + n, 0] += sig[:n] * l; out[i:i + n, 1] += sig[:n] * r

def env(n, a=0.02, d=0.3, curve=2.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(1e-3, a)) * np.exp(-t / max(1e-3, d)) ** 1.0
    return e

def lowpass_sweep(x, f0, f1, q=0.0):
    """One-pole lowpass whose cutoff moves from f0 to f1 (Hz) over the signal: the body of a whoosh."""
    y = np.zeros_like(x); state = 0.0
    fs = np.linspace(f0, f1, len(x))
    a = 1 - np.exp(-2 * np.pi * fs / SR)
    for i in range(len(x)):
        state += a[i] * (x[i] - state); y[i] = state
    return y

def whoosh(dur, up=True, f=(300, 5200), gain=0.5):
    n = int(dur * SR); x = rng.standard_normal(n)
    y = lowpass_sweep(x, *(f if up else f[::-1]))
    y = y - lowpass_sweep(y, 80, 80)                                   # no rumble
    t = np.arange(n) / SR / dur
    e = np.sin(np.pi * np.clip(t, 0, 1)) ** (2.2 if up else 1.6)         # swell and fall
    return y / (np.max(np.abs(y)) + 1e-9) * e * gain

def pluck(freq, dur=0.35, gain=0.35):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.01 * t) + 0.12 * np.sin(2 * np.pi * freq * 3.02 * t)
    return s * np.exp(-t / 0.09) * np.minimum(1, t / 0.004) * gain

def ping(freq=1175, dur=1.6, gain=0.22):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2.0 * t)) * np.exp(-t / 0.55) * np.minimum(1, t / 0.01) * gain

def tick(gain=0.18):
    n = int(0.05 * SR); t = np.arange(n) / SR
    return rng.standard_normal(n) * np.exp(-t / 0.006) * gain

def boom(dur=3.2, gain=0.8):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 42 + 38 * np.exp(-t / 0.35)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t / 1.1) + 0.25 * np.sin(2 * ph) * np.exp(-t / 0.5)) * np.minimum(1, t / 0.005) * gain

def reverb(x, tail=1.4, mix=0.35):
    n = int(tail * SR); ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / (tail / 4.5)); ir /= np.sqrt(np.sum(ir ** 2))
    from numpy.fft import rfft, irfft
    m = len(x) + n; X = rfft(x, m) * rfft(ir, m)
    return (1 - mix) * np.pad(x, (0, n)) + mix * irfft(X, m)

def mixn(a, b):
    n = max(len(a), len(b)); r = np.zeros(n); r[:len(a)] += a; r[:len(b)] += b
    return r

starts = [(x['o'], x['t']) for x in sched['scn']]
t_of = {o: t for o, t in starts}

# 1. the camera travels between groups: a whoosh that rises into the next page (the camera leaves at `start`, arrives at `end`)
travels = [(12.45, 13.75, True, 0.55), (21.25, 22.06, False, 0.45), (27.95, 28.94, True, 0.4), (30.3, 31.52, True, 0.5), (35.1, 36.1, True, 0.45)]
for a, b, up, g in travels:
    put(whoosh(b - a + 0.15, up=up, gain=g), a, pan=0.2 if up else -0.2)

# 2. the six kinds: a soft pluck on each name, rising, with a tick
for k, (o, f) in enumerate(zip(['t0', 't1', 't2', 't3', 't4', 't5'], [392, 440, 494, 523, 587, 659])):
    t0 = t_of[o]
    put(pluck(f), t0, pan=-0.3 + 0.12 * k); put(tick(), t0)
put(whoosh(1.2, up=True, f=(200, 3000), gain=0.35), t_of['t5'] + 0.2)

# 3. the real shot (13.75 – 22.06): a room tone, the widget's clicks, sonar pings with the ripples of the lock screen
a, b = t_of['widget'], t_of[10] if 10 in t_of else 22.06
a, b = 13.75, 22.06
n = int((b - a) * SR); room = lowpass_sweep(rng.standard_normal(n), 420, 380) * 0.020
room *= np.minimum(1, np.arange(n) / SR / 0.8) * np.minimum(1, (n - np.arange(n)) / SR / 0.8)
put(room, a)
for k in range(8): put(tick(0.12), a + 0.45 + k * 0.14, pan=0.15)
for k in range(5): put(ping(1175 if k % 2 == 0 else 880), 16.45 + k * 1.67, pan=0.1)
put(pluck(784, 0.6, 0.25), 19.6)                                    # the display lights in the glasses
put(whoosh(0.9, up=True, f=(900, 7000), gain=0.25), 19.35)

# 4. the super agent: a low breath that opens, then a sparkle for the new things it makes
put(whoosh(1.3, up=True, f=(150, 1800), gain=0.4), 31.4)
for k in range(7): put(pluck(1318 + 110 * (k % 4), 0.25, 0.14), 34.4 + k * 0.17, pan=-0.4 + 0.13 * k)

# 5. the end: a riser to the last card, then a low boom and a long tail
end = t_of['end']
put(whoosh(end - 42.6, up=True, f=(120, 6500), gain=0.55), 42.6)
put(reverb(mixn(boom(), 0.5 * pluck(196, 2.5, 0.6)), tail=2.4, mix=0.45), end - 0.02, gain=0.9)

out = np.tanh(out * 0.9) * 0.9
pcm = (np.clip(out, -1, 1) * 32767).astype('<i2')
with wave.open(sys.argv[2], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('sfx', round(len(pcm) / SR, 1), 's')
