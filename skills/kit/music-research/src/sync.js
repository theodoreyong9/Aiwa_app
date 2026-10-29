// Fills catalog/tracks.jsonl. Incompetech: its one list file, read once. OpenGameArt: the listing pages of the audio under CC0 / CC BY, then the pages not
// seen yet, slowly (its robots.txt asks for 10 s between two requests). No audio file is downloaded here: the register keeps the address of the file.
// Wherever a robots.txt says no, or cannot be read, nothing is fetched.
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { parseRobots, allowed, crawlDelay } from './robots.js';
import { parsePieces, PIECES_URL } from './incompetech.js';
import { BASE, LICENCE_IDS, listingPath, listingSlugs, parseTrack } from './oga.js';

export const USER_AGENT = 'Mozilla/5.0 (compatible; aiwa-music-research; +https://github.com/theodoreyong9/Aiwa_app)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function loadCatalog(dir) {
  const file = join(dir, 'tracks.jsonl');
  return existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : [];
}
export function saveCatalog(dir, rows) {
  mkdirSync(dir, { recursive: true });
  const sorted = [...rows].sort((a, b) => a.source.localeCompare(b.source) || a.id.localeCompare(b.id));
  writeFileSync(join(dir, 'tracks.jsonl'), sorted.map((r) => JSON.stringify(r)).join('\n') + '\n');
}
const robotsOf = async (origin, fetchFn) => {
  const res = await fetchFn(origin + '/robots.txt', { headers: { 'User-Agent': USER_AGENT } });
  if (!res.ok) throw new Error(`${origin}/robots.txt answers ${res.status}`);
  return parseRobots(await res.text());
};

export async function syncIncompetech({ dir, fetchFn = fetch } = {}) {
  const summary = { source: 'incompetech', new: 0, errors: [] };
  try {
    const url = new URL(PIECES_URL);
    if (!allowed(await robotsOf(url.origin, fetchFn), url.pathname)) { summary.errors.push('robots.txt forbids pieces.json, nothing fetched'); return summary; }
    const res = await fetchFn(PIECES_URL, { headers: { 'User-Agent': USER_AGENT } });
    if (!res.ok) throw new Error(`pieces.json answers ${res.status}`);
    const tracks = parsePieces(await res.json());
    if (tracks.length < 100) throw new Error(`only ${tracks.length} pieces read (the file changed?), the register is left as it was`);
    const rows = loadCatalog(dir);
    const known = new Set(rows.filter((r) => r.source === 'incompetech').map((r) => r.id));
    summary.new = tracks.filter((t) => !known.has(t.id)).length;
    saveCatalog(dir, [...rows.filter((r) => r.source !== 'incompetech'), ...tracks]);
    summary.total = tracks.length;
  } catch (err) { summary.errors.push(String(err.message ?? err)); }
  return summary;
}

export async function syncOga({ dir, max = 30, pages = 2, delayMs = 10000, fetchFn = fetch, log = console.log } = {}) {
  const summary = { source: 'opengameart', new: 0, skipped: 0, errors: [] };
  let robots;
  try { robots = await robotsOf(BASE, fetchFn); } catch (err) { summary.errors.push(`robots.txt unreadable, nothing fetched: ${err.message}`); return summary; }
  const wait = Math.max(delayMs, (crawlDelay(robots) ?? 0) * 1000);
  const get = (path) => fetchFn(BASE + path, { headers: { 'User-Agent': USER_AGENT, Accept: 'text/html' }, redirect: 'follow' });
  const rows = loadCatalog(dir);
  const skipFile = join(dir, 'oga-skipped.json');
  const skipped = new Set(existsSync(skipFile) ? JSON.parse(readFileSync(skipFile, 'utf8')) : []);
  const known = new Set(rows.filter((r) => r.source === 'opengameart').map((r) => r.page.split('/content/')[1]));
  const todo = [];
  for (const id of Object.values(LICENCE_IDS)) {
    for (let page = 0; page < pages; page++) {
      const path = listingPath(id, page);
      if (!allowed(robots, path)) { summary.errors.push(`robots.txt forbids ${path}`); break; }
      try {
        const res = await get(path);
        if (!res.ok) throw new Error(`listing answers ${res.status}`);
        for (const s of listingSlugs(await res.text())) if (!known.has(s) && !skipped.has(s) && !todo.includes(s)) todo.push(s);
      } catch (err) { summary.errors.push(String(err.message ?? err)); }
      await sleep(wait);
    }
  }
  for (const slugName of todo.slice(0, max)) {
    const path = `/content/${slugName}`;
    if (!allowed(robots, path)) { skipped.add(slugName); continue; }
    try {
      const res = await get(path);
      if (!res.ok) throw new Error(`${path} answers ${res.status}`);
      const track = parseTrack(await res.text(), slugName);
      if (!track) { skipped.add(slugName); summary.skipped++; }
      else { rows.push({ ...track, seen: new Date().toISOString().slice(0, 10) }); summary.new++; log(`+ ${track.title} (${track.licence})`); }
    } catch (err) { summary.errors.push(String(err.message ?? err)); }
    await sleep(wait);
  }
  saveCatalog(dir, rows);
  writeFileSync(skipFile, JSON.stringify([...skipped].sort()));
  summary.total = rows.filter((r) => r.source === 'opengameart').length;
  return summary;
}
