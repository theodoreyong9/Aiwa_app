// Renders the frames of one page of the screens (ui10.built.html, served over http by the folder of the film) : node render_ui10.js <mode> <w> <h> <t0> <t1> <outdir> [part count]
const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [mode, w, h, t0, t1, out, part = 0, count = 1] = process.argv.slice(2); const fps = 24;
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] }); const p = await b.newPage({ viewport: { width: +w, height: +h } });
  p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto(`http://127.0.0.1:${process.env.PORT || 8099}/ui/ui10.built.html?m=${mode}&bg=/bgframes`);
  await p.waitForFunction(() => typeof window.render === 'function');
  const a = Math.round(+t0 * fps), z = Math.round(+t1 * fps);
  for (let i = a; i < z; i++) {
    if (i % +count !== +part) continue;
    await p.evaluate(t => window.render(t), i / fps);
    await p.screenshot({ path: `${out}/${String(i).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 93 });
  }
  if (mode === 'p3') fs.writeFileSync(`${out}/../p3rect.json`, JSON.stringify(await p.evaluate(() => window.__frameRect)));
  await b.close();
})();
