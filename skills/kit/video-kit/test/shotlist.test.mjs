import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildShotlist } from '../src/shotlist.js';

const story = { title: 'Test', format: '16:9', scenes: [
  { id: 'hook', seconds: 4, tool: 'html', line: 'Crée.' },
  { id: 'glasses', seconds: 6, tool: 'blender', brief: 'a pair of glasses, slow dolly in' },
  { id: 'cafe', seconds: 5, tool: 'footage', brief: 'a cafe, a person walks', licence: 'Pexels, free licence, one person, no release needed for a background figure' },
  { id: 'dream', seconds: 3.5, tool: 'generated', brief: 'a crowd of people in a plaza at dusk', camera: 'slow crane up' },
] };

test('the shot list gives the times of each shot, the clips of what is not drawn by the page, and the prompts of what a generator must make', () => {
  const r = buildShotlist(story);
  assert.equal(r.total, 18.5); assert.deepEqual(r.problems, []);
  assert.deepEqual(r.clips.map((c) => [c.shot, c.start, c.end]), [['glasses', 4, 10], ['cafe', 10, 15], ['dream', 15, 18.5]]);
  assert.equal(r.clips[0].file, 'aiwa-videos/clips/glasses/%05d.png'); assert.equal(r.clips[0].fps, 30);
  assert.equal(r.clips[2].file, 'aiwa-videos/clips/dream.mp4');
  assert.match(r.markdown, /no text, no logo, no watermark, no recognisable real person/);
  assert.match(r.markdown, /Camera: slow crane up/);
  assert.match(r.markdown, /It is a made-up picture: it is labelled as an illustration/);
});

test('a footage without its licence, an unknown tool and a missing duration are named as problems', () => {
  const r = buildShotlist({ scenes: [{ id: 'a', seconds: 3, tool: 'footage' }, { id: 'b', seconds: 2, tool: 'magic' }, { id: 'c', tool: 'html' }] });
  assert.equal(r.problems.length, 3);
  assert.match(r.problems.join(' '), /a: a footage needs its source and its licence/);
  assert.throws(() => buildShotlist({ scenes: [] }), /no scene/);
});
