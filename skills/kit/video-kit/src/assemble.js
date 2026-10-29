// Frames + an optional audio file → MP4 (H.264 + AAC, faststart). No audio: a silent AAC track is still written, because some players and
// platforms refuse a file without one (the check reports a missing or silent track either way).
//   audio   the music (a generated bed or a real track: it is looped if shorter than the film, faded in and out, and cut at the end of the film)
//   voice   a voice-over: the music goes down while it speaks. duck 'strong' (default) lets the voice lead; 'light' keeps the music forward, for a film
//           of a few punchy lines over a loud track (the voice is a little louder than the music and still clear).
//   look    { grade, bloom, grain, vignette }: one look on the whole film, in the same encode (see transform.js for the values)
//   clips   shots that are not drawn by the page: a list of { file, start, end?, fps?, fit?, fade?, loop? }  (loop: a single picture, held from start to end), laid over the frames between `start` and `end` (seconds).
//           file: a video (mp4, mov…) or an image sequence (a pattern like shots/glasses/%05d.png, played at `fps`, 30 by default); a clip with an alpha channel
//           (PNG frames rendered with `render --transparent`) is laid over the picture, an opaque one replaces it. fit: 'cover' (default, fills the frame) or 'contain'.
//           fade: seconds of cross-fade at each end (default 0.25). A clip is cut to the frame, never stretched. startNumber: the number of the first image of a sequence
//           (an overlay rendered for a range of the film starts at its own frame number: `start` is then startNumber / fps).
import { readdirSync, readFileSync, openSync, readSync, closeSync, existsSync } from 'node:fs';
import { ffmpegPath, run } from './ffmpeg.js';
import { transformFilter } from './transform.js';

// the width and height of a JPEG or a PNG file, from its header (no tool needed)
export function imageSize(file) {
  const fd = openSync(file, 'r'); const head = Buffer.alloc(32); readSync(fd, head, 0, 32, 0);
  if (head.readUInt32BE(0) === 0x89504e47) { closeSync(fd); return { w: head.readUInt32BE(16), h: head.readUInt32BE(20) }; }
  closeSync(fd);
  const b = readFileSync(file);
  for (let i = 2; i < b.length - 9;) {
    if (b[i] !== 0xff) { i++; continue; }
    const m = b[i + 1];
    if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
    i += 2 + b.readUInt16BE(i + 2);
  }
  throw new Error(`${file}: not a JPEG or PNG picture`);
}

export function clipFilters(clips, base, W, H, fps) {
  // returns { inputs: [...ffmpeg input args], graph: 'filter text', last: label }
  const inputs = []; const parts = []; let last = base;
  clips.forEach((c, i) => {
    const start = Number(c.start ?? 0), fade = c.fade ?? 0.25, cfps = c.fps || fps;
    const isSeq = /%0?\d*d/.test(c.file);
    if (!isSeq && !existsSync(c.file)) throw new Error(`clip ${c.file} does not exist`);
    inputs.push(...(isSeq ? [...(c.startNumber != null ? ['-start_number', String(c.startNumber)] : []), '-framerate', String(cfps), '-i', c.file] : c.loop ? ['-loop', '1', '-framerate', String(cfps), '-i', c.file] : ['-i', c.file]));   // loop: one picture held for the whole time (a credit line, a logo)
    const fit = c.fit === 'contain' ? `scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=black@0` : `scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}`;
    const end = c.end == null ? null : Number(c.end);
    let chain = `${fit},format=rgba,setpts=PTS-STARTPTS+${start}/TB`;
    if (fade > 0) chain += `,fade=t=in:st=${start}:d=${fade}:alpha=1` + (end != null ? `,fade=t=out:st=${Math.max(start, end - fade)}:d=${fade}:alpha=1` : '');
    parts.push({ i, chain, end, start });
  });
  return { inputs, parts, last };
}

export function assemble({ framesDir, audio = null, voice = null, out, fps = 30, crf = 23, audioBitrate = '128k', duck = 'strong', fade = 1.5, clips = [], look = null }) {
  const names = readdirSync(framesDir).filter((f) => /\.(jpg|png)$/.test(f)).sort();
  const frames = names.length;
  const ext = names[0].endsWith('.png') ? 'png' : 'jpg';
  const seconds = frames / fps;
  const { w: W, h: H } = imageSize(`${framesDir}/${names[0]}`);
  const input = ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', `${framesDir}/%05d.${ext}`];
  // the inputs, in order: 0 the frames, 1 the music (or silence), 2 the voice, then one per clip
  const audioArgs = audio ? ['-stream_loop', '-1', '-i', audio] : ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo'];
  const voiceArgs = audio && voice ? ['-i', voice] : [];
  const firstClip = voiceArgs.length ? 3 : 2;
  const cf = clipFilters(clips, '[0:v]', W, H, fps);
  const music = `[1:a]afade=t=in:d=0.3,afade=t=out:st=${Math.max(0, seconds - fade).toFixed(2)}:d=${fade}`;
  const mix = duck === 'light'
    ? 'sidechaincompress=threshold=0.05:ratio=3.5:attack=10:release=300:makeup=1[d];[d][vox1]amix=inputs=2:normalize=0:weights=1 1.15,alimiter=limit=0.5:level=disabled[m]'
    : 'sidechaincompress=threshold=0.02:ratio=9:attack=15:release=450:makeup=1[d];[d][vox1]amix=inputs=2:normalize=0:weights=0.8 1.25,alimiter=limit=0.5:level=disabled[m]';
  const graph = [];
  let vlabel = '0:v';
  cf.parts.forEach((p, k) => {
    const inN = firstClip + k;
    graph.push(`[${inN}:v]${p.chain}[c${k}]`);
    const enable = p.end != null ? `enable='between(t,${p.start},${p.end})':` : `enable='gte(t,${p.start})':`;
    graph.push(`[${vlabel}][c${k}]overlay=${enable}eof_action=pass:format=auto[v${k}]`);
    vlabel = `v${k}`;
  });
  // look: the same grade, bloom, vignette and grain on the WHOLE film (drawn pages, 3D shots and footage alike), in the one encode: a film of pieces of different origin reads as one picture
  if (look) { graph.push(`[${vlabel}]${transformFilter({ ...look, fps: null, scale: null })}[vlook]`); vlabel = 'vlook'; }
  if (audio && voice) graph.push(`${music}[mus];[2:a]asplit[vox1][vox2];[mus][vox2]${mix}`);
  else if (audio) graph.push(`${music},alimiter=limit=0.5:level=disabled[m]`);
  const useGraph = graph.length > 0;
  const args = [...input, ...audioArgs, ...voiceArgs, ...cf.inputs, ...(useGraph ? ['-filter_complex', graph.join(';')] : []),
    '-map', vlabel !== '0:v' ? `[${vlabel}]` : '0:v', '-map', audio ? '[m]' : '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', String(crf), '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', audioBitrate, '-t', seconds.toFixed(3), '-movflags', '+faststart', out];
  run(ffmpegPath(), args);
  return out;
}
