// One visit: Playwright drives Chromium (navigation, scroll, hover, screenshots), the Chrome DevTools Protocol watches what
// the browser itself knows (network, animations, performance, console, targets). Raw observations only; detection and
// classification come after, from these.
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { INIT_SCRIPT } from './instrument.js';
import { extractFeatures } from './extract.js';
import { UA } from '../util.js';

const TYPE_OF = { Document: 'DOCUMENT', Stylesheet: 'CSS', Script: 'JS', Image: 'IMAGE', Font: 'FONT', Media: 'VIDEO', XHR: 'XHR', Fetch: 'FETCH', WebSocket: 'WEBSOCKET', Other: 'OTHER' };

/** CDP session on a page: network inventory, animations as the browser starts them, console and exceptions, metrics. */
async function attachCdp(page, context) {
  const cdp = await context.newCDPSession(page);
  const obs = { network: new Map(), animations: [], console: [], exceptions: [], failed: [], targets: [], metrics: {} };
  await cdp.send('Network.enable');
  await cdp.send('Animation.enable');
  await cdp.send('Performance.enable');
  await cdp.send('Log.enable').catch(() => {});
  cdp.on('Network.requestWillBeSent', (e) => obs.network.set(e.requestId, { url: e.request.url, method: e.request.method, type: TYPE_OF[e.type] ?? 'OTHER', initiator: e.initiator?.type ?? '' }));
  cdp.on('Network.responseReceived', (e) => { const r = obs.network.get(e.requestId); if (r) Object.assign(r, { status: e.response.status, mime: e.response.mimeType, fromCache: !!e.response.fromDiskCache }); });
  cdp.on('Network.loadingFinished', (e) => { const r = obs.network.get(e.requestId); if (r) r.bytes = e.encodedDataLength; });
  cdp.on('Network.loadingFailed', (e) => { const r = obs.network.get(e.requestId); obs.failed.push({ url: r?.url ?? '', error: e.errorText }); });
  cdp.on('Animation.animationStarted', (e) => { const a = e.animation; obs.animations.push({ type: a.type, name: a.name, duration: a.source?.duration, delay: a.source?.delay, iterations: a.source?.iterations, easing: a.source?.easing }); });
  cdp.on('Runtime.exceptionThrown', (e) => obs.exceptions.push(String(e.exceptionDetails?.exception?.description ?? e.exceptionDetails?.text ?? '').slice(0, 300)));
  cdp.on('Log.entryAdded', (e) => { if (e.entry.level === 'error' || e.entry.level === 'warning') obs.console.push({ level: e.entry.level, text: String(e.entry.text).slice(0, 200) }); });
  await cdp.send('Runtime.enable');
  return { cdp, obs };
}

async function settle(page, ms = 1500) { await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {}); await page.waitForTimeout(ms); }

async function scrollThrough(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const vh = page.viewportSize().height;
  const steps = Math.min(12, Math.ceil(height / vh));
  for (let i = 1; i <= steps; i++) { await page.mouse.wheel(0, vh * 0.9); await page.waitForTimeout(350); }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
}

/** Hovers a few obvious interactive elements and records which of them changed visibly. */
async function probeHover(page, max = 6) {
  const handles = await page.$$('a, button, [role="button"], nav *, [class*="card"], [class*="btn"]');
  const seen = [];
  for (const h of handles) {
    if (seen.length >= max) break;
    const box = await h.boundingBox().catch(() => null);
    if (!box || box.width < 20 || box.height < 12 || box.y > page.viewportSize().height * 3) continue;
    const read = () => h.evaluate((el) => { const c = getComputedStyle(el); return [c.transform, c.opacity, c.color, c.backgroundColor, c.boxShadow, c.textDecorationLine, c.filter, c.letterSpacing].join('|'); });
    const before = await read().catch(() => null);
    await h.hover({ timeout: 1500 }).catch(() => {});
    await page.waitForTimeout(450);
    const after = await read().catch(() => null);
    if (before !== null && after !== null) seen.push({ changed: before !== after, tag: await h.evaluate((el) => el.tagName.toLowerCase()).catch(() => '') });
  }
  return { probed: seen.length, changed: seen.filter((s) => s.changed).length };
}

async function observeContext(browser, url, { mobile, shotDir, wantShots, fullPage }) {
  const context = await browser.newContext(mobile
    ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: `${UA} Mobile` }
    : { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, userAgent: UA });
  const page = await context.newPage();
  await page.addInitScript(INIT_SCRIPT);
  const { cdp, obs } = await attachCdp(page, context);
  const t0 = Date.now();
  const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await settle(page);
  const status = response?.status() ?? 0;
  const shots = {};
  const shot = async (name, opts = {}) => { if (!wantShots) return; mkdirSync(shotDir, { recursive: true }); const file = `${name}.jpg`; await page.screenshot({ path: join(shotDir, file), type: 'jpeg', quality: 70, ...opts }).catch(() => {}); shots[name] = file; };
  await shot(mobile ? 'mobile' : 'desktop');
  const before = await page.evaluate(extractFeatures);
  await scrollThrough(page);
  const features = await page.evaluate(extractFeatures);
  const hover = mobile ? { probed: 0, changed: 0 } : await probeHover(page);
  if (!mobile && fullPage && process.env.DR_FULLPAGE !== '0') {
    // the whole page, but not more than 6000 px: pictures are what makes the catalogue heavy in Git
    const height = Math.min(await page.evaluate(() => document.documentElement.scrollHeight), 6000);
    await shot('fullpage', { fullPage: true, clip: { x: 0, y: 0, width: 1440, height }, timeout: 20000 });
  }
  const metrics = Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
  const timing = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; const paints = Object.fromEntries(performance.getEntriesByType('paint').map((p) => [p.name, Math.round(p.startTime)])); return { domContentLoaded: Math.round(n?.domContentLoadedEventEnd ?? 0), load: Math.round(n?.loadEventEnd ?? 0), ...paints }; });
  // the reveal on scroll: how many elements are drawn differently once the page has been scrolled through
  const frames = page.frames().length;
  const workers = page.workers().length;
  const requests = [...obs.network.values()];
  await context.close();
  return {
    mobile, status, ms: Date.now() - t0, features, featuresBeforeScroll: { elements: before.elements, canvases: before.media.canvases.length, animations: before.motion.animations, hidden: before.hiddenElements },
    scrollReveal: Math.max(0, before.hiddenElements - features.hiddenElements),
    hover, shots, performance: { metrics: { jsHeapUsedSize: metrics.JSHeapUsedSize, layoutCount: metrics.LayoutCount, recalcStyleCount: metrics.RecalcStyleCount, scriptDuration: metrics.ScriptDuration, taskDuration: metrics.TaskDuration, nodes: metrics.Nodes }, timing },
    network: requests, animationsReported: obs.animations.slice(0, 60), console: obs.console.slice(0, 20), exceptions: obs.exceptions.slice(0, 10), failed: obs.failed.slice(0, 20), targets: { frames, workers },
  };
}

/** Visits `url` on desktop and on a phone. Returns raw observations (see detection/ and classify/ for what is made of them). */
export async function crawl(url, { shotDir = null, fullPage = true, executablePath = process.env.CHROMIUM_PATH || undefined } = {}) {
  // loaded here, not at the top: reading the published catalogue (search, research) needs no browser, and a phone has none
  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ executablePath, args: ['--autoplay-policy=no-user-gesture-required'] });
  try {
    const desktop = await observeContext(browser, url, { mobile: false, shotDir, wantShots: !!shotDir, fullPage });
    const mobile = await observeContext(browser, url, { mobile: true, shotDir, wantShots: !!shotDir, fullPage: false }).catch((err) => ({ error: String(err.message ?? err) }));
    return { url, at: new Date().toISOString(), desktop, mobile };
  } finally { await browser.close(); }
}
