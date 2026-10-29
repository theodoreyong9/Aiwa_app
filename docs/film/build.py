"""Builds the pages of the film from the timeline: screens.html -> screens.built.html, phone.html -> phone.built.html (the timeline put inside).   python3 docs/videos/aiwa-os3/build.py"""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
tl = json.load(open(os.path.join(D, 'timeline.json')))
for name in ('screens', 'phone', 'overlay', 'contract'):
    src = open(os.path.join(D, name + '.html'), encoding='utf-8').read().replace('__TIMELINE__', json.dumps(tl, ensure_ascii=False))
    open(os.path.join(D, name + '.built.html'), 'w', encoding='utf-8').write(src)
print('built')
