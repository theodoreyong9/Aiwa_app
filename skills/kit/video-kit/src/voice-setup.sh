#!/bin/sh
# Sets up the natural French voice used by voice.py: the Piper voice "siwis medium" through sherpa-onnx (runs on the CPU, about 80 MB, from PyPI and GitHub
# releases). Run it once. Without it, voice.py falls back on espeak-ng (robotic).  --with-kokoro adds a second neural voice (about 350 MB).
set -e
python3 -m pip install -q sherpa-onnx soundfile
DIR="${HOME}/.cache/aiwa-video"
mkdir -p "$DIR"
V=vits-piper-fr_FR-siwis-medium
if [ ! -s "$DIR/$V/fr_FR-siwis-medium.onnx" ]; then
  curl -fsSL -o "$DIR/$V.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/$V.tar.bz2"
  tar -xjf "$DIR/$V.tar.bz2" -C "$DIR" && rm -f "$DIR/$V.tar.bz2"
fi
if [ "$1" = "--with-kokoro" ]; then
  python3 -m pip install -q kokoro-onnx
  BASE=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
  [ -s "$DIR/kokoro-v1.0.onnx" ] || curl -fsSL -o "$DIR/kokoro-v1.0.onnx" "$BASE/kokoro-v1.0.onnx"
  [ -s "$DIR/voices-v1.0.bin" ] || curl -fsSL -o "$DIR/voices-v1.0.bin" "$BASE/voices-v1.0.bin"
fi
command -v espeak-ng >/dev/null 2>&1 || apt-get install -y espeak-ng >/dev/null 2>&1 || true
echo "voice ready: $DIR"
