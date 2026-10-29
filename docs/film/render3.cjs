// Renders the 3D page frame by frame (needs the little web server of the film: python3 -m http.server 8123 in the folder that holds three/, ph/, tv/, fonts/, timeline.json, scene.html).
//   node render3.cjs OUT_DIR FPS WIDTH HEIGHT WORKERS [FROM TO]     resumable: frames already on disk are kept
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [out, fpsA, wA, hA, wk, fromA, toA] = process.argv.slice(2);
  const fps = +fpsA, W = +wA, H = +hA, workers = +wk, total = Math.round(67 * fps);
  const from = +(fromA || 0), to = Math.min(total, +(toA || total));
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const chunk = Math.ceil((to - from) / workers);
  const open = async () => { const p = await b.newPage({ viewport: { width: W, height: H } }); await p.goto(`http://127.0.0.1:8123/scene.html?w=${W}&h=${H}`); await p.waitForFunction('window.READY===true', null, { timeout: 90000 }); return p };
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const a = from + w * chunk, e = Math.min(to, a + chunk); if (a >= e) return;
    let p = await open();
    for (let i = a; i < e; i++) {
      const f = `${out}/${String(i).padStart(5, '0')}.jpg`;
      if (fs.existsSync(f) && fs.statSync(f).size > 2000) continue;
      for (let tr = 1; ; tr++) { try { await p.evaluate(t => window.render(t), i / fps); await p.screenshot({ path: f, type: 'jpeg', quality: 90 }); break } catch (er) { if (tr >= 4) throw er; try { await p.close() } catch {} p = await open() } }
    }
    await p.close();
  }));
  await b.close(); console.log('done');
})();
