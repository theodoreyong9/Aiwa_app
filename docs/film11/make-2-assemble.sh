#!/bin/bash
# film 11, the end: the sound (voices, effects, music), the frames of /tmp/os11/out, the assembly (video-kit). Needs the frames composed (compose11.py) and the voices (voice11.py).
set -e
cd "$(dirname "$0")"; R=$(cd ../.. && pwd); W=/tmp/os11/w; mkdir -p $W
python3 sound11.py /tmp/os11/voice $W
MUS=${MUS:-/tmp/os3/mus/inc-orion-300xb.mp3}
T=$(python3 -c "import json;print(json.load(open('timeline11.json'))['total'])"); SH=$(python3 -c "import json;print(json.load(open('timeline11.json'))['act3']['shatter'])")
ffmpeg -loglevel error -y -i $MUS -i $W/sfx.wav -filter_complex "[0:a]loudnorm=I=-15:TP=-1.5:LRA=7,afade=t=in:st=0:d=3,atrim=0:$SH,afade=t=out:st=$(python3 -c "print($SH-.25)"):d=0.25,apad=whole_dur=$T,atrim=0:$T[m];[1:a]volume=0.85[s];[m][s]amix=inputs=2:normalize=0:duration=longest,atrim=0:$T,alimiter=limit=0.97[o]" -map "[o]" $W/bed.wav
ffmpeg -loglevel error -y -i $W/bed.wav -i $W/vo.wav -filter_complex "[1:a]asplit[v1][v2];[0:a][v1]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=350[bd];[bd][v2]amix=inputs=2:normalize=0:weights='1 1.25',loudnorm=I=-12:TP=-1:LRA=9,atrim=0:$T[o]" -map "[o]" -ar 44100 $W/mix.wav
(cd $R/skills/kit/video-kit && node src/cli.js assemble /tmp/os11/out $W/film11.mp4 --fps=24 --audio=$W/bed.wav --voice=$W/vo.wav --duck=light --grade=cinematic --bloom=0.08 --grain=0.025 --vignette=0.2 --crf=18 2>&1 | tail -2)
ffmpeg -loglevel error -y -i $W/film11.mp4 -i $W/mix.wav -map 0:v -map 1:a -c:v libx264 -preset slow -crf 25 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart $W/film11-send.mp4
ls -la $W/film11-send.mp4; ffprobe -v error -show_entries format=duration -of csv=p=0 $W/film11-send.mp4
