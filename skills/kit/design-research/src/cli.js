#!/usr/bin/env node
// design-research: bootstrap | sync | crawl <url> | classify <id> | search "<brief>" | research "<brief>" | doctor
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';
import { Catalog, fetchRemoteSites } from './catalog/store.js';
import { sync, crawlUrl, reclassify, homeDirs } from './pipeline.js';
import { search } from './retrieval/search.js';
import { buildPack } from './pack.js';
import { registries } from './registry/index.js';
import { writeJson } from './util.js';

// what a run found and what went wrong, kept in the catalogue so that a failed run can be read from the repository
const keepRun = (name, summary) => { writeJson(join(dirs.catalog, `last-${name}.json`), { at: new Date().toISOString(), ...summary }); return summary; };

const HOME = resolve(process.env.DR_HOME ?? join(dirname(fileURLToPath(import.meta.url)), '..'));
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const words = args.filter((a) => !a.startsWith('--'));
const [command, ...rest] = words;
const dirs = homeDirs(HOME);
const out = (v) => console.log(typeof v === 'string' ? v : JSON.stringify(v, null, 2));

const usage = `design-research
  bootstrap                  first catalogue: several pages of both registries, then the crawls
  sync                       recent projects of both registries; visits what is new, failed or stale (--only=csswinner: one registry)
  crawl <url>                visits one site and adds it to the catalogue
  classify <id>              re-runs the analysis on the stored observation
  search "<brief>"           ranked references (--format=site|pwa|apk|contract_ui, --limit=5, --json)
  research "<brief>"         search + the research pack in .research/latest (--format=, --json)
  doctor                     what is in the catalogue and whether the pipeline can run`;

async function main() {
  switch (command) {
    case 'bootstrap': return out(keepRun('sync', await sync({ home: HOME, limit: 120, pages: 6, maxCrawls: Number(flags.crawls ?? 60) })));
    case 'sync': return out(keepRun('sync', await sync({ home: HOME, limit: Number(flags.limit ?? 30), pages: Number(flags.pages ?? 2), maxCrawls: Number(flags.crawls ?? 20), ...(flags.only ? { registries: String(flags.only).split(',') } : {}) })));
    case 'crawl': { if (!rest[0]) throw new Error('crawl <url>'); const s = await crawlUrl({ home: HOME, url: rest[0] }); return out({ id: s.id, crawl: s.crawl, traits: s.traits, tech: s.tech?.map((t) => `${t.name} (${t.status} ${t.confidence})`), transposable: s.transposable && Object.fromEntries(Object.entries(s.transposable).filter(([, v]) => v?.verdict).map(([k, v]) => [k, v.verdict])) }); }
    case 'classify': { if (!rest[0]) throw new Error('classify <id>'); const s = reclassify(new Catalog(dirs.catalog), rest[0], dirs); return out(s.traits); }
    case 'analyze': return out('Interpretation (art direction, tone, why a reference works) is done by Claude Code from the research pack and its screenshots: run `design-research research "<brief>"`.');
    case 'search': case 'research': {
      const brief = rest.join(' ');
      if (!brief) throw new Error(`${command} "<brief>"`);
      // DR_CATALOG_URL: read the published catalogue instead of a local one (a phone, a session without the repository);
      // DR_SHOTS_URL: where its screenshots are
      const sites = process.env.DR_CATALOG_URL ? await fetchRemoteSites(process.env.DR_CATALOG_URL) : new Catalog(dirs.catalog).all();
      const result = search(sites, brief, { format: flags.format, limit: Number(flags.limit ?? 5) });
      if (command === 'research') {
        const outDir = resolve(process.env.DR_PACK ?? '.research/latest');
        await buildPack(result, brief, { outDir, catalogDir: dirs.catalog, format: result.plan.format, shotsUrl: process.env.DR_SHOTS_URL ?? null });
        if (!flags.json) console.log(`research pack written to ${outDir}`);
      }
      if (flags.json) return out(result);
      out(`format ${result.plan.format}; ${result.considered.crawled} crawled of ${result.considered.catalog}`);
      for (const r of result.results) out(`${String(r.score).padEnd(5)} ${r.site.id}  [${r.matched.join(', ')}]  ${r.site.transposable[result.plan.format].verdict}`);
      if (!result.results.length) out('nothing matched: the catalogue is empty or not crawled yet (design-research sync)');
      return;
    }
    case 'doctor': {
      const catalog = new Catalog(dirs.catalog);
      const sites = catalog.all();
      const byStatus = {};
      for (const s of sites) byStatus[s.crawl?.status ?? 'never'] = (byStatus[s.crawl?.status ?? 'never'] ?? 0) + 1;
      let browser = 'ok';
      try { const { chromium } = await import('playwright'); const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined }); await b.close(); } catch (err) { browser = `cannot launch Chromium: ${String(err.message).split('\n')[0]}`; }
      return out({ home: HOME, sites: sites.length, crawl: byStatus, in_both_registries: sites.filter((s) => s.sources?.length > 1).length, registries: catalog.state.registries, known_registries: Object.keys(registries), browser, catalog_dir: existsSync(dirs.catalog) });
    }
    default: out(usage);
  }
}
main().catch((err) => { console.error(String(err.message ?? err)); process.exit(1); });
