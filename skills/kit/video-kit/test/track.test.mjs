import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const py = ['python3.13', 'python3'].find((p) => spawnSync(p, ['-c', 'import cv2, numpy']).status === 0);
const need = { skip: py ? false : 'python with opencv and numpy is not installed here (pip install opencv-python-headless numpy)' };

test('the tracker follows a textured square that moves over a noisy background, and says where it lost it', need, () => {
  const dir = mkdtempSync(join(tmpdir(), 'vk-track-'));
  const video = join(dir, 'm.mp4'), out = join(dir, 't.json');
  const make = `
import cv2, numpy as np
rng = np.random.default_rng(3)
bg = rng.integers(40, 120, (240, 320, 3), dtype=np.uint8)
tex = rng.integers(0, 255, (50, 50, 3), dtype=np.uint8)
w = cv2.VideoWriter(r'${video}', cv2.VideoWriter_fourcc(*'mp4v'), 25, (320, 240))
for i in range(60):
    f = bg.copy(); x = 20 + i * 4; y = 100 + int(20 * np.sin(i / 8))
    f[y:y+50, x:x+50] = tex
    w.write(f)
w.release()`;
  assert.equal(spawnSync(py, ['-c', make]).status, 0);
  const r = spawnSync(py, [join(here, '..', 'src', 'track.py'), video, out, '--bbox=20,100,50,50', '--smooth=0'], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const t = JSON.parse(readFileSync(out, 'utf8'));
  assert.equal(t.fps, 25); assert.equal(t.frames.length, 60);
  const last = t.frames[59], truth = { x: 20 + 59 * 4, y: 100 + Math.round(20 * Math.sin(59 / 8)) };
  assert.ok(Math.abs(last.x - truth.x) < 20 && Math.abs(last.y - truth.y) < 20, `end ${last.x},${last.y} vs ${truth.x},${truth.y}`);
  assert.ok(t.frames.filter((f) => f.ok).length > 50);
});

test('the tracker refuses a call without a box, with a sentence that says what to give', need, () => {
  const r = spawnSync(py, [join(here, '..', 'src', 'track.py'), 'x.mp4', 'o.json'], { encoding: 'utf8' });
  assert.notEqual(r.status, 0); assert.match(r.stderr, /--bbox=x,y,w,h/);
});
