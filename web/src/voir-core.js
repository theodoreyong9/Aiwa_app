// « Voir », the parts that need no page: the map cell, the cleaning of a stranger's links, the check of a signed entry.
import { verifyHex } from 'aiwa-core';

export const NEAR_LENGTH = 8;                          // a geohash of 8 characters is a cell of about 38 x 19 m: « near » means about 50 m
const BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz';
const KINDS = new Set(['docs', 'media', 'app', 'page', 'contract']);
const MAX_LINKS = 6, MAX_URL = 300, FRESH_MS = 10 * 60_000;
const BLOCKED = 'aiwa-voir-blocked';
export const PERIOD_MS = 30_000;
export const utf8 = new TextEncoder();

/** The bounds of a geohash cell. */
export function bounds(hash) {
  let latLo = -90, latHi = 90, lonLo = -180, lonHi = 180, even = true;
  for (const ch of hash) {
    const v = BASE32.indexOf(ch);
    for (let b = 4; b >= 0; b--) {
      const bit = (v >> b) & 1;
      if (even) { const mid = (lonLo + lonHi) / 2; if (bit) lonLo = mid; else lonHi = mid; } else { const mid = (latLo + latHi) / 2; if (bit) latLo = mid; else latHi = mid; }
      even = !even;
    }
  }
  return { latLo, latHi, lonLo, lonHi };
}

/** The cell of a position and the (up to) three neighbours toward which it is nearest to the edge: the people within about 50 m are in one of these. */
export function cellsAround(lat, lon, length = NEAR_LENGTH) {
  const own = geohash(lat, lon, length), b = bounds(own);
  const cLat = (b.latLo + b.latHi) / 2, cLon = (b.lonLo + b.lonHi) / 2, sLat = b.latHi - b.latLo, sLon = b.lonHi - b.lonLo;
  const dy = lat >= cLat ? 1 : -1, dx = lon >= cLon ? 1 : -1;
  return [...new Set([own, geohash(cLat + dy * sLat, cLon, length), geohash(cLat, cLon + dx * sLon, length), geohash(cLat + dy * sLat, cLon + dx * sLon, length)])];
}

/** A geohash of `length` characters for a position: a map cell, the coarsest thing this page ever sends. */
export function geohash(lat, lon, length) {
  let latLo = -90, latHi = 90, lonLo = -180, lonHi = 180, bit = 0, ch = 0, even = true, out = '';
  while (out.length < length) {
    if (even) { const mid = (lonLo + lonHi) / 2; if (lon >= mid) { ch = (ch << 1) | 1; lonLo = mid; } else { ch <<= 1; lonHi = mid; } }
    else { const mid = (latLo + latHi) / 2; if (lat >= mid) { ch = (ch << 1) | 1; latLo = mid; } else { ch <<= 1; latHi = mid; } }
    even = !even;
    if (++bit === 5) { out += BASE32[ch]; bit = 0; ch = 0; }
  }
  return out;
}

export const readBlocked = () => { try { return new Set(JSON.parse(localStorage.getItem(BLOCKED) ?? '[]')); } catch { return new Set(); } };
export const writeBlocked = (set) => { try { localStorage.setItem(BLOCKED, JSON.stringify([...set])); } catch { /* it lasts until the page closes */ } };

/** Only https links of a known kind, short, at most MAX_LINKS: what a stranger sends is never trusted further than that. */
export function cleanLinks(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const item of raw.slice(0, MAX_LINKS)) {
    if (!item || typeof item.kind !== 'string' || !KINDS.has(item.kind) || typeof item.url !== 'string' || item.url.length > MAX_URL) continue;
    let url;
    try { url = new URL(item.url); } catch { continue; }
    if (url.protocol !== 'https:') continue;
    out.push({ kind: item.kind, url: url.href });
  }
  return out;
}

/** The bytes that are signed: a fixed order of fields, so that the sender and the receiver read the same message. */
export const messageOf = (e) => utf8.encode(JSON.stringify({ v: 1, cell: e.cell, repo: e.repo, links: e.links, score: e.score, laps: e.laps, ts: e.ts, pub: e.pub }));

/** The reach of « Voir », from the nearest to the whole world: the length of the geohash that names the room (8 = a cell of 38 x 19 m) and the distance it stands for. A wider reach is a wider room: only the people who joined it are seen. */
export const LEVELS = [
  { len: 8, meters: 50, label: '50 m' }, { len: 7, meters: 150, label: '150 m' }, { len: 6, meters: 1_200, label: '1 km' }, { len: 5, meters: 5_000, label: '5 km' },
  { len: 4, meters: 40_000, label: '40 km' }, { len: 3, meters: 156_000, label: '150 km' }, { len: 2, meters: 1_250_000, label: '1 250 km' }, { len: 0, meters: Infinity, label: 'Monde' },
];
/** The name of the room of a cell at a level (`world` for the whole world). */
export const roomName = (cell, level) => `voir:${LEVELS[level].len === 0 ? 'world' : cell.slice(0, LEVELS[level].len)}`;

/** The distance in metres between a position and the centre of a cell (a haversine: good to a few metres, the cell is 38 m wide). */
export function distanceTo(lat, lon, cell) {
  const b = bounds(cell), cLat = (b.latLo + b.latHi) / 2, cLon = (b.lonLo + b.lonHi) / 2, rad = Math.PI / 180;
  const dLat = (cLat - lat) * rad, dLon = (cLon - lon) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat * rad) * Math.cos(cLat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** What the two sliders keep: people within `maxMeters` (the nearest level also keeps the people of the neighbouring cells, about 50 m) and with a score of at least `minScore`. */
export function filterRows(rows, { here, maxMeters = Infinity, minScore = -Infinity }) {
  return rows.filter((e) => e.score >= minScore && (!here || maxMeters === Infinity || distanceTo(here.lat, here.lon, e.cell) <= Math.max(maxMeters, 60)));
}

/** The lowest and the highest score among the people detected (null when there is nobody). */
export function scoreRange(rows) {
  if (rows.length === 0) return null;
  const scores = rows.map((e) => e.score);
  return { min: Math.min(...scores), max: Math.max(...scores) };
}

/** An entry received: valid, signed by the key it names, fresh, links cleaned; or null. `cells` are the cells or the prefixes of the room it came from. */
export function checkEntry(entry, cells, now = Date.now()) {
  const allowed = Array.isArray(cells) ? cells : [cells];
  if (!entry || entry.v !== 1 || typeof entry.cell !== 'string' || !/^[0-9b-hjkmnp-z]{8}$/.test(entry.cell) || !allowed.some((c) => entry.cell.startsWith(c)) || typeof entry.pub !== 'string' || typeof entry.sig !== 'string') return null;
  if (typeof entry.ts !== 'number' || Math.abs(now - entry.ts) > FRESH_MS) return null;
  const links = cleanLinks(entry.links);
  const repo = typeof entry.repo === 'string' && /^[\w.-]{1,60}\/[\w.-]{1,100}$/.test(entry.repo) ? entry.repo : '';
  const score = Number.isFinite(entry.score) ? entry.score : 0, laps = Number.isFinite(entry.laps) ? entry.laps : 0;
  const clean = { v: 1, cell: entry.cell, repo, links, score, laps, ts: entry.ts, pub: entry.pub };
  if (!verifyHex(messageOf(entry), entry.sig, entry.pub)) return null;
  return { ...clean, sig: entry.sig };
}


/** A card read from a QR code or a pasted text: { repo, links }, links cleaned; or a single https link; or null. Unsigned: it is shown as « from a code », never as a ranked person. */
export function parseCard(text) {
  const raw = String(text ?? '').trim();
  if (!raw || raw.length > 1500) return null;
  if (raw.startsWith('{')) {
    try {
      const card = JSON.parse(raw);
      const links = cleanLinks(card.links);
      const repo = typeof card.repo === 'string' && /^[\w.-]{1,60}\/[\w.-]{1,100}$/.test(card.repo) ? card.repo : '';
      return links.length ? { repo, links } : null;
    } catch { return null; }
  }
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return null;
    return { repo: '', links: [{ kind: 'page', url: url.href }] };
  } catch { return null; }
}

/** The text of my QR code: my repository and my links, short. */
export const cardText = (repo, links) => JSON.stringify({ v: 1, repo, links: cleanLinks(links) });

/** « owner/name » from what a person types: two words (the GitHub name, the repository), « owner/name », or a github.com address. Null when it is not a repository. */
export function parseRepo(owner, name) {
  let o = String(owner ?? '').trim(), n = String(name ?? '').trim();
  const joined = n ? `${o}/${n}` : o;
  const m = /^(?:https?:\/\/)?(?:www\.)?(?:github\.com\/)?@?([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\/([\w.-]{1,100}?)(?:\.git)?(?:[/?#].*)?$/.exec(joined);
  return m ? `${m[1]}/${m[2]}` : null;
}

/** The public web links of the Files of a repository (the same ones the widget publishes): docs, media, app, page, contract. */
export function repoLinks(repo) {
  const [owner, name] = repo.split('/');
  const page = name.toLowerCase() === `${owner.toLowerCase()}.github.io` ? `https://${owner}.github.io/` : `https://${owner}.github.io/${name}/`;
  return [
    { kind: 'docs', url: `https://github.com/${repo}/tree/HEAD/docs` },
    { kind: 'media', url: `https://github.com/${repo}/releases/tag/videos` },
    { kind: 'app', url: `https://github.com/${repo}/releases` },
    { kind: 'page', url: page },
    { kind: 'contract', url: `https://github.com/${repo}/tree/HEAD/aiwa-apps` },
  ];
}
