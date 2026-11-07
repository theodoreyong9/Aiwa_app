#!/bin/bash
# film 12, the end: the sound (voices, effects, the music made as long as the film), the frames of /tmp/os12/out, the assembly (video-kit).
# Needs the frames composed (compose12.py) and the voices (voice12.py, in /tmp/os11/voice: the text of the voices did not change).
set -e
cd "$(dirname "$0")"; R=$(cd ../.. && pwd); W=/tmp/os12/w; mkdir -p $W
python3 sound12.py ${VOICES:-/tmp/os11/voice} $W
MUS=${MUS:-/tmp/os3/mus/inc-hiding-your-reality.mp3}
T=$(python3 -c "import json;print(json.load(open('timeline12.json'))['total'])"); SH=$(python3 -c "import json;print(json.load(open('timeline12.json'))['act3']['shatter'])")
# the track is 90 s: it is played, then its last minute comes back (crossfaded) so that it covers the film; it opens softly, dips at the break, and ends with the film
ffmpeg -loglevel error -y -i $MUS -filter_complex "[0:a]asplit[a][b];[a]atrim=0:90,asetpts=PTS-STARTPTS[a1];[b]atrim=24:90,asetpts=PTS-STARTPTS[b1];[a1][b1]acrossfade=d=5:c1=tri:c2=tri,loudnorm=I=-15:TP=-1.5:LRA=7,afade=t=in:st=0:d=4,volume='if(between(t,$SH-0.05,$SH+0.9),0.3,1)':eval=frame,atrim=0:$T,afade=t=out:st=$(python3 -c "print($T-6)"):d=6[m]" -map "[m]" $W/music.wav
ffmpeg -loglevel error -y -i $W/music.wav -i $W/sfx.wav -filter_complex "[1:a]volume=0.9[s];[0:a][s]amix=inputs=2:normalize=0:duration=longest,atrim=0:$T,alimiter=limit=0.97[o]" -map "[o]" $W/bed.wav
ffmpeg -loglevel error -y -i $W/bed.wav -i $W/vo.wav -filter_complex "[1:a]asplit[v1][v2];[0:a][v1]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=350[bd];[bd][v2]amix=inputs=2:normalize=0:weights='1 1.25',loudnorm=I=-12:TP=-1:LRA=9,atrim=0:$T[o]" -map "[o]" -ar 44100 $W/mix.wav
(cd $R/skills/kit/video-kit && node src/cli.js assemble /tmp/os12/out $W/film12.mp4 --fps=24 --audio=$W/bed.wav --voice=$W/vo.wav --duck=light --grade=cinematic --bloom=0.08 --grain=0.025 --vignette=0.2 --crf=18 2>&1 | tail -2)
ffmpeg -loglevel error -y -i $W/film12.mp4 -i $W/mix.wav -map 0:v -map 1:a -c:v libx264 -preset slow -crf 24 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart $W/film12-send.mp4
ls -la $W/film12-send.mp4; ffprobe -v error -show_entries format=duration -of csv=p=0 $W/film12-send.mp4
