// Dumps the constellations engine (docs/videos/aiwa-v28/video-film.html) for the one-scene film (docs/videos/aiwa-v29/scene.py): positions of every point per frame, threads, camera moves. Run from video-kit/: node src/dump-constellations.mjs <out dir> [fps]
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
const out = process.argv[2], FPS = +(process.argv[3] || 12), PAGE = process.argv[4] || 'docs/videos/aiwa-v28/video-film.html';
mkdirSync(out, { recursive: true });
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto('file://' + (await import('node:path')).resolve(PAGE)); await p.evaluate(() => window.READY);
const meta = await p.evaluate((FPS) => {
  const units = [];
  for (let k = 0; k < NS; k++) { const gi = GOF[k]; if (gi >= 0 && k !== GR[gi].a) continue; units.push(k); }
  const U = units.map(k => { const gi = GOF[k], g = gi >= 0 ? GR[gi] : null;
    const sets = g ? PG[gi].map(a => Array.from(a)) : [Array.from(PAIRS[k])];
    const verm = []; const vf = g ? (g.sa ? (i => i % 9 === 0 || (i >= 1950 && i % 2 == 0)) : g.world ? (i => i % 9 === 0 || (i >= 1450 && i % 3 == 0)) : (i => i % 9 === 0)) : (i => i % 9 === 0);
    for (let i = 0; i < N; i++) verm.push(vf(i) ? 1 : 0);
    const sz = []; for (let i = 0; i < N; i++) sz.push(hs(i, 8));
    return { k, slot: SLOT[k], o: SCN[k].o, t0: SCN[k].t, group: gi, last: g ? g.b : k, sa: !!(g && g.sa), world: !!(g && g.world), sets, verm, sz } });
  return { N, NS, NSLOT, SLOT, GOF, YAW, TS, TRAV, scn: SCN.map(x => [x.t, x.o, x.c]), total: TOTAL, units: U, fps: FPS };
}, FPS);
writeFileSync(out + '/meta.json', JSON.stringify(meta));
const frames = Math.ceil(meta.total * FPS);
const camAll = [];
// per frame: camera and unit positions, evaluated page-side
const buf = {}; meta.units.forEach(u => buf[u.k] = []);
const vis = {};
for (let f = 0; f < frames; f++) {
  const t = f / FPS;
  const r = await p.evaluate(({ t, units }) => {
    const g0 = progress(t), k = g0.k, nx = Math.min(NS - 1, k + 1);
    const mo = moveAt(t, k, g0.u);
    const rel = kk => { const v = [P3[kk][0] - C3[kk][0], P3[kk][1] - C3[kk][1], P3[kk][2] - C3[kk][2]]; const cy = Math.cos(mo[0]), sy = Math.sin(mo[0]);
      let x = v[0] * cy + v[2] * sy, z = -v[0] * sy + v[2] * cy, y = v[1]; const cp = Math.cos(mo[1]), sp = Math.sin(mo[1]); const y2 = y * cp - z * sp, z2 = y * sp + z * cp;
      const X = x * mo[2], Y = y2 * mo[2], Z = z2 * mo[2]; const cs = Math.cos(YAW[kk]), sn = Math.sin(YAW[kk]); return [X * cs - Z * sn, Y, X * sn + Z * cs] };
    const roll = .03 * Math.sin(t * .55 + 1) + ((g0.k + 1 < NS && SLOT[g0.k + 1] !== SLOT[g0.k]) ? Math.sin(Math.PI * g0.u) * .1 * Math.sin(SLOT[g0.k] * 2.1) : 0);
    const cam = { t, k, u: g0.u, slotA: SLOT[k], slotB: SLOT[nx], relA: rel(k), relB: rel(nx), roll, mo };
    const list = [];
    for (const kk of units) {
      const gi = GOF[kk], s = SCN[kk].t; const g = gi >= 0 ? GR[gi] : null;
      const lastK = g ? g.b : kk; const nextStart = lastK + 1 < NS ? SCN[lastK + 1].t : 1e9;
      if (t < s - 1.1 || t > nextStart + 1.6) continue;
      let psi, al = 1, ia = 0, mB = 0, pa = -1, pb = -1, pos;
      pos = new Float32Array(N * 3);
      if (g) { psi = .12 * Math.sin(t * .6) + (g.sa || g.world ? t * .3 : 0); al = clamp((t - (s - .9)) / .9);
        const f2 = stageF(g, t), n = g.b - g.a; ia = Math.min(Math.floor(f2), g.sa ? 1 : g.world ? 3 : n - 1); const m = f2 - ia;
        const gp = g.sa ? saPos : g.world ? worldPos : morphPos; pa = ia; pb = m > 0 ? ia + 1 : -1; mB = sm(clamp(m));
        for (let i = 0; i < N; i++) { const q = gp(i, t, g); pos[i * 3] = q[0]; pos[i * 3 + 1] = q[1]; pos[i * 3 + 2] = q[2] } }
      else { const A = CLOUD[kk], lt = t - s; let sw = .95 * (1 - eo(clamp(lt / .9))); if (kk + 1 < NS) { const ts = TS[kk]; if (t > ts) sw = -.95 * eio(clamp((t - ts) / TRAV[kk])) } sw += .07 * Math.sin(t * .8 + kk);
        psi = sw; al = clamp((t - (s - .9)) / .9); pa = 0; pos.set(A) }
      list.push({ k: kk, psi, al, pa, pb, mB, pos: Array.from(pos) });
    }
    return { cam, list };
  }, { t, units: meta.units.map(u => u.k) });
  camAll.push(r.cam);
  for (const e of r.list) { (vis[e.k] ||= []).push({ f, psi: e.psi, al: e.al, pa: e.pa, pb: e.pb, mB: e.mB }); buf[e.k].push(Float32Array.from(e.pos)); }
}
for (const u of meta.units) { const arr = buf[u.k]; const all = new Float32Array(arr.length * meta.N * 3); arr.forEach((a, i) => all.set(a, i * meta.N * 3)); writeFileSync(`${out}/pos_${u.k}.f32`, Buffer.from(all.buffer)); }
writeFileSync(out + '/frames.json', JSON.stringify({ fps: FPS, frames, cam: camAll, vis }));
console.log('ok', frames, Object.keys(vis).map(k => k + ':' + vis[k].length).join(' '));
await b.close();
