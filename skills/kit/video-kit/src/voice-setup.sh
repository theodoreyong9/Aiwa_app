#!/bin/sh
# Sets up the natural voices used by voice.py, through sherpa-onnx (they run on the CPU; PyPI and GitHub releases, no account, no key). Run it once; voice.py runs it by itself when a voice is missing.
#   by default: the Piper voice "siwis medium" (French, about 80 MB, fast) AND the Kokoro voice (about 350 MB; English, better than Piper; French "ff_siwis", equivalent to Piper;
#   about five times slower than Piper: for films, not for a live conversation).
#   --light         only the Piper voice (no Kokoro).
#   --with-english  adds the English Piper voice "ryan high" (about 130 MB), a lighter English voice than Kokoro.
# Without any of this, voice.py falls back on espeak-ng (robotic).
set -e
python3 -m pip install -q sherpa-onnx soundfile
DIR="${HOME}/.cache/aiwa-video"
mkdir -p "$DIR"
V=vits-piper-fr_FR-siwis-medium
if [ ! -s "$DIR/$V/fr_FR-siwis-medium.onnx" ]; then
  curl -fsSL -o "$DIR/$V.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$V.tar.bz2"
  tar -xjf "$DIR/$V.tar.bz2" -C "$DIR" && rm -f "$DIR/$V.tar.bz2"
fi
fetch() {  # fetch NAME FILE-THAT-PROVES-IT: the model archive of the sherpa-onnx releases, once
  if [ ! -s "$DIR/$1/$2" ]; then
    curl -fsSL -o "$DIR/$1.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$1.tar.bz2"
    tar -xjf "$DIR/$1.tar.bz2" -C "$DIR" && rm -f "$DIR/$1.tar.bz2"
  fi
}
LIGHT=0
for flag in "$@"; do
  case "$flag" in
    --light) LIGHT=1 ;;
    --with-english) fetch vits-piper-en_US-ryan-high en_US-ryan-high.onnx ;;
  esac
done
[ "$LIGHT" = 1 ] || fetch kokoro-multi-lang-v1_0 model.onnx
command -v espeak-ng >/dev/null 2>&1 || apt-get install -y espeak-ng >/dev/null 2>&1 || true
echo "voice ready: $DIR"
