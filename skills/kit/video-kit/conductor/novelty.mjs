#!/usr/bin/env node
// novelty <concept.json> [--films=docs/videos]: a film must be NEW. The record of what was already made is the folders of the films themselves: every docs/videos/<film>/concept.json.
//   concept.json: { id, language, metaphor, objects: [], places: [], transitions: [], tracking: "" }
// Errors (the film is not made): no metaphor; the language of one of the last five films; an object, a place or a transition also used by one of the last three; the tracking style of one of the last two.
// "Last" = the highest version numbers in the folder names (aiwa-v33-..., aiwa-v32...). The film being checked is not compared with itself.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith('--'));
const dirArg = (args.find((a) => a.startsWith('--films=')) || '--films=docs/videos').slice(8);
const c = JSON.parse(readFileSync(file, 'utf8'));
const norm = (s) => String(s).toLowerCase().trim();
const errors = [];
if (!c.metaphor || String(c.metaphor).trim().length < 40) errors.push('no metaphor: say in a sentence how the STRUCTURE of the subject becomes the structure of the pictures (not a theme laid on top)');
for (const k of ['language', 'tracking']) if (!c[k]) errors.push(`no ${k}`);
for (const k of ['objects', 'places', 'transitions']) if (!Array.isArray(c[k]) || !c[k].length) errors.push(`no ${k}`);
const root = resolve(dirArg);
const films = existsSync(root) ? readdirSync(root).map((d) => ({ d, f: join(root, d, 'concept.json') })).filter((x) => existsSync(x.f))
  .map((x) => ({ ...JSON.parse(readFileSync(x.f, 'utf8')), folder: x.d, n: +((x.d.match(/v(\d+)/) || [])[1] || 0) })).sort((a, b) => a.n - b.n) : [];
const others = films.filter((f) => f.id !== c.id && f.folder !== c.id);
const last = (n) => others.slice(-n);
for (const f of last(5)) if (norm(f.language) === norm(c.language || '')) errors.push(`the language "${c.language}" is the one of ${f.folder}`);
for (const f of last(3)) for (const k of ['objects', 'places', 'transitions']) {
  const used = new Set((f[k] || []).map(norm));
  for (const x of c[k] || []) if (used.has(norm(x))) errors.push(`${k}: "${x}" was already used by ${f.folder}`);
}
for (const f of last(2)) if (norm(f.tracking) === norm(c.tracking || '')) errors.push(`the tracking style "${c.tracking}" is the one of ${f.folder}`);
if (errors.length) { for (const e of errors) console.log('NOT NEW:', e); process.exit(1); }
console.log(`new: ok (compared with ${last(5).map((f) => f.folder).join(', ') || 'no earlier film'})`);
