import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { transform, transformFilter, GRADES } from '../src/transform.js';
import { hasFfmpeg, ffmpegPath, run } from '../src/ffmpeg.js';

const need = { skip: hasFfmpeg() ? false : 'ffmpeg is not installed here' };
const dur = (f) => { const r = spawnSync(ffmpegPath(), ['-hide_banner', '-i', f], { encoding: 'utf8' }); const m = /Duration: (\d+):(\d+):([\d.]+)/.exec(r.stderr); return +m[1] * 3600 + +m[2] * 60 + +m[3]; };
const pixel = (f, t) => { const r = spawnSync(ffmpegPath(), ['-loglevel', 'error', '-ss', String(t), '-i', f, '-frames:v', '1', '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1e6 }); return [...r.stdout.subarray(0, 3)]; };
const src = () => { const d = mkdtempSync(join(tmpdir(), 'vk-tr-')); run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=10', '-t', '2', '-pix_fmt', 'yuv420p', join(d, 'in.mp4')]); return d; };

test('the filter says what it does, and refuses what it does not know', () => {
  assert.ok(Object.keys(GRADES).includes('teal-orange'));
  assert.match(transformFilter({ speed: 2 }), /setpts=PTS\/2/);
  assert.match(transformFilter({ bloom: 0.3, grain: 0.05, vignette: 0.4 }), /gblur.*blend.*vignette.*noise/);
  assert.throws(() => transformFilter({ grade: 'sepia' }), /unknown grade "sepia"/);
  assert.throws(() => transformFilter({ speed: 0 }), /speed must be positive/);
  assert.throws(() => transformFilter({ crop: 'wide' }), /bad crop/);
});

test('speed, crop and grade really change the picture', need, () => {
  const d = src();
  transform({ input: join(d, 'in.mp4'), out: join(d, 'fast.mp4'), speed: 2, fps: 10 });
  assert.ok(Math.abs(dur(join(d, 'fast.mp4')) - 1) < 0.3, `a 2 s clip at speed 2 lasts about 1 s: ${dur(join(d, 'fast.mp4'))}`);
  transform({ input: join(d, 'in.mp4'), out: join(d, 'sq.mp4'), crop: '1:1', fps: 10 });
  const info = spawnSync(ffmpegPath(), ['-hide_banner', '-i', join(d, 'sq.mp4')], { encoding: 'utf8' }).stderr;
  assert.match(info, /180x180/);
  transform({ input: join(d, 'in.mp4'), out: join(d, 'mono.mp4'), grade: 'mono', fps: 10 });
  const [r, g, b] = pixel(join(d, 'mono.mp4'), 0.5);
  assert.ok(Math.abs(r - g) < 6 && Math.abs(g - b) < 6, `a grey picture: ${r},${g},${b}`);
  transform({ input: join(d, 'in.mp4'), out: join(d, 'full.mp4'), grade: 'teal-orange', bloom: 0.3, grain: 0.04, vignette: 0.3, fps: 10 });
  assert.ok(existsSync(join(d, 'full.mp4')) && dur(join(d, 'full.mp4')) > 1.5);
});

test('a render made at 12 images a second is smoothed to 30 and brought to the size of the film', need, () => {
  const d = mkdtempSync(join(tmpdir(), 'vk-tr2-'));
  run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=160x90:r=12', '-t', '2', join(d, '%05d.png')]);
  transform({ input: join(d, '%05d.png'), out: join(d, 'o.mp4'), inputFps: 12, fps: 30, interpolate: true, scale: '320x180' });
  const info = spawnSync(ffmpegPath(), ['-hide_banner', '-i', join(d, 'o.mp4')], { encoding: 'utf8' }).stderr;
  assert.match(info, /320x180/); assert.match(info, /30 fps/);
  assert.ok(Math.abs(dur(join(d, 'o.mp4')) - 2) < 0.2, String(dur(join(d, 'o.mp4'))));
  assert.throws(() => transformFilter({ scale: 'big' }), /bad scale/);
});
