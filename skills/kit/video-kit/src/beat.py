#!/usr/bin/env python3
"""A procedural track with a real pulse, made for a video: kick, snare, hats, bass, pad, an arpeggio, a riser into a drop, and an accent on
every cut of the picture. No sample, no licence question, pure Python (no numpy). It is a designed placeholder, not a hit: replace it with a
licensed track when there is one.

  beat.py out.wav SECONDS [--bpm=108] [--drop=SECONDS] [--cuts=3.2,6.4,...] [--cuts-file=frames/cuts.json] [--seed=7] [--mood=minor|major]

  --drop   where the full groove starts (a riser leads into it); default: a quarter of the way in, snapped to a bar
  --cuts   the instants where the picture changes: each gets a hit (the render writes them to frames/cuts.json: --cuts-file reads that)
"""
import json, math, random, struct, sys, wave

SR = 44100


def args():
    pos, opt = [], {}
    for a in sys.argv[1:]:
        if a.startswith('--'):
            k, _, v = a[2:].partition('=')
            opt[k] = v
        else:
            pos.append(a)
    return pos, opt


def main():
    pos, opt = args()
    out, seconds = pos[0], float(pos[1])
    bpm = float(opt.get('bpm', 108))
    beat = 60.0 / bpm
    bar = beat * 4
    rnd = random.Random(int(opt.get('seed', 7)))
    cuts = [float(x) for x in opt.get('cuts', '').split(',') if x]
    if opt.get('cuts-file'):
        try:
            cuts += json.load(open(opt['cuts-file'])).get('cuts', [])
        except (OSError, ValueError):
            pass
    drop = float(opt['drop']) if opt.get('drop') else max(bar * 2, round(seconds * 0.25 / bar) * bar)
    n = int(SR * seconds)
    buf = [0.0] * n
    minor = opt.get('mood', 'minor') != 'major'
    # progression (roots in Hz) and chord tones: A minor  Am F C G   or   C major  C G Am F
    prog = [(55.0, [220.0, 261.63, 329.63]), (43.65, [174.61, 220.0, 261.63]), (65.41, [261.63, 329.63, 392.0]), (49.0, [196.0, 246.94, 293.66])] if minor else \
           [(65.41, [261.63, 329.63, 392.0]), (49.0, [196.0, 246.94, 293.66]), (55.0, [220.0, 261.63, 329.63]), (43.65, [174.61, 220.0, 261.63])]

    def add(t0, samples, gain=1.0):
        i0 = int(t0 * SR)
        for k, v in enumerate(samples):
            j = i0 + k
            if 0 <= j < n:
                buf[j] += v * gain

    def kick():
        s, ph = [], 0.0
        for k in range(int(0.34 * SR)):
            f = 44 + 100 * math.exp(-k / SR * 32)
            ph += 2 * math.pi * f / SR
            s.append(math.sin(ph) * math.exp(-k / SR * 8.5))
        return s

    def snare():
        return [(rnd.uniform(-1, 1) * math.exp(-k / SR * 20) * 0.55 + math.sin(2 * math.pi * 188 * k / SR) * math.exp(-k / SR * 28) * 0.4) for k in range(int(0.22 * SR))]

    def hat(decay=95, length=0.07):
        prev, s = 0.0, []
        for k in range(int(length * SR)):
            x = rnd.uniform(-1, 1)
            s.append((x - prev) * 0.5 * math.exp(-k / SR * decay))
            prev = x
        return s

    def boom():
        s, ph = [], 0.0
        for k in range(int(0.5 * SR)):
            ph += 2 * math.pi * (70 - 35 * min(1, k / (0.5 * SR))) / SR
            s.append(math.sin(ph) * math.exp(-k / SR * 6))
        return s

    def crash(length=1.4):
        prev, s = 0.0, []
        for k in range(int(length * SR)):
            x = rnd.uniform(-1, 1)
            s.append((x - prev) * 0.45 * math.exp(-k / SR * 3.2))
            prev = x
        return s

    def riser(length):
        m, s, ph = int(length * SR), [], 0.0
        for k in range(m):
            p = k / m
            ph += 2 * math.pi * (220 + 1500 * p * p) / SR
            s.append((rnd.uniform(-1, 1) * 0.5 + math.sin(ph) * 0.5) * p ** 2.2)
        return s

    def tone(f, length, attack=0.01, decay=6.0, harm=(1.0, 0.35, 0.15)):
        s = []
        for k in range(int(length * SR)):
            t = k / SR
            env = min(1.0, t / attack) * math.exp(-t * decay)
            s.append(sum(h * math.sin(2 * math.pi * f * (i + 1) * t) for i, h in enumerate(harm)) * env)
        return s

    K, S, H, HO, B = kick(), snare(), hat(), hat(28, 0.22), boom()
    kicks = []
    t, step = 0.0, 0
    while t < seconds:
        barno = int(t / bar)
        beat_in_bar = int(round((t - barno * bar) / beat)) % 4
        grooving = t >= drop - 1e-6
        root, chord = prog[barno % 4]
        # pad: one soft chord per bar, from the start
        if abs(t - barno * bar) < 1e-6:
            for f in chord:
                add(t, tone(f, bar * 1.05, attack=0.6, decay=0.5, harm=(1.0, 0.25)), 0.05)
        # kick: beat 1 only before the drop, four on the floor after
        if (not grooving and beat_in_bar == 0) or grooving:
            add(t, K, 0.85 if grooving else 0.6)
            kicks.append(t)
        if grooving and beat_in_bar in (1, 3):
            add(t, S, 0.5)
        # hats on the eighths (quieter before the drop), an open hat on the off-beat of 4
        add(t, H, 0.22 if grooving else 0.1)
        add(t + beat / 2, HO if (grooving and beat_in_bar == 3) else H, 0.2 if grooving else 0.08)
        if grooving:
            # bass: root on 1, the octave on the "and" of 2, the root again on 3
            if beat_in_bar == 0:
                add(t, tone(root, beat * 1.9, attack=0.005, decay=2.4, harm=(1.0, 0.5, 0.2)), 0.45)
            if beat_in_bar == 1:
                add(t + beat / 2, tone(root * 2, beat * 0.9, attack=0.005, decay=4.0, harm=(1.0, 0.4)), 0.3)
            if beat_in_bar == 2:
                add(t, tone(root, beat * 1.4, attack=0.005, decay=3.0, harm=(1.0, 0.5, 0.2)), 0.4)
            # arpeggio in sixteenths on the chord tones, a pluck
            for q in range(4):
                f = chord[(step * 4 + q) % 3] * (2 if (step + q) % 5 == 0 else 1)
                add(t + q * beat / 4, tone(f, 0.22, attack=0.003, decay=14), 0.12)
        t += beat
        step += 1

    # riser into the drop, a crash on it
    rl = min(drop, bar * 1.5)
    if drop - rl >= 0:
        add(drop - rl, riser(rl), 0.35)
    add(drop, crash(), 0.5)
    add(drop, B, 0.6)
    # an accent on every cut of the picture: a short noise hit and a low boom, louder when it falls between beats
    for c in cuts:
        if 0 <= c < seconds:
            near = min(abs(c - k) for k in kicks) if kicks else 1
            add(c, hat(35, 0.16), 0.5 if near > 0.05 else 0.3)
            add(c, B, 0.45 if near > 0.05 else 0.25)
    # the end: a last hit
    add(max(0, seconds - 1.6), B, 0.5)
    # duck everything but the kick a little right after each kick (the pulse breathes): done on the whole mix, cheaply
    if kicks:
        ki = 0
        for i in range(n):
            tt = i / SR
            while ki + 1 < len(kicks) and kicks[ki + 1] <= tt:
                ki += 1
            d = tt - kicks[ki]
            if 0 <= d < 0.18:
                buf[i] *= 0.62 + 0.38 * (d / 0.18)
    # master: fade in/out, soft clip, normalise
    fade_in, fade_out = 0.4, 1.4
    for i in range(n):
        tt = i / SR
        g = min(1.0, tt / fade_in) * min(1.0, max(0.0, (seconds - tt) / fade_out))
        buf[i] = math.tanh(buf[i] * 1.15) * g
    peak = max(1e-9, max(abs(v) for v in buf))
    scale = 0.89 / peak
    with wave.open(out, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v * scale)) * 32000)) for v in buf))
    print(out)


main()
