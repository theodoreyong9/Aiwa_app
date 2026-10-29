// Poly Haven (polyhaven.com): everything it publishes is CC0, and it has a public API for programs (a unique User-Agent is asked for). The API lists every asset with its
// name, tags, categories, description, authors, size and polycount, and gives, for one asset, the address of each file.
export const API = 'https://api.polyhaven.com';
export const USER_AGENT = 'aiwa-asset-research (+https://github.com/theodoreyong9/Aiwa_app)';
export const KINDS = { models: 'model', hdris: 'hdri', textures: 'texture' };

const list = (v) => (Array.isArray(v) ? v : []);
const attr = (a) => Object.entries(a || {}).flatMap(([k, v]) => list(v).length ? list(v).map(String) : [String(v)]);

export function normalize(id, v, kind) {
  return {
    id: `ph-${id}`, native: id, kind, source: 'polyhaven', licence: 'cc0', name: v.name || id, page: `https://polyhaven.com/a/${id}`,
    description: String(v.description || '').slice(0, 300), tags: list(v.tags).map((t) => String(t).toLowerCase()), categories: list(v.categories).map((t) => String(t).toLowerCase()),
    attributes: attr(v.attributes).map((t) => t.toLowerCase()), authors: Object.keys(v.authors || {}), max_resolution: v.max_resolution || null,
    polycount: v.polycount ?? null, dimensions: v.dimensions ? v.dimensions.map((x) => Math.round(x)) : null, published: v.date_published ? new Date(v.date_published * 1000).toISOString().slice(0, 10) : null,
  };
}

export async function listAssets(fetchFn = fetch) {
  const rows = [];
  for (const [t, kind] of Object.entries(KINDS)) {
    const res = await fetchFn(`${API}/assets?t=${t}`, { headers: { 'User-Agent': USER_AGENT } });
    if (!res.ok) throw new Error(`${API}/assets?t=${t} answers ${res.status}`);
    const d = await res.json();
    for (const [id, v] of Object.entries(d)) rows.push(normalize(id, v, kind));
  }
  return rows;
}

// Which files to download for one asset, from the answer of /files/<id>: [{ path, url }] (path is relative to the folder of the asset).
export function pickFiles(kind, files, { res = '2k' } = {}) {
  const order = ['1k', '2k', '4k', '8k'];
  const near = (obj) => (obj && (obj[res] ? res : order.filter((r) => obj[r]).sort((a, b) => Math.abs(order.indexOf(a) - order.indexOf(res)) - Math.abs(order.indexOf(b) - order.indexOf(res)))[0]));
  if (kind === 'model') {
    const r = near(files.gltf); if (!r) throw new Error('no glTF file for this model');
    const g = files.gltf[r].gltf;
    const out = [{ path: g.url.split('/').pop(), url: g.url }];
    for (const [p, f] of Object.entries(g.include || {})) out.push({ path: p, url: f.url });
    return out;
  }
  if (kind === 'hdri') {
    const r = near(files.hdri); if (!r) throw new Error('no HDRI file');
    const f = files.hdri[r].hdr || files.hdri[r].exr; if (!f) throw new Error('no .hdr or .exr at this size');
    return [{ path: f.url.split('/').pop(), url: f.url }];
  }
  const maps = { Diffuse: 'diffuse', nor_gl: 'normal', Rough: 'roughness', Displacement: 'displacement', arm: 'arm', Metal: 'metal', AO: 'ao' };
  const out = [];
  for (const [k, name] of Object.entries(maps)) {
    const r = near(files[k]); if (!r) continue;
    const f = files[k][r].jpg || files[k][r].png; if (f) out.push({ path: `${name}.${f.url.split('.').pop()}`, url: f.url });
  }
  if (!out.length) throw new Error('no texture map found');
  return out;
}
