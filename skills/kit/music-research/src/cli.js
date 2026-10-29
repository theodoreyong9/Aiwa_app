#!/usr/bin/env node
// music-research search "<brief>" [--credit=ok|none --bpm=100-130 --energy=4 --min=20 --max=120 --source=incompetech|opengameart --limit=5]
// music-research credit <id>                       the credit line to show (or "none")
// music-research fetch <id> <out-file>             downloads that one track (from its source, else from the release `music`) and prints its credit
// music-research stats | sync --source=incompetech|opengameart [--max=30 --pages=2]
// The register is read from catalog/tracks.jsonl, or from MR_CATALOG_URL (the raw address of that file) when the repository is not cloned.
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { creditLine, sourceLine, usable } from './track.js';
import { search, stats } from './search.js';
import { loadCatalog, syncIncompetech, syncOga, USER_AGENT } from './sync.js';

const MIRROR = 'https://github.com/theodoreyong9/Aiwa_store/releases/download/music';
const dir = join(dirname(fileURLToPath(import.meta.url)), '..', 'catalog');
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const [command, a, b] = args.filter((x) => !x.startsWith('--'));

async function rows() {
  if (process.env.MR_CATALOG_URL) {
    const res = await fetch(process.env.MR_CATALOG_URL);
    if (!res.ok) throw new Error(`register not readable (${res.status})`);
    return (await res.text()).split('\n').filter(Boolean).map((l) => JSON.parse(l));
  }
  return loadCatalog(dir);
}
const range = (v) => (v ? v.split('-').map(Number).slice(0, 2) : null);

try {
  if (command === 'search') {
    const found = search(await rows(), a || '', { credit: flags.credit || 'ok', bpm: range(flags.bpm), energy: flags.energy ? Number(flags.energy) : null, minSeconds: flags.min ? Number(flags.min) : null, maxSeconds: flags.max ? Number(flags.max) : null, source: flags.source || null, limit: Number(flags.limit || 5) });
    console.log(JSON.stringify(found, null, 1));
  } else if (command === 'credit') {
    const t = (await rows()).find((r) => r.id === a);
    if (!t) throw new Error(`no track ${a}`);
    console.log(creditLine(t) ?? 'none');
  } else if (command === 'fetch') {
    const t = (await rows()).find((r) => r.id === a);
    if (!t || !usable(t.licence)) throw new Error(`no usable track ${a}`);
    // the source first, then the copy in the release `music` of this repository (made on request by the "Music mirror" workflow), unless MR_NO_MIRROR is set
    const tries = [t.file, ...(process.env.MR_NO_MIRROR ? [] : [`${MIRROR}/${t.id}.mp3`])];
    let buf = null, failure = '';
    for (const url of tries) {
      try {
        const res = await fetch(url, { headers: { 'User-Agent': USER_AGENT }, redirect: 'follow' });
        if (!res.ok) { failure += `${url} answers ${res.status}; `; continue; }
        const got = Buffer.from(await res.arrayBuffer());
        if (got.length < 50000) { failure += `${url}: only ${got.length} bytes; `; continue; }
        buf = got; break;
      } catch (err) { failure += `${url}: ${err.message}; `; }
    }
    if (!buf) throw new Error(`${failure}the track cannot be reached from here: say so, and take another track or the generated bed (beat.py)`);
    writeFileSync(b, buf);
    console.log(JSON.stringify({ id: t.id, out: b, bytes: buf.length, credit: creditLine(t), source: sourceLine(t) }));
  } else if (command === 'stats') console.log(JSON.stringify(stats(await rows()), null, 1));
  else if (command === 'sync') {
    const r = flags.source === 'opengameart' ? await syncOga({ dir, max: Number(flags.max || 30), pages: Number(flags.pages || 2) }) : await syncIncompetech({ dir });
    console.log(JSON.stringify(r));
  } else console.log('music-research search | credit | fetch | stats | sync (see the header of src/cli.js)');
} catch (err) { console.error(String(err.message ?? err)); process.exit(2); }
