import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { assemble, imageSize } from '../src/assemble.js';
import { hasFfmpeg, ffmpegPath, run } from '../src/ffmpeg.js';

const need = { skip: hasFfmpeg() ? false : 'ffmpeg is not installed here' };
const ff = (...a) => run(ffmpegPath(), ['-y', '-loglevel', 'error', ...a]);
const pixel = (file, t) => { const r = spawnSync(ffmpegPath(), ['-loglevel', 'error', '-ss', String(t), '-i', file, '-frames:v', '1', '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1e6 }); return [...r.stdout.subarray(0, 3)]; };

function fixture() {
  const dir = mkdtempSync(join(tmpdir(), 'vk-clips-'));
  mkdirSync(join(dir, 'f')); mkdirSync(join(dir, 'a'));
  ff('-f', 'lavfi', '-i', 'color=c=red:s=160x90:r=10', '-t', '4', join(dir, 'f', '%05d.jpg'));                         // 4 s of red frames
  ff('-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=10', '-t', '1', '-pix_fmt', 'yuv420p', join(dir, 'blue.mp4'));  // a 1 s blue video, another size
  ff('-f', 'lavfi', '-i', 'color=c=lime@0.6:s=80x45:r=10,format=rgba', '-t', '1', join(dir, 'a', '%05d.png'));      // a translucent green image sequence
  return dir;
}

test('imageSize reads JPEG and PNG headers', need, () => {
  const d = fixture();
  assert.deepEqual(imageSize(join(d, 'f', '00001.jpg')), { w: 160, h: 90 });
  assert.deepEqual(imageSize(join(d, 'a', '00001.png')), { w: 80, h: 45 });
});

test('an opaque clip replaces the frames between start and end, and only there', need, () => {
  const d = fixture();
  const out = join(d, 'o.mp4');
  assemble({ framesDir: join(d, 'f'), out, fps: 10, crf: 18, clips: [{ file: join(d, 'blue.mp4'), start: 1.5, end: 2.5, fade: 0 }] });
  const before = pixel(out, 0.5), inside = pixel(out, 2.0), after = pixel(out, 3.3);
  assert.ok(before[0] > 150 && before[2] < 90, `before ${before}`);       // red
  assert.ok(inside[2] > 150 && inside[0] < 90, `inside ${inside}`);        // blue, whatever its size was (cut to the frame)
  assert.ok(after[0] > 150 && after[2] < 90, `after ${after}`);
});

test('an image sequence with an alpha channel is laid over the picture, not instead of it', need, () => {
  const d = fixture();
  const out = join(d, 'o2.mp4');
  assemble({ framesDir: join(d, 'f'), out, fps: 10, crf: 18, clips: [{ file: join(d, 'a', '%05d.png'), start: 1, end: 2, fade: 0, fit: 'cover' }] });
  const inside = pixel(out, 1.5);
  assert.ok(inside[0] > 40 && inside[1] > 40, `a mix of red and green: ${inside}`);   // neither pure red nor pure green
  assert.ok(inside[0] > 60, `the red picture still shows: ${inside}`);
});

test('a missing clip is refused with its name', need, () => {
  const d = fixture();
  assert.throws(() => assemble({ framesDir: join(d, 'f'), out: join(d, 'x.mp4'), fps: 10, clips: [{ file: join(d, 'nope.mp4'), start: 0 }] }), /nope\.mp4 does not exist/);
});

test('render --transparent writes PNG frames with an alpha channel: the page background stays empty', need, async () => {
  const { renderFrames } = await import('../src/render.js');
  const { writeFileSync, readdirSync } = await import('node:fs');
  const dir = mkdtempSync(join(tmpdir(), 'vk-alpha-'));
  const page = join(dir, 'p.html');
  writeFileSync(page, '<!doctype html><html><body style="margin:0;background:transparent"><div style="position:absolute;left:40px;top:20px;width:30px;height:30px;background:#f00"></div><script>window.render=(t)=>{}</script></body></html>');
  const r = await renderFrames({ page, outDir: join(dir, 'o'), width: 160, height: 90, fps: 10, seconds: 0.2, workers: 1, transparent: true });
  assert.equal(r.frames, 2);
  const files = readdirSync(join(dir, 'o')).filter((f) => f.endsWith('.png'));
  assert.equal(files.length, 2);
  const px = (x, y) => { const o = spawnSync(ffmpegPath(), ['-loglevel', 'error', '-i', join(dir, 'o', files[0]), '-vf', `crop=1:1:${x}:${y},format=rgba`, '-f', 'rawvideo', '-'], { maxBuffer: 1e6 }); return [...o.stdout.subarray(0, 4)]; };
  assert.equal(px(5, 5)[3], 0, 'the empty corner is transparent');
  assert.equal(px(50, 30)[3], 255, 'the square is opaque');
});

test('the shotlist command writes the files and exits 1 when something is missing', need, async () => {
  const { writeFileSync, readFileSync } = await import('node:fs');
  const dir = mkdtempSync(join(tmpdir(), 'vk-sl-'));
  writeFileSync(join(dir, 's.json'), JSON.stringify({ title: 'T', scenes: [{ id: 'a', seconds: 3, tool: 'html' }, { id: 'b', seconds: 2, tool: 'footage' }] }));
  const cli = join(dirname(new URL(import.meta.url).pathname), '..', 'src', 'cli.js');
  const bad = spawnSync('node', [cli, 'shotlist', join(dir, 's.json'), join(dir, 'out')], { encoding: 'utf8' });
  assert.equal(bad.status, 1); assert.match(bad.stdout, /licence/);
  writeFileSync(join(dir, 's.json'), JSON.stringify({ title: 'T', scenes: [{ id: 'a', seconds: 3, tool: 'html' }, { id: 'b', seconds: 2, tool: 'footage', licence: 'CC0, archive.org' }] }));
  const ok = spawnSync('node', [cli, 'shotlist', join(dir, 's.json'), join(dir, 'out')], { encoding: 'utf8' });
  assert.equal(ok.status, 0, ok.stderr + ok.stdout);
  assert.deepEqual(JSON.parse(readFileSync(join(dir, 'out', 'clips.json'), 'utf8')).map((c) => c.shot), ['b']);
});

test('an image sequence that starts at its own frame number is laid at the instant given', need, () => {
  const d = fixture();
  const out = join(d, 'o3.mp4');
  // the green frames are numbered 00000…, the clip says they start at 5 (a render of a range of the film numbers its images from the frame of the range)
  run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=lime@0.6:s=80x45:r=10,format=rgba', '-t', '1', '-start_number', '20', join(d, 'a', 'n%05d.png')]);
  assemble({ framesDir: join(d, 'f'), out, fps: 10, crf: 18, clips: [{ file: join(d, 'a', 'n%05d.png'), startNumber: 20, fps: 10, start: 2, end: 3, fade: 0 }] });
  const before = pixel(out, 1.0), inside = pixel(out, 2.5);
  assert.ok(before[1] < 60, `red before: ${before}`);
  assert.ok(inside[1] > 40, `green mixed in: ${inside}`);
});

test('a clip and a voice-over with a music track assemble together (the labels of the two graphs do not clash)', need, () => {
  const d = fixture();
  const out = join(d, 'o4.mp4');
  run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=f=220:d=4', join(d, 'm.wav')]);
  run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=f=440:d=2', join(d, 'v.wav')]);
  assemble({ framesDir: join(d, 'f'), out, fps: 10, crf: 18, audio: join(d, 'm.wav'), voice: join(d, 'v.wav'), duck: 'light', clips: [{ file: join(d, 'a', '%05d.png'), start: 1, end: 2, fade: 0 }] });
  assert.ok(pixel(out, 1.5)[1] > 40, 'the clip is there');
});

test('a look on the whole film is applied in the same encode (a vignette darkens the corners, the centre stays)', need, () => {
  const d = fixture();
  const plain = join(d, 'p.mp4'), looked = join(d, 'l.mp4');
  assemble({ framesDir: join(d, 'f'), out: plain, fps: 10, crf: 18 });
  assemble({ framesDir: join(d, 'f'), out: looked, fps: 10, crf: 18, look: { grade: 'mono', vignette: 0.9 } });
  const a = pixel(plain, 1.0), b = pixel(looked, 1.0);
  assert.ok(a[0] > 150 && a[1] < 60, `the frames are red: ${a}`);
  assert.ok(Math.abs(b[0] - b[1]) < 40, `mono: no more colour: ${b}`);
});

test('a single picture can be held over the film from a start to an end (loop): a credit line, a logo', need, () => {
  const d = fixture();
  const out = join(d, 'o5.mp4');
  run(ffmpegPath(), ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=lime@0.6:s=80x45,format=rgba', '-frames:v', '1', join(d, 'one.png')]);
  assemble({ framesDir: join(d, 'f'), out, fps: 10, crf: 18, clips: [{ file: join(d, 'one.png'), loop: true, start: 1, end: 3, fade: 0 }] });
  assert.ok(pixel(out, 2.5)[1] > 40, 'the picture is still there at 2.5 s');
  assert.ok(pixel(out, 0.5)[1] < 60, 'and not before it starts');
});
