// The mood of a moment (what the idea FEELS like) decides how everything around it is done: the colour, the camera, the sound, the light. One vector per beat, five numbers
// from 0 to 1; every number below is a rule that can be read, argued with and changed, not a taste hidden in a script.
//   energy   0 calm … 1 frantic        warmth   0 cool … 1 warm            scale    0 intimate … 1 cosmic
//   tension  0 resolved … 1 unresolved  awe      0 plain … 1 wonder
export const MOODS = ['energy', 'warmth', 'scale', 'tension', 'awe'];
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
export const norm = (m = {}) => Object.fromEntries(MOODS.map((k) => [k, clamp(Number.isFinite(m[k]) ? m[k] : 0.5)]));

/** The grade of the place: a cool, dark, intimate moment is not graded like a warm, wide, bright one. */
export function gradeOf(m) {
  m = norm(m);
  return {
    brightness: +lerp(0.42, 0.74, clamp(0.35 + m.scale * 0.35 + m.warmth * 0.25)).toFixed(3),   // wide and warm places stay lighter; the intimate ones fall into the dark (the sculptures are light: the place must stay darker than they are)
    contrast: +lerp(1.0, 1.32, m.tension).toFixed(3),
    saturate: +lerp(0.55, 1.05, clamp(m.warmth * 0.6 + m.awe * 0.5)).toFixed(3),
    hue: Math.round(lerp(14, -14, m.warmth)),                                                    // degrees: cool tilts to blue, warm to amber
    tint: [Math.round(lerp(70, 255, m.warmth)), Math.round(lerp(120, 150, m.warmth)), Math.round(lerp(255, 70, m.warmth))],
    tintAlpha: +lerp(0.10, 0.24, m.awe).toFixed(3),
    vignette: +lerp(0.38, 0.62, 1 - m.scale).toFixed(3),
    blur: +lerp(0, 2.2, 1 - m.scale).toFixed(2),                                                  // px of depth of field on the place: the closer the idea, the softer the place behind it
  };
}

/** How the camera behaves: it moves with the energy and breathes with the scale. */
export function cameraOf(m) {
  m = norm(m);
  return {
    swing: +lerp(0.55, 1.35, m.energy).toFixed(3),            // the sculpture's own yaw swing and the keys of the engine's moves are multiplied by this
    roll: +lerp(0.01, 0.07, m.energy * 0.7 + m.tension * 0.3).toFixed(3),
    parallax: +lerp(1.25, 0.45, m.scale).toFixed(3),            // an intimate place shifts a lot behind the idea; a cosmic one hardly moves
    zoom: +lerp(0.02, 0.10, m.energy).toFixed(3),
    shake: +lerp(0, 2.2, Math.max(0, m.energy - 0.6) / 0.4).toFixed(2),
  };
}

/** The time a passage from one place to the next takes: the more energy, the shorter. Seconds. */
export const transitionSeconds = (from, to) => +lerp(1.45, 0.55, clamp((norm(from).energy + norm(to).energy) / 2)).toFixed(2);

/** The sound of the moment. ambience: the level of the bed of the place; hits: how many accents a second of it carries; music: the gain of the track. */
export function soundOf(m) {
  m = norm(m);
  return { ambience: +lerp(0.10, 0.32, m.scale).toFixed(3), hits: +lerp(0.4, 1.8, m.energy).toFixed(2), music: +lerp(0.78, 1.0, m.energy * 0.6 + m.awe * 0.4).toFixed(3), brightness: +lerp(0.25, 0.9, m.warmth * 0.5 + m.awe * 0.5).toFixed(3) };
}

/** The sculpture: how bright it burns and how many threads it shows. */
export const sculptureOf = (m) => { m = norm(m); return { glow: +lerp(0.8, 1.35, m.awe).toFixed(3), threads: +lerp(0.7, 1.15, m.tension).toFixed(3), size: +lerp(0.9, 1.15, m.scale).toFixed(3) }; };
