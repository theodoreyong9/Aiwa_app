#!/usr/bin/env python3
"""A voice-over track from a list of cues, with a local text-to-speech engine. No account, no network, no licence question.

  voice.py cues.json out.wav SECONDS [--lang=fr] [--speed=150] [--voice=NAME]

  cues.json: [ { "at": 3.2, "text": "Salut, je suis Yo." }, … ]    each line is spoken from its `at` second; the track is SECONDS long
  Engines, in order: piper (PIPER_BIN and PIPER_MODEL set), sherpa (the Piper voice "siwis medium", French, natural: run `sh voice-setup.sh` once; the speed
  is --kspeed=1.0), kokoro (`sh voice-setup.sh --with-kokoro`: another neural voice, French and English), espeak-ng (`apt-get install -y espeak-ng`:
  intelligible, robotic), flite. Every voice goes through the same light mastering (equaliser, soft compression, a little room) so that it sits in a mix.
  The engine used and the duration of each line are printed as JSON, so that a line which runs into the next one can be seen and shortened.
  Honest limit: espeak-ng is robotic; the neural voices are far more natural, but they are not a studio narrator. Say which engine spoke.
"""
import json, os, shutil, subprocess, sys, tempfile, wave


def load_kokoro():
    """The kokoro engine, or None: the python package and its two model files (see voice-setup.sh; KOKORO_MODEL and KOKORO_VOICES override the places)."""
    cache = os.path.join(os.path.expanduser('~'), '.cache', 'aiwa-video')
    model = os.environ.get('KOKORO_MODEL') or os.path.join(cache, 'kokoro-v1.0.onnx')
    voices = os.environ.get('KOKORO_VOICES') or os.path.join(cache, 'voices-v1.0.bin')
    if not (os.path.exists(model) and os.path.exists(voices)):
        return None
    try:
        import soundfile  # noqa: F401
        from kokoro_onnx import Kokoro
        return Kokoro(model, voices)
    except Exception:
        return None


def load_sherpa():
    """The Piper voice "siwis medium" through sherpa-onnx, or None (see voice-setup.sh; SHERPA_VOICE_DIR overrides the place)."""
    d = os.environ.get('SHERPA_VOICE_DIR') or os.path.join(os.path.expanduser('~'), '.cache', 'aiwa-video', 'vits-piper-fr_FR-siwis-medium')
    onnx = os.path.join(d, 'fr_FR-siwis-medium.onnx')
    if not os.path.exists(onnx):
        return None
    try:
        import soundfile  # noqa: F401
        import sherpa_onnx as so
        cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(
            model=onnx, tokens=os.path.join(d, 'tokens.txt'), data_dir=os.path.join(d, 'espeak-ng-data')), num_threads=4), max_num_sentences=1)
        return so.OfflineTts(cfg)
    except Exception:
        return None


# light mastering: remove rumble, a little presence, tame the low-mids, even out the level, a short room
MASTER = 'highpass=f=70,equalizer=f=3000:t=q:w=1.2:g=2.5,equalizer=f=200:t=q:w=1:g=-1.5,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=3,aecho=0.85:0.4:35|70:0.12|0.06'


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith('--')]
    opt = dict(a[2:].partition('=')[::2] for a in sys.argv[1:] if a.startswith('--'))
    cues_file, out, seconds = pos[0], pos[1], float(pos[2])
    lang, speed, voice = opt.get('lang', 'fr'), opt.get('speed', '150'), opt.get('voice', '')
    ffmpeg = os.environ.get('FFMPEG') or 'ffmpeg'
    cues = json.load(open(cues_file))
    tmp = tempfile.mkdtemp(prefix='vo-')
    engine, kokoro, sherpa = None, None, None
    if os.environ.get('PIPER_BIN') and os.environ.get('PIPER_MODEL'):
        engine = 'piper'
    elif lang == 'fr' and not voice and (sherpa := load_sherpa()):
        engine = 'sherpa'
    elif (kokoro := load_kokoro()):
        engine = 'kokoro'
    elif shutil.which('espeak-ng'):
        engine = 'espeak-ng'
    elif shutil.which('flite'):
        engine = 'flite'
    if not engine:
        print(json.dumps({'ok': False, 'error': 'no text-to-speech engine: apt-get install -y espeak-ng (or set PIPER_BIN and PIPER_MODEL)'}))
        sys.exit(3)
    parts, report = [], []
    for i, c in enumerate(cues):
        wav = os.path.join(tmp, f'{i:02d}.wav')
        text = str(c['text'])
        if engine == 'piper':
            subprocess.run([os.environ['PIPER_BIN'], '--model', os.environ['PIPER_MODEL'], '--output_file', wav], input=text, text=True, check=True, capture_output=True)
        elif engine == 'sherpa':
            import soundfile as sf
            audio = sherpa.generate(text, sid=0, speed=float(opt.get('kspeed', 1.0)))
            sf.write(wav, audio.samples, audio.sample_rate)
        elif engine == 'kokoro':
            import soundfile as sf
            lang_code = {'fr': 'fr-fr', 'en': 'en-us'}.get(lang, lang)
            name = voice or {'fr': 'ff_siwis', 'en': 'af_heart'}.get(lang, 'ff_siwis')
            samples, rate = kokoro.create(text, voice=name, speed=float(opt.get('kspeed', 1.0)), lang=lang_code)
            sf.write(wav, samples, rate)
        elif engine == 'espeak-ng':
            subprocess.run(['espeak-ng', '-v', voice or lang, '-s', speed, '-p', '45', '-w', wav, text], check=True, capture_output=True)
        else:
            subprocess.run(['flite', '-t', text, '-o', wav], check=True, capture_output=True)
        with wave.open(wav) as w:
            dur = w.getnframes() / w.getframerate()
        report.append({'at': c['at'], 'seconds': round(dur, 2), 'ends': round(c['at'] + dur, 2), 'text': text})
        parts.append((c['at'], wav))
    # place each line at its second, on a track of the right length
    cmd = [ffmpeg, '-y', '-loglevel', 'error']
    for _, wav in parts:
        cmd += ['-i', wav]
    filt = ''.join(f'[{i}:a]aresample=44100,aformat=channel_layouts=mono,adelay={int(at * 1000)}:all=1[a{i}];' for i, (at, _) in enumerate(parts))
    filt += ''.join(f'[a{i}]' for i in range(len(parts))) + f'amix=inputs={len(parts)}:normalize=0,{MASTER},apad=whole_dur={seconds},atrim=0:{seconds},loudnorm=I=-16:TP=-1.5:LRA=7[v]'
    subprocess.run(cmd + ['-filter_complex', filt, '-map', '[v]', '-ar', '44100', '-ac', '1', out], check=True)
    overlaps = [(a['text'][:30], b['text'][:30]) for a, b in zip(report, report[1:]) if a['ends'] > b['at']]
    print(json.dumps({'ok': True, 'engine': engine, 'out': out, 'lines': report, 'overlaps': overlaps}, ensure_ascii=False))


main()
