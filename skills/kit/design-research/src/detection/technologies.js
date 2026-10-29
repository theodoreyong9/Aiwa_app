// What the page is built with, from what the browser showed. Every detection carries its status (OBSERVED: seen in the
// running page or in a resource it loaded; INFERRED: only a pattern; DECLARED: only named in the markup), its
// confidence and the evidence. A name in the HTML alone is never presented as an observation.

const GLOBALS = [
  ['GSAP', 'gsap'], ['ScrollTrigger', 'ScrollTrigger'], ['Three.js', 'THREE'], ['Lenis', 'Lenis'], ['PixiJS', 'PIXI'], ['anime.js', 'anime'], ['Barba.js', 'barba'],
  ['Swiper', 'Swiper'], ['Matter.js', 'Matter'], ['p5.js', 'p5'], ['Babylon.js', 'BABYLON'], ['Lottie', 'lottie'], ['Locomotive Scroll', 'LocomotiveScroll'],
  ['SplitText', 'SplitText'], ['SplitType', 'SplitType'], ['Rive', 'Rive'], ['OGL', 'OGL'], ['regl', 'regl'], ['Phaser', 'Phaser'], ['jQuery', 'jQuery'], ['Alpine.js', 'Alpine'],
];
const FILES = [
  ['GSAP', /gsap(\.min)?\.js|\/gsap@|gsap-[\w-]*\.js/i], ['ScrollTrigger', /scrolltrigger/i], ['Three.js', /three(\.module)?(\.min)?\.js|\/three@|three-[\w-]*\.js/i], ['Lenis', /lenis/i],
  ['PixiJS', /pixi/i], ['Barba.js', /barba/i], ['Swiper', /swiper/i], ['Lottie', /lottie/i], ['Locomotive Scroll', /locomotive/i], ['Matter.js', /matter(\.min)?\.js/i], ['Babylon.js', /babylon/i],
  ['Rive', /rive(\.wasm|\.js)/i], ['Framer Motion', /framer-motion/i],
];
const MARKERS = [['Next.js', 'next'], ['Nuxt', 'nuxt'], ['React', 'reactRoot'], ['Vue', 'vue'], ['Svelte', 'svelte'], ['Astro', 'astro'], ['Webflow', 'webflow'], ['WordPress', 'wordpress'], ['Framer', 'framer'], ['Shopify', 'shopify'], ['Wix', 'wix'], ['Squarespace', 'squarespace']];
const HOSTS = [
  ['Google Analytics', /google-analytics\.com|googletagmanager\.com/i, 'analytics'], ['Plausible', /plausible\.io/i, 'analytics'], ['Vimeo', /vimeo(cdn)?\.com/i, 'video'], ['YouTube', /youtube(-nocookie)?\.com|ytimg\.com/i, 'video'],
  ['Mux', /mux\.com|stream\.mux/i, 'video'], ['Cloudinary', /cloudinary\.com/i, 'image CDN'], ['imgix', /imgix\.net/i, 'image CDN'], ['Sanity', /sanity\.io/i, 'CMS'], ['Contentful', /contentful\.com/i, 'CMS'], ['Prismic', /prismic\.io/i, 'CMS'],
  ['Google Fonts', /fonts\.(googleapis|gstatic)\.com/i, 'font provider'], ['Adobe Fonts', /use\.typekit\.net|fonts\.adobe\.com/i, 'font provider'], ['Fontshare', /fontshare\.com/i, 'font provider'],
];

/** @returns {Array<{name:string, kind:string, status:string, confidence:number, evidence:string[]}>} */
export function detect(observation) {
  const d = observation.desktop;
  const f = d.features;
  const out = new Map();
  const add = (name, kind, status, confidence, evidence) => {
    const cur = out.get(name);
    if (!cur) { out.set(name, { name, kind, status, confidence, evidence: [evidence] }); return; }
    cur.evidence.push(evidence);
    cur.confidence = Math.min(0.99, Math.max(cur.confidence, confidence) + (status === 'OBSERVED' ? 0.02 : 0));
    if (status === 'OBSERVED') cur.status = 'OBSERVED';
  };
  for (const [name, key] of GLOBALS) if (f.globals[key]) add(name, 'library', 'OBSERVED', 0.97, `window.${key} is defined`);
  const scripts = d.network.filter((r) => r.type === 'JS' && (r.status ?? 200) < 400).map((r) => r.url);
  for (const [name, re] of FILES) { const hit = scripts.find((u) => re.test(u)); if (hit) add(name, 'library', 'OBSERVED', 0.85, `loaded ${hit.split('/').pop().split('?')[0]}`); }
  for (const [name, key] of MARKERS) if (f.markers[key]) add(name, 'framework', 'OBSERVED', 0.9, `marker "${key}" present in the running page`);
  const hosts = new Set(d.network.map((r) => { try { return new URL(r.url).host; } catch { return ''; } }));
  for (const [name, re, kind] of HOSTS) { const hit = [...hosts].find((h) => re.test(h)); if (hit) add(name, kind, 'OBSERVED', 0.9, `requests to ${hit}`); }
  // rendering, from what the page asked of the canvas API
  const ctx = f.runtime.contexts ?? {};
  if (ctx.webgl2) add('WebGL2', 'rendering', 'OBSERVED', 0.99, `getContext("webgl2") called ${ctx.webgl2}x`);
  if (ctx.webgl || ctx['experimental-webgl']) add('WebGL', 'rendering', 'OBSERVED', 0.99, 'getContext("webgl") called');
  if (ctx.webgpu) add('WebGPU', 'rendering', 'OBSERVED', 0.99, 'getContext("webgpu") called');
  if (ctx['2d']) add('Canvas 2D', 'rendering', 'OBSERVED', 0.99, `getContext("2d") called ${ctx['2d']}x`);
  if (f.runtime.wasm) add('WebAssembly', 'rendering', 'OBSERVED', 0.99, `WebAssembly.instantiate called ${f.runtime.wasm}x`);
  if (f.runtime.startViewTransition || f.motion.viewTransitionCss) add('View Transitions API', 'motion', 'OBSERVED', 0.9, f.runtime.startViewTransition ? 'document.startViewTransition called' : '::view-transition rules in the stylesheets');
  if (f.motion.scrollTimelineCss) add('CSS scroll-driven animations', 'motion', 'OBSERVED', 0.9, 'animation-timeline in the stylesheets');
  // a pattern, never a certainty
  if (!out.has('GSAP') && f.runtime.raf > 200 && f.motion.animations === 0 && f.runtime.io > 0) add('JS-driven animation (library unknown)', 'motion', 'INFERRED', 0.5, `${f.runtime.raf} animation frames requested, no CSS animation, IntersectionObserver used`);
  return [...out.values()].sort((a, b) => b.confidence - a.confidence);
}
