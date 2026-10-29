// The cinematic engine: turns a list of SHOTS into window.render(t). Load motion.js first, then define window.THEME and window.SHOTS, then
// load this file (see cinematic.html). Everything is a pure function of t.
//
// THEME: { bg, ink, muted, accent, accent2, font, grain (0..0.15), vignette (0..0.8) }
//
// SHOT: { seconds, bg, transition: { type, seconds }, layers: [ … ] }      (the transition describes how the shot comes IN)
//   bg: { type: 'solid', color } | { type: 'gradient', colors: [a, b], angle, drift } | { type: 'blobs', colors: [a, b, c] }
//   transition.type: fade push push-up wipe zoom iris slice flash        shots overlap during the transition
//
// LAYER (x, y = centre in % of the frame, w = width in % of the frame, each one number or [portrait, landscape]; at = seconds from the start of the shot):
//   { type: 'text',  text, x, y, w, size (vmin, or [portrait, landscape]), weight, color, align, font, upper, spacing, leading,
//                    mode: 'words'|'chars'|'lines', effect: 'mask'|'rise'|'blur'|'scale'|'drop'|'type'|'fade', at, dur, stagger,
//                    out: { at, effect }, accent: { word: colour } }
//   { type: 'image', src, x, y, w, frame: 'none'|'browser'|'phone', radius, enter: 'rise'|'scale'|'fade'|'left'|'right', at, dur,
//                    cam: { from: { x, y, s, r }, to: { … }, at, dur }, out: { at } }
//   { type: 'page',  src (a tall picture from `video-kit capture`), pageW, viewH, scroll: [fromPx, toPx], scrollAt, scrollDur, frame, x, y, w, enter, at, dur, cam }
//                    (the real page, scrolled as a function of time)
//   { type: 'html',  markup, css, id, design: [w, h] px, x, y, w, enter, at, dur, cam, out, tick(root, t, M) }   (any HTML at a design size, scaled; tick animates it)
//   { type: 'shape', kind: 'bar'|'circle'|'rect', x, y, w, h (vmin), color, radius, at, dur, from: { s, o, w }, out: { at } }
//   { type: 'counter', from, to, at, dur, decimals, prefix, suffix, sep, x, y, size, weight, color }
//   { type: 'svg', markup, x, y, w, at, dur, stroke, width }       (paths with class "d" draw themselves)
(function () {
  const M = window.M;
  const THEME = Object.assign({ bg: '#0b0b12', ink: '#f4f4f8', muted: '#a9a9bd', accent: '#cc785c', accent2: '#6c8cff', font: '"Liberation Sans", Arial, sans-serif', grain: 0.05, vignette: 0.4 }, window.THEME || {});
  const SHOTS = window.SHOTS || [];
  const W = innerWidth, H = innerHeight, vmin = Math.min(W, H) / 100, portrait = H / W >= 1.2;
  const stage = document.getElementById('stage');
  stage.style.cssText += `;position:relative;width:100vw;height:100vh;overflow:hidden;background:${THEME.bg};color:${THEME.ink};font-family:${THEME.font}`;
  const loading = [];
  const pick = (v, d) => (Array.isArray(v) ? (portrait ? v[0] : v[1]) : v ?? d);       // [portrait, landscape] or one value for both
  const size = (s, d) => pick(s, d) * vmin;
  const px = (v) => `${v}px`;

  function pos(l, extra = '') {
    const d = document.createElement('div');
    d.style.cssText = `position:absolute;left:${pick(l.x, 50)}%;top:${pick(l.y, 50)}%;transform:translate(-50%,-50%);${l.w ? `width:${pick(l.w)}%;` : ''}${extra}`;
    return d;
  }
  function enterStyle(el, kind, p) {
    const k = 1 - p;
    if (!kind || kind === 'none') { el.style.opacity = p > 0 ? 1 : 0; return; }
    el.style.opacity = p;
    el.style.transform = kind === 'scale' ? `scale(${0.82 + 0.18 * p})` : kind === 'left' ? `translateX(${-k * 14}vmin)` : kind === 'right' ? `translateX(${k * 14}vmin)` : kind === 'fade' ? 'none' : `translateY(${k * 8}vmin) scale(${0.97 + 0.03 * p})`;
  }
  function frame(kind, wPx, aspect, radius) {
    const f = document.createElement('div'), inner = document.createElement('div');
    const r = radius ?? (kind === 'phone' ? 5 : 1.4) * vmin;
    if (kind === 'browser') {
      f.style.cssText = `border-radius:${r}px;background:#16161e;box-shadow:0 ${3 * vmin}px ${9 * vmin}px rgba(0,0,0,.55);overflow:hidden;border:1px solid rgba(255,255,255,.08)`;
      const bar = document.createElement('div'); bar.style.cssText = `height:${3.2 * vmin}px;display:flex;align-items:center;gap:${0.8 * vmin}px;padding:0 ${1.4 * vmin}px`;
      for (const c of ['#ff5f57', '#febc2e', '#28c840']) { const dot = document.createElement('i'); dot.style.cssText = `width:${1.1 * vmin}px;height:${1.1 * vmin}px;border-radius:50%;background:${c}`; bar.append(dot); }
      f.append(bar);
    } else if (kind === 'phone') {
      f.style.cssText = `border-radius:${r}px;background:#0c0c10;border:${0.9 * vmin}px solid #26262e;box-shadow:0 ${3 * vmin}px ${9 * vmin}px rgba(0,0,0,.55);overflow:hidden`;
    } else {
      f.style.cssText = `border-radius:${r}px;overflow:hidden;box-shadow:0 ${3 * vmin}px ${9 * vmin}px rgba(0,0,0,.5)`;
    }
    inner.style.cssText = `position:relative;width:100%;aspect-ratio:${aspect};overflow:hidden;background:#000`;
    f.append(inner);
    return { f, inner };
  }
  function camTimes(l, shotSeconds) {
    const c = l.cam; if (!c) return null;
    const at = c.at ?? l.at ?? 0;
    return { at, dur: c.dur ?? Math.max(0.1, shotSeconds - at) };
  }

  const builders = {
    text(l, shot) {
      const outer = pos(Object.assign({ w: 86 }, l), 'text-align:' + (l.align || 'center'));
      const host = document.createElement('div');
      host.style.cssText = `font-size:${px(size(l.size, 7))};font-weight:${l.weight || 800};color:${l.color || THEME.ink};line-height:${l.leading || 1.04};letter-spacing:${l.spacing ?? -0.02}em;${l.upper ? 'text-transform:uppercase;' : ''}${l.font ? `font-family:${l.font};` : ''}text-wrap:balance`;
      outer.append(host);
      const k = M.kinetic(host, l.text, { mode: l.mode, effect: l.effect, at: l.at ?? 0, dur: l.dur, stagger: l.stagger, out: l.out, accent: l.accent });
      return { el: outer, update: (t) => k.set(t) };
    },
    image(l, shot) {
      const outer = pos(l); const anim = document.createElement('div'); outer.append(anim);
      const img = new Image(); img.src = l.src;
      const framed = l.frame && l.frame !== 'none';
      let camTarget = img;
      const aspectOf = () => (img.naturalWidth && img.naturalHeight ? `${img.naturalWidth}/${img.naturalHeight}` : '16/9');
      if (framed) {
        const fr = frame(l.frame, 0, '16/9', l.radius); fr.inner.append(img);
        img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top';
        anim.append(fr.f); camTarget = fr.f;
        loading.push(img.decode().then(() => { fr.inner.style.aspectRatio = aspectOf(); }).catch(() => {}));
      } else {
        img.style.cssText = `display:block;width:100%;border-radius:${px(l.radius ?? 1.2 * vmin)};box-shadow:0 ${3 * vmin}px ${9 * vmin}px rgba(0,0,0,.5)`;
        anim.append(img);
        loading.push(img.decode().catch(() => {}));
      }
      const ct = camTimes(l, shot.seconds);
      return {
        el: outer,
        update(t) {
          enterStyle(anim, l.enter || 'rise', M.prog(t, l.at ?? 0, l.dur ?? 0.7, M.ease.outExpo));
          if (ct) M.cam(camTarget, l.cam.from, l.cam.to, M.prog(t, ct.at, ct.dur, M.ease.inOutSine));
          if (l.out) anim.style.opacity = Math.min(Number(anim.style.opacity), 1 - M.prog(t, l.out.at, 0.35, M.ease.inOutCubic));
        },
      };
    },
    page(l, shot) {
      // The real page, as a tall picture made by `video-kit capture` (the page laid out in a viewport of its own width and height, then
      // photographed in full: its viewport units, its reveal-on-scroll and its fonts are as the visitor sees them), scrolled as a function of time.
      const outer = pos(l); const anim = document.createElement('div'); outer.append(anim);
      const pageW = l.pageW || 1440, viewH = l.viewH || Math.round(pageW * 9 / 16);
      const fr = frame(l.frame || 'browser', 0, `${pageW}/${viewH}`, l.radius); anim.append(fr.f);
      const img = new Image(); img.src = l.src; img.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:auto;will-change:transform';
      fr.inner.append(img);
      loading.push(img.decode().catch(() => {}));
      const ct = camTimes(l, shot.seconds);
      return {
        el: outer,
        update(t) {
          const sc = fr.inner.clientWidth / pageW || 1;
          const sp = M.prog(t, l.scrollAt ?? l.at ?? 0, l.scrollDur ?? shot.seconds, M.ease.inOutCubic);
          const [a, b] = l.scroll || [0, 0];
          img.style.transform = `translateY(${-(a + (b - a) * sp) * sc}px)`;
          enterStyle(anim, l.enter || 'rise', M.prog(t, l.at ?? 0, l.dur ?? 0.7, M.ease.outExpo));
          if (ct) { const op = anim.style.opacity; M.cam(fr.f, l.cam.from, l.cam.to, M.prog(t, ct.at, ct.dur, M.ease.inOutSine)); anim.style.opacity = op; }
        },
      };
    },
    html(l, shot) {
      // Any HTML, drawn at a design size [width, height] in pixels and scaled to the layer's width: a widget, a card, a list. `css` is added to the page
      // once; `tick(root, t, M)` runs at every frame with the local time, to animate what is inside (a pure function of t). Avoid emoji (a session may
      // have no emoji font): draw icons as inline SVG.
      const [dw, dh] = l.design || [1000, 600];
      const wPx = pick(l.w, 50) / 100 * W, sc = wPx / dw;
      const outer = pos(l); outer.style.width = px(wPx); outer.style.height = px(dh * sc);
      const anim = document.createElement('div'); anim.style.cssText = 'position:absolute;inset:0';
      const box = document.createElement('div'); box.style.cssText = 'position:absolute;inset:0';
      const inner = document.createElement('div'); inner.style.cssText = `position:absolute;left:0;top:0;width:${dw}px;height:${dh}px;transform-origin:0 0;transform:scale(${sc})`;
      inner.innerHTML = l.markup;
      if (l.css && !document.getElementById('css-' + (l.id || l.css.length))) { const st = document.createElement('style'); st.id = 'css-' + (l.id || l.css.length); st.textContent = l.css; document.head.append(st); }
      box.append(inner); anim.append(box); outer.append(anim);
      const ct = camTimes(l, shot.seconds);
      return {
        el: outer,
        update(t) {
          enterStyle(anim, l.enter || 'rise', M.prog(t, l.at ?? 0, l.dur ?? 0.7, M.ease.outExpo));
          if (ct) M.cam(box, l.cam.from, l.cam.to, M.prog(t, ct.at, ct.dur, M.ease.inOutSine));
          if (l.out) anim.style.opacity = Math.min(Number(anim.style.opacity), 1 - M.prog(t, l.out.at, 0.35, M.ease.inOutCubic));
          if (l.tick) l.tick(inner, t, M);
        },
      };
    },
    shape(l) {
      const outer = pos(l); const d = document.createElement('div'); outer.append(d);
      const w = pick(l.w, 30) * vmin, h = pick(l.h, 0.6) * vmin;
      d.style.cssText = `width:${l.kind === 'circle' ? h : w}px;height:${h}px;background:${l.color || THEME.accent};border-radius:${l.kind === 'circle' ? '50%' : px((l.radius ?? 0.3) * vmin)};transform-origin:${l.origin || 'left center'}`;
      if (l.kind === 'circle') outer.style.transformOrigin = 'center';
      return {
        el: outer,
        update(t) {
          const p = M.prog(t, l.at ?? 0, l.dur ?? 0.6, M.ease.outExpo), from = l.from || {};
          const o = from.o ?? 0, s = from.s ?? 0;
          d.style.opacity = o + (1 - o) * p;
          d.style.transform = l.kind === 'bar' ? `scaleX(${s + (1 - s) * p})` : `scale(${s + (1 - s) * p})`;
          if (l.out) d.style.opacity = d.style.opacity * (1 - M.prog(t, l.out.at, 0.3, M.ease.inOutCubic));
        },
      };
    },
    counter(l) {
      const outer = pos(l, 'text-align:center'); const d = document.createElement('div');
      d.style.cssText = `font-size:${px(size(l.size, 12))};font-weight:${l.weight || 800};color:${l.color || THEME.ink};font-variant-numeric:tabular-nums;letter-spacing:-.02em`;
      outer.append(d);
      return { el: outer, update(t) { const p = M.prog(t, l.at ?? 0, l.dur ?? 1.4, M.ease.outExpo); M.counter(d, l.from ?? 0, l.to ?? 100, p, l); d.style.opacity = t >= (l.at ?? 0) ? 1 : 0; } };
    },
    svg(l) {
      const outer = pos(l); outer.innerHTML = l.markup;
      const paths = [...outer.querySelectorAll('.d')];
      paths.forEach((p) => { p.style.fill = 'none'; p.style.stroke = l.stroke || THEME.accent; p.style.strokeWidth = String(l.width || 3); p.style.strokeLinecap = 'round'; });
      return { el: outer, update(t) { const p = M.prog(t, l.at ?? 0, l.dur ?? 1.2, M.ease.inOutCubic); paths.forEach((el, i) => M.draw(el, M.clamp(p * 1.2 - i * 0.1))); } };
    },
  };

  function background(b = {}) {
    const d = document.createElement('div'); d.style.cssText = 'position:absolute;inset:0';
    const c = b.colors || [THEME.bg, THEME.bg];
    if (b.type === 'gradient') {
      return { el: d, update: (t) => { const a = (b.angle ?? 160) + (b.drift ? Math.sin(t * 0.5) * 18 : 0); d.style.background = `linear-gradient(${a}deg, ${c[0]}, ${c[1]})`; } };
    }
    if (b.type === 'blobs') {
      return { el: d, update: (t) => {
        const p = (i, k) => 50 + 34 * Math.sin(t * (0.23 + i * 0.11) + i * 2.1 + k);
        d.style.background = [0, 1, 2].map((i) => `radial-gradient(60% 60% at ${p(i, 0)}% ${p(i, 1.7)}%, ${c[i % c.length]}, transparent 70%)`).join(',') + `, ${b.base || THEME.bg}`;
      } };
    }
    d.style.background = b.color || THEME.bg;
    return { el: d, update() {} };
  }

  // ---- build ------------------------------------------------------------------------------------------------------------------------
  let start = 0;
  const shots = SHOTS.map((s, i) => {
    const tr = i === 0 ? { type: 'fade', seconds: 0 } : Object.assign({ type: 'fade', seconds: 0.45 }, s.transition || {});
    if (i > 0) start = start - tr.seconds + SHOTS[i - 1].seconds;
    const el = document.createElement('div'); el.style.cssText = `position:absolute;inset:0;overflow:hidden;z-index:${i + 1};display:none`;
    const bg = background(s.bg); el.append(bg.el);
    const layers = (s.layers || []).map((l) => { const b = builders[l.type]; if (!b) throw new Error(`unknown layer type "${l.type}"`); const built = b(l, s); el.append(built.el); return built; });
    stage.append(el);
    return { s, el, bg, layers, t0: start, t1: start + s.seconds, tr };
  });
  const total = shots.length ? shots[shots.length - 1].t1 : 0;
  window.TIMELINE = shots.map((x, i) => ({ i, t0: x.t0, t1: x.t1, seconds: x.s.seconds }));   // when each shot starts and ends: the clips laid over the page (3D shots) are placed with it

  const vignette = document.createElement('div'); vignette.style.cssText = `position:absolute;inset:0;z-index:900;pointer-events:none;background:radial-gradient(120% 100% at 50% 50%, transparent 55%, rgba(0,0,0,${THEME.vignette}) 100%)`;
  const grain = document.createElement('canvas'); grain.width = 320; grain.height = Math.round(320 * H / W);
  grain.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:901;pointer-events:none;mix-blend-mode:overlay';
  stage.append(vignette, grain);

  const reset = (el) => { el.style.transform = 'none'; el.style.opacity = 1; el.style.clipPath = 'none'; el.style.filter = 'none'; };
  window.TOTAL_SECONDS = total;
  window.CUTS = shots.slice(1).map((x) => +x.t0.toFixed(3));                       // the instants of change, for the sound
  window.READY = Promise.all(loading).then(() => document.fonts && document.fonts.ready);
  window.render = (t) => {
    shots.forEach((sh, i) => {
      const vis = t >= sh.t0 - 1e-6 && t <= sh.t1 + 1e-6;
      sh.el.style.display = vis ? 'block' : 'none';
      if (!vis) return;
      reset(sh.el);
      sh.bg.update(t - sh.t0);
      sh.layers.forEach((l) => l.update(t - sh.t0));
    });
    for (let i = 1; i < shots.length; i++) {
      const sh = shots[i], prev = shots[i - 1];
      if (t >= sh.t0 && t <= sh.t0 + sh.tr.seconds && sh.tr.seconds > 0) M.trans(sh.tr.type, (t - sh.t0) / sh.tr.seconds, prev.el, sh.el);
    }
    if (THEME.grain > 0) M.grain(grain, t, THEME.grain);
  };
  window.render(0);
})();
