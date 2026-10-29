import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseCampaign, listingSlugs, textOf, excerpt } from '../src/campaign.js';
import { parseRobots, allowed, crawlDelay } from '../src/robots.js';
import { sync, loadCatalog } from '../src/sync.js';
import { research, stats } from '../src/research.js';

// A page shaped like a campaign page of Ads of the World (its text, as read in a probe on 2026-10-10), with the navigation around it.
const PAGE = (title, brand, campaign, agency, desc, facts, cats, extra = '') => `<!doctype html><html><head>
<title>${title} • Ads of the World™ | Part of The Clio Network</title>
<meta content='${title} • Ads of the World™ | Part of The Clio Network' property='og:title'>
<meta content='https://www.adsoftheworld.com/rails/active_storage/x/thumb.jpg' property='og:image'>
<script>var x = "Description";</script></head><body>
<nav><a href="/">Highlighted</a><a href="/">Professional</a><a>Login</a></nav>
<main><div>ADVERTISING</div><h1><a>${brand}</a> <span>${campaign}</span></h1><div>Agency:</div><div><a>${agency}</a></div>
<h2>Description</h2><p>${desc}</p><p>${facts}</p><h3>Categories</h3><ul>${cats.map((c) => `<li><a>${c}</a></li>`).join('')}</ul><div>Share</div>${extra}</main><footer>Newer</footer></body></html>`;

const HARDYS = PAGE('Hardys Wine: Almost Unbelievable', 'Hardys Wine', 'Almost Unbelievable', 'Special London',
  'Australian wine brand Hardys is undergoing its biggest transformation yet. At the centre of the relaunch is “Almost Unbelievable,” which tells the story of founder Thomas Hardy&rsquo;s arrival in Australia from Devon in 1850 with just £30.',
  'This professional campaign titled \'Almost Unbelievable\' was published in Australia in October, 2026. It was created for the brand: Hardys Wine, by ad agency: Special London. This Film and Integrated media campaign is related to the Alcoholic Drinks industry and contains 1 media asset. It was submitted 1 day ago.',
  ['Hardys Wine', 'Special London', 'Australia', 'Oceania', 'Integrated', 'Film', 'Alcoholic Drinks']);
const SUPERCELL = PAGE('Supercell: 30 Seconds Left - Season 2', 'Supercell', '30 Seconds Left - Season 2', 'TBWA\\Helsinki',
  'A second season of a comedy series for a mobile game.', 'This professional campaign titled \'30 Seconds Left - Season 2\' was published in Finland in October, 2026. It was created for the brand: Supercell, by ad agency: TBWA. This Film media campaign is related to the Gaming industry and contains 3 media assets.',
  ['Supercell', 'Finland', 'Film', 'Gaming'], '<iframe src="https://www.youtube.com/embed/EXrtXB_u_60"></iframe><a href="https://www.youtube.com/watch?v=TiTuSU3ynfc">x</a>');

test('a campaign page becomes a record: credits, kind of work, an excerpt of the idea and the address of the film', () => {
  const r = parseCampaign(HARDYS, 'almost-unbelievable');
  assert.equal(r.title, 'Hardys Wine: Almost Unbelievable');
  assert.equal(r.brand, 'Hardys Wine');
  assert.equal(r.campaign, 'Almost Unbelievable');
  assert.equal(r.agency, 'Special London');
  assert.equal(r.country, 'Australia');
  assert.equal(r.year, 2026);
  assert.equal(r.month, 'October');
  assert.deepEqual(r.media, ['Film', 'Integrated']);
  assert.equal(r.industry, 'Alcoholic Drinks');
  assert.equal(r.assets, 1);
  assert.ok(r.categories.includes('Oceania') && !r.categories.includes('Share'));
  assert.ok(r.idea.startsWith('Australian wine brand Hardys') && r.idea.length <= 330);
  assert.match(r.idea, /Thomas Hardy’s|Thomas Hardy's|Thomas Hardy’s/, 'entities are decoded');
  assert.equal(r.url, 'https://www.adsoftheworld.com/campaigns/almost-unbelievable');
  assert.deepEqual(r.video.youtube, []);
  const s = parseCampaign(SUPERCELL, '30-seconds-left-season-2');
  assert.deepEqual(s.video.youtube, ['EXrtXB_u_60', 'TiTuSU3ynfc']);
});

test('a page whose facts are worded differently still gives the sector and the kind of work; section links are not campaigns', () => {
  const html = PAGE('Brand: Name', 'Brand', 'Name', 'Agency X', 'An idea.', 'This professional campaign titled \'Name\' was published in France in September, 2026. It is related to the Banking industry and contains 2 media assets.', ['Brand', 'Agency X', 'France', 'Print', 'Outdoor', 'Banking']);
  const r = parseCampaign(html, 'name');
  assert.equal(r.industry, 'Banking'); assert.equal(r.assets, 2); assert.deepEqual(r.media, ['Print', 'Outdoor']);
  assert.ok(r.facts.includes('published in France'));
  assert.deepEqual(listingSlugs('<a href="/campaigns/new">n</a><a href="/campaigns/real-one">r</a>'), ['real-one']);
});

test('the excerpt of an idea is short, cut at a word, and says so', () => {
  const long = 'word '.repeat(200).trim();
  assert.ok(excerpt(long, 100).length <= 101 && excerpt(long, 100).endsWith('…'));
  assert.equal(excerpt('short', 100), 'short');
  assert.deepEqual(textOf('<p>a&amp;b</p><script>no</script><p>c</p>'), ['a&b', 'c']);
});

test('a listing gives the campaign slugs, once each, in order', () => {
  const html = '<a href="/campaigns/b-one">x</a><a href="/campaigns/a-two">y</a><a href="/campaigns/b-one">z</a><a href="/campaigns">all</a><a href="/about">no</a>';
  assert.deepEqual(listingSlugs(html), ['b-one', 'a-two']);
});

test('robots.txt: a generic bot is allowed what is not disallowed, the longest rule wins, an unreadable file allows nothing', () => {
  const g = parseRobots('User-agent: *\nDisallow: /healthcheck.html\nDisallow: /*?page=\nDisallow: /settings\n\nUser-agent: Googlebot\nAllow: /\nCrawl-delay: 3');
  assert.equal(allowed(g, '/campaigns/almost-unbelievable'), true);
  assert.equal(allowed(g, '/campaigns?page=2'), false);
  assert.equal(allowed(g, '/settings'), false);
  const closed = parseRobots('User-agent: *\nCrawl-delay: 10\nDisallow: /\nUser-agent: Googlebot\nAllow: /');
  assert.equal(allowed(closed, '/campaigns/x'), false, 'The One Show style: everything is disallowed for a generic bot');
  assert.equal(crawlDelay(closed), 10);
  const mixed = parseRobots('User-agent: *\nDisallow: /a\nAllow: /a/b');
  assert.equal(allowed(mixed, '/a/b/c'), true);
  assert.equal(allowed(mixed, '/a/c'), false);
});

function fakeSite(pages) {
  const asked = [];
  const fetchFn = async (url) => {
    const path = url.replace('https://www.adsoftheworld.com', '');
    asked.push(path);
    if (pages[path] === undefined) return { ok: false, status: 404, text: async () => '' };
    return { ok: true, status: 200, text: async () => pages[path] };
  };
  return { fetchFn, asked };
}

test('sync reads the listings, then only the campaigns it has not seen, politely, and writes the catalogue', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'vr-'));
  const site = fakeSite({
    '/robots.txt': 'User-agent: *\nDisallow: /*?page=\n',
    '/': '<a href="/campaigns/almost-unbelievable">a</a><a href="/campaigns/30-seconds-left-season-2">b</a>',
    '/campaigns': '<a href="/campaigns/almost-unbelievable">a</a>',
    '/campaigns/almost-unbelievable': HARDYS, '/campaigns/30-seconds-left-season-2': SUPERCELL,
  });
  const first = await sync({ dir, fetchFn: site.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(first.new, 2); assert.equal(first.total, 2); assert.deepEqual(first.errors, []);
  assert.equal(loadCatalog(dir).length, 2);
  assert.ok(existsSync(join(dir, 'last-sync.json')));
  const asked = site.asked.length;
  const second = await sync({ dir, fetchFn: site.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(second.new, 0); assert.equal(second.known, 2);
  assert.equal(site.asked.slice(asked).filter((p) => p.startsWith('/campaigns/')).length, 0, 'a known campaign is not fetched again');
  // a record without its "facts" (written by an earlier version) is read again, to be completed
  const { writeFileSync } = await import('node:fs');
  writeFileSync(join(dir, 'campaigns.jsonl'), loadCatalog(dir).map((r) => { const { facts, ...old } = r; return JSON.stringify(old); }).join('\n') + '\n');
  const refreshed = await sync({ dir, fetchFn: site.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(refreshed.new, 2); assert.equal(loadCatalog(dir).length, 2); assert.ok(loadCatalog(dir).every((r) => 'facts' in r));
  const limited = await sync({ dir: mkdtempSync(join(tmpdir(), 'vr-')), fetchFn: site.fetchFn, delayMs: 0, max: 1, log: () => {} });
  assert.equal(limited.new, 1, 'at most max new campaigns per run');
});

test('sync fetches nothing when robots.txt cannot be read or forbids the path, and says a page it cannot read', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'vr-'));
  const none = fakeSite({});
  const a = await sync({ dir, fetchFn: none.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(a.new, 0); assert.match(a.errors[0], /robots\.txt unreadable/); assert.deepEqual(none.asked, ['/robots.txt']);
  const closed = fakeSite({ '/robots.txt': 'User-agent: *\nDisallow: /\n', '/': '<a href="/campaigns/x-y">a</a>' });
  const b = await sync({ dir, fetchFn: closed.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(b.new, 0); assert.ok(b.skipped_by_robots >= 2); assert.deepEqual(closed.asked, ['/robots.txt']);
  const broken = fakeSite({ '/robots.txt': 'User-agent: *\n', '/': '<a href="/campaigns/x-y">a</a>', '/campaigns/x-y': '<html><body>blocked</body></html>' });
  const c = await sync({ dir: mkdtempSync(join(tmpdir(), 'vr-')), fetchFn: broken.fetchFn, delayMs: 0, log: () => {} });
  assert.equal(c.new, 0); assert.match(c.errors.join(' '), /nothing readable/);
});

test('research brings back the campaigns closest to a brief, with credits and the address of the film, never the film', () => {
  const rows = [parseCampaign(HARDYS, 'almost-unbelievable'), parseCampaign(SUPERCELL, '30-seconds-left-season-2')];
  const wine = research(rows, 'une vidéo promotionnelle pour un vin australien', { limit: 3 });
  assert.equal(wine[0].title, 'Hardys Wine: Almost Unbelievable');
  assert.equal(wine[0].film, null, 'no film address on that page');
  const game = research(rows, 'a mobile game comedy series');
  assert.equal(game[0].brand, 'Supercell');
  assert.equal(game[0].film, 'https://www.youtube.com/watch?v=EXrtXB_u_60');
  assert.deepEqual(research(rows, 'zzz qqq'), []);
  assert.equal(research(rows, 'game', { industry: 'wine' }).length, 0, 'the industry filter applies');
  assert.equal(stats(rows).total, 2);
});
