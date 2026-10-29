import { renderFrames } from './src/render.js';
import { readdirSync, mkdirSync } from 'node:fs';
const D = '/tmp/claude-0/-home-user/1aa30d49-56f8-5824-83e0-00fb58d4972c/scratchpad/aiwa3/f8', TOTAL = 4768;
mkdirSync(D, { recursive: true });
for (let pass = 0; pass < 4; pass++) {
  const have = new Set(readdirSync(D).filter((f) => f.endsWith('.jpg')).map((f) => +f.slice(0, 5)));
  const ranges = []; let s = null;
  for (let i = 0; i <= TOTAL; i++) { const miss = i < TOTAL && !have.has(i); if (miss && s === null) s = i; if (!miss && s !== null) { ranges.push([s, i]); s = null; } }
  if (!ranges.length) break;
  for (const [a, b] of ranges) { await renderFrames({ page: '../docs/video-vision/video.html?nophone=1&noplanets=1&noimage=1', outDir: D, seconds: 159, fps: 30, width: 1920, height: 1080, workers: 2, from: a, to: b }); console.log('done', a, b); }
}
console.log('ALL-COMPLETE');
