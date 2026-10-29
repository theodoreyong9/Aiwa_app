import { chromium } from 'playwright';
const [page, outPrefix, ...ts] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()) });
await p.goto('file://' + page); await p.waitForFunction(() => typeof window.render === 'function'); await p.evaluate(() => window.READY);
for (const t of ts) { await p.evaluate(t => window.render(t), Number(t)); await p.screenshot({ path: `${outPrefix}_${t}.jpg`, type: 'jpeg', quality: 85 }); }
console.log('errors:', errs.slice(0, 5).join(' | ') || 'none');
await b.close();
