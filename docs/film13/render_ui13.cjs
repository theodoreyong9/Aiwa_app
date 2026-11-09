// Renders the frames of the film (ui13.built.html over http). The real profile page (a WebGL liquid) is drawn with a clock of our own: its animation callbacks run only when this script says so, one tick per frame.
//   node render_ui13.cjs <t0> <t1> <outdir>
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [t0, t1, out] = process.argv.slice(2); const fps = 24; fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } });
  await ctx.addInitScript(() => { let vt = 0, q = []; performance.now = () => vt; window.requestAnimationFrame = cb => { q.push(cb); return q.length; }; window.cancelAnimationFrame = () => {};
    window.__tick = ms => { vt += ms; const cbs = q; q = []; cbs.forEach(cb => { try { cb(vt); } catch (e) {} }); }; });
  const p = await ctx.newPage(); p.on('pageerror', e => console.log('ERR', e.message));
  const tick = ms => p.evaluate(ms => { window.__tick && window.__tick(ms); document.querySelectorAll('iframe').forEach(f => { try { f.contentWindow.__tick && f.contentWindow.__tick(ms); } catch (e) {} }); }, ms);
  await p.goto(`http://127.0.0.1:${process.env.PORT || 8099}/ui13/${process.env.PAGE || 'ui13.built.html'}`);
  await p.waitForFunction(() => typeof window.render === 'function');
  const a = Math.round(+t0 * fps), z = Math.round(+t1 * fps);
  await p.evaluate(t => window.render(t), a / fps);
  for (let k = 0; k < 120; k++) await tick(1000 / fps);
  for (let i = a; i < z; i++) {
    await p.evaluate(t => window.render(t), i / fps); await tick(1000 / fps);
    await p.screenshot({ path: `${out}/${String(i).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 93 });
  }
  await b.close();
})();
