// What a track of the register is, which licences are accepted, and the credit line each one asks for. A licence that is not in LICENCES is not usable:
// non-commercial (NC), no-derivatives (ND), share-alike (SA, which could reach the film) and anything unknown are left out, never guessed.
export const LICENCES = {
  cc0: { credit: false, name: 'CC0 1.0', url: 'https://creativecommons.org/publicdomain/zero/1.0/' },
  pd: { credit: false, name: 'domaine public', url: null },
  'cc-by-4.0': { credit: true, name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' },
  'cc-by-3.0': { credit: true, name: 'CC BY 3.0', url: 'https://creativecommons.org/licenses/by/3.0/' },
};
export const usable = (licence) => Object.prototype.hasOwnProperty.call(LICENCES, licence);

// The credit to show (small, in the film or its description), or null when the licence asks for none.
export function creditLine(t) {
  const L = LICENCES[t.licence];
  if (!L || !L.credit) return null;
  return `Musique : « ${t.title} », ${t.artist}${t.source === 'incompetech' ? ' (incompetech.com)' : ''}, ${L.name}`;
}
// A line to keep in the film's report whatever the licence (the source of the track and where its licence was read).
export const sourceLine = (t) => `${t.title} — ${t.artist} — ${LICENCES[t.licence]?.name ?? t.licence} — ${t.page}`;

// Mood words that raise or lower the energy of a track (1 calm … 5 very intense). A rough reading of the tags and the tempo, said so in `energy_basis`.
const UP = { intense: 2, aggressive: 2, driving: 1.5, action: 1.5, epic: 1.5, powerful: 1.5, energetic: 1.5, exciting: 1, heroic: 1, triumphant: 1, uplifting: 0.5, bouncy: 0.5, grooving: 0.5, tense: 0.5, battle: 1.5, dramatic: 1 };
const DOWN = { calming: -2, relaxed: -1.5, peaceful: -2, sad: -1.5, dreamy: -1, sentimental: -1, ambient: -1.5, eerie: -0.5, sleepy: -2, gentle: -1.5 };
export function energyOf(tags, bpm) {
  let e = 2.5;
  for (const t of tags || []) e += UP[t] ?? DOWN[t] ?? 0;
  if (bpm) e += Math.max(-1, Math.min(1.5, (bpm - 100) / 40));
  return Math.max(1, Math.min(5, Math.round(e)));
}
export const slug = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
export const seconds = (hms) => String(hms || '').split(':').reduce((a, p) => a * 60 + Number(p), 0) || null;
