import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { creditLine, energyOf, usable, seconds } from '../src/track.js';
import { parsePieces } from '../src/incompetech.js';
import { parseTrack, listingSlugs, pageLicence } from '../src/oga.js';
import { search } from '../src/search.js';
import { parseRobots, allowed, crawlDelay } from '../src/robots.js';
import { syncIncompetech, syncOga, loadCatalog } from '../src/sync.js';

const pieces = [
  { title: 'Sneaky Snitch', filename: 'Sneaky Snitch.mp3', length: '00:02:17', instruments: 'Oboe, Strings, Snare Drum', bpm: '87', description: 'An oboe and a snare drum dance.', feel: 'Bouncy, Dark, Humorous, Mysterious' },
  { title: 'Hit the Gas', filename: 'Hit the Gas.mp3', length: '00:03:00', instruments: 'Drums, Electric Guitar', bpm: '140', description: 'Fast and loud.', feel: 'Aggressive, Driving, Intense' },
  { title: 'Floating Cities', filename: 'Floating Cities.mp3', length: '00:04:30', instruments: 'Synth', bpm: '70', description: 'Slow pads.', feel: 'Calming, Relaxed' },
];
const tracks = parsePieces(pieces);
const ogaPage = `<html><head><title>Battle Theme A | OpenGameArt.org</title></head><body><a href="/users/cynicmusic">cynicmusic</a>
<div class="field-name-field-art-licenses field-label-above"> License(s):&nbsp; CC0 Collections:&nbsp; <a href="/content/x">x</a></div>
<div class="field-name-field-art-tags"><div class="field-items"><div><a href="/art-search-advanced?field_art_tags_tid=RPG">RPG</a></div><div><a href="/art-search-advanced?field_art_tags_tid=epic">epic</a></div></div></div>
<div class="field-name-field-art-files"><a href="https://opengameart.org/sites/default/files/battleThemeA.mp3" type="audio/mpeg; length=3289143" download="battleThemeA.mp3">battleThemeA.mp3</a></div></body></html>`;

test('incompetech pieces become tracks with tempo, tags, credit and an energy reading', () => {
  assert.equal(tracks.length, 3);
  const t = tracks[1];
  assert.equal(t.id, 'inc-hit-the-gas'); assert.equal(t.bpm, 140); assert.equal(t.seconds, 180); assert.deepEqual(t.tags, ['aggressive', 'driving', 'intense']);
  assert.match(t.file, /mp3-royaltyfree\/Hit%20the%20Gas\.mp3$/);
  assert.ok(t.energy >= 4 && tracks[2].energy <= 2, `${t.energy} ${tracks[2].energy}`);
  assert.equal(creditLine(t), 'Musique : « Hit the Gas », Kevin MacLeod (incompetech.com), CC BY 4.0');
});

test('only accepted licences are usable and CC0 asks for no credit', () => {
  for (const l of ['cc0', 'pd', 'cc-by-4.0', 'cc-by-3.0']) assert.ok(usable(l));
  for (const l of ['cc-by-nc-4.0', 'cc-by-sa-4.0', 'cc-by-nd-4.0', 'gpl-3.0', undefined]) assert.ok(!usable(l), String(l));
  assert.equal(creditLine({ licence: 'cc0', title: 'x', artist: 'y' }), null);
  assert.equal(creditLine({ licence: 'cc-by-nc-4.0', title: 'x', artist: 'y' }), null);
  assert.equal(seconds('00:02:17'), 137);
  assert.ok(energyOf(['calming', 'relaxed'], 70) <= 1 && energyOf(['intense', 'aggressive', 'driving'], 150) === 5);
});

test('search: a French brief finds the right mood, filters are exact, "none" keeps only tracks without credit', () => {
  const rows = [...tracks, ...[parseTrack(ogaPage, 'battle-theme-a')]];
  const punchy = search(rows, 'musique énergique et punchy', { limit: 3 });
  assert.equal(punchy[0].id, 'inc-hit-the-gas');
  assert.deepEqual(search(rows, 'énergique', { bpm: [60, 90] }), []);
  assert.equal(search(rows, '', { bpm: [60, 90], limit: 5 }).length, 2);
  assert.equal(search(rows, 'épique', { credit: 'none' })[0].id, 'oga-battle-theme-a');
  assert.ok(search(rows, 'énergique', { credit: 'none' }).every((r) => r.credit === null));
  assert.ok(search(rows, '', { energy: 4 }).every((r) => r.energy >= 4));
  assert.ok(search([{ id: 'z', licence: 'cc-by-nc-4.0', tags: ['intense'], title: 'z', artist: 'z' }], 'intense').length === 0);
});

test('an OpenGameArt page is read: title, author, licence, tags and the mp3 with its size', () => {
  const t = parseTrack(ogaPage, 'battle-theme-a');
  assert.equal(t.title, 'Battle Theme A'); assert.equal(t.artist, 'cynicmusic'); assert.equal(t.licence, 'cc0');
  assert.deepEqual(t.tags, ['rpg', 'epic']); assert.equal(t.file, 'https://opengameart.org/sites/default/files/battleThemeA.mp3'); assert.equal(t.bytes, 3289143);
  assert.equal(pageLicence(ogaPage.replace('CC0', 'CC-BY 3.0, GPL 2.0')), 'cc-by-3.0');
  assert.equal(pageLicence(ogaPage.replace('CC0', 'CC-BY-SA 3.0')), null);
  assert.equal(parseTrack(ogaPage.replace('CC0', 'GPL 3.0'), 'x'), null);
  assert.deepEqual(listingSlugs('<a href="/content/faq">faq</a><a href="/content/a-b">a</a><a href="/content/a-b">a</a><a href="/content/c">c</a>'), ['a-b', 'c']);
});

test('robots.txt rules are respected', () => {
  const g = parseRobots('User-agent: *\nCrawl-delay: 10\nDisallow: /includes/\nDisallow: /misc/\n');
  assert.ok(allowed(g, '/content/battle-theme-a')); assert.ok(!allowed(g, '/misc/x')); assert.equal(crawlDelay(g), 10);
});

const fake = (routes) => async (url) => {
  const key = Object.keys(routes).find((k) => String(url).includes(k));
  if (!key) return { ok: false, status: 404, text: async () => '', json: async () => ({}) };
  const v = routes[key];
  return { ok: true, status: 200, text: async () => (typeof v === 'string' ? v : JSON.stringify(v)), json: async () => v };
};

test('sync incompetech writes the register and refuses a suspiciously small list', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'mr-'));
  const many = Array.from({ length: 150 }, (_, i) => ({ ...pieces[0], title: `Piece ${i}`, filename: `Piece ${i}.mp3` }));
  const r = await syncIncompetech({ dir, fetchFn: fake({ 'robots.txt': 'User-agent: *\nDisallow: /web-bin/\n', 'pieces.json': many }) });
  assert.equal(r.errors.length, 0); assert.equal(loadCatalog(dir).length, 150);
  const bad = await syncIncompetech({ dir, fetchFn: fake({ 'robots.txt': 'User-agent: *\nDisallow:\n', 'pieces.json': pieces }) });
  assert.ok(bad.errors[0].includes('only 3 pieces')); assert.equal(loadCatalog(dir).length, 150);
  const no = await syncIncompetech({ dir, fetchFn: fake({ 'robots.txt': 'User-agent: *\nDisallow: /music/\n', 'pieces.json': many }) });
  assert.ok(no.errors[0].includes('forbids'));
});

test('sync opengameart reads the listing then the new pages, skips unusable ones and remembers them', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'mr-'));
  const fetchFn = fake({ 'robots.txt': 'User-agent: *\nCrawl-delay: 0\nDisallow: /misc/\n', 'art-search-advanced': '<a href="/content/battle-theme-a">a</a><a href="/content/gpl-song">b</a>', '/content/battle-theme-a': ogaPage, '/content/gpl-song': ogaPage.replace('CC0', 'GPL 3.0') });
  const r = await syncOga({ dir, max: 5, pages: 1, delayMs: 0, fetchFn, log: () => {} });
  assert.equal(r.new, 1); assert.equal(r.skipped, 1);
  assert.equal(loadCatalog(dir)[0].id, 'oga-battle-theme-a');
  assert.deepEqual(JSON.parse(readFileSync(join(dir, 'oga-skipped.json'), 'utf8')), ['gpl-song']);
  const again = await syncOga({ dir, max: 5, pages: 1, delayMs: 0, fetchFn, log: () => {} });
  assert.equal(again.new, 0);
  const blind = await syncOga({ dir, delayMs: 0, fetchFn: fake({}), log: () => {} });
  assert.ok(blind.errors[0].includes('nothing fetched'));
});
