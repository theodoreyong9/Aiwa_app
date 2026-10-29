"""The campaigns, as the film shows them (old film time, the time of the scene): pairs « a file + a connector » fall one by one, ever faster, onto the super agent; each one that lands
sends a wave, and the pair is multiplied into copies that ride the wave outward. The scene (scene3d.py) draws it and the sound (sound.py) is placed on the same schedule."""
T0, T1 = 36.6, 39.4          # the first pair leaves, the last one leaves
FALL = 0.52                  # seconds from the top to the super agent
WAVE = 1.25                  # seconds a wave lives
FILES = ['file_docs', 'file_media', 'file_app', 'file_page', 'file_contract']
CHANNELS = ['ch_gmail', 'ch_whatsapp', 'ch_telegram', 'ch_linkedin', 'ch_x']


def schedule():
    out, t, n = [], T0, 0
    while t < T1:
        out.append(dict(n=n, t0=round(t, 3), t1=round(t + FALL, 3), file=FILES[(n * 3 + 1) % 5], chan=CHANNELS[(n * 2 + n // 5) % 5], x=(((n * 37) % 11) - 5) / 5 * 0.07, a=((n * 137) % 360)))
        t += max(0.11, 0.34 - 0.0786 * (t - T0))
        n += 1
    return out
