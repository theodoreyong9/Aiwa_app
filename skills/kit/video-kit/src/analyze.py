#!/usr/bin/env python3
"""Reads a film and writes a report of how it is made: its shots and their rhythm, its movement, its sound, its colour. Pure Python and ffmpeg: no
other tool, no account, no network. The film is only read (and may be deleted afterwards): what is kept is the REPORT, measurements and short
notes in our own words, never a picture or a sound of the film.

  analyze.py film.mp4 [--out report.json] [--md report.md] [--title "name"] [--scene=0.3]

What it measures (all of it can be checked against the film):
  shots       where the picture cuts (scene-change score above --scene), each shot's length, average colour, mean brightness, movement
  rhythm      number of shots, average and median shot length, the share of shots under one second, the first cut (the hook), the pace in each
              tenth of the film, and whether it speeds up (cuts per second in the last third over the first third)
  movement    the mean absolute difference of consecutive frames, per second (a still picture is near zero)
  sound       loudness per second, the silences, the loudness range, an estimate of the tempo (autocorrelation of the onsets) and how sure it is
  colour      the average colour, the brightness and saturation of the whole, and per shot
  transcript  only when faster-whisper is installed (otherwise null: it is not guessed)
Limits: it finds HARD cuts well (a new picture); a soft transition (a dissolve, a push) or a text change on a similar dark background is found late or not at all, so the shot count then understates (lower --scene to 0.1 to be more sensitive, at the cost of false cuts on fast movement); the tempo is meaningless for speech without music.
"""
import colorsys, json, math, os, re, statistics, subprocess, sys

FFMPEG = os.environ.get('FFMPEG') or 'ffmpeg'


def run(args, **kw):
    return subprocess.run([FFMPEG, '-hide_banner', '-nostats'] + args, capture_output=True, **kw)


def probe(path):
    err = run(['-i', path]).stderr.decode('utf-8', 'replace')
    d = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    v = re.search(r'Video: .*?, (\d{2,5})x(\d{2,5})', err)
    fps = re.search(r'(\d+(?:\.\d+)?) fps', err)
    return {'duration': round(dur, 3), 'width': int(v.group(1)) if v else None, 'height': int(v.group(2)) if v else None,
            'fps': float(fps.group(1)) if fps else None, 'has_audio': 'Audio:' in err}


def shots_cuts(path, scene):
    out = run(['-i', path, '-an', '-vf', f'scale=320:-1,select=gt(scene\\,{scene}),metadata=print:key=lavfi.scene_score:file=-', '-f', 'null', '-']).stdout.decode()
    return [float(m.group(1)) for m in re.finditer(r'pts_time:([\d.]+)', out)]


def motion_series(path):
    out = run(['-i', path, '-an', '-vf', 'scale=320:-1,fps=15,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-', '-f', 'null', '-']).stdout.decode()
    return [float(x) for x in re.findall(r'YAVG=([\d.]+)', out)]          # 15 values per second


def avg_rgb(path, t):
    r = run(['-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']).stdout
    return list(r[:3]) if len(r) >= 3 else None


def loudness(path):
    out = run(['-i', path, '-vn', '-af', 'aresample=44100,asetnsamples=n=4410,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-', '-f', 'null', '-']).stdout.decode()
    vals = []
    for m in re.finditer(r'RMS_level=(-?[\d.]+|-inf)', out):
        vals.append(-120.0 if m.group(1) == '-inf' else float(m.group(1)))
    return vals                                                           # 10 values per second


def tempo(db):
    """BPM by autocorrelation of the onset strength (positive changes of the loudness envelope, 10 Hz)."""
    if len(db) < 80:
        return None, 0.0
    env = [10 ** (max(v, -80) / 20) for v in db]
    onset = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    mean = sum(onset) / len(onset)
    onset = [o - mean for o in onset]
    best, best_lag, scores = 0.0, None, []
    for lag in range(3, 21):                                              # 0.3 s .. 2 s at 10 Hz  → 200 .. 30 bpm
        s = sum(onset[i] * onset[i + lag] for i in range(len(onset) - lag)) / (len(onset) - lag)
        scores.append(s)
        if s > best:
            best, best_lag = s, lag
    if not best_lag or best <= 0:
        return None, 0.0
    var = sum(o * o for o in onset) / len(onset) or 1e-12
    return round(600.0 / best_lag, 1), round(min(1.0, best / var), 2)


def transcript(path):
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None
    try:
        model = WhisperModel('tiny', compute_type='int8')
        segs, _ = model.transcribe(path)
        return [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()} for s in segs]
    except Exception:
        return None


def hsv(rgb):
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return round(h * 360), round(s, 2), round(v, 2)


def main():
    pos, opt, argv = [], {}, sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith('--'):
            k, eq, v = a[2:].partition('=')
            if not eq and i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                i += 1
                v = argv[i]
            opt[k] = v
        else:
            pos.append(a)
        i += 1
    path = pos[0]
    scene = float(opt.get('scene', 0.3))
    info = probe(path)
    dur = info['duration']
    cuts = [c for c in shots_cuts(path, scene) if 0.2 < c < dur - 0.2]
    bounds = [0.0] + cuts + [dur]
    motion = motion_series(path)
    per_sec = [round(sum(motion[i:i + 15]) / max(1, len(motion[i:i + 15])), 3) for i in range(0, len(motion), 15)]
    shots = []
    for a, b in zip(bounds, bounds[1:]):
        mid = (a + b) / 2
        rgb = avg_rgb(path, mid) or [0, 0, 0]
        m = motion[int(a * 15):max(int(a * 15) + 1, int(b * 15))]
        shots.append({'start': round(a, 2), 'end': round(b, 2), 'len': round(b - a, 2), 'rgb': rgb, 'hsv': hsv(rgb), 'motion': round(sum(m) / len(m), 3) if m else 0.0})
    lens = [s['len'] for s in shots]
    third = dur / 3 if dur else 1
    first_rate = sum(1 for c in cuts if c < third) / third
    last_rate = sum(1 for c in cuts if c > 2 * third) / third
    deciles = [sum(1 for c in cuts if i * dur / 10 <= c < (i + 1) * dur / 10) for i in range(10)]
    stats = {
        'shots': len(shots), 'asl': round(statistics.mean(lens), 2) if lens else None, 'median_shot': round(statistics.median(lens), 2) if lens else None,
        'shortest': min(lens) if lens else None, 'longest': max(lens) if lens else None,
        'share_under_1s': round(sum(1 for x in lens if x < 1) / len(lens), 2) if lens else None,
        'first_cut': cuts[0] if cuts else None,
        'cuts_per_tenth': deciles,
        'acceleration': round(last_rate / first_rate, 2) if first_rate > 0 else None,
    }
    audio = None
    if info['has_audio']:
        db = loudness(path)
        sec = [round(sum(db[i:i + 10]) / len(db[i:i + 10]), 1) for i in range(0, len(db), 10)]
        silences, start = [], None
        for i, v in enumerate(db + [0]):
            if v < -50 and start is None:
                start = i / 10
            elif v >= -50 and start is not None:
                if i / 10 - start >= 0.5:
                    silences.append([round(start, 1), round(i / 10, 1)])
                start = None
        live = [v for v in db if v > -70]
        bpm, conf = tempo(db)
        audio = {'loudness_per_second_db': sec, 'silences': silences, 'range_db': round(max(live) - min(live), 1) if live else None, 'bpm': bpm, 'bpm_confidence': conf}
    mean_rgb = [round(sum(s['rgb'][k] * s['len'] for s in shots) / dur) for k in range(3)] if dur else [0, 0, 0]
    colour = {'average_rgb': mean_rgb, 'hsv': hsv(mean_rgb), 'brightness_per_shot': [s['hsv'][2] for s in shots], 'saturation_mean': round(statistics.mean(s['hsv'][1] for s in shots), 2) if shots else None}
    report = {'title': opt.get('title') or os.path.basename(path), 'file': os.path.basename(path), 'scene_threshold': scene, **info, 'stats': stats, 'shots': shots,
              'movement': {'mean': round(statistics.mean(motion), 3) if motion else None, 'median': round(statistics.median(motion), 3) if motion else None,
                           'still_half_seconds': round(sum(1 for i in range(0, len(motion) - 7, 7) if sum(motion[i:i + 7]) / 7 < 0.15) / max(1, len(motion) // 7), 2), 'per_second': per_sec},
              'audio': audio, 'colour': colour, 'transcript': transcript(path)}
    report['reading'] = reading(report)
    out = opt.get('out')
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if out:
        open(out, 'w', encoding='utf-8').write(text)
    if opt.get('md'):
        open(opt['md'], 'w', encoding='utf-8').write(markdown(report))
    print(text if not out else out)


def reading(r):
    """Short notes in words, computed from the numbers (not an opinion of the film)."""
    s, m, a = r['stats'], r['movement'], r['audio']
    notes = [f"{s['shots']} shots in {r['duration']:.1f} s: average {s['asl']} s, median {s['median_shot']} s, longest {s['longest']} s; {int((s['share_under_1s'] or 0) * 100)}% of the shots last under a second."]
    if s['first_cut'] is not None:
        notes.append(f"First cut at {s['first_cut']} s" + (' (the hook is quick).' if s['first_cut'] < 2 else ' (a slow opening).'))
    if s['acceleration']:
        notes.append(f"The pace {'speeds up' if s['acceleration'] > 1.2 else 'slows down' if s['acceleration'] < 0.8 else 'stays even'} (last third over first third: ×{s['acceleration']}).")
    notes.append(f"Movement: mean {m['mean']}, {int(m['still_half_seconds'] * 100)}% of the half-seconds barely move" + (' (it reads as a slideshow).' if m['still_half_seconds'] > 0.4 else '.'))
    if a:
        notes.append(f"Sound: loudness range {a['range_db']} dB, {len(a['silences'])} silence(s)" + (f", tempo about {a['bpm']} bpm (confidence {a['bpm_confidence']})." if a['bpm'] else '.'))
    return notes


def markdown(r):
    lines = [f"# {r['title']}", '', f"{r['width']}x{r['height']}, {r['duration']:.1f} s, {r['fps']} fps. Measured by `video-kit/src/analyze.py` (scene threshold {r['scene_threshold']}).", '']
    lines += [f'- {n}' for n in r['reading']]
    lines += ['', '## Shots', '', '| # | start | length | brightness | movement |', '|---|---|---|---|---|']
    lines += [f"| {i + 1} | {s['start']} | {s['len']} | {s['hsv'][2]} | {s['motion']} |" for i, s in enumerate(r['shots'])]
    return '\n'.join(lines) + '\n'


main()
