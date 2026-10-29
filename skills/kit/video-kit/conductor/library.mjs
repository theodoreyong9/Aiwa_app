// The library of the conductor: the tools (transitions, sound beds, actors) and the places (the footage index and the panoramas of the asset register), found BY MOOD.
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MOODS, norm } from './mood.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const loadLibrary = () => JSON.parse(readFileSync(join(here, 'library.json'), 'utf8'));
const jsonl = (p) => (existsSync(p) ? readFileSync(p, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);

/** How far two moods are (0 = the same). Only the dimensions the tool speaks of count. */
export function distance(want, tool) {
  const w = norm(want); const keys = Object.keys(tool || {}).filter((k) => MOODS.includes(k));
  if (!keys.length) return 0.5;
  return Math.sqrt(keys.reduce((a, k) => a + (w[k] - tool[k]) ** 2, 0) / keys.length);
}

/** The tool of a kind that suits a mood best: pick('transitions', mood, { not: ['cut'] }). */
export function pick(kind, mood, { not = [], lib = loadLibrary() } = {}) {
  return (lib[kind] || []).filter((t) => !not.includes(t.id)).map((t) => ({ t, d: distance(mood, t.mood) })).sort((a, b) => a.d - b.d)[0]?.t || null;
}

/** The mood of a panorama, from its tags and categories (the same few rules as the footage index). */
export function moodOfPanorama(r) {
  const t = ` ${[r.name, ...(r.tags || []), ...(r.categories || []), ...(r.attributes || [])].join(' ').toLowerCase()} `; const has = (...w) => w.some((x) => t.includes(x));
  const m = { energy: 0.25, warmth: 0.5, scale: 0.5, tension: 0.3, awe: 0.4 };
  if (has('night', 'moon', 'blue hour', 'snow', 'ice')) m.warmth -= 0.3;
  if (has('sunrise', 'sunset', 'golden', 'warm', 'dawn', 'desert')) m.warmth += 0.3;
  if (has('studio', 'indoor', 'interior', 'room', 'hall', 'garage', 'workshop')) m.scale -= 0.3;
  if (has('outdoor', 'mountain', 'sky', 'horizon', 'landscape', 'field')) m.scale += 0.25;
  if (has('industrial', 'abandoned', 'neon', 'urban', 'city', 'street', 'foundry')) m.energy += 0.2;
  if (has('abandoned', 'dark', 'foundry', 'ruin')) m.tension += 0.3;
  if (has('sunset', 'sunrise', 'stars', 'night sky', 'milky')) m.awe += 0.3;
  return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, +Math.max(0, Math.min(1, v)).toFixed(2)]));
}

/**
 * The places that suit a moment, from the two indexes (the footage and the panoramas), best first: { kind: 'footage'|'panorama', id, title, licence, credit, d }.
 * `words`: what the place must be about ("city night"), `mood`: how the moment feels; a clip at least `seconds` long.
 */
export function places({ words = '', mood = {}, seconds = 0, limit = 8, footagePath = join(here, '..', '..', 'asset-research', 'catalog', 'footage.jsonl'), assetsPath = join(here, '..', '..', 'asset-research', 'catalog', 'assets.jsonl'), kinds = ['footage', 'panorama'] } = {}) {
  const ws = String(words).toLowerCase().split(/\s+/).filter(Boolean);
  const score = (text) => ws.reduce((a, w) => a + (text.includes(w) ? 1 : 0), 0);
  const out = [];
  if (kinds.includes('footage')) for (const r of jsonl(footagePath)) {
    if (r.seconds && r.seconds < seconds) continue;
    const hit = score(`${r.title} ${(r.tags || []).join(' ')}`.toLowerCase()); if (ws.length && !hit) continue;
    out.push({ kind: 'footage', id: r.id, title: r.title, licence: r.licence, credit: r.credit, seconds: r.seconds, d: distance(mood, r.mood) - 0.15 * hit });
  }
  if (kinds.includes('panorama')) for (const r of jsonl(assetsPath)) {
    if (r.kind !== 'hdri') continue;
    const hit = score(`${r.name} ${(r.tags || []).join(' ')} ${(r.categories || []).join(' ')}`.toLowerCase()); if (ws.length && !hit) continue;
    out.push({ kind: 'panorama', id: r.id, title: r.name, licence: 'CC0', credit: `Poly Haven · ${r.name}`, d: distance(mood, moodOfPanorama(r)) - 0.15 * hit });
  }
  return out.sort((a, b) => a.d - b.d).slice(0, limit);
}
