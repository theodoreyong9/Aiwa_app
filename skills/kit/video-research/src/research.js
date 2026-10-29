// From the words of a brief to the campaigns of the catalogue that come closest: a plain keyword score over the title, the brand, the idea, the
// categories, the industry and the kind of media. It does not understand the brief; it brings back a few campaigns whose ideas and credits a session
// reads (and cites) before writing its own script. The result carries the page address and the film address, never the film.
const STOP = new Set('the a an of and or for to in on with by is are be it this that from at as de la le les un une des du et ou pour dans sur avec par est sont ce cette qui que au aux en ma mon mes ta ton tes sa son ses vidéo video film promotionnelle promo faire fais'.split(' '));
// A brief is often written in French and the catalogue is in English: the common words of a brief are carried over (not a translation, a bridge).
const BRIDGE = { vin: 'wine', vins: 'wine', biere: 'beer', alcool: 'alcohol', voiture: 'car auto automotive', auto: 'car automotive', jeu: 'game gaming', jeux: 'games gaming', mode: 'fashion', beaute: 'beauty', nourriture: 'food', cuisine: 'food', restaurant: 'food restaurant', banque: 'bank finance', assurance: 'insurance', sante: 'health healthcare', voyage: 'travel tourism', tourisme: 'tourism travel', sport: 'sport sports', musique: 'music', application: 'app mobile', appli: 'app mobile', mobile: 'mobile app', telephone: 'phone mobile', technologie: 'technology tech', enfants: 'kids children', enfant: 'kid children', animaux: 'pet pets animals', chien: 'dog pet', chat: 'cat pet', cafe: 'coffee', the: 'tea', eau: 'water', energie: 'energy', maison: 'home', immobilier: 'real estate property', education: 'education school', ecole: 'school education', emploi: 'job recruitment', recrutement: 'recruitment job', caritatif: 'charity nonprofit', association: 'charity nonprofit', ecologie: 'sustainability environment', environnement: 'environment sustainability', australien: 'australian australia', francais: 'french france', humour: 'humor comedy funny', drole: 'funny comedy humor', emotion: 'emotional', luxe: 'luxury', mariage: 'wedding', livre: 'book', film: 'film', serie: 'series', paiement: 'payment finance', crypto: 'crypto blockchain finance' };
const words0 = (s) => (String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-z0-9]{3,}/g) || []).filter((w) => !STOP.has(w));

export function research(rows, brief, { limit = 8, industry = null, medium = null } = {}) {
  // a brief is a few CONCEPTS (each word of it, with the English words it is bridged to): a campaign scores by how many concepts it answers, and by the
  // field in which each is found (title and brand count more than the categories), so that one word repeated everywhere does not beat three concepts met.
  const concepts = [...new Set(words0(brief))].map((w) => new Set([w, ...(BRIDGE[w] ? BRIDGE[w].split(' ') : [])]));
  const scored = rows.map((r) => {
    if (industry && !(r.industry || '').toLowerCase().includes(industry.toLowerCase())) return null;
    if (medium && !(r.media || []).some((m) => m.toLowerCase().includes(medium.toLowerCase()))) return null;
    const fields = [[r.title, 3], [r.brand, 3], [r.campaign, 2], [r.idea, 2], [(r.categories || []).join(' '), 1.5], [r.industry, 2], [(r.media || []).join(' '), 1]].map(([t, w]) => [new Set(words0(t)), w]);
    let score = 0, met = 0;
    for (const c of concepts) {
      let best = 0;
      for (const [have, w] of fields) for (const t of c) if (have.has(t)) best = Math.max(best, w);
      if (best) { met++; score += best; }
    }
    return met ? { score: score + met * 2, r } : null;
  }).filter(Boolean).sort((a, b) => b.score - a.score || (b.r.year ?? 0) - (a.r.year ?? 0)).slice(0, limit);
  return scored.map(({ score, r }) => ({
    score, title: r.title, brand: r.brand, agency: r.agency, country: r.country, year: r.year, media: r.media, industry: r.industry, idea: r.idea, page: r.url,
    film: r.video?.youtube?.[0] ? `https://www.youtube.com/watch?v=${r.video.youtube[0]}` : r.video?.vimeo?.[0] ? `https://vimeo.com/${r.video.vimeo[0]}` : null,
  }));
}

export function stats(rows) {
  const count = (f) => Object.entries(rows.reduce((o, r) => { for (const k of [].concat(f(r) ?? [])) o[k] = (o[k] || 0) + 1; return o; }, {})).sort((a, b) => b[1] - a[1]).slice(0, 12);
  return { total: rows.length, industries: count((r) => r.industry), media: count((r) => r.media), years: count((r) => r.year), countries: count((r) => r.country) };
}
