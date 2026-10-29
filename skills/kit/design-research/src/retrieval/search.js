// Filter, then rank. Structured filtering first (the format must be able to use the reference, the crawl must have
// worked), then a score that adds the measured traits the brief asked for and a small text match. Every result says
// which traits matched, so a reference is never a black-box pick.
import { plan } from './plan.js';

const textOf = (site) => [site.title, site.description, site.id, ...(site.tech ?? []).map((t) => t.name)].join(' ').toLowerCase();

export function search(sites, brief, { format, limit = 5 } = {}) {
  const p = plan(brief, { format });
  const candidates = sites.filter((s) => s.crawl?.status === 'ok' && s.traits && s.transposable);
  const filtered = candidates.filter((s) => s.transposable[p.format]?.verdict !== 'no');
  const scored = filtered.map((site) => {
    let score = 0;
    const matched = [];
    for (const w of p.wanted) {
      if ((site.traits[w.dimension] ?? []).includes(w.trait)) { score += w.weight * (0.5 + p.dimensions[w.dimension] / 2); matched.push(`${w.dimension}:${w.trait}`); }
    }
    const text = textOf(site);
    const hits = p.words.filter((word) => text.includes(word)).length;
    score += Math.min(0.5, hits * 0.1);
    if (site.transposable[p.format]?.verdict === 'yes') score += 0.2;
    if (site.sources?.length > 1) score += 0.15;                    // listed by both registries
    score -= (site.health?.exceptions ?? 0) > 3 ? 0.3 : 0;          // broken pages are poor references
    return { site, score: Math.round(score * 100) / 100, matched };
  }).filter((r) => r.score > 0).sort((a, b) => b.score - a.score || a.site.id.localeCompare(b.site.id));
  return { plan: p, considered: { catalog: sites.length, crawled: candidates.length, usable_for_format: filtered.length }, results: scored.slice(0, limit) };
}
