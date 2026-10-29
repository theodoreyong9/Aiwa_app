// Draws the overlay (labels that follow the objects, title cards) as transparent PNG frames, at the size of the final film.
//   node render_overlay.cjs OUT_DIR FPS WIDTH HEIGHT WORKERS      (the little web server of the film must run on 8123, see render3.cjs)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [out, fpsA, wA, hA, wk, framesA, anchorsA] = process.argv.slice(2);
  const fps = +fpsA, W = +wA, H = +hA, workers = +wk, total = +(framesA || Math.round(67 * fps));
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch();
  const chunk = Math.ceil(total / workers);
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const a = w * chunk, e = Math.min(total, a + chunk); if (a >= e) return;
    const p = await b.newPage({ viewport: { width: W, height: H } }); const errs = [];
    p.on('pageerror', x => errs.push(String(x)));
    await p.goto(`http://127.0.0.1:8123/overlay.built.html?a=${anchorsA || '/anchors_main.json'}&w=${W}&h=${H}`); await p.waitForFunction('typeof window.render==="function"');
    for (let i = a; i < e; i++) {
      const f = `${out}/${String(i).padStart(5, '0')}.png`;
      if (fs.existsSync(f) && fs.statSync(f).size > 100) continue;
      await p.evaluate(t => window.render(t), i / fps); await p.screenshot({ path: f, type: 'png', omitBackground: true });
    }
    if (errs.length) console.log('errors', errs.slice(0, 3));
  }));
  await b.close(); console.log('done');
})();
