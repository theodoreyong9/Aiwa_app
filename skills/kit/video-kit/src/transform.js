// The look of a film, applied the same way to every shot (a render, a real footage, a clip from a generator), so that pieces of different origin read as one picture:
// a colour grade, a bloom on the highlights, film grain, a vignette, a speed, a crop to the format. ffmpeg only.
//
//   video-kit transform <in> <out.mp4> [--grade=clean|cinematic|teal-orange|warm|mono] [--bloom=0.3] [--grain=0.05] [--vignette=0.35] [--speed=1] [--crop=16:9] [--fps=30]
//                       [--input-fps=12 --interpolate] [--scale=1920x1080]     (a render made at 12 images a second, smoothed to 30; a render made small, brought to the size of the film)
//   in: a video, or an image sequence (shots/glasses/%05d.png, played at --fps, 30 by default). The output is a high-quality H.264 (crf 14), made to be laid with `assemble --clips`.
import { ffmpegPath, run } from './ffmpeg.js';

export const GRADES = {
  clean: '',
  cinematic: 'eq=contrast=1.08:saturation=1.06:gamma=0.97,curves=m=0/0.02 0.5/0.5 1/0.97',
  'teal-orange': 'eq=contrast=1.1:saturation=1.08,colorbalance=rs=-0.07:bs=0.09:rm=0.05:bm=-0.05:rh=0.09:bh=-0.09',
  warm: 'eq=contrast=1.05:saturation=1.04,colorbalance=rm=0.06:bm=-0.05:rh=0.05:bh=-0.04',
  mono: 'hue=s=0,eq=contrast=1.15',
};

export function transformFilter({ grade = 'clean', bloom = 0, grain = 0, vignette = 0, speed = 1, crop = null, fps = null, interpolate = false, scale = null } = {}) {
  if (!(grade in GRADES)) throw new Error(`unknown grade "${grade}" (${Object.keys(GRADES).join(', ')})`);
  if (!(speed > 0)) throw new Error('speed must be positive');
  const chain = [];
  if (speed !== 1) chain.push(`setpts=PTS/${speed}`);
  if (crop) { const [a, b] = crop.split(':').map(Number); if (!(a > 0 && b > 0)) throw new Error(`bad crop "${crop}" (like 16:9)`); chain.push(`crop='min(iw,ih*${a}/${b})':'min(ih,iw*${b}/${a})'`); }
  if (GRADES[grade]) chain.push(GRADES[grade]);
  if (fps) chain.push(interpolate ? `minterpolate=fps=${fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1` : `fps=${fps}`);
  if (scale) { const [w, h] = scale.split('x').map(Number); if (!(w > 0 && h > 0)) throw new Error(`bad scale "${scale}" (like 1920x1080)`); chain.push(`scale=${w}:${h}:flags=lanczos`); }
  chain.push('format=yuv420p');
  let g = chain.join(',');
  if (bloom > 0) g += `,split[a][b];[b]curves=all='0/0 0.78/0 1/1',gblur=sigma=22[h];[a][h]blend=all_mode=screen:all_opacity=${Math.min(1, bloom)}`;
  const post = [];
  if (vignette > 0) post.push(`vignette=angle=PI/${(5 / Math.max(0.1, vignette) / 1.75).toFixed(2)}`);
  if (grain > 0) post.push(`noise=alls=${Math.round(grain * 200)}:allf=t`);
  if (post.length) g += (bloom > 0 ? ',' : ',') + post.join(',');
  return g;
}

export function transform({ input, out, fps = 30, inputFps = null, ...look }) {
  const isSeq = /%0?\d*d/.test(input);
  const vf = transformFilter({ ...look, fps: look.fps ?? (look.interpolate ? fps : null) });
  const args = ['-y', '-loglevel', 'error', ...(isSeq ? ['-framerate', String(inputFps || fps)] : []), '-i', input, '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out];
  run(ffmpegPath(), args);
  return out;
}
