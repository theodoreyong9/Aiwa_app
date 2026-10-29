// The research pack for Claude Code: structured references, the patterns the references share, the measured ranges, the
// screenshots. The synthesis is a table of what was MEASURED across references; what it means for the brief is left to
// the reader of the pack, who has the pictures.
import { mkdirSync, copyFileSync, existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const count = (lists) => { const m = new Map(); for (const l of lists) for (const t of new Set(l)) m.set(t, (m.get(t) ?? 0) + 1); return [...m.entries()].sort((a, b) => b[1] - a[1]); };
const range = (xs) => xs.length ? [Math.min(...xs), Math.max(...xs)] : null;

export function sharedPatterns(refs) {
  const dims = ['typography', 'composition', 'motion', 'interaction', 'rendering', 'palette'];
  const out = {};
  for (const d of dims) out[d] = count(refs.map((r) => r.traits[d] ?? [])).filter(([, n]) => n >= Math.min(2, refs.length)).map(([trait, n]) => ({ trait, in: `${n}/${refs.length}` }));
  return out;
}

export async function buildPack(result, brief, { outDir, catalogDir, format, shotsUrl = null, fetchFn = fetch }) {
  mkdirSync(join(outDir, 'screenshots'), { recursive: true });
  const refs = [];
  for (const { site, score, matched } of result.results) {
    const shots = {};
    for (const [kind, set] of Object.entries(site.screenshots ?? {})) for (const file of Object.values(set ?? {})) {
      const from = join(catalogDir, '..', 'screenshots', site.id, file);
      const name = `${site.id}-${kind}-${file}`;
      if (existsSync(from)) { copyFileSync(from, join(outDir, 'screenshots', name)); (shots[kind] ??= []).push(`screenshots/${name}`); }
      else if (shotsUrl) {
        try { const res = await fetchFn(`${shotsUrl.replace(/\/$/, '')}/${site.id}/${file}`); if (res.ok) { writeFileSync(join(outDir, 'screenshots', name), Buffer.from(await res.arrayBuffer())); (shots[kind] ??= []).push(`screenshots/${name}`); } } catch { /* the pack works without the picture */ }
      }
    }
    refs.push({
      id: site.id, url: site.url, title: site.title, score, matched, sources: site.sources, traits: site.traits, tokens: site.tokens,
      technology: site.tech.map((t) => ({ name: t.name, status: t.status, confidence: t.confidence, evidence: t.evidence })), transposable_to_format: site.transposable[format], needs_interpretation: site.needs_interpretation,
      health: site.health, responsive: site.responsive, screenshots: shots,
    });
  }
  const tokens = {
    max_font_size_px: range(refs.map((r) => r.tokens.typography.sizeMax)),
    transition_ms: range(refs.flatMap((r) => r.tokens.motion.transitionsMs)),
    mean_saturation: range(refs.map((r) => r.tokens.color.saturation)),
  };
  const shared = sharedPatterns(refs);
  writeFileSync(join(outDir, 'query.json'), JSON.stringify({ brief, format, plan: result.plan, considered: result.considered, at: new Date().toISOString() }, null, 2) + '\n');
  writeFileSync(join(outDir, 'references.json'), JSON.stringify({ references: refs, shared_patterns: shared, measured_ranges: tokens }, null, 2) + '\n');
  const lines = [
    `# Research pack`, '', `Brief: ${brief}`, `Format: ${format}`, '',
    `${refs.length} references out of ${result.considered.catalog} in the catalogue (${result.considered.crawled} crawled, ${result.considered.usable_for_format} usable for ${format}).`, '',
    '## What the references share (measured)', '',
    ...Object.entries(shared).flatMap(([d, list]) => list.length ? [`- **${d}**: ${list.map((p) => `${p.trait} (${p.in})`).join(', ')}`] : []), '',
    '## Measured ranges', '', `- largest text: ${tokens.max_font_size_px ? tokens.max_font_size_px.join(' to ') + ' px' : 'n/a'}`, `- transition durations: ${tokens.transition_ms ? tokens.transition_ms.join(' to ') + ' ms' : 'n/a'}`, '',
    '## References', '',
    ...refs.map((r) => `- **${r.title || r.id}** (${r.url}) score ${r.score}; matched ${r.matched.join(', ') || 'text only'}; for ${format}: ${r.transposable_to_format?.verdict} (${r.transposable_to_format?.reason})`), '',
    '## How to use this', '',
    '- Look at the screenshots; the traits are measurements, not taste. `needs_interpretation` lists what only a look can say (art direction, tone, why it works).',
    '- Take patterns shared by several references. Do not copy any site\'s identity, layout, content, assets or distinctive implementation.',
    `- Respect the format: for ${format}, the "transposable" verdict says what fits (a single HTML file of 512 KB or less rules out a 3D scene).`, '',
  ];
  writeFileSync(join(outDir, 'synthesis.md'), lines.join('\n'));
  return { refs, shared, tokens };
}
