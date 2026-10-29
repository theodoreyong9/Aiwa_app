#!/usr/bin/env node
// The INDEX of free footage (not a store): one line per clip in catalog/footage.jsonl — where it is, its licence, its credit, its length, its size, its words and a mood — and nothing
// else. A film takes a clip from it by mood and asks for the file only when it renders (footage.mjs fetch). Sources without a key: NASA, Wikimedia Commons, Internet Archive, ESO.
//   footage-index.mjs sync [--themes="a;b;c"] [--per=12]      adds what the themes find (the existing lines are kept and not doubled)
//   footage-index.mjs search "<words>" [--mood=calm|energetic|warm|cool|cosmic|intimate] [--limit=6] [--seconds=8]      reads the index (offline)
// Licences kept: public domain, CC0, CC BY (credit printed in the film). Not CC BY-SA, not "all rights reserved".
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const UA = 'aiwa-footage-index/1 (https://github.com/theodoreyong9/Aiwa_app)';
const FILE = join(dirname(fileURLToPath(import.meta.url)), '..', 'catalog', 'footage.jsonl');
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const i = a.indexOf('='); return i < 0 ? [a.slice(2), true] : [a.slice(2, i), a.slice(i + 1)]; }));
const [command, ...rest] = args.filter((x) => !x.startsWith('--'));
const KEEP = /^(cc0|public domain|pd|cc[ -]by( [0-9.]+)?|cc-by-[0-9.]+)$/i;
const get = async (url) => { const r = await fetch(url, { headers: { 'User-Agent': UA } }); if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** The mood of a clip, from its words: five numbers 0..1 (the vector of video-kit/conductor/mood.mjs). A first guess that a person can correct in the file. */
export function moodOfWords(text) {
  const t = ` ${String(text).toLowerCase()} `; const has = (...w) => w.some((x) => t.includes(x));
  const m = { energy: 0.4, warmth: 0.5, scale: 0.5, tension: 0.3, awe: 0.5 };
  if (has('timelapse', 'time-lapse', 'traffic', 'rush', 'storm', 'fast', 'sped up', 'waves', 'launch', 'fire')) m.energy += 0.3;
  if (has('calm', 'slow', 'quiet', 'peace', 'fog', 'mist', 'sunrise', 'sunset', 'dawn', 'clouds', 'drift', 'still')) m.energy -= 0.2;
  if (has('sunrise', 'sunset', 'golden', 'warm', 'fire', 'desert', 'dawn', 'dusk', 'lava')) m.warmth += 0.3;
  if (has('night', 'snow', 'ice', 'arctic', 'moon', 'blue', 'aurora', 'cold', 'winter', 'ocean', 'space', 'stars', 'galaxy')) m.warmth -= 0.3;
  if (has('earth', 'orbit', 'space', 'planet', 'galaxy', 'stars', 'milky way', 'nebula', 'mars', 'moon', 'sun ', 'iss', 'aerial', 'satellite')) { m.scale += 0.4; m.awe += 0.3; }
  if (has('room', 'desk', 'hand', 'closeup', 'close-up', 'macro', 'interior', 'kitchen', 'street', 'walk')) m.scale -= 0.3;
  if (has('storm', 'chase', 'danger', 'dark', 'ruin', 'abandoned', 'crash', 'war')) m.tension += 0.3;
  if (has('aurora', 'milky way', 'nebula', 'earth', 'sunrise', 'timelapse', 'galaxy', 'volcano')) m.awe += 0.2;
  return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, +Math.max(0, Math.min(1, v)).toFixed(2)]));
}

async function nasa(q, per) {
  const j = await get(`https://images-api.nasa.gov/search?q=${encodeURIComponent(q)}&media_type=video`);
  return (j.collection?.items || []).slice(0, per).map((it) => { const d = it.data?.[0] || {};
    return { id: `nasa:${d.nasa_id}`, source: 'nasa', title: d.title, words: [d.title, ...(d.keywords || [])].join(' '), licence: 'NASA media (public domain)', credit: `NASA (${d.nasa_id})`, seconds: null, width: null, page: `https://images.nasa.gov/details/${d.nasa_id}` }; });
}
async function commons(q, per) {
  const j = await get(`https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=${per * 3}&gsrsearch=${encodeURIComponent(q + ' filetype:video')}&prop=imageinfo&iiprop=url|size|extmetadata|duration`);
  const out = [];
  for (const p of Object.values(j.query?.pages || {})) {
    const ii = p.imageinfo?.[0]; if (!ii) continue; const lic = (ii.extmetadata?.LicenseShortName?.value || '').trim();
    if (!KEEP.test(lic) || (ii.width || 0) < 1280) continue;
    const artist = (ii.extmetadata?.Artist?.value || '').replace(/<[^>]+>/g, '').slice(0, 80);
    out.push({ id: `commons:${p.title.replace(/^File:/, '')}`, source: 'commons', title: p.title.replace(/^File:/, ''), words: `${p.title} ${(ii.extmetadata?.ImageDescription?.value || '').replace(/<[^>]+>/g, '').slice(0, 200)}`, licence: lic, credit: `${artist || 'unknown'} · ${lic} · Wikimedia Commons`, seconds: Math.round(ii.duration || 0), width: ii.width, page: ii.descriptionurl });
  }
  return out.slice(0, per);
}
async function archive(q, per) {
  const j = await get(`https://archive.org/advancedsearch.php?q=${encodeURIComponent(`(${q}) AND mediatype:movies AND (licenseurl:*publicdomain* OR licenseurl:*zero* OR collection:nasa)`)}&fl[]=identifier&fl[]=title&fl[]=description&fl[]=licenseurl&rows=${per}&output=json`);
  return (j.response?.docs || []).map((d) => ({ id: `archive:${d.identifier}`, source: 'archive', title: d.title, words: `${d.title} ${String(d.description || '').slice(0, 200)}`, licence: /publicdomain|zero/.test(d.licenseurl || '') ? 'Public domain / CC0' : 'NASA media (public domain)', credit: `Internet Archive (${d.identifier})`, seconds: null, width: null, page: `https://archive.org/details/${d.identifier}` }));
}
async function eso(per) {
  const j = await get('https://www.eso.org/public/videos/?search=&type=json').catch(() => null);
  return Array.isArray(j) ? j.slice(0, per).map((v) => ({ id: `eso:${v.id}`, source: 'eso', title: v.title, words: `${v.title} ${v.subject_name || ''}`, licence: 'CC BY 4.0', credit: 'ESO (CC BY 4.0)', seconds: null, width: null, page: `https://www.eso.org/public/videos/${v.id}/` })) : [];
}

const read = () => (existsSync(FILE) ? readFileSync(FILE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const THEMES = 'city night;street lights;earth from space;sunrise;aurora;clouds timelapse;ocean waves;forest;mountains;desert;stars milky way;mars;moon;galaxy nebula;server data center;laboratory;factory machines;highway traffic;snow;fire;rain;waterfall;aerial city;volcano;underwater;satellite;astronaut';

try {
  if (command === 'sync') {
    const rows = read(); const have = new Set(rows.map((r) => r.id)); const per = Number(flags.per || 12);
    for (const q of String(flags.themes || THEMES).split(';').map((x) => x.trim()).filter(Boolean)) {
      for (const [name, fn] of [['nasa', () => nasa(q, per)], ['commons', () => commons(q, per)], ['archive', () => archive(q, per)]]) {
        try { for (const c of await fn()) if (!have.has(c.id)) { have.add(c.id); rows.push({ ...c, tags: [q], mood: moodOfWords(`${c.words} ${q}`), indexed: new Date().toISOString().slice(0, 10) }); delete rows.at(-1).words; } }
        catch (e) { console.log(`! ${name} "${q}": ${e.message}`); }
        await sleep(1500);
      }
    }
    try { for (const c of await eso(per)) if (!have.has(c.id)) { have.add(c.id); rows.push({ ...c, tags: ['space'], mood: moodOfWords(c.words + ' space'), indexed: new Date().toISOString().slice(0, 10) }); delete rows.at(-1).words; } } catch (e) { console.log(`! eso: ${e.message}`); }
    writeFileSync(FILE, rows.map((r) => JSON.stringify(r)).join('\n') + '\n');
    console.log(`index: ${rows.length} clips`);
  } else if (command === 'search') {
    const words = rest.join(' ').toLowerCase().split(/\s+/).filter(Boolean); const limit = Number(flags.limit || 6); const minS = Number(flags.seconds || 0);
    const want = { calm: { energy: 0.15 }, energetic: { energy: 0.85 }, warm: { warmth: 0.85 }, cool: { warmth: 0.15 }, cosmic: { scale: 0.9 }, intimate: { scale: 0.1 } }[flags.mood];
    const scored = read().map((r) => {
      const hay = `${r.title} ${(r.tags || []).join(' ')}`.toLowerCase();
      let s = words.reduce((a, w) => a + (hay.includes(w) ? 1 : 0), 0);
      if (want) for (const [k, v] of Object.entries(want)) s += 1 - Math.abs((r.mood?.[k] ?? 0.5) - v);
      if (r.seconds && r.seconds < minS) s -= 2;
      return { s, r };
    }).filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, limit);
    console.log(JSON.stringify(scored.map(({ s, r }) => ({ score: +s.toFixed(2), id: r.id, title: r.title, licence: r.licence, credit: r.credit, seconds: r.seconds, mood: r.mood })), null, 1));
  } else { console.log('footage-index.mjs sync [--themes=a;b] [--per=12] | search "<words>" [--mood=calm] [--limit=6]'); process.exit(2); }
} catch (e) { console.error(e.message || e); process.exit(1); }
