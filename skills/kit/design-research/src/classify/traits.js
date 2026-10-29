// Traits that follow from measurements, by rules written down here and nowhere else. What a measurement cannot say (is it
// "luxury"? is it "playful"?) is not guessed: it stays in `needs_interpretation` for the reader that has the screenshots
// (Claude Code, from the research pack).

const GENERIC_SERIF = /serif|times|georgia|garamond|playfair|didot|bodoni|baskerville|cormorant|canela|tiempos|lora|merriweather|fraunces|newsreader|ivar|gt super|editorial new/i;
const SANS_NOT_SERIF = /sans|helvetica|arial|inter|grotesk|grotesque|neue|roboto|poppins|manrope|satoshi|general|switzer|geist/i;
const CONDENSED = /condensed|narrow|compress|oswald|bebas|anton|league gothic|barlow condensed|fjalla/i;
const MONO = /mono|courier|consolas|menlo|plex mono|jetbrains/i;

export function classify(observation, tech) {
  const d = observation.desktop;
  const f = d.features;
  const names = new Set(tech.map((t) => t.name));
  const ctx = f.runtime.contexts ?? {};
  const has3d = !!(ctx.webgl || ctx.webgl2 || ctx.webgpu || ctx['experimental-webgl']) || names.has('Three.js') || names.has('Babylon.js');
  const families = f.typography.families.map(([name]) => name);
  const dominant = families[0] ?? '';

  const typography = [];
  if (f.typography.sizeMaxVw >= 9 || f.typography.sizeMax >= 140) typography.push('oversized');
  if (families.some((n) => GENERIC_SERIF.test(n)) && !SANS_NOT_SERIF.test(dominant)) typography.push('serif');
  if (SANS_NOT_SERIF.test(dominant) || (!GENERIC_SERIF.test(dominant) && dominant)) typography.push('sans');
  if (families.some((n) => CONDENSED.test(n))) typography.push('condensed');
  if (families.some((n) => MONO.test(n))) typography.push('mono');
  if (f.typography.variableFont) typography.push('variable');
  if (f.typography.textTransforms.some(([t]) => t === 'uppercase')) typography.push('uppercase');
  if (f.typography.scaleRatio >= 8) typography.push('high-contrast-scale');
  if (f.typography.families.length <= 1 && f.typography.sizeMaxVw < 6) typography.push('minimal');
  if (names.has('SplitText') || names.has('SplitType')) typography.push('kinetic');

  const composition = [];
  if (f.layout.fullscreenSections >= 3) composition.push('fullscreen');
  if (f.layout.asymmetricGrids >= 1) composition.push('asymmetric');
  if (f.layout.grid >= 3) composition.push('grid');
  if (f.layout.splitScreen) composition.push('split-screen');
  if (f.layout.absolute > 15 || f.layout.fixed >= 3) composition.push('layered');
  if (f.layout.pages >= 8) composition.push('long-scroll');
  if (f.layout.sticky >= 2) composition.push('sticky-sections');

  const motion = [];
  if (names.has('ScrollTrigger') || names.has('Locomotive Scroll') || f.motion.scrollTimelineCss) motion.push('scroll-driven');
  if (names.has('Lenis') || names.has('Locomotive Scroll')) motion.push('smooth-scroll');
  if (d.scrollReveal >= 1 || (f.runtime.io >= 1 && f.motion.transitionDurationsMs.length > 0)) motion.push('reveal');
  if (names.has('Barba.js') || names.has('View Transitions API')) motion.push('page-transition');
  if (f.motion.infiniteAnimations >= 2) motion.push('continuous');
  if (names.has('Matter.js')) motion.push('physics');
  if (ctx['2d'] && f.runtime.raf > 300 && !has3d) motion.push('canvas-animation');
  if (names.has('Lottie') || names.has('Rive')) motion.push('vector-animation');
  const durations = f.motion.transitionDurationsMs.map(([ms]) => ms);
  if (durations.length && Math.max(...durations) >= 900) motion.push('slow-easing');
  if (!motion.length && f.motion.animations + durations.length < 3) motion.push('static');

  const interaction = [];
  if (d.hover.probed && d.hover.changed / d.hover.probed >= 0.5) interaction.push('rich-hover');
  if (f.media.customCursor) interaction.push('custom-cursor');
  if (names.has('Swiper')) interaction.push('carousel');
  if (f.media.videos.some((v) => v.autoplay)) interaction.push('autoplay-video');
  if (f.runtime.raf > 300 && has3d) interaction.push('scene-driven');

  const rendering = [];
  if (has3d) rendering.push('3D');
  if (ctx.webgpu) rendering.push('WebGPU'); else if (ctx.webgl || ctx.webgl2) rendering.push('WebGL');
  if (ctx['2d']) rendering.push('Canvas');
  if (f.media.svg >= 12) rendering.push('SVG-heavy');
  if (f.media.videos.length) rendering.push('video');
  if (!rendering.length) rendering.push('DOM-CSS');

  const lumValue = f.color.backgroundLuminance;
  const palette = [];
  if (lumValue !== null) palette.push(lumValue < 0.18 ? 'dark' : lumValue > 0.7 ? 'light' : 'mid-tone');
  palette.push(f.color.meanSaturation < 0.15 ? 'monochrome' : f.color.meanSaturation > 0.55 ? 'vivid' : 'restrained');
  if (f.color.backgrounds.length <= 2 && f.elements < 400) palette.push('minimal');

  const responsive = observation.mobile?.features
    ? { mobileCanvasDropped: (f.media.canvases.length > 0) && observation.mobile.features.media.canvases.length === 0, mobileFullscreenSections: observation.mobile.features.layout.fullscreenSections, mobileMenuHidden: false }
    : null;

  return {
    traits: { typography: [...new Set(typography)], composition, motion, interaction, rendering, palette },
    needs_interpretation: ['art_direction', 'industry', 'tone', 'why_it_works'],
    responsive,
  };
}

/** Which of our formats can use what this reference does. Patterns (type, colour, motion rhythm) always carry; heavy techniques do not. */
export function transposability(observation, tech, traits) {
  const bytes = observation.desktop.network.reduce((n, r) => n + (r.bytes ?? 0), 0);
  const heavy = traits.rendering.includes('3D') || traits.rendering.includes('WebGPU') || bytes > 6_000_000;
  const mobileDropsHeavy = !!observation.mobile?.features && observation.mobile.features.media.canvases.length === 0 && observation.desktop.features.media.canvases.length > 0;
  const libs = tech.filter((t) => t.kind === 'library' && t.status === 'OBSERVED').map((t) => t.name);
  const oneFile = {
    verdict: heavy ? 'partial' : 'yes',
    reason: heavy ? 'the 3D / heavy-media technique does not fit a single HTML file of 512 KB or less: take the composition, type and motion rhythm, not the scene' : 'fits a single HTML file',
  };
  return {
    site: { verdict: 'yes', reason: heavy ? 'a hosted site can carry the weight' : 'no constraint' },
    pwa: { ...oneFile, mobile_note: mobileDropsHeavy ? 'the reference itself drops its canvas on a phone' : undefined },
    apk: { ...oneFile, mobile_note: mobileDropsHeavy ? 'the reference itself drops its canvas on a phone' : undefined },
    contract_ui: { verdict: 'partial', reason: 'a contract has no screen of its own: only type, colour, spacing and state design apply to the screen that shows it' },
    libraries_seen: libs,
    transfer_bytes: bytes,
  };
}
