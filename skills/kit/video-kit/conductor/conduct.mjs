#!/usr/bin/env node
// conduct <film.json> [--pages=a,b,c --plates=a,b --sprites=a,b] [--out=plan.json]: checks the film graph against the craft rules and writes the plan the stage and the mixer follow.
import { readFileSync, writeFileSync } from 'node:fs';
import { validate, plan } from './conductor.mjs';
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const i = a.indexOf('='); return [a.slice(2, i), a.slice(i + 1)]; }));
const [file] = args.filter((a) => !a.startsWith('--'));
const film = JSON.parse(readFileSync(file, 'utf8'));
const list = (v) => (v ? String(v).split(',') : null);
const r = validate(film, { pages: list(flags.pages), plates: list(flags.plates), sprites: list(flags.sprites) });
for (const w of r.warnings) console.log('warning:', w);
for (const e of r.errors) console.log('ERROR:', e);
if (r.errors.length) process.exit(1);
if (flags.out) { writeFileSync(flags.out, JSON.stringify(plan(film), null, 1)); console.log('plan:', flags.out); }
