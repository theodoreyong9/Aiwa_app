#!/bin/bash
set -e
cd /home/user/aiwa_store/docs/videos/aiwa-os3
rm -rf /tmp/os3/f6 && python3 retime.py /tmp/os3/f6
(ss -ltn 2>/dev/null | grep -q 8123) || (cd /tmp/srv && setsid nohup python3 -m http.server 8123 --bind 127.0.0.1 > /tmp/srv.log 2>&1 &); sleep 2
ln -sfn /tmp/os3/f6/anchors.json /tmp/srv/anchors6.json
ln -sfn /home/user/aiwa_store/docs/videos/aiwa-os3/overlay.built.html /tmp/srv/overlay.built.html
rm -f /tmp/aiwa-v25; ln -s /home/user/aiwa_store/docs/videos/aiwa-v25 /tmp/aiwa-v25
rm -rf /tmp/os3/ov6 && NODE_PATH=/home/user/aiwa_store/node_modules timeout 3000 node render_overlay.cjs /tmp/os3/ov6 24 1920 1080 4 1884 /anchors6.json 2>&1 | tail -1
cd /tmp/os3 && rm -rf comp6 && mkdir comp6 && ffmpeg -loglevel error -y -framerate 24 -i f6/%05d.jpg -framerate 24 -i ov6/%05d.png -filter_complex "[0]scale=1920:1080:flags=lanczos,unsharp=5:5:0.6:5:5:0[b];[b][1]overlay=format=auto" -q:v 2 comp6/%05d.jpg
ls comp6 | wc -l
cd /home/user/aiwa_store/docs/videos/aiwa-os3 && python3 sound5.py timeline.json /tmp/os3/w/sfx6.wav
cd /tmp/os3/w && ffmpeg -loglevel error -y -i /tmp/os3/mus/inc-at-launch.mp3 -i sfx6.wav -filter_complex "[0:a]loudnorm=I=-13:TP=-1.5:LRA=7,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,adelay=950|950,afade=t=in:st=0.95:d=0.4,afade=t=out:st=75.0:d=3.5,apad=whole_dur=78.5,atrim=0:78.5[m];[1:a]volume=0.55[s];[m][s]amix=inputs=2:normalize=0:duration=longest,atrim=0:78.5,alimiter=limit=0.97[o]" -map "[o]" bed6.wav
ffmpeg -loglevel error -y -i bed6.wav -i vo6.wav -filter_complex "[1:a]asplit[v1][v2];[0:a][v1]sidechaincompress=threshold=0.04:ratio=3.5:attack=10:release=300[bd];[bd][v2]amix=inputs=2:normalize=0:weights='1 1.1',loudnorm=I=-11:TP=-1:LRA=9,atrim=0:78.5[o]" -map "[o]" -ar 44100 mix6.wav
cd /home/user/aiwa_store && node video-kit/src/cli.js assemble /tmp/os3/comp6 /tmp/os3/w/aiwa-os3-v6.mp4 --fps=24 --audio=/tmp/os3/w/bed6.wav --voice=/tmp/os3/w/vo6.wav --duck=light --grade=cinematic --bloom=0.08 --grain=0.025 --vignette=0.2 --crf=18 2>&1 | tail -1
cd /tmp/os3/w && ffmpeg -loglevel error -y -i aiwa-os3-v6.mp4 -i mix6.wav -map 0:v -map 1:a -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart aiwa-os3-v6-send.mp4
ls -la aiwa-os3-v6-send.mp4; ffprobe -v error -show_entries format=duration -of csv=p=0 aiwa-os3-v6-send.mp4
echo MAKE6DONE > /tmp/os3/make6.done
