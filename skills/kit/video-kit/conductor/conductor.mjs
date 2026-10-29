// The conductor: from the FILM GRAPH (the beats of a film, each with its idea, its mood, its place, its actors and the way it hands over to the next) to the PLAN that the
// stage and the mixer follow. It decides nothing at random and nothing by taste: every choice is a rule of mood.mjs or a check of validate().
import { norm, gradeOf, cameraOf, transitionSeconds, soundOf, sculptureOf } from './mood.mjs';

export const TRANSITIONS = ['iris', 'whip', 'dissolve', 'zoom', 'cut', 'continue', 'morph', 'rack', 'plunge', 'flow'];   // morph: one form becomes the next (the shader worlds)
const THROUGH = /^(center|point:-?[0-9.]+,-?[0-9.]+|actor:[a-z0-9_-]+|sculpture)$/;

/** Checks a film graph against the rules of the craft. Returns { errors: [], warnings: [] }: errors stop the render, warnings are said. */
export function validate(film, { pages = null, plates = null, sprites = null } = {}) {
  const errors = [], warnings = [];
  const e = (m) => errors.push(m), w = (m) => warnings.push(m);
  const beats = film.beats || [];
  if (!beats.length) { e('no beats'); return { errors, warnings }; }
  const worlds = film.worlds || {};
  let prev = null;
  beats.forEach((b, i) => {
    const id = b.id || `#${i}`;
    if (!b.idea || String(b.idea).trim().length < 4) e(`${id}: no idea (one line: what this moment says)`);
    if (pages && !pages.map(String).includes(String(b.page))) e(`${id}: the page "${b.page}" is not in the engine`);
    if (typeof b.t !== 'number') e(`${id}: no time`);
    if (prev && b.t <= prev.t) e(`${id}: starts before the one before it`);
    const wd = worlds[b.world];
    if (!wd) e(`${id}: the place "${b.world}" is not described`);
    else if (wd.kind === 'plate' && plates && !plates.includes(wd.plate)) e(`${id}: the plate "${wd.plate}" is not rendered or copied`);
    for (const a of b.actors || []) if (sprites && !sprites.includes(a.sprite)) e(`${id}: the actor sprite "${a.sprite}" is missing`);
    if (b.transition) {
      const t = b.transition;
      if (!TRANSITIONS.includes(t.kind)) e(`${id}: the transition "${t.kind}" is not one of ${TRANSITIONS.join(', ')}`);
      if (['iris', 'zoom'].includes(t.kind) && !THROUGH.test(t.through || '')) e(`${id}: a ${t.kind} needs "through" (center, point:x,y, actor:<id> or sculpture): the thing the camera goes through`);
      if (prev && prev.world === b.world && !['continue', 'cut', 'dissolve', 'morph'].includes((prev.transition || {}).kind)) w(`${id}: the same place as the beat before it, and a ${(prev.transition || {}).kind} to nowhere`);
    }
    if (prev) {
      const d = Math.abs(norm(prev.mood).energy - norm(b.mood).energy);
      if (d > 0.6 && !['whip', 'cut'].includes((prev.transition || {}).kind)) w(`${id}: the energy jumps by ${d.toFixed(2)} from the beat before it; only a whip or a cut can carry that`);
      if (prev.world !== b.world && !prev.transition) e(`${prev.id}: the place changes after it and nothing hands over (no transition)`);
    }
    prev = b;
  });
  // peaks: at most one beat of energy >= 0.85 every 8 seconds; the film lands (the last beat is calm)
  const peaks = beats.filter((b) => norm(b.mood).energy >= 0.85).map((b) => b.t);
  for (let i = 1; i < peaks.length; i++) if (peaks[i] - peaks[i - 1] < 8) w(`two peaks of energy only ${(peaks[i] - peaks[i - 1]).toFixed(1)} s apart (${peaks[i - 1].toFixed(1)} and ${peaks[i].toFixed(1)}): a peak needs room`);
  if (norm(beats[beats.length - 1].mood).energy > 0.5) w('the film does not land: the last beat is still above 0.5 of energy');
  // a place is not held for ever
  let run = null;
  for (const b of beats) { if (!run || run.world !== b.world) run = { world: b.world, t: b.t }; else if (b.t - run.t > 16) w(`the place "${b.world}" has lasted more than 16 s at ${b.t.toFixed(1)}`); }
  return { errors, warnings };
}

/** The plan: for each beat its times, its grade, its camera character, its transition (with the times of the hand-over), its actors, and the sound cues of the whole film. */
export function plan(film, total = film.total) {
  const beats = film.beats;
  const out = { title: film.title, total, fps: film.fps || 30, worlds: film.worlds, beats: [], sound: { cues: [], ambience: [], music: [] } };
  beats.forEach((b, i) => {
    const next = beats[i + 1];
    const t0 = b.t, t1 = next ? next.t : total;
    const m = norm(b.mood);
    const tr = b.transition && next ? { ...b.transition, dur: b.transition.dur || transitionSeconds(b.mood, next.mood) } : null;
    if (tr) { tr.t1 = t1; tr.t0 = Math.max(t0, t1 - tr.dur); }       // the hand-over ends when the next beat begins
    const actors = (b.actors || []).map((a) => ({ ...a, in: a.in ?? t0, dissolve: a.dissolve ?? null, reform: a.reform ?? null }));
    out.beats.push({ id: b.id, page: b.page, idea: b.idea, form: b.form || null, place: b.place || null, stage: b.stage || null, screen: b.screen || 0, say: b.say || null, image: b.image || null, t0, t1, world: b.world, mood: m, grade: gradeOf(m), camera: cameraOf(m), sculpture: sculptureOf(m), transition: tr, actors });
    const s = soundOf(m);
    // sound: the bed of the place, the track's gain, an accent on each beat (its pitch follows the warmth), the whoosh and the arrival of each hand-over, the riser of each dissolve
    out.sound.ambience.push({ t0, t1, bed: (film.worlds[b.world] || {}).ambience || 'room', level: s.ambience, brightness: s.brightness });
    out.sound.music.push({ t0, t1, gain: s.music });
    out.sound.cues.push({ t: t0 + 0.02, kind: 'accent', pitch: s.brightness, level: 0.5 + 0.4 * m.energy });
    if (tr) {
      out.sound.cues.push({ t: tr.t0, kind: tr.kind === 'whip' ? 'whip' : 'whoosh', dur: tr.dur, level: 0.55 + 0.35 * m.energy });
      out.sound.cues.push({ t: tr.t1, kind: 'arrive', level: 0.5 + 0.4 * norm(next.mood).energy });
    }
    for (const a of actors) if (a.dissolve) out.sound.cues.push({ t: a.dissolve[0], kind: 'riser', dur: a.dissolve[1] - a.dissolve[0], level: 0.5 });
  });
  return out;
}
