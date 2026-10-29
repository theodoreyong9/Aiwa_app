#!/usr/bin/env node
// Free footage of places and things, for the video kit: found and copied where the network allows it (GitHub's runners), never by the session itself.
//   footage.mjs search "<query>" [--limit=8]     NASA (public domain) and Wikimedia Commons (only CC0 / public domain / CC BY are kept) -> a line per clip
//   footage.mjs fetch <name>=<source:id>[@start-seconds] ... [--seconds=12] [--out=dir]      source = nasa:<nasa_id> | commons:<File name> | url:<https address of a video>
//                       -> out/<name>.mp4 (1920x1080, 30 images a second, no sound, the first N seconds) and out/<name>.json (where it comes from, its licence, the credit)
// Nothing here is a copy of a catalogue: every clip keeps its own address and licence next to it, and the credit to print in the film.
import { writeFileSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';

const UA = 'aiwa-footage/1 (https://github.com/theodoreyong9/Aiwa_app)';
const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const [command, ...rest] = args.filter((x) => !x.startsWith('--'));
const get = async (url, opt = {}) => { const res = await fetch(url, { headers: { 'User-Agent': UA }, redirect: 'follow', ...opt }); if (!res.ok) throw new Error(`${url}: ${res.status}`); return res; };
const KEEP = /^(cc0|public domain|pd|cc[ -]by( [0-9.]+)?|cc-by-[0-9.]+)$/i;

async function searchNasa(q, limit) {
  const j = await (await get(`https://images-api.nasa.gov/search?q=${encodeURIComponent(q)}&media_type=video`)).json();
  return (j.collection?.items || []).slice(0, limit).map((it) => { const d = it.data?.[0] || {};
    return { source: 'nasa', id: d.nasa_id, title: d.title, licence: 'NASA media (public domain, credit NASA)', seconds: null, page: `https://images.nasa.gov/details/${d.nasa_id}` }; });
}
async function searchCommons(q, limit) {
  const url = `https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=${limit * 3}&gsrsearch=${encodeURIComponent(q + ' filetype:video')}&prop=imageinfo&iiprop=url|size|mime|extmetadata|duration`;
  const j = await (await get(url)).json();
  const out = [];
  for (const p of Object.values(j.query?.pages || {})) {
    const ii = p.imageinfo?.[0]; if (!ii) continue;
    const lic = ii.extmetadata?.LicenseShortName?.value || '';
    if (!KEEP.test(lic.trim())) continue;
    out.push({ source: 'commons', id: p.title.replace(/^File:/, ''), title: p.title, licence: lic, seconds: Math.round(ii.duration || 0), width: ii.width, height: ii.height,
      author: (ii.extmetadata?.Artist?.value || '').replace(/<[^>]+>/g, '').slice(0, 80), url: ii.url, page: ii.descriptionurl });
  }
  return out.filter((x) => (x.width || 0) >= 1280).slice(0, limit);
}

async function resolve(spec) {
  const [src, ...r] = spec.split(':'); const id = r.join(':');
  if (src === 'url') return { url: id, licence: 'see source', credit: id, page: id };
  if (src === 'nasa') {
    const j = await (await get(`https://images-api.nasa.gov/asset/${encodeURIComponent(id)}`)).json();
    const files = (j.collection?.items || []).map((x) => x.href).filter((h) => /\.mp4$/i.test(h));
    const pick = files.find((h) => /~large\./.test(h)) || files.find((h) => /~medium\./.test(h)) || files.find((h) => /~orig\./.test(h)) || files[0];      // large first: the original of a NASA film can be gigabytes
    if (!pick) throw new Error(`no mp4 for nasa:${id}`);
    return { url: pick.replace(/^http:/, 'https:'), licence: 'NASA media (public domain)', credit: `NASA (${id})`, page: `https://images.nasa.gov/details/${id}` };
  }
  if (src === 'commons') {
    const j = await (await get(`https://commons.wikimedia.org/w/api.php?action=query&format=json&titles=${encodeURIComponent('File:' + id)}&prop=imageinfo&iiprop=url|extmetadata`)).json();
    const ii = Object.values(j.query.pages)[0].imageinfo?.[0]; if (!ii) throw new Error(`no file ${id}`);
    const lic = ii.extmetadata?.LicenseShortName?.value || '';
    if (!KEEP.test(lic.trim())) throw new Error(`licence not kept for ${id}: ${lic}`);
    const artist = (ii.extmetadata?.Artist?.value || '').replace(/<[^>]+>/g, '').slice(0, 80);
    return { url: ii.url, licence: lic, credit: `${artist || 'unknown'} · ${lic} · Wikimedia Commons`, page: ii.descriptionurl };
  }
  throw new Error(`unknown source ${src}`);
}

try {
  if (command === 'search') {
    const q = rest.join(' '); const limit = Number(flags.limit || 8);
    const [a, b] = await Promise.allSettled([searchNasa(q, limit), searchCommons(q, limit)]);
    for (const r of [a, b]) {
      if (r.status === 'rejected') { console.log(`! ${r.reason?.message || r.reason}`); continue; }
      for (const c of r.value) console.log(`${c.source}:${c.id} | ${c.licence} | ${c.seconds ?? '?'}s | ${c.width ? c.width + 'x' + c.height : '?'} | ${c.title}`);
    }
  } else if (command === 'fetch') {
    const out = String(flags.out || 'footage'); mkdirSync(out, { recursive: true });
    for (const item of rest) {
      const [name, specAt] = [item.slice(0, item.indexOf('=')), item.slice(item.indexOf('=') + 1)];
      const at = specAt.lastIndexOf('@'); const spec = at > 0 && /^[0-9.]+$/.test(specAt.slice(at + 1)) ? specAt.slice(0, at) : specAt; const start = spec === specAt ? 0 : Number(specAt.slice(at + 1));
      try {
        const m = await resolve(spec);
        const mp4 = join(out, `${name}.mp4`);
        // Wikimedia slows down a client that asks fast: a pause between clips, and three tries with a longer wait each time. A clip that is too small is not kept.
        let last = '';
        for (let tryN = 0; tryN < 3; tryN++) {
          if (tryN) await new Promise((r) => setTimeout(r, 25000 * tryN));
          // ffmpeg reads the address itself and only what it needs (a seek in a long film does not download the film)
          const ff = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-user_agent', UA, '-ss', String(start), '-i', m.url, '-t', String(flags.seconds || 12), '-an', '-vf', 'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30', '-c:v', 'libx264', '-crf', '20', '-preset', 'fast', '-pix_fmt', 'yuv420p', mp4], { encoding: 'utf8', timeout: 20 * 60 * 1000 });
          const size = existsSync(mp4) ? statSync(mp4).size : 0;
          if (ff.status === 0 && size > 200000) { last = ''; break; }
          if (tryN === 1) {       // a source ffmpeg cannot seek over the network (an Ogg file, for example): the file is downloaded whole, and cut here
            try {
              const raw = join(out, `${name}.src`); writeFileSync(raw, Buffer.from(await (await get(m.url)).arrayBuffer()));
              const f2 = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', String(start), '-i', raw, '-t', String(flags.seconds || 12), '-an', '-vf', 'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30', '-c:v', 'libx264', '-crf', '20', '-preset', 'fast', '-pix_fmt', 'yuv420p', mp4], { encoding: 'utf8', timeout: 20 * 60 * 1000 });
              if (f2.status === 0 && existsSync(mp4) && statSync(mp4).size > 200000) { last = ''; break; }
            } catch (e2) { last = `download: ${e2.message}`; }
          }
          last = ff.status === 0 ? `the clip is too small (${size} bytes)` : `ffmpeg: ${ff.stderr.slice(-200)}`;
        }
        if (last) throw new Error(last);
        writeFileSync(join(out, `${name}.json`), JSON.stringify({ name, spec, start, ...m }, null, 1));
        console.log(`ok ${name} <- ${spec} @${start}s (${m.licence}) ${m.credit}`);
      } catch (err) { console.log(`! ${name}: ${err.message}`); }
      await new Promise((r) => setTimeout(r, 8000));
    }
  } else { console.log('footage.mjs search "<query>" | fetch name=source:id ...'); process.exit(2); }
} catch (err) { console.error(err.message || err); process.exit(1); }
