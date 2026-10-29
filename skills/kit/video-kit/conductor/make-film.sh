#!/bin/sh
# make-film.sh <film.json> <workdir> [music.wav]: from a film graph (outline.mjs) to the mp4, any film, any quality that uses the conductor. Run from the repository root.
#   plan -> clips (a missing one is reported, never replaced) -> stage -> render -> voice -> sound -> assemble -> check
set -e
FILM=$1; W=$2; MUSIC=$3
[ -n "$FILM" ] && [ -n "$W" ] || { echo "usage: make-film.sh film.json workdir [music.wav]"; exit 1; }
mkdir -p "$W"
T=$(node -e "console.log(JSON.parse(require('fs').readFileSync('$FILM','utf8')).total)")
node video-kit/conductor/conduct.mjs "$FILM" --out="$W/plan.json"
node video-kit/conductor/stage/stage.mjs "$W/plan.json" "$W" "$FILM"
[ -n "$RESUME" ] || rm -rf "$W/frames"   # RESUME=1 keeps the frames already rendered
N=$(node -e "console.log(Math.round($T*30))")
# a long render can lose the browser: it is started again, and the frames already on disk are kept
for TRY in $(seq 1 30); do
  node video-kit/src/cli.js render "$W/stage/index.html" "$W/frames" --seconds="$T" --width=1920 --height=1080 --workers=4 || true
  [ "$(ls "$W/frames" | grep -c '\.jpg$')" -ge "$N" ] && break
done
[ "$(ls "$W/frames" | grep -c '\.jpg$')" -ge "$N" ] || { echo "the render did not finish"; exit 1; }
node -e "const p=JSON.parse(require('fs').readFileSync('$W/plan.json','utf8'));require('fs').writeFileSync('$W/cues.json',JSON.stringify(p.beats.filter(b=>b.say).map(b=>({at:+(b.t0+.25).toFixed(2),text:b.say}))))"
python3 video-kit/src/voice.py "$W/cues.json" "$W/vo.wav" "$T" > "$W/voice.log" 2>&1 || { echo "no voice (see $W/voice.log): the film has the sound design only"; rm -f "$W/vo.wav"; }
python3 video-kit/conductor/mix.py "$W/plan.json" "$W/audio.wav" ${MUSIC:+--music "$MUSIC"}
node video-kit/src/cli.js assemble "$W/frames" "$W/film.mp4" --audio="$W/audio.wav" ${W:+$( [ -f "$W/vo.wav" ] && echo --voice="$W/vo.wav" )} --duck=light --crf=20 --grade=cinematic --bloom=0.06 --grain=0.012 --vignette=0.18
node video-kit/src/cli.js check "$W/film.mp4" --seconds="$T" --width=1920 --height=1080
