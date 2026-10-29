// Incompetech (Kevin MacLeod) publishes the whole list of its pieces as one file, pieces.json, with the tempo, the feel, the instruments and a description of
// each. Every piece is under Creative Commons Attribution (the credit is asked for, or a paid licence without credit); the site's robots.txt allows /music.
import { energyOf, seconds, slug } from './track.js';

export const PIECES_URL = 'https://incompetech.com/music/royalty-free/pieces.json';
const FILES = 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/';

export function parsePieces(json) {
  const list = Array.isArray(json) ? json : [];
  return list.filter((p) => p && p.title && p.filename).map((p) => {
    const bpm = Number(p.bpm) || null;
    const tags = String(p.feel || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    return {
      id: `inc-${slug(p.title)}`, title: p.title, artist: 'Kevin MacLeod', source: 'incompetech', licence: 'cc-by-4.0',
      page: 'https://incompetech.com/music/royalty-free/faq.html', file: FILES + encodeURIComponent(p.filename),
      seconds: seconds(p.length), bpm, bpm_basis: bpm ? 'declared' : null, tags, instruments: String(p.instruments || '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean),
      description: String(p.description || '').slice(0, 280), uploaded: p.uploaded || null,
      energy: energyOf(tags, bpm), energy_basis: 'tags+bpm',
    };
  });
}
