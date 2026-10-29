#!/usr/bin/env node
// outline <story.json> --docs=<folder> [--seconds=60 --out=film.json]: from the STORY of a film (what the agent understood in the user's documents) to the film graph the conductor plays.
// The agent writes the story; this file does the rest by rule: the budget of beats and words from the duration, the check that every line of the film rests on a passage of the documents,
// the places (from the footage and panorama indexes, best by mood, never the same one twice in a row) and the transitions (by mood). Nothing is invented and nothing needs an API key.
// story.json: { title, style, beats: [{ id, say, idea, source: { file, quote }, mood: {energy,warmth,scale,tension,awe}, place: "words to look for" }] }
import { readFileSync, readdirSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { pick, places, loadLibrary } from './library.mjs';
import { validate } from './conductor.mjs';

// the sources, by how often what they hold is a usable place: NASA footage is made to be looked at, Commons is mixed, the Internet Archive is mostly broadcast television
const SOURCE_BIAS = { nasa: 0, commons: 0.06, archive: 0.3 };
const WORDS_PER_SECOND = 2.4;   // a calm spoken voice
/** How many beats and how many spoken words a film of `seconds` can hold: a beat lasts 3 to 6 s, the voice does not run over the picture. */
export function budget(seconds) {
  const beats = Math.max(3, Math.min(90, Math.round(seconds / 4.5)));
  return { beats, beatSeconds: +(seconds / beats).toFixed(2), words: Math.floor(seconds * WORDS_PER_SECOND) };
}

const squash = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
/** Reads the documents of a folder (text, markdown, json, csv...) into { file: text }. */
export function readDocs(dir) {
  const out = {};
  const walk = (d) => { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) walk(p); else if (/\.(md|txt|json|csv|html?|ya?ml)$/i.test(f)) out[p.slice(dir.length + 1)] = readFileSync(p, 'utf8'); } };
  walk(dir); return out;
}

/** Checks a story against the documents and the budget. Returns { errors, warnings }. */
export function checkStory(story, docs, seconds) {
  const errors = [], warnings = [], b = budget(seconds);
  const beats = story.beats || [];
  if (beats.length > b.beats + 2) errors.push(`${beats.length} beats for ${seconds} s: at most ${b.beats + 2} (about one every 4.5 s)`);
  if (beats.length < Math.max(3, b.beats - 3)) warnings.push(`only ${beats.length} beats for ${seconds} s: the film will feel slow (about ${b.beats})`);
  const words = beats.reduce((a, x) => a + String(x.say || '').split(/\s+/).filter(Boolean).length, 0);
  if (words > b.words) errors.push(`${words} spoken words for ${seconds} s: at most ${b.words}; cut the lines, do not speed up the voice`);
  const flat = Object.fromEntries(Object.entries(docs).map(([f, t]) => [f, squash(t)]));
  const seen = new Set();
  for (const x of beats) {
    const id = x.id || '?';
    if (!x.idea) errors.push(`${id}: no idea`);
    if (!x.place) errors.push(`${id}: no place (words to look for in the footage index)`);
    if (seen.has(id)) errors.push(`${id}: the id is used twice`); seen.add(id);
    if (!x.say) continue;                                  // a beat without a line carries a picture only: nothing to prove
    const q = squash((x.source || {}).quote || '');
    if (!q) { errors.push(`${id}: the line "${x.say}" has no source quote from the documents`); continue; }
    const file = (x.source || {}).file; const hay = file ? flat[file] : Object.values(flat).join(' ');
    if (file && hay === undefined) errors.push(`${id}: the document "${file}" is not in the folder`);
    else if (!hay.includes(q)) errors.push(`${id}: the quote "${x.source.quote}" is not in ${file || 'the documents'} (copy it word for word)`);
  }
  return { errors, warnings };
}

/** The film graph from a story that passed checkStory: places by mood (never the same twice in a row), transitions by mood, times by an even beat. */
export function toFilm(story, seconds, { footagePath, assetsPath } = {}) {
  const lib = loadLibrary(); const opts = { ...(footagePath ? { footagePath } : {}), ...(assetsPath ? { assetsPath } : {}) };
  const worlds = {}, beats = [], credits = [], uses = {}; let last = null;
  const n = story.beats.length, step = seconds / n;
  story.beats.forEach((x, i) => {
    // a clip chosen by hand (the agent looked at it): story.pool[name] = { spec, title, credit, licence }, beat.clip = name
    if (x.clip) {
      const c = (story.pool || {})[x.clip]; if (!c) throw new Error(`${x.id}: the clip "${x.clip}" is not in story.pool`);
      if (!worlds[x.clip]) { worlds[x.clip] = { kind: 'plate', plate: x.clip, spec: c.spec, ambience: 'air', says: c.title, ...(c.window ? { window: c.window } : {}) }; credits.push({ id: c.spec, credit: c.credit, licence: c.licence }); }
      last = x.clip; const nx = story.beats[i + 1]; const t2 = nx ? pick('transitions', nx.mood, { lib }) : null;
      beats.push({ id: x.id, page: x.id, t: +(i * step).toFixed(3), world: x.clip, idea: x.idea, say: x.say || null, mood: x.mood, ...(x.image ? { image: x.image } : {}), ...(t2 ? { transition: { kind: t2.id, ...(t2.needs === 'through' ? { through: 'center' } : {}) } } : {}) });
      return;
    }
    // the best place that is not the last one, not banned (story.avoid: ids whose clip turned out unusable), and not worn out: a clip already used counts against itself
    const find = (words, onlyUsed) => places({ words, mood: x.mood, seconds: step + 1, limit: 120, kinds: ['footage'], ...opts }).filter((p) => p.id !== last && !(story.avoid || []).includes(p.id) && (!story.sources || story.sources.includes(p.id.split(':')[0])) && (!onlyUsed || uses[p.id]))
      .map((p) => ({ p, k: p.d + 0.12 * (uses[p.id] || 0) + (SOURCE_BIAS[p.id.split(':')[0]] ?? 0.1) })).sort((a, b) => a.k - b.k)[0]?.p;
    // a long film does not need a clip for every beat: once `story.clips` different clips are in, the next beats come back to the best of them
    const full = Object.keys(uses).length >= (story.clips || Math.max(6, Math.round(n / 2.5)));
    const cand = (full && (find(x.place, true) || find('', true))) || find(x.place) || find('');
    if (cand) uses[cand.id] = (uses[cand.id] || 0) + 1;
    const key = cand ? cand.id.replace(/[^a-z0-9]+/gi, '-').toLowerCase() : 'none';
    if (cand && !worlds[key]) { worlds[key] = cand.kind === 'footage' ? { kind: 'plate', plate: key, spec: cand.id, ambience: 'air', says: cand.title } : { kind: 'panorama', panorama: cand.id, ambience: 'air', says: cand.title }; credits.push({ id: cand.id, credit: cand.credit, licence: cand.licence }); }
    last = cand && cand.id;
    const next = story.beats[i + 1];
    const tr = next ? pick('transitions', next.mood, { not: i === 0 ? [] : [], lib }) : null;
    beats.push({ id: x.id, page: x.id, t: +(i * step).toFixed(3), world: key, idea: x.idea, say: x.say || null, mood: x.mood, ...(x.image ? { image: x.image } : {}),
      ...(tr ? { transition: { kind: tr.id, ...(tr.needs === 'through' ? { through: 'center' } : {}) } } : {}) });
  });
  return { film: { title: story.title, style: story.style || 'documentary', total: seconds, fps: 30, worlds, beats }, credits };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const i = a.indexOf('='); return [a.slice(2, i), a.slice(i + 1)]; }));
  const [file] = args.filter((a) => !a.startsWith('--'));
  const seconds = +(flags.seconds || 60);
  const story = JSON.parse(readFileSync(file, 'utf8'));
  const docs = flags.docs && existsSync(flags.docs) ? readDocs(flags.docs) : {};
  const b = budget(seconds); console.log(`budget: ${b.beats} beats of about ${b.beatSeconds} s, ${b.words} words at most`);
  const c = checkStory(story, docs, seconds);
  for (const w of c.warnings) console.log('warning:', w);
  for (const e of c.errors) console.log('ERROR:', e);
  if (c.errors.length) process.exit(1);
  const { film, credits } = toFilm(story, seconds);
  const v = validate(film);
  for (const w of v.warnings) console.log('warning:', w);
  for (const e of v.errors) console.log('ERROR:', e);
  if (v.errors.length) process.exit(1);
  const out = flags.out || 'film.json'; writeFileSync(out, JSON.stringify(film, null, 1)); writeFileSync(out.replace(/\.json$/, '') + '.credits.json', JSON.stringify(credits, null, 1));
  console.log('film:', out, '· credits:', credits.length);
}
