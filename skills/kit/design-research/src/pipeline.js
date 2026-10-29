// Sync and crawl: registries → deduplicated catalogue → the sites that need a visit → observation → analysis → catalogue.
import { join } from 'node:path';
import { Catalog } from './catalog/store.js';
import { discover } from './registry/index.js';
import { crawl } from './crawler/crawl.js';
import { analyze } from './analyze.js';
import { writeJson, readJson, siteId, cleanUrl } from './util.js';

export const homeDirs = (home) => ({ catalog: join(home, 'catalog'), screenshots: join(home, 'screenshots'), analysis: join(home, 'analysis') });

/** Visits one catalogue entry and stores the observation, the analysis and the screenshots. Never throws: a failure is recorded. */
export async function visit(catalog, site, dirs, { crawlFn = crawl, log = () => {} } = {}) {
  const attempts = (site.crawl?.attempts ?? 0) + 1;
  try {
    const observation = await crawlFn(site.url, { shotDir: join(dirs.screenshots, site.id) });
    const status = observation.desktop.status;
    if (status >= 400 || status === 0) throw new Error(`HTTP ${status}`);
    const raw = { ...observation, desktop: { ...observation.desktop, network: observation.desktop.network.slice(0, 400) }, mobile: observation.mobile?.error ? observation.mobile : { ...observation.mobile, network: undefined } };
    writeJson(join(dirs.analysis, `${site.id}.raw.json`), raw);
    Object.assign(site, analyze(observation), { crawl: { status: 'ok', at: observation.at, ms: observation.desktop.ms, attempts } });
    delete site.updated_pending;
    log(`ok    ${site.id}`);
  } catch (err) {
    const dead = /ENOTFOUND|ERR_NAME_NOT_RESOLVED|HTTP 404|HTTP 410/.test(String(err.message ?? err));
    site.crawl = { status: dead ? 'dead' : 'failed', at: new Date().toISOString(), attempts, error: String(err.message ?? err).slice(0, 200) };
    log(`${dead ? 'dead ' : 'fail '} ${site.id}: ${site.crawl.error}`);
  }
  catalog.save();
}

/** Re-runs the analysis on the stored observation (after the rules changed), without visiting the site again. */
export function reclassify(catalog, id, dirs) {
  const site = catalog.get(id);
  const raw = readJson(join(dirs.analysis, `${id}.raw.json`), null);
  if (!site || !raw) throw new Error(`no stored observation for ${id}`);
  Object.assign(site, analyze(raw));
  catalog.save();
  return site;
}

export async function sync({ home, registries = ['awwwards', 'csswinner'], limit = 30, pages = 2, maxCrawls = 20, fetchFn = fetch, crawlFn = crawl, delayMs = 1500, log = console.log } = {}) {
  const dirs = homeDirs(home);
  const catalog = new Catalog(dirs.catalog);
  const summary = { NEW: 0, UPDATED: 0, UNCHANGED: 0, crawled: 0, errors: [], registries: {} };
  for (const name of registries) {
    const { found, errors } = await discover(name, { limit, pages, fetchFn, delayMs, render: fetchFn === fetch });
    for (const item of found) summary[catalog.upsert(item)]++;
    summary.errors.push(...errors.map((e) => `${name}: ${e}`));
    summary.registries[name] = { found: found.length };
    catalog.state.registries[name] = { last_sync: new Date().toISOString(), found: found.length, errors: errors.length };
    log(`${name}: ${found.length} listed, ${errors.length} errors`);
  }
  catalog.save();
  const todo = catalog.all().map((s) => [s, catalog.recrawlReason(s)]).filter(([, why]) => why).slice(0, maxCrawls);
  for (const [site, why] of todo) { log(`visit ${site.id} (${why})`); await visit(catalog, site, dirs, { crawlFn, log }); summary.crawled++; }
  catalog.save();
  return summary;
}

export async function crawlUrl({ home, url, crawlFn = crawl, log = console.log }) {
  const dirs = homeDirs(home);
  const catalog = new Catalog(dirs.catalog);
  const clean = cleanUrl(url);
  const id = siteId(clean);
  if (!catalog.get(id)) catalog.upsert({ url: clean, registry: 'manual', award: '', page: clean });
  await visit(catalog, catalog.get(id), dirs, { crawlFn, log });
  return catalog.get(id);
}
