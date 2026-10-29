// The brief, read as dimensions. A fixed lexicon (French and English) maps words to the measured traits and to the
// weight of each dimension for THIS brief: a brief about motion weighs motion, one about type weighs type. Nothing here
// is learned; it is a table you can read and extend.

export const FORMATS = ['site', 'pwa', 'apk', 'contract_ui'];

const LEXICON = [
  // [pattern, dimension, trait, weight]
  [/cin[eé]ma|cinematic|immersi|film|narratif|storytelling/, 'motion', 'scroll-driven', 1], [/cin[eé]ma|cinematic|immersi/, 'composition', 'fullscreen', 0.8],
  [/scroll|d[eé]fil/, 'motion', 'scroll-driven', 1], [/parallax/, 'motion', 'scroll-driven', 0.8], [/fluide|smooth|souple/, 'motion', 'smooth-scroll', 1],
  [/transition|morph/, 'motion', 'page-transition', 1], [/anim|mouvement|motion|vivant|kinetic|cin[eé]tique/, 'motion', 'reveal', 0.7], [/continu|loop|boucle|ambient/, 'motion', 'continuous', 0.8],
  [/lent|slow|calme|serein|zen/, 'motion', 'slow-easing', 0.8], [/physique|physics|gravit/, 'motion', 'physics', 1], [/particule|particle/, 'motion', 'canvas-animation', 0.9],
  [/3d|webgl|shader|immersif|sc[eè]ne/, 'rendering', '3D', 1], [/webgpu/, 'rendering', 'WebGPU', 1], [/vid[eé]o/, 'rendering', 'video', 0.8], [/svg|illustration|vectoriel/, 'rendering', 'SVG-heavy', 0.7],
  [/typo|titre|headline|oversized|g[eé]ant|massive|grand texte/, 'typography', 'oversized', 1], [/[eé]ditorial|magazine|journal|livre/, 'typography', 'serif', 0.8], [/serif|empattement/, 'typography', 'serif', 1],
  [/condens|[eé]troit|affiche|poster/, 'typography', 'condensed', 0.9], [/cin[eé]tique|kinetic|texte anim/, 'typography', 'kinetic', 1], [/majuscule|uppercase/, 'typography', 'uppercase', 0.8], [/mono|code|technique/, 'typography', 'mono', 0.7],
  [/minimal|[eé]pur|sobre|simple|clean|[aà] l'essentiel/, 'typography', 'minimal', 0.8], [/minimal|[eé]pur|sobre|clean/, 'palette', 'minimal', 1],
  [/sombre|dark|noir|nuit|nocturne/, 'palette', 'dark', 1], [/clair|light|blanc|lumineux/, 'palette', 'light', 1], [/monochrome|noir et blanc|n&b/, 'palette', 'monochrome', 1], [/vif|vivid|color[eé]|pop|satur[eé]/, 'palette', 'vivid', 1], [/pastel|doux|soft|sobre/, 'palette', 'restrained', 0.7],
  [/asym[eé]tri/, 'composition', 'asymmetric', 1], [/grille|grid|bento/, 'composition', 'grid', 1], [/plein [eé]cran|fullscreen|full screen/, 'composition', 'fullscreen', 1], [/split|deux colonnes|moiti[eé]/, 'composition', 'split-screen', 1],
  [/superpos|layer|profondeur|depth|couches/, 'composition', 'layered', 1], [/long|infini|scroll infini/, 'composition', 'long-scroll', 0.6],
  [/hover|survol|interactif|interaction|ludique|jeu/, 'interaction', 'rich-hover', 1], [/curseur|cursor/, 'interaction', 'custom-cursor', 1], [/carrousel|carousel|slider/, 'interaction', 'carousel', 1],
];
const DIMENSIONS = ['motion', 'rendering', 'typography', 'palette', 'composition', 'interaction'];
const FORMAT_WORDS = [[/\bpwa\b|progressive/, 'pwa'], [/\bapk\b|android|mobile|appli(cation)? mobile|t[eé]l[eé]phone/, 'apk'], [/contrat|contract/, 'contract_ui'], [/\bsite\b|vitrine|landing|page web|web/, 'site']];

/** @returns {{ format: string, dimensions: Record<string,number>, wanted: Array<{dimension:string, trait:string, weight:number}>, words: string[] }} */
export function plan(brief, { format } = {}) {
  const text = brief.toLowerCase();
  const wanted = new Map();
  for (const [re, dimension, trait, weight] of LEXICON) {
    if (!re.test(text)) continue;
    const key = `${dimension}:${trait}`;
    wanted.set(key, { dimension, trait, weight: Math.max(wanted.get(key)?.weight ?? 0, weight) });
  }
  const dimensions = Object.fromEntries(DIMENSIONS.map((d) => [d, 0]));
  for (const w of wanted.values()) dimensions[w.dimension] = Math.min(1, dimensions[w.dimension] + w.weight * 0.6);
  const inferred = format ?? FORMAT_WORDS.find(([re]) => re.test(text))?.[1] ?? 'site';
  return { format: inferred, dimensions, wanted: [...wanted.values()], words: [...new Set(text.match(/[a-zà-ÿ0-9]{4,}/g) ?? [])] };
}
