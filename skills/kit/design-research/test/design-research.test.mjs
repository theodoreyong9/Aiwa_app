import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { crawl } from '../src/crawler/crawl.js';
import { analyze } from '../src/analyze.js';
import { Catalog, fetchRemoteSites } from '../src/catalog/store.js';
import { discover } from '../src/registry/index.js';
import { sync, homeDirs, reclassify } from '../src/pipeline.js';
import { plan } from '../src/retrieval/plan.js';
import { search } from '../src/retrieval/search.js';
import { buildPack } from '../src/pack.js';
import { siteId, cleanUrl, robotsAllows } from '../src/util.js';
import { serve, fakeFetch } from '../support/helpers.mjs';

let web, cinematic, plain, cinematicRaw;
before(async () => {
  web = await serve();
  const dir = mkdtempSync(join(tmpdir(), 'dr-shots-'));
  cinematicRaw = await crawl(`${web.base}/cinematic.html`, { shotDir: dir });
  cinematic = analyze(cinematicRaw);
  plain = analyze(await crawl(`${web.baseIp}/plain.html`, {}));
});
after(() => web.close());

test('the crawl measures a cinematic page: type, composition, motion, rendering', () => {
  const t = cinematic.traits;
  assert.ok(t.typography.includes('oversized'), `typography ${t.typography}`);
  assert.ok(t.typography.includes('serif'));
  assert.ok(t.typography.includes('uppercase'));
  assert.ok(t.composition.includes('fullscreen'));
  assert.ok(t.motion.includes('scroll-driven'));
  assert.ok(t.motion.includes('smooth-scroll'));
  assert.ok(t.motion.includes('reveal'));
  assert.ok(t.motion.includes('continuous'));
  assert.ok(t.motion.includes('slow-easing'));
  assert.ok(t.interaction.includes('custom-cursor'));
  assert.ok(t.rendering.includes('3D') && t.rendering.includes('WebGL'));
  assert.ok(t.palette.includes('dark'));
  assert.equal(cinematic.tokens.color.variables['--accent'], '#c9a46a');
  assert.ok(cinematic.tokens.typography.sizeMaxVw >= 11);
});

test('a plain page is described as plain, not as something it is not', () => {
  assert.ok(plain.traits.motion.includes('static'));
  assert.deepEqual(plain.traits.rendering, ['DOM-CSS']);
  assert.ok(plain.traits.palette.includes('light'));
  assert.ok(!plain.traits.typography.includes('oversized'));
  assert.equal(plain.tech.length, 0);
});

test('every detection carries its status, its confidence and its evidence; a library is only OBSERVED when the page shows it', () => {
  const gsap = cinematic.tech.find((t) => t.name === 'GSAP');
  assert.equal(gsap.status, 'OBSERVED');
  assert.ok(gsap.confidence >= 0.9 && gsap.evidence[0].includes('window.gsap'));
  const webgl = cinematic.tech.find((t) => t.name === 'WebGL');
  assert.equal(webgl.status, 'OBSERVED');
  for (const t of cinematic.tech) { assert.ok(['OBSERVED', 'INFERRED', 'DECLARED', 'UNKNOWN'].includes(t.status)); assert.ok(t.evidence.length > 0); }
  assert.ok(!cinematic.tech.some((t) => t.name === 'Three.js'), 'WebGL alone does not make it Three.js');
});

test('CDP saw the network, the animations and the targets; a screenshot exists for desktop and mobile', () => {
  const d = cinematicRaw.desktop;
  assert.ok(d.network.some((r) => r.type === 'DOCUMENT' && r.status === 200));
  assert.ok(d.animationsReported.length > 0, 'Animation domain events');
  assert.ok(d.performance.metrics.layoutCount > 0);
  assert.ok(d.targets.frames >= 1);
  assert.equal(d.shots.desktop, 'desktop.jpg');
  assert.ok(cinematicRaw.mobile.shots.mobile);
  assert.ok(cinematicRaw.mobile.features.elements > 0 && cinematicRaw.desktop.scrollReveal >= 3);
});

test('what a format can use: a 3D reference is partial for a single-file app, a plain one is fine', () => {
  assert.equal(cinematic.transposable.site.verdict, 'yes');
  assert.equal(cinematic.transposable.apk.verdict, 'partial');
  assert.match(cinematic.transposable.pwa.reason, /512 KB/);
  assert.equal(plain.transposable.pwa.verdict, 'yes');
  assert.equal(cinematic.transposable.contract_ui.verdict, 'partial');
});

test('one site listed by two registries is one entry with two sources', () => {
  const dir = mkdtempSync(join(tmpdir(), 'dr-cat-'));
  const c = new Catalog(dir);
  assert.equal(c.upsert({ url: 'https://www.example.com/?utm_source=awwwards', registry: 'awwwards', award: 'SOTD', page: 'a' }), 'NEW');
  assert.equal(c.upsert({ url: 'https://example.com/', registry: 'csswinner', award: 'SOTD', page: 'b' }), 'UPDATED');
  assert.equal(c.upsert({ url: 'https://example.com/', registry: 'csswinner', award: 'SOTD', page: 'b' }), 'UNCHANGED');
  assert.equal(c.all().length, 1);
  assert.equal(c.get('example.com').sources.length, 2);
  c.save();
  assert.equal(new Catalog(dir).get('example.com').sources.length, 2);
  assert.equal(siteId('https://WWW.Foo.com/x'), 'foo.com');
  assert.equal(cleanUrl('https://a.com/?utm_source=x&keep=1#h'), 'https://a.com/?keep=1');
});

test('robots.txt: Disallow and Allow prefixes for everybody', () => {
  const robots = 'User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nDisallow: /private\nAllow: /private/open\n';
  assert.equal(robotsAllows(robots, '/websites/'), true);
  assert.equal(robotsAllows(robots, '/private/x'), false);
  assert.equal(robotsAllows(robots, '/private/open/x'), true);
});

test('the registry parsers find the projects and their outbound link', async () => {
  const fetchFn = fakeFetch(1234);
  const a = await discover('awwwards', { limit: 5, pages: 1, fetchFn, delayMs: 0 });
  assert.deepEqual(a.found.map((f) => f.title), ['Maison Nuit', 'Café du coin']);
  assert.ok(a.found[0].url.startsWith('http://localhost:1234/cinematic.html'));
  assert.equal(a.errors.length, 0);
  const c = await discover('csswinner', { limit: 5, pages: 1, fetchFn, delayMs: 0 });
  assert.equal(c.found.length, 1);
  assert.equal(c.found[0].url, 'http://localhost:1234/cinematic.html');
});

test('sync: new sites are visited once, the second run changes nothing, a failed site is retried a bounded number of times', async () => {
  const home = mkdtempSync(join(tmpdir(), 'dr-home-'));
  const fetchFn = fakeFetch(web.port);
  const quiet = () => {};
  const first = await sync({ home, registries: ['awwwards', 'csswinner'], limit: 5, pages: 1, maxCrawls: 5, fetchFn, delayMs: 0, log: quiet });
  assert.equal(first.NEW, 2);
  assert.equal(first.UPDATED, 1, 'csswinner lists a site awwwards already listed');
  assert.equal(first.crawled, 2);
  const catalog = new Catalog(homeDirs(home).catalog);
  const maison = catalog.get('localhost');
  assert.equal(maison.crawl.status, 'ok');
  assert.equal(maison.sources.length, 2);
  assert.ok(maison.traits.rendering.includes('3D'));
  assert.ok(existsSync(join(home, 'screenshots', 'localhost', 'desktop.jpg')));
  assert.ok(existsSync(join(home, 'analysis', 'localhost.raw.json')));
  const second = await sync({ home, registries: ['awwwards', 'csswinner'], limit: 5, pages: 1, maxCrawls: 5, fetchFn, delayMs: 0, log: quiet });
  assert.equal(second.NEW, 0); assert.equal(second.UPDATED, 0); assert.equal(second.crawled, 0);
  // re-classify from the stored observation, without a visit
  const again = reclassify(new Catalog(homeDirs(home).catalog), 'localhost', homeDirs(home));
  assert.ok(again.traits.motion.includes('scroll-driven'));
  // a failing crawl is recorded and retried up to the limit
  const failing = async () => { throw new Error('boom'); };
  const c2 = new Catalog(homeDirs(home).catalog);
  c2.upsert({ url: 'http://broken.invalid/', registry: 'manual', award: '', page: 'm' }); c2.save();
  for (let i = 0; i < 5; i++) await sync({ home, registries: [], maxCrawls: 5, crawlFn: failing, log: quiet });
  const broken = new Catalog(homeDirs(home).catalog).get('broken.invalid');
  assert.equal(broken.crawl.status, 'failed');
  assert.equal(broken.crawl.attempts, 3);
});

test('the brief becomes dimensions, and the search ranks by what was measured, per format, with the reasons', () => {
  const p = plan('un site cinématique, sombre, avec une scène 3D et de très grands titres');
  assert.equal(p.format, 'site');
  assert.ok(p.dimensions.motion > 0 && p.dimensions.rendering > 0 && p.dimensions.palette > 0 && p.dimensions.typography > 0);
  const sites = [
    { id: 'a.com', title: 'A', crawl: { status: 'ok' }, sources: [{}], traits: cinematic.traits, tech: cinematic.tech, transposable: cinematic.transposable },
    { id: 'b.com', title: 'B', crawl: { status: 'ok' }, sources: [{}], traits: plain.traits, tech: plain.tech, transposable: plain.transposable },
    { id: 'c.com', title: 'C', crawl: { status: 'failed' }, sources: [{}] },
  ];
  const r = search(sites, 'un site cinématique, sombre, avec une scène 3D et de très grands titres');
  assert.equal(r.results[0].site.id, 'a.com');
  assert.ok(r.results[0].matched.includes('rendering:3D') && r.results[0].matched.includes('palette:dark'));
  assert.equal(r.considered.crawled, 2);
  const minimal = search(sites, 'un apk android clair et épuré', { limit: 5 });
  assert.equal(minimal.plan.format, 'apk', 'the word android asks for the phone format');
  assert.equal(minimal.results[0].site.id, 'b.com', 'a plain light page fits a single-file app better than a 3D scene');
});

test('the research pack: references with evidence, shared patterns, measured ranges, screenshots, a how-to', async () => {
  const home = mkdtempSync(join(tmpdir(), 'dr-pack-'));
  const out = join(home, 'pack');
  const sites = [1, 2, 3].map((i) => ({ id: `s${i}.com`, url: `https://s${i}.com`, title: `S${i}`, crawl: { status: 'ok' }, sources: [{ registry: 'awwwards' }], traits: cinematic.traits, tech: cinematic.tech, tokens: cinematic.tokens, transposable: cinematic.transposable, needs_interpretation: cinematic.needs_interpretation, screenshots: {} }));
  const result = search(sites, 'cinématique sombre 3D', { limit: 3 });
  const { shared } = await buildPack(result, 'cinématique sombre 3D', { outDir: out, catalogDir: join(home, 'catalog'), format: 'site' });
  assert.ok(shared.motion.some((m) => m.trait === 'scroll-driven' && m.in === '3/3'));
  const refs = JSON.parse(readFileSync(join(out, 'references.json'), 'utf8'));
  assert.equal(refs.references.length, 3);
  assert.ok(refs.references[0].technology[0].evidence.length > 0);
  assert.ok(refs.measured_ranges.max_font_size_px);
  const md = readFileSync(join(out, 'synthesis.md'), 'utf8');
  assert.match(md, /Do not copy any site/);
  assert.match(md, /needs_interpretation/);
  assert.ok(existsSync(join(out, 'query.json')));
});

test('a session without the repository reads the published catalogue and its screenshots', async () => {
  const sites = [{ id: 'r.com', url: 'https://r.com', title: 'R', crawl: { status: 'ok' }, sources: [{ registry: 'awwwards' }], traits: cinematic.traits, tech: cinematic.tech, tokens: cinematic.tokens, transposable: cinematic.transposable, needs_interpretation: [], screenshots: { desktop: { desktop: 'desktop.jpg' } } }];
  const fetchFn = async (url) => {
    if (String(url).endsWith('/sites.jsonl')) return { ok: true, status: 200, text: async () => sites.map((s) => JSON.stringify(s)).join('\n') + '\n' };
    if (String(url).endsWith('/r.com/desktop.jpg')) return { ok: true, status: 200, arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer };
    return { ok: false, status: 404 };
  };
  const loaded = await fetchRemoteSites('https://example.test/catalog/', fetchFn);
  assert.equal(loaded.length, 1);
  const out = join(mkdtempSync(join(tmpdir(), 'dr-remote-')), 'pack');
  await buildPack(search(loaded, 'cinématique sombre 3D'), 'cinématique sombre 3D', { outDir: out, catalogDir: '/nowhere/catalog', format: 'site', shotsUrl: 'https://example.test/shots', fetchFn });
  const refs = JSON.parse(readFileSync(join(out, 'references.json'), 'utf8'));
  assert.deepEqual(refs.references[0].screenshots.desktop, ['screenshots/r.com-desktop-desktop.jpg']);
  assert.ok(existsSync(join(out, 'screenshots', 'r.com-desktop-desktop.jpg')));
  await assert.rejects(fetchRemoteSites('https://example.test/none', async () => ({ ok: false, status: 404 })), /HTTP 404/);
});
