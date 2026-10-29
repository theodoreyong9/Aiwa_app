// Fills catalog/assets.jsonl from the Poly Haven API: three requests (models, HDRIs, textures), once a week. No file is downloaded here.
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { listAssets } from './polyhaven.js';

export const loadCatalog = (dir) => (existsSync(join(dir, 'assets.jsonl')) ? readFileSync(join(dir, 'assets.jsonl'), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
export function saveCatalog(dir, rows) {
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'assets.jsonl'), [...rows].sort((a, b) => a.kind.localeCompare(b.kind) || a.id.localeCompare(b.id)).map((r) => JSON.stringify(r)).join('\n') + '\n');
}
export async function sync({ dir, fetchFn = fetch } = {}) {
  const summary = { new: 0, errors: [] };
  try {
    const rows = await listAssets(fetchFn);
    if (rows.length < 300) throw new Error(`only ${rows.length} assets read (the API changed?), the register is left as it was`);
    const known = new Set(loadCatalog(dir).map((r) => r.id));
    summary.new = rows.filter((r) => !known.has(r.id)).length;
    saveCatalog(dir, rows);
    summary.total = rows.length;
  } catch (err) { summary.errors.push(String(err.message ?? err)); }
  return summary;
}
