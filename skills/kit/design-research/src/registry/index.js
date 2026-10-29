// The two registries of V1: Awwwards and CSS Winner (Site of the Day). Each yields { name, url, registry, award, page, date }.
// The parsers read the public listing pages and each project's page; they are written for the markup as known and were
// NOT run against the live sites when written (no network where they were written). `doctor` and the health workflow
// say when a parser finds nothing, which is what a markup change looks like.
import { politeFetch, renderPage } from '../util.js';

const hrefs = (html, re) => [...new Set([...html.matchAll(re)].map((m) => m[1]))];
const meta = (html, prop) => (new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]+content=["']([^"']*)["']`, 'i').exec(html)
  || new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]+(?:property|name)=["']${prop}["']`, 'i').exec(html))?.[1];
const decode = (s) => (s ?? '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').trim();

export const registries = {
  awwwards: {
    award: 'SOTD',
    listings: (page = 1) => [`https://www.awwwards.com/websites/sites_of_the_day/?page=${page}`],
    projectLinks: (html) => hrefs(html, /href=["'](?:https:\/\/www\.awwwards\.com)?(\/sites\/[a-z0-9][a-z0-9-]*)["']/gi),
    projectUrl: (path) => `https://www.awwwards.com${path}`,
    // the project page links out to the site; the outbound link carries awwwards in its utm parameters
    parseProject(html) {
      const out = hrefs(html, /href=["'](https?:\/\/[^"']+)["'][^>]*>\s*(?:<[^>]+>\s*)*(?:Visit|Visiter)/gi)[0]
        ?? hrefs(html, /href=["'](https?:\/\/(?!(?:www\.)?awwwards\.com)[^"']*utm_source=awwwards[^"']*)["']/gi)[0];
      return { url: out && decode(out), title: decode(meta(html, 'og:title')?.replace(/\s*[-|–].*awwwards.*$/i, '')) };
    },
  },
  csswinner: {
    award: 'SOTD',
    // its listing is drawn by JavaScript: the plain HTML holds no project link, so the listing is read in Chromium
    rendered: true,
    // the listing address was a guess that gave a 404: several are tried, and what the first page shows is kept when none works
    listings: (page = 1) => ['https://www.csswinner.com/winners/', 'https://www.csswinner.com/'].map((u) => (page > 1 ? `${u}page/${page}/` : u)),
    projectLinks: (html) => hrefs(html, /href=["'](?:https:\/\/www\.csswinner\.com)?(\/details\/[a-z0-9][a-z0-9-]*\/\d+)\/?["']/gi),
    projectUrl: (path) => `https://www.csswinner.com${path}`,
    parseProject(html) {
      // the page links its own social accounts first, then the site (seen on the live pages): the first outbound link that is not a social or share link
      const social = /^https?:\/\/(?:[a-z0-9-]+\.)*(?:csswinner\.com|twitter\.com|x\.com|facebook\.com|pinterest\.com|instagram\.com|linkedin\.com|youtube\.com|dribbble\.com|behance\.net|github\.com|webflow\.com|google\.com|gmpg\.org|w3\.org)(?:[/?#]|$)/i;
      const out = hrefs(html, /href=["'](https?:\/\/(?!(?:www\.)?csswinner\.com)[^"']+)["'][^>]*>\s*(?:<[^>]+>\s*)*(?:Visit|Visiter|Launch)/gi)[0]
        ?? hrefs(html, /href=["'](https?:\/\/[^"']+)["']/gi).find((h) => !social.test(h));
      return { url: out && decode(out), title: decode(meta(html, 'og:title')?.replace(/\s*[-|–].*css\s*winner.*$/i, '')) };
    },
  },
};

/** Discovers up to `limit` recent projects of a registry. Returns { found, errors }. */
export async function discover(name, { limit = 30, pages = 2, fetchFn = fetch, delayMs = 1500, render = false } = {}) {
  const registry = registries[name];
  if (!registry) throw new Error(`unknown registry: ${name}`);
  const found = [];
  const errors = [];
  const paths = [];
  for (let page = 1; page <= pages && paths.length < limit; page++) {
    try {
      let got = 0;
      for (const url of registry.listings(page)) {
        try {
          const html = registry.rendered && render ? await renderPage(url, { fetchFn, delayMs }) : await politeFetch(url, { fetchFn, delayMs });
          const links = registry.projectLinks(html);
          for (const p of links) if (!paths.includes(p)) paths.push(p);
          if (links.length) { got = links.length; break; }
          errors.push(`${url}: reachable but no project link; project-looking links: ${hrefs(html, /href=["']((?:https:\/\/www\.csswinner\.com)?\/[^"'#]*[a-z0-9-]{3,}[^"'#]*)["']/gi).filter((h) => !/\.(css|js|png|ico|svg)/.test(h)).slice(0, 30).join(' ')}; page size ${html.length}; title: ${decode(/<title[^>]*>([^<]*)/i.exec(html)?.[1] ?? '')}; ${(html.match(/<a[\s>]/gi) ?? []).length} anchors; site paths: ${hrefs(html, /href=["'](?:https?:\/\/www\.csswinner\.com)?(\/[^"'#?]+)["']/gi).slice(0, 70).join(' ')}; text: ${html.replace(/<(script|style)[\s\S]*?<\/\1>/gi, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 200)}`);
        } catch (err) { errors.push(String(err.message ?? err)); }
      }
      if (!got) break;
    } catch (err) { errors.push(String(err.message ?? err)); break; }
  }
  for (const path of paths.slice(0, limit)) {
    try {
      const page = registry.projectUrl(path);
      let parsed = registry.parseProject(await politeFetch(page, { fetchFn, delayMs }));
      // the outbound link may be drawn by JavaScript too: one more try in Chromium
      if (!parsed.url && registry.rendered && render) parsed = registry.parseProject(await renderPage(page, { fetchFn, delayMs }));
      if (parsed.url) found.push({ registry: name, award: registry.award, page, url: parsed.url, title: parsed.title || '' });
      else errors.push(`${page}: no outbound link found; external hrefs: ${hrefs(await politeFetch(page, { fetchFn, delayMs }), /href=["'](https?:\/\/(?!(?:www\.|cdn\.)?csswinner\.com)[^"']+)["']/gi).slice(0, 12).join(' ')}`);
    } catch (err) { errors.push(String(err.message ?? err)); }
  }
  return { found, errors };
}
