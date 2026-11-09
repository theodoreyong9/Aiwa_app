#!/bin/sh
# Sets up the natural French voice used by voice.py: the Piper voice "siwis medium" through sherpa-onnx (runs on the CPU, about 80 MB, from PyPI and GitHub
# releases). Run it once. Without it, voice.py falls back on espeak-ng (robotic).
#   --with-english  adds the English Piper voice "ryan high" (about 130 MB).
#   --with-kokoro   adds the Kokoro voice (about 350 MB; French "ff_siwis" and English; more natural, about five times slower than Piper: for films, not for a live conversation).
# The two flags can be given together, in any order.
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
for flag in "$@"; do
  case "$flag" in
    --with-english) fetch vits-piper-en_US-ryan-high en_US-ryan-high.onnx ;;
    --with-kokoro) fetch kokoro-multi-lang-v1_0 model.onnx ;;
  esac
done
command -v espeak-ng >/dev/null 2>&1 || apt-get install -y espeak-ng >/dev/null 2>&1 || true
echo "voice ready: $DIR"
