// Renders the frames of one page of the screens (ui12.built.html, served over http by the folder of the film). The pages that hold the real profile page (a WebGL liquid that draws itself in requestAnimationFrame)
// are drawn with a clock of our own: the animation frame callbacks run only when this script says so (one tick = one frame of the film), so the liquid moves smoothly and the same way at every run.
//   node render_ui12.cjs <mode> <w> <h> <t0> <t1> <outdir>        (PNG=1: a transparent PNG)
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [mode, w, h, t0, t1, out] = process.argv.slice(2); const fps = 24; const live = ['s3', 's5b', 's5c'].includes(mode);
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await b.newContext({ viewport: { width: +w, height: +h } });
  if (live) await ctx.addInitScript(() => { let vt = 0, q = []; performance.now = () => vt; window.requestAnimationFrame = cb => { q.push(cb); return q.length; }; window.cancelAnimationFrame = () => {};
    window.__tick = ms => { vt += ms; const cbs = q; q = []; cbs.forEach(cb => { try { cb(vt); } catch (e) {} }); }; });
  const p = await ctx.newPage();
  p.on('pageerror', e => console.log('ERR', e.message));
  const tick = ms => p.evaluate(ms => { window.__tick && window.__tick(ms); document.querySelectorAll('iframe').forEach(f => { try { f.contentWindow.__tick && f.contentWindow.__tick(ms); } catch (e) {} }); }, ms);
  await p.goto(`http://127.0.0.1:${process.env.PORT || 8099}/ui12/ui12.built.html?m=${mode}`);
  await p.waitForFunction(() => typeof window.render === 'function');
  const a = Math.round(+t0 * fps), z = Math.round(+t1 * fps);
  await p.evaluate(t => window.render(t), a / fps);                       // the first picture builds the frames of the real page
  if (live) for (let k = 0; k < 120; k++) await tick(1000 / fps);          // and the liquid settles
  for (let i = a; i < z; i++) {
    await p.evaluate(t => window.render(t), i / fps);
    if (live) await tick(1000 / fps);
    if (process.env.PNG) await p.screenshot({ path: `${out}/${String(i).padStart(5, '0')}.png`, type: 'png', omitBackground: true }); else await p.screenshot({ path: `${out}/${String(i).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 93 });
  }
  await b.close();
})();
