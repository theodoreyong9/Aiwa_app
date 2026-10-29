// From the words of a brief and a few limits (credit, tempo, length, energy) to the tracks that come closest. A plain concept score over the tags, the
// description, the instruments and the title; the filters are exact. It brings back a few tracks to listen to; the agent chooses.
import { creditLine, usable } from './track.js';

const STOP = new Set('the a an of and or for to in on with by is are be it this that from at as de la le les un une des du et ou pour dans sur avec par est sont ce cette qui que au aux en musique morceau son video vidéo faire fais'.split(' '));
// The words of a brief are often French and the tags English: a bridge, not a translation.
const BRIDGE = {
  energique: 'energetic intense driving action exciting', punchy: 'driving intense action powerful', puissant: 'powerful intense epic', fort: 'intense powerful driving', rythme: 'driving grooving', rythmee: 'driving grooving',
  sombre: 'dark eerie', tendu: 'tense dark mysterious', tension: 'tense dark mysterious', triomphant: 'triumphant epic heroic uplifting', epique: 'epic heroic dramatic', heroique: 'heroic epic',
  joyeux: 'bright bouncy uplifting', gai: 'bright bouncy humorous', leger: 'bright bouncy', drole: 'humorous bouncy', calme: 'calming relaxed peaceful', doux: 'calming relaxed gentle', triste: 'sad sentimental',
  mysterieux: 'mysterious dark', futuriste: 'electronic futuristic scifi', electro: 'electronic techno', moderne: 'electronic modern', cinematique: 'cinematic epic dramatic', guitare: 'guitar', piano: 'piano', cordes: 'strings',
  action: 'action driving', combat: 'battle action intense', course: 'driving action', sport: 'action driving energetic', luxe: 'elegant smooth', nostalgique: 'nostalgic sentimental', suspense: 'tense mysterious', groove: 'grooving', danse: 'grooving dance',
};
const words0 = (s) => (String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-z0-9]{3,}/g) || []).filter((w) => !STOP.has(w));

export function search(rows, brief, { credit = 'ok', bpm = null, minSeconds = null, maxSeconds = null, energy = null, limit = 5, source = null } = {}) {
  const concepts = [...new Set(words0(brief))].map((w) => new Set([w, ...(BRIDGE[w] ? BRIDGE[w].split(' ') : [])]));
  const scored = rows.map((t) => {
    if (!usable(t.licence)) return null;
    if (credit === 'none' && creditLine(t)) return null;           // "none": only tracks that ask for no credit
    if (source && t.source !== source) return null;
    if (bpm && (!t.bpm || t.bpm < bpm[0] || t.bpm > bpm[1])) return null;
    if (minSeconds && (t.seconds ?? 0) < minSeconds) return null;
    if (maxSeconds && (t.seconds ?? 1e9) > maxSeconds) return null;
    if (energy && t.energy < energy) return null;
    const fields = [[(t.tags || []).join(' '), 3], [t.description, 1.5], [(t.instruments || []).join(' '), 1.5], [t.title, 1]].map(([s, w]) => [new Set(words0(s)), w]);
    let score = 0, met = 0;
    for (const c of concepts) {
      let best = 0;
      for (const [have, w] of fields) for (const x of c) if (have.has(x)) best = Math.max(best, w);
      if (best) { met++; score += best; }
    }
    if (concepts.length && !met) return null;
    return { score: score + met * 2 + (energy ? t.energy * 0.3 : 0) + (t.bpm ? 0.1 : 0), t };
  }).filter(Boolean).sort((a, b) => b.score - a.score || b.t.energy - a.t.energy).slice(0, limit);
  return scored.map(({ score, t }) => ({
    id: t.id, score: Math.round(score * 10) / 10, title: t.title, artist: t.artist, source: t.source, licence: t.licence, bpm: t.bpm, bpm_basis: t.bpm_basis, energy: t.energy,
    seconds: t.seconds, tags: t.tags, instruments: t.instruments, description: t.description, credit: creditLine(t), page: t.page, file: t.file,
  }));
}

export function stats(rows) {
  const count = (f) => Object.entries(rows.reduce((o, r) => { for (const k of [].concat(f(r) ?? [])) o[k] = (o[k] || 0) + 1; return o; }, {})).sort((a, b) => b[1] - a[1]).slice(0, 12);
  return { total: rows.length, sources: count((r) => r.source), licences: count((r) => r.licence), energy: count((r) => r.energy), tags: count((r) => r.tags) };
}
