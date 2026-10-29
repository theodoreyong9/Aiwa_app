#!/usr/bin/env python3
"""A quiet procedural bed: a soft pad on a chord, a tick at each scene change. Placeholder music (no licence question): replace it with a
licensed track when there is one. Usage: audio-bed.py out.wav SECONDS [scene-start-seconds ...]"""
import math, struct, sys, wave

out, seconds = sys.argv[1], float(sys.argv[2])
marks = [float(x) for x in sys.argv[3:]]
SR = 44100
n = int(SR * seconds)
chord = [220.0, 261.63, 329.63]          # A minor
buf = [0.0] * n
for i in range(n):
    t = i / SR
    fade = min(1.0, t / 1.0) * min(1.0, max(0.0, (seconds - t) / 1.2))
    pad = sum(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t) for f in chord) / (3 * 1.3)
    buf[i] = 0.18 * fade * pad * (0.85 + 0.15 * math.sin(2 * math.pi * 0.2 * t))
for m in marks:
    start = int(m * SR)
    for k in range(int(0.12 * SR)):
        if start + k < n:
            buf[start + k] += 0.12 * math.sin(2 * math.pi * 1320 * k / SR) * math.exp(-k / SR * 40)
with wave.open(out, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v)) * 32000)) for v in buf))
print(out)
