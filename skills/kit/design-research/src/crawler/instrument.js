// Runs in the page BEFORE its own scripts (addInitScript): records what a script does that the DOM cannot show afterwards
// — which canvas contexts it asked for, how many animation frames it requested, which observers it built.
export const INIT_SCRIPT = `(() => {
  const rec = (window.__dr = { contexts: {}, raf: 0, io: 0, ro: 0, mo: 0, startViewTransition: 0, workers: 0, wasm: 0 });
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) { rec.contexts[type] = (rec.contexts[type] || 0) + 1; return getContext.call(this, type, ...rest); };
  const raf = window.requestAnimationFrame;
  window.requestAnimationFrame = function (cb) { rec.raf++; return raf.call(window, cb); };
  for (const [name, key] of [['IntersectionObserver', 'io'], ['ResizeObserver', 'ro'], ['MutationObserver', 'mo']]) {
    const Original = window[name];
    if (!Original) continue;
    window[name] = class extends Original { constructor(...args) { super(...args); rec[key]++; } };
  }
  if (document.startViewTransition) { const s = document.startViewTransition; document.startViewTransition = function (...a) { rec.startViewTransition++; return s.apply(document, a); }; }
  const W = window.Worker;
  if (W) window.Worker = class extends W { constructor(...a) { super(...a); rec.workers++; } };
  if (window.WebAssembly && WebAssembly.instantiate) { const i = WebAssembly.instantiate; WebAssembly.instantiate = function (...a) { rec.wasm++; return i.apply(WebAssembly, a); }; }
})();`;
