// The catalog: one line per site in catalog/sites.jsonl (diffable in Git, readable by Claude), one canonical entry per
// site whatever the number of registries that list it, and a small state file saying what was synced and when.
import { join } from 'node:path';
import { siteId, cleanUrl, readJsonl, writeJsonl, readJson, writeJson } from '../util.js';

export const STALE_DAYS = 90;
export const MAX_ATTEMPTS = 3;

/** The catalogue as published (a URL to the folder that holds sites.jsonl): what a phone or a session without the repository reads. */
export async function fetchRemoteSites(baseUrl, fetchFn = fetch) {
  const res = await fetchFn(`${baseUrl.replace(/\/$/, '')}/sites.jsonl`);
  if (!res.ok) throw new Error(`catalogue not reachable: HTTP ${res.status}`);
  return (await res.text()).split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

export class Catalog {
  constructor(dir) {
    this.dir = dir;
    this.file = join(dir, 'sites.jsonl');
    this.stateFile = join(dir, 'registry-state.json');
    this.sites = new Map(readJsonl(this.file).map((s) => [s.id, s]));
    this.state = readJson(this.stateFile, { registries: {} });
  }

  save() {
    writeJsonl(this.file, [...this.sites.values()].sort((a, b) => a.id.localeCompare(b.id)));
    writeJson(this.stateFile, this.state);
  }

  get(id) { return this.sites.get(id); }
  all() { return [...this.sites.values()]; }

  /** Adds a listing. Returns 'NEW' (unknown site), 'UPDATED' (a new source or a changed url) or 'UNCHANGED'. */
  upsert({ url, title = '', registry, award, page, date = new Date().toISOString() }) {
    const clean = cleanUrl(url);
    const id = siteId(clean);
    const source = { registry, award, page, date: date.slice(0, 10) };
    const existing = this.sites.get(id);
    if (!existing) {
      this.sites.set(id, { id, url: clean, title, sources: [source], first_seen: date, last_seen: date, crawl: { status: 'never', attempts: 0 } });
      return 'NEW';
    }
    existing.last_seen = date;
    if (!existing.title && title) existing.title = title;
    const known = existing.sources.some((s) => s.registry === registry && s.page === page);
    if (known) return 'UNCHANGED';
    existing.sources.push(source);
    return 'UPDATED';
  }

  /** What to do with a site on this run: 'crawl' or null, and why. */
  recrawlReason(site, now = Date.now()) {
    const c = site.crawl ?? { status: 'never' };
    if (c.status === 'never') return 'NEW';
    if (c.status === 'failed') return c.attempts < MAX_ATTEMPTS ? 'FAILED' : null;
    if (c.status === 'dead') return null;
    if (site.updated_pending) return 'UPDATED';
    if (now - Date.parse(c.at) > STALE_DAYS * 86400000) return 'STALE';
    return null;
  }
}
