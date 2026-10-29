// Small shared helpers: canonical site ids, JSONL files, a polite fetch with a robots.txt check.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export const UA = 'aiwa-design-research/0.1 (design reference study; one visit per site, respects robots.txt)';

/** The canonical id of a site: its host without "www." — two registries naming the same site give the same id. */
export function siteId(url) {
  const { hostname } = new URL(url);
  return hostname.toLowerCase().replace(/^www\./, '');
}

/** The URL of a site without tracking parameters and without a trailing path noise. */
export function cleanUrl(url) {
  const u = new URL(url);
  for (const key of [...u.searchParams.keys()]) if (/^(utm_|ref$|source$|fbclid$|gclid$)/i.test(key)) u.searchParams.delete(key);
  u.hash = '';
  return u.toString();
}

export function readJsonl(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8').split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

export function writeJsonl(path, rows) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, rows.map((row) => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''));
}

export function readJson(path, fallback) {
  return existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : fallback;
}

export function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(value, null, 2) + '\n');
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Is `path` allowed for everybody by this robots.txt? (Only the "User-agent: *" group, Disallow and Allow prefixes.) */
export function robotsAllows(robotsTxt, path) {
  let applies = false;
  let best = { len: -1, allow: true };
  for (const raw of robotsTxt.split('\n')) {
    const line = raw.split('#')[0].trim();
    const m = /^([a-z-]+)\s*:\s*(.*)$/i.exec(line);
    if (!m) continue;
    const key = m[1].toLowerCase();
    const value = m[2].trim();
    if (key === 'user-agent') applies = value === '*';
    else if (applies && (key === 'disallow' || key === 'allow') && value && path.startsWith(value) && value.length > best.len) best = { len: value.length, allow: key === 'allow' };
  }
  return best.allow;
}

/** fetch with our user agent, a timeout, and a check of the host's robots.txt (cached for the run). */
const robotsCache = new Map();
async function checkRobots(url, fetchFn, timeoutMs) {
  const u = new URL(url);
  if (!robotsCache.has(u.origin)) {
    try {
      const res = await fetchFn(`${u.origin}/robots.txt`, { headers: { 'user-agent': UA }, signal: AbortSignal.timeout(timeoutMs) });
      robotsCache.set(u.origin, res.ok ? await res.text() : '');
    } catch { robotsCache.set(u.origin, ''); }
  }
  if (!robotsAllows(robotsCache.get(u.origin), u.pathname + u.search)) throw new Error(`robots.txt disallows ${u.pathname}`);
}

/** The page AFTER its scripts ran (Chromium), for listings that are drawn by JavaScript. Same robots.txt check and pace as politeFetch. */
export async function renderPage(url, { fetchFn = fetch, delayMs = 1500, timeoutMs = 45000, executablePath = process.env.CHROMIUM_PATH || undefined } = {}) {
  await checkRobots(url, fetchFn, 30000);
  await sleep(delayMs);
  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ executablePath });
  try {
    const page = await browser.newPage({ userAgent: UA });
    await page.goto(url, { waitUntil: 'networkidle', timeout: timeoutMs }).catch(() => {});
    // lists load more as they are scrolled
    for (let i = 0; i < 4; i++) { await page.mouse.wheel(0, 4000); await page.waitForTimeout(600); }
    return await page.content();
  } finally { await browser.close(); }
}

export async function politeFetch(url, { fetchFn = fetch, delayMs = 1500, timeoutMs = 30000 } = {}) {
  const u = new URL(url);
  await checkRobots(url, fetchFn, timeoutMs);
  await sleep(delayMs);
  const res = await fetchFn(url, { headers: { 'user-agent': UA, accept: 'text/html,*/*' }, signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.text();
}
