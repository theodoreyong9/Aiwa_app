// The whole page as ONE tall picture, for the cinematic engine's "page" layer. The page is laid out in a viewport of the given width and height
// (so its vh units and its media queries are what a visitor sees), scrolled once from top to bottom to wake what appears on scroll (observers,
// lazy images), then photographed in full. A file path or an address.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export async function capturePage({ source, out, width = 1440, height = 810, executablePath = process.env.CHROMIUM_PATH || undefined }) {
  const url = /^https?:|^file:/.test(source) ? source : pathToFileURL(resolve(source)).href;
  if (!/^https?:|^file:/.test(source) && !existsSync(source)) throw new Error(`no such file: ${source}`);
  const browser = await chromium.launch({ executablePath });
  try {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForTimeout(600);
    const total = await page.evaluate(() => document.documentElement.scrollHeight);
    for (let y = 0; y < total; y += Math.floor(height * 0.6)) { await page.evaluate((v) => window.scrollTo(0, v), y); await page.waitForTimeout(120); }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    await page.screenshot({ path: out, fullPage: true });
    return { out, width, pageHeight: total, errors };
  } finally { await browser.close(); }
}
