#!/bin/bash
# film 12, the stations (six dioramas and the wide shot): Cycles, resumable. Needs /tmp/bpyenv (bpy) and the assets of /tmp/ph (skills/kit/asset-research: fetch).
cd "$(dirname "$0")"
OUT=${OUT:-/tmp/os12/st}; PY=${PY:-/tmp/bpyenv/bin/python}; mkdir -p "$OUT"
for s in S1 S2 S3 S4 S5 S6 WIDE; do
  [ -s "$OUT/${s}_depth.png" ] && [ -s "$OUT/${s}.json" ] && { echo "have $s"; continue; }
  nice -n 5 $PY scene12.py -- --shot $s --out "$OUT" --width 2880 --height 1620 --samples 64 2>&1 | grep -E "^station|Error|Traceback"
  echo "$s done $(date +%T)" >> "$OUT/steps.log"
done
echo ALLDONE >> "$OUT/steps.log"
