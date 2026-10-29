#!/usr/bin/env node
// video-kit render <page.html> <frames-dir> --seconds=25 [--fps=30 --width=1080 --height=1920 --workers=4]
// video-kit assemble <frames-dir> <out.mp4> [--audio=music.mp3 --voice=vo.wav --duck=strong|light --fps=30]   (--voice: the music ducks under it; light = music stays forward)
// (assemble also takes --grade=cinematic --bloom=0.2 --grain=0.03 --vignette=0.25: one look on the whole film, in the same encode)
// (assemble also takes --clips=clips.json: shots made elsewhere, laid over the frames; see the header of src/assemble.js)
// video-kit transform <in> <out.mp4> [--grade=cinematic --bloom=0.3 --grain=0.05 --vignette=0.35 --speed=1 --crop=16:9]   (the look of the film, the same on every shot)
// video-kit shotlist <storyboard.json> <out-dir>   (the shots to make, what to ask a generator for, and the clips.json for assemble; exit 1 when something is missing)
// video-kit capture <url-or-file> <out.png> [--width=1440 --height=810]   (the whole page as one tall picture, for the "page" layer)
// video-kit check <video.mp4> [--seconds=25 --width=1080 --height=1920]   (exit code 1 when a blocking error is found)
import { readFileSync } from 'node:fs';
import { renderFrames } from './render.js';
import { assemble } from './assemble.js';
import { checkVideo } from './qc.js';
import { capturePage } from './capture.js';
import { buildShotlist } from './shotlist.js';
import { transform } from './transform.js';
import { writeFileSync, mkdirSync } from 'node:fs';

const args = process.argv.slice(2);
const flags = Object.fromEntries(args.filter((a) => a.startsWith('--')).map((a) => { const [k, v] = a.slice(2).split('='); return [k, v ?? true]; }));
const [command, a, b] = args.filter((x) => !x.startsWith('--'));
const num = (v, d) => (v === undefined ? d : Number(v));
try {
  if (command === 'render') console.log(JSON.stringify(await renderFrames({ page: a, outDir: b, seconds: num(flags.seconds), fps: num(flags.fps, 30), width: num(flags.width, 1080), height: num(flags.height, 1920), workers: num(flags.workers, 4), transparent: !!flags.transparent })));
  else if (command === 'assemble') console.log(assemble({ framesDir: a, out: b, audio: flags.audio || null, voice: flags.voice || null, duck: flags.duck || 'strong', clips: flags.clips ? JSON.parse(readFileSync(flags.clips, 'utf8')) : [], look: (flags.grade || flags.bloom || flags.grain || flags.vignette) ? { grade: flags.grade || 'clean', bloom: num(flags.bloom, 0), grain: num(flags.grain, 0), vignette: num(flags.vignette, 0) } : null, fps: num(flags.fps, 30), crf: num(flags.crf, 23) }));
  else if (command === 'capture') console.log(JSON.stringify(await capturePage({ source: a, out: b, width: num(flags.width, 1440), height: num(flags.height, 810) })));
  else if (command === 'transform') console.log(transform({ input: a, out: b, grade: flags.grade || 'clean', bloom: num(flags.bloom, 0), grain: num(flags.grain, 0), vignette: num(flags.vignette, 0), speed: num(flags.speed, 1), crop: flags.crop || null, fps: num(flags.fps, 30), inputFps: num(flags['input-fps'], null), interpolate: !!flags.interpolate, scale: flags.scale || null }));
  else if (command === 'shotlist') { const r = buildShotlist(JSON.parse(readFileSync(a, 'utf8'))); mkdirSync(b, { recursive: true }); writeFileSync(`${b}/shotlist.md`, r.markdown); writeFileSync(`${b}/clips.json`, JSON.stringify(r.clips, null, 1)); console.log(JSON.stringify({ shots: r.clips.length, seconds: r.total, problems: r.problems })); process.exit(r.problems.length ? 1 : 0); }
  else if (command === 'check') { const r = checkVideo(a, { seconds: num(flags.seconds, null), width: num(flags.width, null), height: num(flags.height, null), fps: num(flags.fps, null) }); console.log(JSON.stringify(r, null, 2)); process.exit(r.ok ? 0 : 1); }
  else console.log('video-kit render | assemble | check (see the header of src/cli.js)');
} catch (err) { console.error(String(err.message ?? err)); process.exit(2); }
