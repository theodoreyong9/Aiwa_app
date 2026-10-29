import test from 'node:test';
import assert from 'node:assert/strict';
import { ed25519 } from '@noble/curves/ed25519.js';
import { geohash, bounds, cellsAround, cleanLinks, checkEntry, parseCard, cardText, parseRepo, repoLinks, linksFromReleases, LEVELS, roomName, distanceTo, filterRows, scoreRange } from '../src/voir-core.js';

// voir-core.js: the parts of « Voir » that need no page
const utf8 = new TextEncoder();
const hex = (b) => Buffer.from(b).toString('hex');
const sign = (e, secret) => hex(ed25519.sign(utf8.encode(JSON.stringify({ v: 1, cell: e.cell, repo: e.repo, links: e.links, score: e.score, laps: e.laps, ts: e.ts, pub: e.pub })), secret));

test('a geohash is the known cell of a known place', () => {
  assert.equal(geohash(57.64911, 10.40744, 11), 'u4pruydqqvj');
  assert.equal(geohash(48.8584, 2.2945, 4), 'u09t');
});

test('only https links of a known kind are kept, short and few', () => {
  const links = cleanLinks([
    { kind: 'page', url: 'https://a.github.io/x/' }, { kind: 'page', url: 'http://insecure.example/' }, { kind: 'script', url: 'https://x.example/' },
    { kind: 'docs', url: 'javascript:alert(1)' }, { kind: 'app', url: 'https://github.com/a/b/releases' }, 'nope',
  ]);
  assert.deepEqual(links.map((l) => l.kind), ['page', 'app']);
  assert.deepEqual(cleanLinks('x'), []);
});

test('an entry is accepted only if it is signed by the key it names, fresh, for this cell', () => {
  const secret = ed25519.utils.randomSecretKey(); const pub = hex(ed25519.getPublicKey(secret));
  const now = Date.now();
  const entry = { v: 1, cell: 'u09tvw0q', repo: 'a/b', links: [{ kind: 'page', url: 'https://a.github.io/b/' }], score: 12.5, laps: 3, ts: now, pub };
  entry.sig = sign(entry, secret);
  assert.equal(checkEntry(entry, 'u09tvw0q', now)?.score, 12.5);
  assert.equal(checkEntry(entry, ['u09t'], now)?.score, 12.5, 'a wider room names a prefix of the cell');
  assert.equal(checkEntry({ ...entry, score: 999 }, 'u09tvw0q', now), null, 'a changed score breaks the signature');
  assert.equal(checkEntry(entry, 'u09uvw0q', now), null, 'another cell');
  assert.equal(checkEntry(entry, 'u09tvw0q', now + 11 * 60_000), null, 'too old');
  assert.equal(checkEntry({ ...entry, links: [{ kind: 'page', url: 'https://evil.example/' }] }, 'u09tvw0q', now), null, 'links are signed too');
  assert.equal(checkEntry(null, 'u09tvw0q', now), null);
});

test('the cells around a position: its own and the neighbours toward the nearest edges, 8 characters (about 38 x 19 m)', () => {
  const cells = cellsAround(46.5197, 6.6323);
  assert.ok(cells.length >= 2 && cells.length <= 4);
  assert.ok(cells.every((c) => c.length === 8));
  assert.equal(cells[0], geohash(46.5197, 6.6323, 8));
  const b = bounds(cells[0]);
  assert.ok(b.latLo <= 46.5197 && 46.5197 <= b.latHi && b.lonLo <= 6.6323 && 6.6323 <= b.lonHi);
  assert.ok(b.latHi - b.latLo < 0.0003 && b.lonHi - b.lonLo < 0.0005);
});

test('a card from a QR code or a pasted text: https links only, nothing else', () => {
  const links = [{ kind: 'page', url: 'https://a.github.io/b/' }, { kind: 'docs', url: 'https://github.com/a/b/tree/HEAD/docs' }];
  const card = parseCard(cardText('a/b', links));
  assert.equal(card.repo, 'a/b');
  assert.equal(card.links.length, 2);
  assert.equal(parseCard('https://a.github.io/b/').links[0].kind, 'page');
  assert.equal(parseCard('http://insecure.example/'), null);
  assert.equal(parseCard('javascript:alert(1)'), null);
  assert.equal(parseCard('{"links":[{"kind":"page","url":"http://x"}]}'), null);
  assert.equal(parseCard('x'.repeat(2000)), null);
});

test('a repository from the GitHub name and the name, or from a pasted address', () => {
  assert.equal(parseRepo('theodoreyong9', 'Aiwa_store'), 'theodoreyong9/Aiwa_store');
  assert.equal(parseRepo('theodoreyong9/Aiwa_store'), 'theodoreyong9/Aiwa_store');
  assert.equal(parseRepo('@jdacunha', 'mon-depot'), 'jdacunha/mon-depot');
  assert.equal(parseRepo('https://github.com/a/b/tree/main/docs'), 'a/b');
  assert.equal(parseRepo('https://github.com/a/b.git'), 'a/b');
  assert.equal(parseRepo('seulement'), null);
  assert.equal(parseRepo('', ''), null);
  assert.equal(parseRepo('a b', 'c'), null);
});

test('the links of the Files of a repository are the five lists, and the newest release of each kind', () => {
  const links = repoLinks('a/b');
  assert.deepEqual(links.map((l) => l.kind), ['docs', 'image', 'video', 'app', 'page']);
  const found = linksFromReleases('a/b', [{ tag_name: 'video-promo-2' }, { tag_name: 'docs-cv-1' }, { tag_name: 'docs-old', draft: false }, { tag_name: 'x-1' }, { tag_name: 'app-z', draft: true }]);
  assert.deepEqual(found, [{ kind: 'docs', url: 'https://github.com/a/b/releases/tag/docs-cv-1' }, { kind: 'video', url: 'https://github.com/a/b/releases/tag/video-promo-2' }]);
  assert.deepEqual(cleanLinks(links), links);
});

test('the two sliders: the reach from 50 m to the world, and the score between the lowest and the highest detected', () => {
  assert.equal(LEVELS[0].meters, 50); assert.equal(LEVELS.at(-1).label, 'Monde'); assert.equal(LEVELS.at(-1).meters, Infinity);
  assert.deepEqual(LEVELS.map((l) => l.len), [8, 7, 6, 5, 4, 3, 2, 0], 'each level is a coarser room');
  assert.equal(roomName('u09tvw0q', 2), 'voir:u09tvw'); assert.equal(roomName('u09tvw0q', 7), 'voir:world');
  const here = { lat: 46.5197, lon: 6.6323 }, near = geohash(46.5197, 6.6323, 8), far = geohash(46.5197 + 0.2, 6.6323, 8);   // 0.2 degree of latitude: about 22 km
  assert.ok(distanceTo(here.lat, here.lon, near) < 40); assert.ok(distanceTo(here.lat, here.lon, far) > 20_000 && distanceTo(here.lat, here.lon, far) < 24_000);
  const rows = [{ cell: near, score: 5 }, { cell: far, score: 20 }, { cell: far, score: 2 }];
  assert.deepEqual(scoreRange(rows), { min: 2, max: 20 }); assert.equal(scoreRange([]), null);
  assert.equal(filterRows(rows, { here, maxMeters: 50 }).length, 1, 'the nearest reach keeps the person next to me');
  assert.equal(filterRows(rows, { here, maxMeters: 40_000 }).length, 3);
  assert.deepEqual(filterRows(rows, { here, maxMeters: Infinity, minScore: 5 }).map((r) => r.score), [5, 20], 'the score slider keeps the scores from its value up');
});
