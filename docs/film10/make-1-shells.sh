#!/bin/bash
# film 10, the shells (the rooms, the phones, the televisions): Cycles, resumable (a picture on disk is kept). Needs /tmp/bpyenv (bpy) and the assets of /tmp/ph.
cd "$(dirname "$0")"
OUT=${OUT:-/tmp/os10/st}; PY=${PY:-/tmp/bpyenv/bin/python}
mkdir -p "$OUT"
run() { tag=$1; shift; [ -s "$OUT/$tag.json" ] && [ -s "$OUT/${tag}_mask.png" ] && { echo "have $tag"; return; }; nice -n 5 $PY scene10.py -- --out "$OUT" "$@" 2>&1 | grep -E "^shot|Error|Traceback" ; echo "$tag done $(date +%T)" >> "$OUT/steps.log"; }
run R1       --shot R1 --width 2880 --height 1620 --samples 64
run R0       --shot R0 --variant on  --width 2880 --height 1620 --samples 64
run R0_off   --shot R0 --variant off --width 2880 --height 1620 --samples 64
run R3       --shot R3 --width 2880 --height 1620 --samples 64
run R4       --shot R4 --width 2880 --height 1620 --samples 64
run R2       --shot R2 --frame -1 --width 2880 --height 1620 --samples 64
for k in $(seq 0 35); do tag=$(printf "R2_%02d" $k); run $tag --shot R2 --frame $k --width 1600 --height 900 --samples 32; done
echo ALLDONE >> "$OUT/steps.log"
