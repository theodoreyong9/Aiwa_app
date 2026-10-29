#!/usr/bin/env python3
"""The mixer of the conductor: from plan.json (video-kit/conductor/conduct.mjs) it builds the sound of the film — the bed of each place, the accent of each beat, the whoosh and the arrival of each
hand-over, the riser of each dissolve — all SYNTHESISED (numpy), with the track under it at the gain each moment asks for. No sample, no licence to carry.
  python3 mix.py plan.json out.wav [--music track.wav]"""
import json, sys, wave
import numpy as np

SR = 44100
plan = json.load(open(sys.argv[1])); out_path = sys.argv[2]
music_path = sys.argv[sys.argv.index('--music') + 1] if '--music' in sys.argv else None
total = plan['total']; N = int(total * SR) + SR
rng = np.random.default_rng(11)
out = np.zeros((N, 2)); bed_mix = np.zeros((N, 2))

def put(buf, sig, t, pan=0.0, gain=1.0):
    i = int(max(0, t) * SR)
    if i >= N: return
    n = min(len(sig), N - i); l, r = (1 - max(0, pan)) * gain, (1 + min(0, pan)) * gain
    buf[i:i + n, 0] += sig[:n] * l; buf[i:i + n, 1] += sig[:n] * r

def shaped_noise(n, lo, hi, tilt=0.0):
    """Noise with the spectrum kept between lo and hi (Hz), by the frequency domain: fast for long beds."""
    x = rng.standard_normal(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    H = ((f >= lo) & (f <= hi)).astype(float) * (1.0 / np.maximum(f, 20) ** tilt if tilt else 1.0)
    H = np.convolve(H, np.ones(31) / 31, mode='same')
    y = np.fft.irfft(X * H, n); return y / (np.max(np.abs(y)) + 1e-9)

def lfo(n, hz, depth=0.5, phase=0.0):
    t = np.arange(n) / SR; return 1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * hz * t + phase))

def bed(kind, n):
    t = np.arange(n) / SR
    if kind == 'void':
        return (0.5 * np.sin(2 * np.pi * 55 * t) * lfo(n, 0.07) + 0.35 * np.sin(2 * np.pi * 82.6 * t + 1) * lfo(n, 0.05, 0.6) + 0.5 * shaped_noise(n, 30, 220, 1.0))
    if kind == 'air':
        return shaped_noise(n, 180, 1800, 0.6) * lfo(n, 0.11, 0.55)
    if kind == 'city':
        base = shaped_noise(n, 40, 420, 0.8) * 0.9 + 0.12 * shaped_noise(n, 2500, 7000)
        for _ in range(max(1, int(n / SR / 3.5))):          # a car goes by
            d = int(rng.uniform(1.2, 2.4) * SR); s0 = rng.integers(0, max(1, n - d)); env = np.sin(np.pi * np.linspace(0, 1, d)) ** 2
            base[s0:s0 + d] += 0.5 * shaped_noise(d, 120, 1400, 0.5) * env
        return base
    if kind == 'machine':
        y = 0.5 * np.sin(2 * np.pi * 60 * t) + 0.3 * np.sin(2 * np.pi * 120 * t) + 0.18 * np.sin(2 * np.pi * 180.5 * t) + 0.25 * shaped_noise(n, 50, 400, 0.7)
        for _ in range(int(n / SR * 2.2)):
            k = int(0.012 * SR); s0 = rng.integers(0, max(1, n - k)); y[s0:s0 + k] += rng.standard_normal(k) * np.exp(-np.arange(k) / (0.003 * SR)) * 0.5
        return y
    if kind == 'shimmer':
        y = np.zeros(n)
        for f0 in (1318, 1568, 1975, 2349, 2637):
            y += np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6)) * lfo(n, rng.uniform(0.08, 0.3), 0.9, rng.uniform(0, 6)) * 0.18
        return y + 0.25 * shaped_noise(n, 3000, 9000)
    return shaped_noise(n, 80, 900, 1.0) * 0.8        # room

# the beds: one per stretch of the same bed, crossfaded over 0.7 s at each change
cur = None
for a in plan['sound']['ambience']:
    if cur and cur['bed'] == a['bed']: cur['t1'] = a['t1']; cur['level'] = max(cur['level'], a['level']); continue
    if cur: runs.append(cur)
    cur = dict(a); runs = locals().get('runs', [])
runs = locals().get('runs', []); runs.append(cur)
for r in runs:
    x = 0.7; t0, t1 = max(0, r['t0'] - x / 2), min(total, r['t1'] + x / 2); n = int((t1 - t0) * SR)
    y = bed(r['bed'], n); y = y / (np.max(np.abs(y)) + 1e-9) * r['level']
    e = np.ones(n); k = int(x * SR); e[:k] = np.linspace(0, 1, k) ** 1.5 if r['t0'] > 0 else 1; e[-k:] = np.linspace(1, 0, k) ** 1.5 if r['t1'] < total else 1
    put(bed_mix, y * e, t0, gain=1.0)

def whoosh(dur, up=True, f=(300, 5200), gain=0.5):
    n = int(dur * SR); x = shaped_noise(n, f[0], f[1], 0.3); t = np.linspace(0, 1, n)
    return x * np.sin(np.pi * t) ** (2.2 if up else 1.5) * gain

def pluck(freq, dur=0.5, gain=0.3):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.01 * t) + 0.12 * np.sin(2 * np.pi * freq * 3.02 * t)) * np.exp(-t / 0.12) * np.minimum(1, t / 0.004) * gain

def boom(dur=1.6, gain=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * (44 + 30 * np.exp(-t * 6)) * t) * np.exp(-t / 0.5) + 0.12 * shaped_noise(n, 80, 600) * np.exp(-t / 0.3)) * gain

def riser(dur, gain=0.4):
    n = int(dur * SR); x = shaped_noise(n, 400, 9000, 0.1); t = np.linspace(0, 1, n)
    return x * t ** 2.4 * gain * (0.4 + 0.6 * np.sin(2 * np.pi * 9 * t * t) ** 2)

SCALE = [0, 2, 4, 7, 9]           # a pentatonic scale: the accents never clash
for i, c in enumerate(plan['sound']['cues']):
    k = c['kind']; lv = c.get('level', 0.5)
    if k == 'accent':
        deg = SCALE[(i * 3) % 5] + 12 * int(c.get('pitch', 0.5) * 2.4); put(out, pluck(110 * 2 ** (deg / 12), gain=0.28 * lv), c['t'], pan=((i % 5) - 2) * 0.12)
    elif k in ('whoosh', 'whip'):
        d = max(0.35, c.get('dur', 1.0)); put(out, whoosh(d + 0.3, up=True, f=((500, 9000) if k == 'whip' else (250, 5200)), gain=0.55 * lv), c['t'] - 0.15)
    elif k == 'arrive':
        put(out, boom(gain=0.5 * lv), c['t']); put(out, pluck(220, 1.4, 0.18 * lv), c['t'] + 0.04)
    elif k == 'riser':
        put(out, riser(max(0.4, c.get('dur', 1.0)), 0.4 * lv), c['t'])

mix = out + bed_mix
music = None
if music_path:
    with wave.open(music_path) as w:
        ch, raw = w.getnchannels(), np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32768
    m = raw.reshape(-1, ch); m = m if ch == 2 else np.repeat(m, 2, axis=1); m = m[:N]
    g = np.ones(len(m))
    for seg in plan['sound']['music']:                      # the gain of the track, beat by beat, smoothed
        g[int(seg['t0'] * SR):int(seg['t1'] * SR)] = seg['gain']
    k = int(0.8 * SR); g = np.convolve(g, np.ones(k) / k, mode='same')
    music = m * g[:, None]
    mix[:len(music)] += music * 0.9
peak = np.max(np.abs(mix)); mix = mix / peak * 0.89 if peak > 0.89 else mix
with wave.open(out_path, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
print('mix:', out_path, f'{total:.1f}s', 'beds:', [r['bed'] for r in runs])
