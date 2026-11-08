"""A small sound-design kit, written with numpy only: layered impacts, whooshes that move, risers, designed interface sounds, a room (convolution reverb), a master bus.
Everything is made from physical ideas (a body that falls in pitch, a crack, a metal that rings, air that moves through a filter) and put through the same room so that it sounds like one place."""
import numpy as np
SR = 44100
rng = np.random.default_rng(13)
def tt(d): return np.arange(int(d * SR)) / SR
def env_exp(d, tau, attack=.001):
    t = tt(d); return np.minimum(1, t / attack) * np.exp(-t / tau)
def onepole(x, fc):
    a = 1 - np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); s = 0.0
    for i, v in enumerate(x): s += a * (v - s); y[i] = s
    return y
def lowpass(x, fc, order=2):
    for _ in range(order): x = onepole(x, fc)
    return x
def highpass(x, fc, order=2):
    for _ in range(order): x = x - onepole(x, fc)
    return x
def bandpass_sweep(x, f0, f1, q=3.0, curve='exp'):
    """A state-variable band-pass whose centre moves from f0 to f1 (air that moves)."""
    n = len(x); f = np.geomspace(f0, f1, n) if curve == 'exp' else np.linspace(f0, f1, n)
    y = np.empty(n); lp = bp = 0.0; damp = 1.0 / q
    for i in range(n):
        g = 2 * np.sin(np.pi * min(f[i], 8500) / SR)
        lp += g * bp; hp = x[i] - lp - damp * bp; bp += g * hp; y[i] = bp
    return y
def noise(d): return rng.standard_normal(int(d * SR))

# ------------------------------------------------------------------ the room
def make_ir(d=2.4, damp=5200, pre=.012):
    n = int(d * SR); t = tt(d); irs = []
    for ch in range(2):
        x = rng.standard_normal(n) * np.exp(-t / (d * .22)); x = lowpass(x, damp, 1)
        x[:int(pre * SR)] = 0; x *= np.minimum(1, t / .02); irs.append(x)
    ir = np.stack(irs, 1); ir /= np.sqrt((ir ** 2).sum(0, keepdims=True)) + 1e-9; return ir
def reverb(sig, ir, wet=1.0):
    """sig: (n,) or (n,2) -> (n,2) wet only (FFT convolution)."""
    if sig.ndim == 1: sig = np.stack([sig, sig], 1)
    n = len(sig) + len(ir) - 1; m = 1 << (n - 1).bit_length(); out = np.zeros((len(sig), 2))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(sig[:, c], m) * np.fft.rfft(ir[:, c], m), m)[:len(sig)]
    return out * wet

# ------------------------------------------------------------------ the sounds (each returns a mono array)
def impact(power=1.0, d=3.2):
    t = tt(d)
    f = 34 + 30 * np.exp(-t / .09)                                      # a body that falls in pitch
    sub = np.sin(np.cumsum(2 * np.pi * f / SR)) * np.exp(-t / .75) * np.minimum(1, t / .004)
    sub += .35 * np.sin(np.cumsum(2 * np.pi * 2 * f / SR)) * np.exp(-t / .22)
    body = lowpass(noise(d), 220) * np.exp(-t / .16) * 7
    crack = highpass(noise(d), 1800) * np.exp(-t / .018) * .9
    mid = lowpass(noise(d), 1500, 1) * np.exp(-t / .07) * .8
    ring = np.zeros_like(t)
    for fr, a, tau in ((97, .22, 2.4), (146, .16, 1.9), (233, .12, 1.5), (341, .07, 1.1), (577, .045, .8)):
        ring += a * np.sin(2 * np.pi * fr * t * (1 + .0008 * rng.standard_normal())) * np.exp(-t / tau)
    x = (sub * 1.15 + body * .55 + crack * .55 + mid * .4 + ring * .5) * power
    return np.tanh(x * 1.2) / 1.1
def whoosh(d=.8, f0=300, f1=4500, q=2.2, tone=.0):
    n = noise(d); x = bandpass_sweep(n, f0, f1, q)
    t = tt(d); e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.6; x = x * e
    if tone: x += tone * np.sin(np.cumsum(2 * np.pi * np.geomspace(f0 * .5, f1 * .4, len(t)) / SR)) * e
    return x / (np.abs(x).max() + 1e-9)
def riser(d, f0=120, f1=1800):
    t = tt(d); u = t / d
    n = bandpass_sweep(noise(d), f0 * 2, f1 * 4, 1.6)
    fr = f0 * (f1 / f0) ** u
    ph = np.cumsum(2 * np.pi * fr / SR); tone = (np.sin(ph) + .5 * np.sin(2 * ph + .3) + .25 * np.sin(3 * ph)) * .5
    pulse = .6 + .4 * np.sin(2 * np.pi * (3 + 14 * u ** 2) * t)             # a pulse that speeds up
    x = (n / (np.abs(n).max() + 1e-9) * .9 + tone * .55) * pulse * (u ** 2.2) * np.minimum(1, (d - t) / .02)
    return x / (np.abs(x).max() + 1e-9)
def click(freq=3800, d=.06, body=1500):
    t = tt(d); c = highpass(noise(d), 1500, 1) * np.exp(-t / .0025)
    b = np.sin(2 * np.pi * body * t * (1 + 1.2 * np.exp(-t / .008))) * np.exp(-t / .012)
    r = bandpass_sweep(noise(d), freq, freq, 6.0) * np.exp(-t / .006) * 2.2
    x = c * .45 + b * .55 + r * .35; return x / (np.abs(x).max() + 1e-9)
def pop(f=420, d=.18):
    t = tt(d); fr = f * (1 + 1.1 * np.exp(-t / .03)); x = np.sin(np.cumsum(2 * np.pi * fr / SR)) * np.exp(-t / .05) * np.minimum(1, t / .002)
    c = click(d=.04) * .35; x[:len(c)] += c
    return x * .9
def fm_bell(f, d=1.6, ratio=3.5, index=2.4, tau=.5):
    t = tt(d); mod = np.sin(2 * np.pi * f * ratio * t) * index * np.exp(-t / (tau * .35))
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / tau) * np.minimum(1, t / .002)
    x += .22 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t / (tau * .5)); return x
def chord(freqs, d=2.2, gap=.07, tau=.8, ratio=3.5):
    out = np.zeros(int((d + gap * len(freqs)) * SR))
    for i, f in enumerate(freqs):
        b = fm_bell(f, d, ratio=ratio, tau=tau); k = int(i * gap * SR); out[k:k + len(b)] += b
    return out / (np.abs(out).max() + 1e-9)
def blip(f, d=.12): t = tt(d); return np.sin(2 * np.pi * f * t) * np.exp(-t / (d * .3)) * np.minimum(1, t / .001)
def shimmer(d=1.6, f=5200): t = tt(d); x = highpass(noise(d), f * .6, 1) * np.exp(-t / (d * .3)) * np.minimum(1, t / .05); return x / (np.abs(x).max() + 1e-9)
def drone(d, f=55, mov=.25):
    t = tt(d); x = np.zeros_like(t)
    for k, dt in enumerate((-.012, 0, .013)):
        fr = f * (1 + dt); x += np.sin(2 * np.pi * fr * t + k) + .5 * np.sin(2 * np.pi * 2 * fr * t) + .25 * np.sin(2 * np.pi * 3 * fr * t)
    x = lowpass(x, 900 + 700 * (1 + np.sin(2 * np.pi * mov * t)).mean(), 1)
    return x / (np.abs(x).max() + 1e-9) * np.minimum(1, t / 1.0) * np.minimum(1, (d - t) / 1.2)
def pad(freqs, d, a=1.6):
    t = tt(d); x = np.zeros_like(t)
    for i, f in enumerate(freqs):
        for dt in (-.006, .006):
            fr = f * (1 + dt); ph = 2 * np.pi * fr * t + i
            x += np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sin(3 * ph) + .15 * np.sin(5 * ph)
    x = lowpass(x, 2400, 1); x /= (np.abs(x).max() + 1e-9)
    return x * np.minimum(1, t / a) * np.minimum(1, (d - t) / 2.0)

class Mix:
    """A dry bus and a room send; master: gentle saturation and a limiter."""
    def __init__(self, total):
        self.n = int(total * SR); self.dry = np.zeros((self.n, 2)); self.send = np.zeros((self.n, 2)); self.ir = make_ir()
    def put(self, sig, t, gain=1.0, pan=0.0, room=.25):
        i = int(t * SR)
        if i < 0 or i >= self.n: return
        sig = sig[:self.n - i]; k = len(sig)
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.dry[i:i + k, 0] += sig * gain * l * 1.414; self.dry[i:i + k, 1] += sig * gain * r * 1.414
        if room > 0: self.send[i:i + k, 0] += sig * gain * room * l * 1.414; self.send[i:i + k, 1] += sig * gain * room * r * 1.414
    def render(self):
        wet = reverb(self.send, self.ir); out = self.dry + wet
        out = np.tanh(out * .9) / .9
        pk = np.abs(out).max(); return out * (.93 / pk if pk > .93 else 1)
