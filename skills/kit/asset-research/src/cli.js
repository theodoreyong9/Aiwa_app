#!/usr/bin/env node
// asset-research search "<what is needed>" [--kind=model|hdri|texture --max-poly=50000 --min-res=2048 --limit=6]
// asset-research fetch <id> <out-dir> [--res=2k]      downloads that one asset (from Poly Haven, else from the release `assets` of this repository, made on request)
// asset-research stats | sync
// The register is read from catalog/assets.jsonl, or from AR_CATALOG_URL (the raw address of that file) when the repository is not cloned.
import { mkdirSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { search, stats } from './search.js';
import { loadCatalog, sync } from './sync.js';
import { API, USER_AGENT, pickFiles } from './polyhaven.js';

const MIRROR = 'https://github.com/theodoreyong9/Aiwa_store/releases/download/assets';
const dir = join(dirname(fileURLToPath(import.meta.url)), '..', 'catalog');
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const [command, a, b] = args.filter((x) => !x.startsWith('--'));
const rows = async () => {
  if (process.env.AR_CATALOG_URL) { const res = await fetch(process.env.AR_CATALOG_URL); if (!res.ok) throw new Error(`register not readable (${res.status})`); return (await res.text()).split('\n').filter(Boolean).map((l) => JSON.parse(l)); }
  return loadCatalog(dir);
};
const get = async (url) => { const res = await fetch(url, { headers: { 'User-Agent': USER_AGENT }, redirect: 'follow' }); if (!res.ok) throw new Error(`${url} answers ${res.status}`); return res; };

try {
  if (command === 'search') console.log(JSON.stringify(search(await rows(), a || '', { kind: flags.kind || null, maxPolycount: flags['max-poly'] ? Number(flags['max-poly']) : null, minResolution: flags['min-res'] ? Number(flags['min-res']) : null, limit: Number(flags.limit || 6) }), null, 1));
  else if (command === 'fetch') {
    const r = (await rows()).find((x) => x.id === a);
    if (!r) throw new Error(`no asset ${a}`);
    mkdirSync(b, { recursive: true });
    let wrote = 0, failure = '';
    try {
      const files = pickFiles(r.kind, await (await get(`${API}/files/${r.native}`)).json(), { res: flags.res || '2k' });
      for (const f of files) { const out = join(b, f.path); mkdirSync(dirname(out), { recursive: true }); writeFileSync(out, Buffer.from(await (await get(f.url)).arrayBuffer())); wrote++; }
    } catch (err) {
      failure = String(err.message ?? err);
      if (process.env.AR_NO_MIRROR) throw err;
      // the copy in the release `assets`: one zip per asset
      try { const zip = join(b, `${r.id}.zip`); writeFileSync(zip, Buffer.from(await (await get(`${MIRROR}/${r.id}.zip`)).arrayBuffer())); const un = spawnSync('unzip', ['-qo', zip, '-d', b]).status === 0 || spawnSync('python3', ['-c', 'import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])', zip, b]).status === 0;
        if (!un) throw new Error(`${zip} is downloaded but cannot be unzipped here (unzip or python3 are missing)`);
        rmSync(zip); wrote = readdirSync(b).length; console.error('from the release (the copy made on request), unzipped'); }
      catch (err2) { throw new Error(`${failure}; the copy ${MIRROR}/${r.id}.zip: ${err2.message}. The source cannot be reached from here: say so and use a shape made in the shot instead`); }
    }
    console.log(JSON.stringify({ id: r.id, name: r.name, kind: r.kind, out: b, files: wrote, licence: 'CC0 (no credit asked; a line « Poly Haven » is appreciated)', page: r.page }));
  } else if (command === 'stats') console.log(JSON.stringify(stats(await rows()), null, 1));
  else if (command === 'sync') console.log(JSON.stringify(await sync({ dir })));
  else console.log('asset-research search | fetch | stats | sync (see the header of src/cli.js)');
} catch (err) { console.error(String(err.message ?? err)); process.exit(2); }
