#!/bin/bash
# film 13, the end: the sound (voice, effects, music), the frames of /tmp/os13/out, the assembly (video-kit). Needs the frames (render_ui13.cjs -> /tmp/os13/ui, then link them as /tmp/os13/out) and the voices (voice13.py).
set -e
cd "$(dirname "$0")"; R=$(cd ../.. && pwd); W=/tmp/os13/w; mkdir -p $W
python3 sound13.py ${VOICES:-/tmp/os13/voice} $W
MUS=${MUS:-/tmp/os3/mus/inc-hiding-your-reality.mp3}
T=$(python3 -c "import json;print(json.load(open('timeline13.json'))['total'])"); SL=$(python3 -c "import json;print(json.load(open('timeline13.json'))['slam'])")
# the track from its 24th second (its drive), short fade in; it falls away at the blow and comes back
ffmpeg -loglevel error -y -ss 24 -i $MUS -filter_complex "[0:a]loudnorm=I=-14:TP=-1.5:LRA=7,afade=t=in:st=0:d=1.5,volume='if(between(t,$SL-0.02,$SL+0.55),0.12,1)':eval=frame,atrim=0:$T,afade=t=out:st=$(python3 -c "print($T-4)"):d=4[m]" -map "[m]" $W/music.wav
ffmpeg -loglevel error -y -i $W/music.wav -i $W/sfx.wav -filter_complex "[1:a]volume=0.55[s];[0:a][s]amix=inputs=2:normalize=0:duration=longest,atrim=0:$T,alimiter=limit=0.97[o]" -map "[o]" $W/bed.wav
ffmpeg -loglevel error -y -i $W/bed.wav -i $W/vo.wav -filter_complex "[1:a]asplit[v1][v2];[0:a][v1]sidechaincompress=threshold=0.03:ratio=4:attack=8:release=300[bd];[bd][v2]amix=inputs=2:normalize=0:weights='1 1.3',loudnorm=I=-12:TP=-2:LRA=8,alimiter=limit=0.84:level=disabled,atrim=0:$T[o]" -map "[o]" -ar 44100 $W/mix.wav
(cd $R/skills/kit/video-kit && node src/cli.js assemble ${FRAMES:-/tmp/os13/ui} $W/film13.mp4 --fps=24 --audio=$W/bed.wav --voice=$W/vo.wav --duck=light --grade=cinematic --bloom=0.1 --grain=0.03 --vignette=0.22 --crf=18 2>&1 | tail -2)
ffmpeg -loglevel error -y -i $W/film13.mp4 -i $W/mix.wav -map 0:v -map 1:a -c:v libx264 -preset slow -crf 24 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart $W/film13-send.mp4
ls -la $W/film13-send.mp4; ffprobe -v error -show_entries format=duration -of csv=p=0 $W/film13-send.mp4
