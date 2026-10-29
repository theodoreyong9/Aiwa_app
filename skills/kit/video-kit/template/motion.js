// Motion primitives for video pages. Everything here is a PURE FUNCTION OF TIME: the same t gives the same picture, so a frame can be
// rendered alone, in any order, on any machine. Load it with <script src="motion.js"> and use window.M.
//
//   M.prog(t, start, dur, ease)     0..1 progress of an animation that starts at `start` and lasts `dur`
//   M.kinetic(host, text, opts)     text split in words / letters / lines, each unit animated with a stagger; returns { set(t) }
//   M.cam(el, from, to, p)          camera move on an element: { x, y (vmin), s (scale), r (deg) } from → to at progress p
//   M.trans(type, p, outEl, inEl)   transition between two full-frame elements: fade push push-up wipe zoom iris slice flash
//   M.counter(el, from, to, p, o)   a number that counts up
//   M.draw(pathEl, p)               an SVG path that draws itself
//   M.grain(canvas, t, alpha)       film grain, different at each frame, the same at the same t
//   M.rand(seed)                    a seeded random generator (mulberry32)
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const ease = {
    linear: (x) => x,
    inCubic: (x) => x * x * x,
    outCubic: (x) => 1 - Math.pow(1 - x, 3),
    outQuart: (x) => 1 - Math.pow(1 - x, 4),
    inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    inOutSine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
    outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    inOutExpo: (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x < 0.5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2),
    outBack: (x) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
  };
  const prog = (t, start, dur, fn = ease.outCubic) => fn(clamp((t - start) / Math.max(1e-6, dur)));
  const rand = (seed) => () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let r = Math.imul(seed ^ (seed >>> 15), 1 | seed); r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r; return ((r ^ (r >>> 14)) >>> 0) / 4294967296; };

  // ---- kinetic text ----------------------------------------------------------------------------------------------------------------
  // opts: mode 'words' | 'chars' | 'lines' (lines: split on \n), effect 'mask' | 'rise' | 'blur' | 'scale' | 'drop' | 'type' | 'fade',
  //       at (s), dur (s per unit), stagger (s between units), out: { at, dur, effect }, accent: { 'word': 'css colour' }
  function kinetic(host, text, o = {}) {
    const mode = o.mode || 'words', effect = o.effect || 'mask', at = o.at || 0, dur = o.dur ?? 0.7, stagger = o.stagger ?? (mode === 'chars' ? 0.03 : 0.09);
    const accent = o.accent || {};
    const units = [];
    const lines = String(text).split('\n');
    const lineUnits = [];
    lines.forEach((line, li) => {
      // a line is a row; in 'lines' mode the row's inner box is what moves (and a row clips it when the effect is a mask)
      const row = document.createElement('div'); row.style.cssText = 'display:block;white-space:pre-wrap' + (mode === 'lines' && effect === 'mask' ? ';overflow:hidden;padding:0.12em 0.04em 0.18em;margin:-0.12em -0.04em -0.18em' : '');
      const inner = document.createElement('div'); inner.style.cssText = 'will-change:transform';
      const words = line.split(' ');
      words.forEach((word, wi) => {
        const w = document.createElement('span');
        w.style.cssText = 'display:inline-block;white-space:pre;' + (effect === 'mask' && mode !== 'lines' ? 'overflow:hidden;vertical-align:top;padding:0.12em 0.04em 0.18em;margin:-0.12em -0.04em -0.18em' : '');
        const parts = mode === 'chars' ? [...word] : [word];
        parts.forEach((p) => {
          const i = document.createElement('span'); i.textContent = p; i.style.cssText = 'display:inline-block;will-change:transform';
          const key = word.replace(/[.,;:!?…]/g, '');
          const col = accent[word] || accent[key];
          if (col) i.style.color = col;
          w.append(i); units.push({ el: i, line: li });
        });
        inner.append(w);
        if (wi < words.length - 1) inner.append(document.createTextNode(' '));
      });
      row.append(inner); host.append(row); lineUnits.push({ el: inner, line: li });
    });
    const anim = mode === 'lines' ? lineUnits : units;
    function apply(u, p, q) {
      const el = u.el, inP = p, outP = q;
      const k = 1 - inP;
      let tf = '', op = 1, fl = '';
      switch (effect) {
        case 'mask': tf = `translateY(${k * 115}%)`; break;
        case 'rise': tf = `translateY(${k * 0.7}em)`; op = inP; break;
        case 'drop': tf = `translateY(${-k * 0.9}em)`; op = inP; break;
        case 'blur': tf = `scale(${1 + k * 0.18})`; op = inP; fl = `blur(${k * 0.3}em)`; break;
        case 'scale': tf = `scale(${1 + k * 0.7})`; op = inP; break;
        case 'type': op = inP > 0.02 ? 1 : 0; break;
        default: op = inP;
      }
      if (outP > 0) {
        const oe = (o.out && o.out.effect) || 'rise';
        if (oe === 'mask') { tf += ` translateY(${-outP * 115}%)`; op *= 1 - outP; }
        else if (oe === 'blur') { fl = `blur(${outP * 0.3}em)`; op *= 1 - outP; }
        else { tf += ` translateY(${-outP * 0.5}em)`; op *= 1 - outP; }
      }
      el.style.transform = tf || 'none'; el.style.opacity = op; el.style.filter = fl || 'none';
    }
    return {
      units: anim,
      set(t) {
        anim.forEach((u, i) => {
          const p = prog(t, at + i * stagger, dur, effect === 'mask' || effect === 'blur' ? ease.outExpo : ease.outCubic);
          const q = o.out ? prog(t, o.out.at + i * stagger * 0.5, o.out.dur ?? 0.35, ease.inOutCubic) : 0;
          apply(u, p, q);
        });
      },
      end: at + Math.max(0, anim.length - 1) * stagger + dur,
    };
  }

  // ---- camera ------------------------------------------------------------------------------------------------------------------------
  function cam(el, from, to, p) {
    const f = Object.assign({ x: 0, y: 0, s: 1, r: 0 }, from), g = Object.assign({ x: 0, y: 0, s: 1, r: 0 }, to);
    el.style.transform = `translate(${lerp(f.x, g.x, p)}vmin, ${lerp(f.y, g.y, p)}vmin) scale(${lerp(f.s, g.s, p)}) rotate(${lerp(f.r, g.r, p)}deg)`;
  }

  // ---- transitions -------------------------------------------------------------------------------------------------------------------
  function reset(el) { el.style.transform = 'none'; el.style.opacity = 1; el.style.clipPath = 'none'; el.style.filter = 'none'; }
  function trans(type, p, outEl, inEl) {
    reset(outEl); reset(inEl);
    const e = ease.inOutCubic(clamp(p));
    switch (type) {
      case 'push': outEl.style.transform = `translateX(${-e * 100}%)`; inEl.style.transform = `translateX(${(1 - e) * 100}%)`; break;
      case 'push-up': outEl.style.transform = `translateY(${-e * 100}%)`; inEl.style.transform = `translateY(${(1 - e) * 100}%)`; break;
      case 'wipe': inEl.style.clipPath = `inset(0 ${(1 - e) * 100}% 0 0)`; break;
      case 'zoom': outEl.style.transform = `scale(${1 + e * 0.7})`; outEl.style.opacity = 1 - e; inEl.style.transform = `scale(${1.3 - e * 0.3})`; inEl.style.opacity = e; break;
      case 'iris': inEl.style.clipPath = `circle(${e * 80}% at 50% 50%)`; break;
      case 'slice': inEl.style.clipPath = `polygon(0 0, ${e * 140}% 0, ${e * 140 - 40}% 100%, 0 100%)`; break;
      case 'flash': outEl.style.opacity = 1 - Math.min(1, e * 2); inEl.style.opacity = Math.max(0, e * 2 - 1); outEl.style.filter = `brightness(${1 + e * 3})`; break;
      default: inEl.style.opacity = e; break;   // 'fade'
    }
  }

  // ---- numbers, paths, grain -----------------------------------------------------------------------------------------------------
  function counter(el, from, to, p, o = {}) {
    const v = lerp(from, to, p), d = o.decimals || 0;
    let s = v.toFixed(d);
    if (o.sep) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, o.sep);
    el.textContent = (o.prefix || '') + s + (o.suffix || '');
  }
  function draw(pathEl, p) {
    const len = pathEl.getTotalLength();
    pathEl.style.strokeDasharray = String(len); pathEl.style.strokeDashoffset = String(len * (1 - p));
  }
  function grain(canvas, t, alpha = 0.06) {
    const c = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
    const img = c.createImageData(w, h), r = rand(Math.floor(t * 24) + 1), a = Math.round(alpha * 255);
    for (let i = 0; i < img.data.length; i += 4) { const v = r() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = a; }
    c.putImageData(img, 0, 0);
  }

  window.M = { clamp, lerp, ease, prog, rand, kinetic, cam, trans, counter, draw, grain };
})();
