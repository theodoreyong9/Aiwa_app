// From raw observations to the catalog entry: detections with their evidence, measured traits, tokens, transposability.
import { detect } from './detection/technologies.js';
import { classify, transposability } from './classify/traits.js';

export function analyze(observation) {
  const tech = detect(observation);
  const { traits, needs_interpretation, responsive } = classify(observation, tech);
  const f = observation.desktop.features;
  const byType = {};
  for (const r of observation.desktop.network) { const t = r.type; byType[t] = byType[t] ?? { count: 0, bytes: 0 }; byType[t].count++; byType[t].bytes += r.bytes ?? 0; }
  return {
    title: f.metaTitle,
    description: f.description,
    lang: f.lang,
    tech,
    traits,
    needs_interpretation,
    tokens: {
      typography: { families: f.typography.families.map(([n, c]) => ({ family: n, uses: c })), sizeMax: f.typography.sizeMax, sizeMaxVw: f.typography.sizeMaxVw, sizeMedian: f.typography.sizeMedian, scaleRatio: f.typography.scaleRatio, weights: f.typography.weights.map(([w]) => w), letterSpacingMean: f.typography.letterSpacingMean },
      color: { background: f.color.background, text: f.color.texts.map(([c]) => c), backgrounds: f.color.backgrounds.map(([c]) => c), saturation: f.color.meanSaturation, variables: f.color.rootVars },
      spacing: f.layout.spacing.map(([px]) => px),
      motion: { transitionsMs: f.motion.transitionDurationsMs.map(([ms]) => ms), animationDurationsMs: f.motion.animationDurations.map((d) => Math.round(d)), easings: f.motion.easings, keyframes: f.motion.keyframes },
    },
    features: {
      layout: { ...f.layout, spacing: undefined }, elements: f.elements, media: { canvases: f.media.canvases.length, videos: f.media.videos.length, svg: f.media.svg, images: f.media.images, iframes: f.media.iframes },
      hover: observation.desktop.hover, observers: { intersection: f.runtime.io, resize: f.runtime.ro }, animationFrames: f.runtime.raf, cdp_animations: observation.desktop.animationsReported.length,
    },
    network: { requests: observation.desktop.network.length, bytes: Object.values(byType).reduce((n, t) => n + t.bytes, 0), byType, failed: observation.desktop.failed.length },
    health: { status: observation.desktop.status, consoleErrors: observation.desktop.console.filter((c) => c.level === 'error').length, exceptions: observation.desktop.exceptions.length, timing: observation.desktop.performance.timing, targets: observation.desktop.targets },
    responsive,
    transposable: transposability(observation, tech, traits),
    screenshots: { desktop: observation.desktop.shots, mobile: observation.mobile?.shots ?? {} },
  };
}
