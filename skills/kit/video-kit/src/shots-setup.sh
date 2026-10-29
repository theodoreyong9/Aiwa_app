#!/bin/sh
# Sets up what the real shots need: Blender as a python package (3D shots, CPU) and OpenCV (tracking a real footage). Run it once, only when a film uses these shots.
# bpy 5 is built for Python 3.13: the script looks for it. About 400 MB, from PyPI. Without a GPU a 1080p frame takes 10 to 25 s: render a few frames first.
set -e
PY=$(command -v python3.13 || true)
if [ -z "$PY" ]; then echo "Python 3.13 is needed for bpy (apt-get install -y python3.13, or use a session image that has it); OpenCV alone works with any python3" >&2; PY=python3; fi
$PY -m pip install -q opencv-python-headless numpy
if [ "$PY" = "$(command -v python3.13 || true)" ]; then $PY -m pip install -q bpy; $PY -c "import bpy; print('blender', bpy.app.version_string)"; fi
$PY -c "import cv2; print('opencv', cv2.__version__)"
echo "shots ready: $PY"
