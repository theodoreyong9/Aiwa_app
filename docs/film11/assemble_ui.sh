#!/bin/bash
# the page of the screens is written in pieces (head, the acts, the scenes); this puts them together
cd "$(dirname "$0")"; P=${PARTS:-/tmp/os11}
cat $P/head.html $P/body_act1.js $( [ -f $P/body_scenes.js ] && echo $P/body_scenes.js ) $P/modes.js $P/footer.js > ui11.html && python3 build11.py
