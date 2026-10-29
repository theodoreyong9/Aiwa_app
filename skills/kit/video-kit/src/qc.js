// The check of a rendered video, independent of what made it. Three levels, as the specification asks: blocking (do not deliver), warning,
// suggestion. A creative judgement is never reported as a certain technical error.
import { statSync } from 'node:fs';
import { ffmpegPath, ffprobePath, run } from './ffmpeg.js';

export function probe(file) {
  let r;
  try { r = run(ffprobePath(), ['-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', file], { allowFail: true }); } catch { r = null; }
  if (r && r.status === 0) return JSON.parse(r.stdout);
  if (r && r.status !== 0) return null;                      // ffprobe ran and could not read the file
  return probeWithFfmpeg(file);                              // no ffprobe (a session with only ffmpeg): the same facts, read from `ffmpeg -i`
}

function probeWithFfmpeg(file) {
  const text = run(ffmpegPath(), ['-hide_banner', '-i', file], { allowFail: true }).stderr;
  const d = /Duration: (\d+):(\d+):([\d.]+)/.exec(text);
  if (!d) return null;
  const streams = [];
  for (const m of text.matchAll(/Stream #\d+:\d+[^:]*: (Video|Audio): ([^\n]+)/g)) {
    if (m[1] === 'Video') {
      const size = /(\d{2,5})x(\d{2,5})/.exec(m[2]);
      const rate = /([\d.]+) fps/.exec(m[2]);
      streams.push({ codec_type: 'video', codec_name: m[2].split(/[ ,(]/)[0], width: size ? Number(size[1]) : 0, height: size ? Number(size[2]) : 0, avg_frame_rate: `${rate ? rate[1] : 0}/1` });
    } else streams.push({ codec_type: 'audio', codec_name: m[2].split(/[ ,]/)[0] });
  }
  return { streams, format: { duration: String(Number(d[1]) * 3600 + Number(d[2]) * 60 + Number(d[3])) } };
}

export function checkVideo(file, { seconds = null, width = null, height = null, fps = null, maxMegabytes = 100, minSeconds = 3 } = {}) {
  const findings = [];
  const add = (level, check, message) => findings.push({ level, check, message });
  const info = probe(file);
  if (!info) return { ok: false, findings: [{ level: 'blocking', check: 'readable', message: 'the file cannot be read by ffprobe' }] };
  const video = info.streams.find((s) => s.codec_type === 'video');
  const audio = info.streams.find((s) => s.codec_type === 'audio');
  const duration = Number(info.format.duration);
  if (!video) add('blocking', 'video-track', 'no video track');
  else {
    if (video.codec_name !== 'h264') add('warning', 'codec', `video codec is ${video.codec_name}, H.264 is what platforms accept`);
    if (width && height && (video.width !== width || video.height !== height)) add('blocking', 'resolution', `resolution is ${video.width}x${video.height}, expected ${width}x${height}`);
    const rate = (() => { const [a, b] = String(video.avg_frame_rate).split('/').map(Number); return b ? a / b : a; })();
    if (fps && Math.abs(rate - fps) > 0.5) add('warning', 'frame-rate', `frame rate is ${rate.toFixed(2)}, expected ${fps}`);
  }
  if (seconds && Math.abs(duration - seconds) > 0.5) add('blocking', 'duration', `duration is ${duration.toFixed(2)} s, expected ${seconds} s`);
  if (duration < minSeconds) add('blocking', 'duration', `duration is ${duration.toFixed(2)} s: too short to be an advertisement`);
  const megabytes = statSync(file).size / 1e6;
  if (megabytes > maxMegabytes) add('warning', 'size', `${megabytes.toFixed(1)} MB is above ${maxMegabytes} MB`);
  if (!audio) add('blocking', 'audio-track', 'no audio track');
  else {
    const v = run(ffmpegPath(), ['-hide_banner', '-nostats', '-i', file, '-vn', '-af', 'volumedetect', '-f', 'null', '-'], { allowFail: true }).stderr;
    const max = Number(/max_volume: (-?[\d.]+) dB/.exec(v)?.[1]);
    const mean = Number(/mean_volume: (-?[\d.]+) dB/.exec(v)?.[1]);
    if (Number.isFinite(max) && max < -50) add('blocking', 'audio-silent', `the audio is silent (peak ${max} dB)`);
    else if (Number.isFinite(max) && max >= -0.1) add('warning', 'audio-clipping', `the audio peaks at ${max} dB: it may clip`);
    else if (Number.isFinite(mean) && mean < -35) add('suggestion', 'audio-level', `the average level is ${mean} dB: quiet`);
  }
  // black screens: more than 0.5 s of (almost) pure black anywhere is almost never intended; a dark design is not black (its background is above the threshold)
  const black = run(ffmpegPath(), ['-hide_banner', '-nostats', '-i', file, '-an', '-vf', 'blackdetect=d=0.5:pix_th=0.03', '-f', 'null', '-'], { allowFail: true }).stderr;
  const blackSpans = [...black.matchAll(/black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)/g)].map((m) => ({ start: Number(m[1]), seconds: Number(m[3]) }));
  const tail = blackSpans.filter((b) => b.start + b.seconds >= duration - 0.6 && b.seconds <= 1.5);   // a fade to black at the very end is a choice
  for (const b of blackSpans.filter((s) => !tail.includes(s))) add('blocking', 'black-screen', `${b.seconds.toFixed(1)} s of black from ${b.start.toFixed(1)} s`);
  // frozen picture: the same image for more than 4 s
  const frozen = run(ffmpegPath(), ['-hide_banner', '-nostats', '-i', file, '-an', '-vf', 'freezedetect=n=-60dB:d=4', '-f', 'null', '-'], { allowFail: true }).stderr;
  for (const m of frozen.matchAll(/freeze_start: ([\d.]+)/g)) add('warning', 'frozen', `the picture does not move for 4 s or more from ${Number(m[1]).toFixed(1)} s`);
  // motion: the share of half-seconds in which the picture barely changes. A slideshow (a still picture under a title, a fade, the next still)
  // has about half of them still; a cut with motion in every shot has none. Measured on small, 15 fps frames, as the mean absolute difference of
  // consecutive frames. This is a hint about the idea, not a technical error: it is never blocking.
  const diff = run(ffmpegPath(), ['-hide_banner', '-nostats', '-i', file, '-an', '-vf', 'scale=320:-1,fps=15,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-', '-f', 'null', '-'], { allowFail: true }).stdout || '';
  const motion = [...diff.matchAll(/YAVG=([\d.]+)/g)].map((m) => Number(m[1]));
  if (motion.length >= 30) {
    const w = 7, windows = [];
    for (let i = 0; i + w <= motion.length; i += w) windows.push(motion.slice(i, i + w).reduce((a, b) => a + b, 0) / w);
    const still = windows.filter((x) => x < 0.15).length / windows.length;
    const sorted = [...motion].sort((a, b) => a - b), median = sorted[Math.floor(sorted.length / 2)];
    if (still > 0.4) add('warning', 'slideshow', `${Math.round(still * 100)}% of the half-seconds barely move (median motion ${median.toFixed(2)}): it looks like a slideshow. Give every shot a movement (camera, text, the page itself)`);
    else if (still > 0.25) add('suggestion', 'slideshow', `${Math.round(still * 100)}% of the half-seconds barely move: more movement would help`);
  }
  const blocking = findings.filter((f) => f.level === 'blocking').length;
  return { ok: blocking === 0, duration, width: video?.width, height: video?.height, megabytes: Math.round(megabytes * 10) / 10, findings };
}
