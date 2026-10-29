// Turns the HTML of a campaign page of adsoftheworld.com into a record: the idea (a short excerpt of the description, with the link to the page), the
// credits (brand, agency, country, year), the kind of work (media, industry) and where the film is (a YouTube or Vimeo address: never fetched).
// Nothing here fetches anything: the page is given.
const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', rsquo: '’', lsquo: '‘', ldquo: '“', rdquo: '”', hellip: '…', ndash: '–', mdash: '—' };
const decode = (s) => s.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (m, e) => {
  if (e[0] === '#') { const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
  return ENTITIES[e.toLowerCase()] ?? m;
});

export function textOf(html) {
  const body = html.replace(/<!--[\s\S]*?-->/g, '').replace(/<(script|style|svg|noscript)[\s\S]*?<\/\1>/gi, '')
    .replace(/<(br|\/p|\/div|\/li|\/h[1-6]|\/dt|\/dd|\/tr|\/section|\/header|\/footer|\/nav|\/a)[^>]*>/gi, '\n').replace(/<[^>]+>/g, ' ');
  return decode(body).replace(/[ \t ]+/g, ' ').split('\n').map((l) => l.trim()).filter(Boolean);
}

const MEDIA = new Set(['film', 'print', 'outdoor', 'digital', 'social', 'integrated', 'design', 'audio', 'radio', 'direct', 'pr', 'ambient', 'mobile', 'experiential', 'promo', 'innovation', 'craft', 'tv', 'television', 'cinema', 'out of home', 'social media', 'branded content', 'activation', 'event', 'packaging', 'press']);
const meta = (html, key) => {
  const m = html.match(new RegExp(`<meta[^>]*(?:property|name)=['"]${key}['"][^>]*content=['"]([^'"]*)['"]`, 'i')) || html.match(new RegExp(`<meta[^>]*content=['"]([^'"]*)['"][^>]*(?:property|name)=['"]${key}['"]`, 'i'));
  return m ? decode(m[1]) : null;
};

/** At most `max` characters, cut at the end of a word, with an ellipsis when something was cut. */
export const excerpt = (s, max = 320) => (s.length <= max ? s : s.slice(0, max).replace(/\s+\S*$/, '') + '…');

export function parseCampaign(html, slug) {
  const full = meta(html, 'og:title') || (html.match(/<title>([^<]*)<\/title>/i) || [])[1] || '';
  const title = decode(full).replace(/\s*[•|]\s*Ads of the World.*$/i, '').trim();
  const colon = title.indexOf(': ');
  const lines = textOf(html);
  const at = (re) => lines.findIndex((l) => re.test(l));
  // credits
  let agency = null;
  const ia = at(/^Agency:?$/i);
  if (ia >= 0) agency = lines[ia + 1] || null;
  else { const m = lines.map((l) => l.match(/^Agency:\s*(.+)$/i)).find(Boolean); agency = m ? m[1] : null; }
  const idesc = at(/^Description$/i);
  const ifacts = at(/^This .*campaign titled/i);
  const descLines = idesc >= 0 ? lines.slice(idesc + 1, ifacts > idesc ? ifacts : idesc + 6) : [];
  const description = descLines.join(' ').trim();
  const facts = ifacts >= 0 ? lines[ifacts] : '';
  const pub = facts.match(/published in (.+?) in ([A-Z][a-z]+),? (\d{4})/);
  const kind = facts.match(/This (.+?) campaign titled/i);
  const work = facts.match(/This ((?:(?!This ).)+?) media campaign is related to the (.+?) industry and contains (\d+) media asset/i);
  const industryOnly = facts.match(/related to the (.+?) industry/i);
  const assetsOnly = facts.match(/contains (\d+) media asset/i);
  const icat = at(/^Categories$/i);
  const categories = [];
  if (icat >= 0) for (const l of lines.slice(icat + 1)) { if (/^(Share|Newer|Older)$/i.test(l)) break; categories.push(l); if (categories.length >= 14) break; }
  const ids = (re) => [...new Set([...html.matchAll(re)].map((m) => m[1]))];
  const youtube = ids(/youtube(?:-nocookie)?\.com\/embed\/([A-Za-z0-9_-]{6,})/g).concat(ids(/youtube\.com\/watch\?v=([A-Za-z0-9_-]{6,})/g)).filter((v, i, a) => a.indexOf(v) === i);
  const vimeo = ids(/player\.vimeo\.com\/video\/(\d+)/g);
  return {
    slug, url: `https://www.adsoftheworld.com/campaigns/${slug}`,
    title, brand: colon > 0 ? title.slice(0, colon) : null, campaign: colon > 0 ? title.slice(colon + 2) : title,
    agency, country: pub ? pub[1] : null, month: pub ? pub[2] : null, year: pub ? Number(pub[3]) : null,
    tier: /student campaign/i.test(facts) ? 'student' : 'professional',
    media: work ? work[1].split(/\s+and\s+|,\s*/).map((x) => x.trim()).filter(Boolean) : categories.filter((c) => MEDIA.has(c.toLowerCase())),
    industry: work ? work[2] : (industryOnly ? industryOnly[1] : null), assets: work ? Number(work[3]) : (assetsOnly ? Number(assetsOnly[1]) : null),
    facts: facts ? excerpt(facts, 420) : '',
    categories, idea: description ? excerpt(description) : null,
    video: { youtube: youtube.slice(0, 3), vimeo: vimeo.slice(0, 3) },
    image: meta(html, 'og:image'),
  };
}

const NOT_CAMPAIGNS = new Set(['new', 'latest', 'popular', 'trending', 'top', 'featured', 'highlighted', 'professional', 'student']);
/** The campaign slugs a listing page links to, in order of appearance (the section links like /campaigns/new are not campaigns). */
export function listingSlugs(html) {
  return [...new Set([...html.matchAll(/href=["']\/campaigns\/([a-z0-9][a-z0-9-]*)["']/gi)].map((m) => m[1]))].filter((s) => !NOT_CAMPAIGNS.has(s));
}
