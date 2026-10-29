// From the words of a brief to the assets that come closest: a plain concept score over the name, the tags, the categories, the description and the attributes; the filters
// are exact. It brings back a few assets to look at (each has a thumbnail on its page); the agent chooses.
const STOP = new Set('the a an of and or for to in on with by is are be it this that from at as de la le les un une des du et ou pour dans sur avec par est sont ce cette qui que au aux en plan scene scène modèle modele objet fais faire'.split(' '));
// The words of a brief are often French, the tags English: a bridge, not a translation.
const BRIDGE = { chaise: 'chair seating', fauteuil: 'armchair chair seating', table: 'table', canape: 'sofa couch', lampe: 'lamp lighting', lumiere: 'lighting light', bureau: 'desk office table', ordinateur: 'computer electronics', telephone: 'phone electronics', ecran: 'screen monitor electronics', voiture: 'car vehicle', arbre: 'tree nature plants', plante: 'plants nature', roche: 'rock rocks', pierre: 'stone rock', bois: 'wood', metal: 'metal', verre: 'glass', rue: 'street urban road', route: 'road street asphalt', usee: 'worn old', use: 'worn old', soleil: 'sun sunrise sunset', ville: 'urban city', nuit: 'night', jour: 'day midday', matin: 'morning', soir: 'sunset', lever: 'sunrise', coucher: 'sunset', studio: 'studio', interieur: 'indoor interior', exterieur: 'outdoor', ciel: 'sky skies', nuageux: 'overcast cloudy', ensoleille: 'clear sunny', cafe: 'cafe coffee restaurant', cuisine: 'kitchen', maison: 'house home', usine: 'industrial factory', industriel: 'industrial', vieux: 'old worn vintage', neuf: 'new clean', sol: 'floor ground', mur: 'wall', brique: 'brick', beton: 'concrete', sable: 'sand', herbe: 'grass', eau: 'water' };
const words0 = (s) => (String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-z0-9]{3,}/g) || []).filter((w) => !STOP.has(w));

export function search(rows, brief, { kind = null, maxPolycount = null, minResolution = null, limit = 6 } = {}) {
  const concepts = [...new Set(words0(brief))].map((w) => new Set([w, ...(BRIDGE[w] ? BRIDGE[w].split(' ') : [])]));
  const scored = rows.map((r) => {
    if (kind && r.kind !== kind) return null;
    if (maxPolycount && r.polycount && r.polycount > maxPolycount) return null;
    if (minResolution && (!r.max_resolution || Math.max(...r.max_resolution) < minResolution)) return null;
    const fields = [[r.name, 3], [r.tags.join(' '), 3], [r.categories.join(' '), 2], [r.attributes.join(' '), 1.5], [r.description, 1]].map(([t, w]) => [new Set(words0(t)), w]);
    let score = 0, met = 0;
    for (const c of concepts) { let best = 0; for (const [have, w] of fields) for (const t of c) if (have.has(t)) best = Math.max(best, w); if (best) { met++; score += best; } }
    if (concepts.length && !met) return null;
    return { score: score + met * 2, r };
  }).filter(Boolean).sort((a, b) => b.score - a.score || (b.r.published || '').localeCompare(a.r.published || '')).slice(0, limit);
  return scored.map(({ score, r }) => ({ id: r.id, score, kind: r.kind, name: r.name, tags: r.tags.slice(0, 10), categories: r.categories.slice(0, 5), description: r.description, polycount: r.polycount, dimensions_mm: r.dimensions, max_resolution: r.max_resolution, authors: r.authors, licence: r.licence, page: r.page }));
}
export const stats = (rows) => ({ total: rows.length, kinds: Object.entries(rows.reduce((o, r) => ((o[r.kind] = (o[r.kind] || 0) + 1), o), {})), licences: Object.entries(rows.reduce((o, r) => ((o[r.licence] = (o[r.licence] || 0) + 1), o), {})) });
