// Runs in the page, after load and a scroll: turns the live page into a small set of measurements (not a DOM dump).
// A function body, evaluated by Playwright; it returns plain data.
export function extractFeatures() {
  const vw = window.innerWidth, vh = window.innerHeight;
  const all = [...document.querySelectorAll('body *')].slice(0, 6000);
  const visible = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05; };
  const inc = (map, key, n = 1) => map.set(key, (map.get(key) || 0) + n);
  const top = (map, n) => [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, n);
  const lum = (rgb) => { const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/.exec(rgb); if (!m) return null; if (m[4] !== undefined && +m[4] === 0) return null; const [r, g, b] = [m[1], m[2], m[3]].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const sat = (rgb) => { const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(rgb); if (!m) return 0; const mx = Math.max(+m[1], +m[2], +m[3]), mn = Math.min(+m[1], +m[2], +m[3]); return mx === 0 ? 0 : (mx - mn) / mx; };

  // typography: families and sizes of the text that is actually shown
  const families = new Map(), sizes = [], weights = new Map(), transforms = new Map(), letterSpacings = [];
  let textNodes = 0, maxFont = 0;
  for (const el of all) {
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1) || !visible(el)) continue;
    const cs = getComputedStyle(el);
    textNodes++;
    const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    inc(families, fam);
    const size = parseFloat(cs.fontSize);
    sizes.push(size); maxFont = Math.max(maxFont, size);
    inc(weights, cs.fontWeight);
    if (cs.textTransform !== 'none') inc(transforms, cs.textTransform);
    const ls = parseFloat(cs.letterSpacing); if (!Number.isNaN(ls)) letterSpacings.push(ls / size);
  }
  sizes.sort((a, b) => a - b);
  const body = getComputedStyle(document.body);
  const fonts = [...document.fonts].filter((f) => f.status === 'loaded').map((f) => ({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style }));
  const variableFont = fonts.some((f) => /\s/.test(String(f.weight))) || all.slice(0, 800).some((el) => getComputedStyle(el).fontVariationSettings !== 'normal');

  // colour: backgrounds by area, text colours by count, the :root custom properties
  const bg = new Map(), fg = new Map();
  for (const el of all.slice(0, 2500)) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (lum(cs.backgroundColor) !== null) inc(bg, cs.backgroundColor, Math.round(Math.min(r.width, vw * 3) * Math.min(r.height, vh * 3) / 1000));
    inc(fg, cs.color);
  }
  const pageBg = lum(body.backgroundColor) !== null ? body.backgroundColor : (lum(getComputedStyle(document.documentElement).backgroundColor) !== null ? getComputedStyle(document.documentElement).backgroundColor : top(bg, 1)[0]?.[0] ?? 'rgb(255, 255, 255)');
  const rootVars = {};
  try { for (const sheet of document.styleSheets) { let rules; try { rules = sheet.cssRules; } catch { continue; } for (const rule of rules) if (rule.selectorText === ':root') for (const p of rule.style) if (p.startsWith('--') && Object.keys(rootVars).length < 40) rootVars[p] = rule.style.getPropertyValue(p).trim(); } } catch { /* cross-origin sheets */ }
  const saturations = top(bg, 6).map(([c]) => sat(c));

  // layout
  let fullscreen = 0, sticky = 0, fixed = 0, grid = 0, flex = 0, absolute = 0, overlaps = 0, asymmetricGrids = 0;
  const gaps = new Map();
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.position === 'sticky') sticky++;
    if (cs.position === 'fixed') fixed++;
    if (cs.position === 'absolute') absolute++;
    if (cs.display === 'grid' || cs.display === 'inline-grid') { grid++; const cols = cs.gridTemplateColumns.split(' ').map(parseFloat).filter(Boolean); if (cols.length > 1 && Math.max(...cols) / Math.min(...cols) > 1.6) asymmetricGrids++; }
    if (cs.display === 'flex') flex++;
    const g = parseFloat(cs.rowGap); if (g > 0) inc(gaps, Math.round(g));
    for (const k of ['paddingTop', 'marginTop']) { const v = parseFloat(cs[k]); if (v > 0 && v < 400) inc(gaps, Math.round(v)); }
    if (el.parentElement === document.body || el.parentElement?.parentElement === document.body) { const r = el.getBoundingClientRect(); if (r.height >= vh * 0.9 && r.width >= vw * 0.9) fullscreen++; }
  }
  const hero = [...document.querySelectorAll('body > *, body > * > *')].find((el) => { const r = el.getBoundingClientRect(); return r.top < vh && r.height > vh * 0.5 && r.width > vw * 0.8; });
  const splitScreen = !!hero && [...hero.children].filter((c) => { const r = c.getBoundingClientRect(); return r.width > vw * 0.4 && r.width < vw * 0.6 && r.height > vh * 0.5; }).length === 2;

  // motion that the browser reports: CSS animations, transitions, Web Animations
  const anims = document.getAnimations().map((a) => { const t = a.effect?.getTiming?.() ?? {}; return { type: a.constructor.name, name: a.animationName || a.transitionProperty || '', duration: t.duration, iterations: t.iterations, easing: t.easing, delay: t.delay, state: a.playState }; });
  const transitionDurations = new Map();
  for (const el of all.slice(0, 2500)) { const d = parseFloat(getComputedStyle(el).transitionDuration); if (d > 0) inc(transitionDurations, Math.round(d * 1000)); }
  const keyframes = new Set();
  let viewTransitionCss = false, scrollTimelineCss = false;
  try { for (const sheet of document.styleSheets) { let rules; try { rules = sheet.cssRules; } catch { continue; } for (const rule of rules) { if (rule.type === CSSRule.KEYFRAMES_RULE) keyframes.add(rule.name); const t = rule.cssText ?? ''; if (t.includes('::view-transition') || t.includes('@view-transition')) viewTransitionCss = true; if (t.includes('animation-timeline') || t.includes('scroll-timeline')) scrollTimelineCss = true; } } } catch { /* ignore */ }

  // elements that are drawn invisible until something happens (what a reveal on scroll starts from)
  let hidden = 0;
  for (const el of all.slice(0, 1500)) { const cs = getComputedStyle(el); if (+cs.opacity < 0.1 && cs.display !== 'none') { const r = el.getBoundingClientRect(); if (r.width > 20 && r.height > 10) hidden++; } }

  // media
  const canvases = [...document.querySelectorAll('canvas')].map((c) => ({ w: c.width, h: c.height, area: Math.round(c.getBoundingClientRect().width * c.getBoundingClientRect().height / (vw * vh) * 100) / 100 }));
  const videos = [...document.querySelectorAll('video')].map((v) => ({ autoplay: v.autoplay, loop: v.loop, muted: v.muted, src: (v.currentSrc || v.src || '').slice(0, 160) }));

  return {
    viewport: { w: vw, h: vh },
    elements: all.length,
    typography: {
      families: top(families, 6), weights: top(weights, 5), textTransforms: top(transforms, 3),
      sizeMin: sizes[0] ?? 0, sizeMedian: sizes[Math.floor(sizes.length / 2)] ?? 0, sizeMax: maxFont, sizeMaxVw: Math.round(maxFont / vw * 1000) / 10,
      scaleRatio: sizes.length ? Math.round(maxFont / (sizes[Math.floor(sizes.length / 2)] || 16) * 10) / 10 : 0,
      letterSpacingMean: letterSpacings.length ? Math.round(letterSpacings.reduce((a, b) => a + b, 0) / letterSpacings.length * 1000) / 1000 : 0,
      loadedFonts: fonts.slice(0, 12), variableFont, textElements: textNodes,
    },
    color: {
      background: pageBg, backgroundLuminance: lum(pageBg), backgrounds: top(bg, 6), texts: top(fg, 5), meanSaturation: saturations.length ? Math.round(saturations.reduce((a, b) => a + b, 0) / saturations.length * 100) / 100 : 0, rootVars,
    },
    layout: { fullscreenSections: fullscreen, sticky, fixed, grid, flex, absolute, asymmetricGrids, splitScreen, scrollHeight: document.documentElement.scrollHeight, pages: Math.round(document.documentElement.scrollHeight / vh * 10) / 10, spacing: top(gaps, 8) },
    motion: {
      animations: anims.length, animationKinds: [...new Set(anims.map((a) => a.type))], infiniteAnimations: anims.filter((a) => a.iterations === Infinity).length,
      animationDurations: anims.map((a) => a.duration).filter((d) => typeof d === 'number').slice(0, 20), easings: [...new Set(anims.map((a) => a.easing))].slice(0, 8),
      transitionDurationsMs: top(transitionDurations, 5), keyframes: [...keyframes].slice(0, 20), viewTransitionCss, scrollTimelineCss,
    },
    hiddenElements: hidden,
    media: { canvases, videos, svg: document.querySelectorAll('svg').length, images: document.images.length, iframes: document.querySelectorAll('iframe').length, customCursor: /none|url/.test(body.cursor) },
    runtime: window.__dr ?? {},
    globals: Object.fromEntries(['gsap', 'ScrollTrigger', 'THREE', 'Lenis', 'PIXI', 'anime', 'barba', 'Swiper', 'Matter', 'p5', 'BABYLON', 'lottie', 'Webflow', 'jQuery', 'Alpine', 'Vue', 'React', 'ReactDOM', 'Locomotive', 'LocomotiveScroll', 'SplitType', 'SplitText', 'Rive', 'OGL', 'regl', 'PhaserGame', 'Phaser', 'motion', 'framerMotion'].map((k) => [k, typeof window[k] !== 'undefined'])),
    markers: {
      next: !!window.__NEXT_DATA__, nuxt: !!window.__NUXT__, reactRoot: !!document.querySelector('[data-reactroot], #__next, #root[data-react]') || !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__?.renderers?.size,
      vue: !!window.__VUE__ || !!document.querySelector('[data-v-app]'), svelte: !!document.querySelector('[class*="svelte-"]'), astro: !!document.querySelector('astro-island'),
      webflow: !!document.documentElement.getAttribute('data-wf-page'), wordpress: !!document.querySelector('link[href*="wp-content"], script[src*="wp-content"]'),
      framer: !!document.querySelector('[data-framer-name], [data-framer-root]'), shopify: !!window.Shopify, wix: !!window.wixBiSession, squarespace: !!window.Static?.SQUARESPACE_CONTEXT,
    },
    metaTitle: document.title, lang: document.documentElement.lang || '', description: document.querySelector('meta[name="description"]')?.content ?? '',
  };
}
