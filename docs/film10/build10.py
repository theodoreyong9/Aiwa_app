"""Fills the timeline and the durations of the voices in the page of the screens: ui10.built.html"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
tl = open(os.path.join(HERE, 'timeline10.json')).read()
dur = open(os.environ.get('DURATIONS', '/tmp/os10/voice/durations.json')).read()
html = open(os.path.join(HERE, 'ui10.html')).read().replace('__TIMELINE__', tl).replace('__DURATIONS__', dur)
open(os.path.join(HERE, 'ui10.built.html'), 'w').write(html); print('ui10.built.html', len(html))
