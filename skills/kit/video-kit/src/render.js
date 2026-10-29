// Renders a timeline page frame by frame. With `transparent`, PNG files with an alpha channel (the page must have a transparent background: THEME.bg 'transparent', grain 0, vignette 0), to be laid over a real footage. The page defines window.render(t) (t in seconds, a pure function of t: the same t draws the
// same picture) and a <meta name="duration"> is not needed: the caller says how long. Frames are JPEG files 00000.jpg, 00001.jpg, …
import { chromium } from 'playwright';
const GL_ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];   // WebGL pages (shader worlds) render in software where there is no GPU
import { mkdirSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export async function renderFrames({ page: pageFile, outDir, width = 1080, height = 1920, fps = 30, seconds, quality = 90, workers = 4, from = 0, to, transparent = false, executablePath = process.env.CHROMIUM_PATH || undefined }) {
  if (!(seconds > 0)) throw new Error('seconds must be positive');
  mkdirSync(outDir, { recursive: true });
  const total = Math.round(seconds * fps);
  const end = to ?? total;
  const browser = await chromium.launch({ executablePath, args: GL_ARGS });
  try {
    const [file, query] = String(pageFile).split('?');                 // video.html?overlay=1: the page may take a query
    const url = pathToFileURL(resolve(file)).href + (query ? `?${query}` : '');
    const chunk = Math.ceil((end - from) / workers);
    await Promise.all(Array.from({ length: workers }, async (_, w) => {
      const a = from + w * chunk, b = Math.min(end, a + chunk);
      if (a >= b) return;
      const errors = [];
      // a page that runs for thousands of frames can lose its renderer (memory): it is opened again and the frame is retried; frames already on disk are kept, so a run can resume
      const open = async () => {
        const pg = await browser.newPage({ viewport: { width, height } });
        pg.on('pageerror', (e) => errors.push(e.message));
        await pg.goto(url);
        await pg.waitForFunction(() => typeof window.render === 'function', null, { timeout: 15000 });
        await pg.evaluate(() => window.READY || null);       // a page that loads pictures, fonts or frames says when it is ready
        await pg.waitForTimeout(500);
        return pg;
      };
      let page = await open();
      if (w === 0) { const meta = await page.evaluate(() => ({ cuts: window.CUTS || [], total: window.TOTAL_SECONDS || null })); writeFileSync(`${outDir}/cuts.json`, JSON.stringify(meta)); }
      for (let i = a; i < b; i++) {
        const file = `${outDir}/${String(i).padStart(5, '0')}.${transparent ? 'png' : 'jpg'}`;
        if (existsSync(file) && statSync(file).size > 2000) continue;
        for (let tries = 1; ; tries++) {
          try {
            await page.evaluate((t) => window.render(t), i / fps);
            await (transparent ? page.screenshot({ path: file, type: 'png', omitBackground: true }) : page.screenshot({ path: file, type: 'jpeg', quality }));
            break;
          } catch (e) {
            if (tries >= 4) throw e;
            try { await page.close(); } catch {}
            page = await open();
          }
        }
      }
      await page.close();
      if (errors.length) throw new Error(`the page raised: ${errors[0]}`);
    }));
  } finally { await browser.close(); }
  return { frames: end - from, fps, width, height };
}
