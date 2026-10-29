// Reads the home page and the campaigns page of adsoftheworld.com (the listing pages its robots.txt allows: pagination is disallowed, so nothing else),
// then the campaign pages it has not seen yet, a few at a time and slowly. Each campaign becomes one line of catalog/campaigns.jsonl. No film is
// fetched: only the page's text and the address of the film. Wherever the robots.txt says no, or cannot be read, nothing is fetched.
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { parseCampaign, listingSlugs } from './campaign.js';
import { parseRobots, allowed, crawlDelay } from './robots.js';

export const BASE = 'https://www.adsoftheworld.com';
export const USER_AGENT = 'Mozilla/5.0 (compatible; aiwa-design-research; +https://github.com/theodoreyong9/Aiwa_app)';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function loadCatalog(dir) {
  const file = join(dir, 'campaigns.jsonl');
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
}
export function saveCatalog(dir, rows) {
  mkdirSync(dir, { recursive: true });
  const sorted = [...rows].sort((a, b) => (b.year ?? 0) - (a.year ?? 0) || a.slug.localeCompare(b.slug));
  writeFileSync(join(dir, 'campaigns.jsonl'), sorted.map((r) => JSON.stringify(r)).join('\n') + '\n');
}

export async function sync({ dir, base = BASE, listings = ['/', '/campaigns'], max = 40, delayMs = 3000, fetchFn = fetch, log = console.log } = {}) {
  const get = (path) => fetchFn(base + path, { headers: { 'User-Agent': USER_AGENT, Accept: 'text/html' }, redirect: 'follow' });
  const summary = { new: 0, known: 0, errors: [], listing: 0, skipped_by_robots: 0 };
  let robots;
  try {
    const res = await get('/robots.txt');
    if (!res.ok) throw new Error(`robots.txt answers ${res.status}`);
    robots = parseRobots(await res.text());
  } catch (err) { summary.errors.push(`robots.txt unreadable, nothing fetched: ${err.message}`); return summary; }
  const wait = Math.max(delayMs, (crawlDelay(robots) ?? 0) * 1000);
  let rows = loadCatalog(dir);
  // a record written before the page text was kept ("facts") is read again, a few per run, to be completed
  const stale = new Set(rows.filter((r) => !('facts' in r)).map((r) => r.slug));
  const known = new Set(rows.filter((r) => !stale.has(r.slug)).map((r) => r.slug));
  const slugs = [];
  for (const path of listings) {
    if (!allowed(robots, path)) { summary.skipped_by_robots++; continue; }
    try {
      const res = await get(path);
      if (!res.ok) throw new Error(`${path} answers ${res.status}`);
      for (const s of listingSlugs(await res.text())) if (!slugs.includes(s)) slugs.push(s);
      summary.listing++;
    } catch (err) { summary.errors.push(String(err.message ?? err)); }
    await sleep(wait);
  }
  summary.known = slugs.filter((s) => known.has(s)).length;
  const todo = [...slugs.filter((s) => !known.has(s) && !stale.has(s)), ...[...stale]].slice(0, max);
  for (const slug of todo) {
    const path = `/campaigns/${slug}`;
    if (!allowed(robots, path)) { summary.skipped_by_robots++; continue; }
    try {
      const res = await get(path);
      if (!res.ok) throw new Error(`${path} answers ${res.status}`);
      const record = parseCampaign(await res.text(), slug);
      if (!record.title || (!record.idea && !record.agency)) throw new Error(`${path}: nothing readable (the page changed?)`);
      rows = rows.filter((r) => r.slug !== slug);
      rows.push({ ...record, seen: new Date().toISOString().slice(0, 10) });
      summary.new++;
      log(`+ ${record.title}`);
    } catch (err) { summary.errors.push(String(err.message ?? err)); }
    await sleep(wait);
  }
  saveCatalog(dir, rows);
  writeFileSync(join(dir, 'last-sync.json'), JSON.stringify({ at: new Date().toISOString(), ...summary, total: rows.length }, null, 1));
  return { ...summary, total: rows.length };
}
