// OpenGameArt: the listing of audio under a licence, then each track's page (title, author, licence, tags, file). Its robots.txt asks for 10 s between two
// requests and allows the content pages; only CC0 and CC BY are kept (GPL, CC BY-SA and the rest are left out).
import { energyOf, slug } from './track.js';

export const BASE = 'https://opengameart.org';
export const LICENCE_IDS = { cc0: 4, 'cc-by-4.0': 17981, 'cc-by-3.0': 2 };
export const listingPath = (licenceId, page = 0) => `/art-search-advanced?keys=&field_art_type_tid%5B%5D=12&field_art_licenses_tid%5B%5D=${licenceId}&sort_by=count&sort_order=DESC${page ? `&page=${page}` : ''}`;
export const listingSlugs = (html) => [...new Set([...html.matchAll(/href="\/content\/([^"#?\/]+)"/g)].map((m) => m[1]))].filter((s) => s !== 'faq');

const text = (s) => s.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&#039;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();
const block = (html, cls) => { const i = html.indexOf(cls); return i < 0 ? '' : html.slice(i, i + 1500); };

// The licence of a page: the best of the accepted ones it offers (CC0 first), or null.
export function pageLicence(html) {
  const label = text(block(html, 'field-name-field-art-licenses')).replace(/^.*?License\(s\):/i, '').split('Collections:')[0];
  if (/\bCC0\b/i.test(label)) return 'cc0';
  if (/CC-BY 4\.0/i.test(label)) return 'cc-by-4.0';
  if (/CC-BY 3\.0/i.test(label)) return 'cc-by-3.0';
  return null;
}

export function parseTrack(html, pageSlug) {
  const licence = pageLicence(html);
  const title = (html.match(/<title>([^<]+?)\s*\|\s*OpenGameArt/i) || [])[1];
  const files = [...html.matchAll(/<a href="(https:\/\/opengameart\.org\/sites\/default\/files\/[^"]+\.(?:mp3|ogg|wav|flac))"([^>]*)>/gi)].map((m) => [m[1], Number((m[2].match(/length=(\d+)/) || [])[1]) || null]);
  const pick = files.find(([u]) => /\.mp3$/i.test(u)) || files[0];
  const author = (html.match(/href="\/users\/([^"]+)"/) || [])[1];
  const tags = [...block(html, 'field-name-field-art-tags').matchAll(/field_art_tags_tid=[^"]*"[^>]*>([^<]+)</g)].map((m) => m[1].trim().toLowerCase());
  const body = text(block(html, 'field-name-body').replace(/^[^>]*>/, '')).slice(0, 280);
  if (!licence || !title || !pick) return null;
  return {
    id: `oga-${slug(pageSlug)}`, title: text(title), artist: decodeURIComponent(author || 'unknown'), source: 'opengameart', licence, page: `${BASE}/content/${pageSlug}`,
    file: pick[0], bytes: pick[1], seconds: null, bpm: null, bpm_basis: null, tags, instruments: [], description: body,
    energy: energyOf(tags, null), energy_basis: 'tags',
  };
}
