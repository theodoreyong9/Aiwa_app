// Finds ffmpeg and ffprobe: FFMPEG / FFPROBE, then the PATH. (A session without them can `pip install imageio-ffmpeg` and set FFMPEG to the
// binary it ships; ffprobe is then replaced by `ffmpeg -i`, which the check handles.)
import { spawnSync } from 'node:child_process';

export const ffmpegPath = () => process.env.FFMPEG || 'ffmpeg';
export const ffprobePath = () => process.env.FFPROBE || 'ffprobe';

export function run(bin, args, { allowFail = false } = {}) {
  const r = spawnSync(bin, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.error) throw new Error(`${bin} cannot run: ${r.error.message}`);
  if (r.status !== 0 && !allowFail) throw new Error(`${bin} failed (${r.status}): ${(r.stderr || '').split('\n').slice(-6).join('\n')}`);
  return r;
}

export const hasFfmpeg = () => { try { return spawnSync(ffmpegPath(), ['-version']).status === 0; } catch { return false; } };
