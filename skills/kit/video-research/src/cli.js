#!/usr/bin/env node
// video-research sync [--max=40]                        read new campaigns of Ads of the World, politely, into catalog/campaigns.jsonl
// video-research research "<brief>" [--limit=8 --industry=… --medium=…]   the campaigns closest to a brief (ideas, credits, links)
// video-research stats                                  what the catalogue holds
// VR_CATALOG_URL: where to read campaigns.jsonl when there is no local copy (a session that did not clone the repository).
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
import { sync, loadCatalog } from './sync.js';
import { research, stats } from './research.js';

const here = dirname(fileURLToPath(import.meta.url));
const dir = process.env.VR_CATALOG_DIR || join(here, '..', 'catalog');
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const [command, brief] = args.filter((a) => !a.startsWith('--'));

async function rows() {
  const local = loadCatalog(dir);
  if (local.length || !process.env.VR_CATALOG_URL) return local;
  const res = await fetch(process.env.VR_CATALOG_URL);
  if (!res.ok) throw new Error(`the catalogue answers ${res.status}`);
  return (await res.text()).split('\n').filter(Boolean).map((l) => JSON.parse(l));
}

try {
  if (command === 'sync') console.log(JSON.stringify(await sync({ dir, max: Number(flags.max ?? 40), log: (m) => console.error(m) }), null, 1));
  else if (command === 'research') {
    const found = research(await rows(), brief || '', { limit: Number(flags.limit ?? 8), industry: flags.industry || null, medium: flags.medium || null });
    const out = join(process.cwd(), '.video-research', 'latest'); mkdirSync(out, { recursive: true });
    writeFileSync(join(out, 'campaigns.json'), JSON.stringify(found, null, 1));
    writeFileSync(join(out, 'campaigns.md'), found.map((c) => `## ${c.title}\n${c.brand ?? ''} · ${c.agency ?? ''} · ${c.country ?? ''} ${c.year ?? ''} · ${(c.media || []).join(', ')} · ${c.industry ?? ''}\n\n${c.idea ?? ''}\n\n${c.page}${c.film ? '\n' + c.film : ''}\n`).join('\n'));
    console.log(JSON.stringify({ campaigns: found.length, files: ['.video-research/latest/campaigns.md', '.video-research/latest/campaigns.json'], first: found.slice(0, 3).map((c) => c.title) }, null, 1));
  } else if (command === 'stats') console.log(JSON.stringify(stats(await rows()), null, 1));
  else console.log('video-research sync | research "<brief>" | stats (see the header of src/cli.js)');
} catch (err) { console.error(String(err.message ?? err)); process.exit(2); }
