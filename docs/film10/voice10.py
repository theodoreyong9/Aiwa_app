"""Film 10, the voices: every line of cues10.json spoken on its own (the Piper voice « siwis », in local), the person's a little lower and closer, the agent's a little brighter with a short room, so that two voices are
heard in the film. Writes <out>/<id>.wav and <out>/durations.json.   python3 voice10.py cues10.json /tmp/os10/voice"""
import json, os, subprocess, sys, wave
import soundfile as sf
import sherpa_onnx as so
cues = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
d = os.path.join(os.path.expanduser('~'), '.cache', 'aiwa-video', 'vits-piper-fr_FR-siwis-medium')
cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(model=os.path.join(d, 'fr_FR-siwis-medium.onnx'), tokens=os.path.join(d, 'tokens.txt'), data_dir=os.path.join(d, 'espeak-ng-data')), num_threads=2), max_num_sentences=1)
tts = so.OfflineTts(cfg)
MASTER = {
    # the person: lower (a shade), warm, close
    'U': 'highpass=f=80,asetrate=22050*0.90,aresample=48000,atempo=1.11,equalizer=f=180:t=q:w=1:g=2,equalizer=f=3200:t=q:w=1.2:g=2,acompressor=threshold=-20dB:ratio=3:attack=6:release=120:makeup=3,aecho=0.8:0.3:22:0.08',
    # the agent: a little higher and brighter, a short room
    'A': 'highpass=f=100,asetrate=22050*1.05,aresample=48000,atempo=0.952,equalizer=f=4200:t=q:w=1.2:g=3,equalizer=f=250:t=q:w=1:g=-2,acompressor=threshold=-20dB:ratio=3:attack=6:release=120:makeup=3,aecho=0.8:0.4:48|90:0.16|0.08',
}
report = {}
for c in cues:
    raw = os.path.join(out, c['id'] + '_raw.wav'); wav = os.path.join(out, c['id'] + '.wav')
    audio = tts.generate(c['text'], sid=0, speed=1.0)
    sf.write(raw, audio.samples, audio.sample_rate)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-af', MASTER[c['who']], wav], check=True)
    with wave.open(wav) as w: report[c['id']] = round(w.getnframes() / w.getframerate(), 2)
    os.remove(raw)
json.dump(report, open(os.path.join(out, 'durations.json'), 'w'), indent=1); print(json.dumps(report))
