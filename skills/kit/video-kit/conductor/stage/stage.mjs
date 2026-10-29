#!/usr/bin/env node
// stage <plan.json> <workdir>: builds <workdir>/stage/index.html from the generic stage, for `video-kit render`. The clips are read from <workdir>/footage/<plate>.mp4 and cut into pictures in
// <workdir>/plates/<plate>/; a clip that is missing is NOT replaced by anything: the script says which ones to fetch (the `Footage` workflow, items "<name>=<spec>") and stops.
import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const [planFile, workArg, filmFile] = process.argv.slice(2);
const work = resolve(workArg);
const plan = JSON.parse(readFileSync(planFile, 'utf8'));
const film = filmFile && existsSync(filmFile) ? JSON.parse(readFileSync(filmFile, 'utf8')) : { worlds: plan.worlds };
const worlds = {}, missing = [], credits = [];
for (const [id, w] of Object.entries(plan.worlds)) {
  if (w.kind !== 'plate') continue;
  const mp4 = join(work, 'footage', `${w.plate}.mp4`), dir = join(work, 'plates', w.plate);
  if (!existsSync(mp4)) { missing.push(`${w.plate}=${w.spec || '?'}`); continue; }
  if (!existsSync(join(dir, '00001.jpg'))) {
    mkdirSync(dir, { recursive: true });
    const r = spawnSync('ffmpeg', ['-v', 'error', '-i', mp4, '-vf', 'scale=-2:900,crop=1600:900', '-q:v', '3', join(dir, '%05d.jpg')]);
    if (r.status) { console.error('ffmpeg failed for', w.plate); process.exit(1); }
  }
  // the useful window of the clip (seconds): the agent looked at it and cut out the slate, the black, the talking head; and its luminance, one value a second, for the auto-exposure
  const n = readdirSync(dir).filter((f) => f.endsWith('.jpg')).length, win = w.window || [0, n / 30];
  const raw = spawnSync('ffmpeg', ['-v', 'error', '-i', mp4, '-vf', 'fps=1,scale=32:18,format=gray', '-f', 'rawvideo', '-'], { maxBuffer: 1 << 26 }).stdout;
  const luma = []; for (let k = 0; k + 576 <= raw.length; k += 576) luma.push(raw.subarray(k, k + 576).reduce((a, v) => a + v, 0) / 576);
  const first = Math.min(...plan.beats.filter((b) => b.world === id).map((b) => b.t0));
  worlds[id] = { dir: 'file://' + dir, n, i0: Math.max(0, Math.round(win[0] * 30)), i1: Math.min(n - 1, Math.round(win[1] * 30) - 1), luma: luma.length ? luma : [78], fps: 30, from: Math.max(0, first - 1.6) };
  const j = join(work, 'footage', `${w.plate}.json`);
  if (existsSync(j)) { try { const c = (JSON.parse(readFileSync(j, 'utf8')).credit || '').replace(' · Wikimedia Commons', ''); if (c && !credits.includes(c)) credits.push(c); } catch {} }
}
if (missing.length) { console.error('MISSING CLIPS: run the Footage workflow (mode fetch) with items:\n' + missing.map((m) => m + '@10').join(';')); process.exit(2); }
const cards = {};
for (const b of plan.beats) if (b.image && existsSync(b.image)) cards[b.image] = 'data:image/' + (b.image.split('.').pop().replace('jpg', 'jpeg')) + ';base64,' + readFileSync(b.image).toString('base64');
const out = join(work, 'stage'); mkdirSync(join(out, 'fonts'), { recursive: true });
for (const f of ['SpaceGrotesk.ttf', 'Fraunces-Italic.ttf', 'JetBrainsMono.ttf']) copyFileSync(join(here, 'fonts', f), join(out, 'fonts', f));
let html = readFileSync(join(here, 'stage.html'), 'utf8');
html = html.replace('__PLAN__', () => JSON.stringify(plan)).replace('__WORLDS__', () => JSON.stringify(worlds)).replace('__CARDS__', () => JSON.stringify(cards)).replace('__CREDITS__', () => JSON.stringify(credits));
writeFileSync(join(out, 'index.html'), html); console.log('stage:', join(out, 'index.html'));
