import { renderFrames } from './src/render.js';
const page = '../docs/video-vision/video.html?nophone=1&noplanets=1&noimage=1';
await renderFrames({ page, outDir: '/tmp/claude-0/-home-user/1aa30d49-56f8-5824-83e0-00fb58d4972c/scratchpad/aiwa3/n7a', seconds: 190, fps: 30, width: 1920, height: 1080, workers: 2, from: 0, to: 277 });
console.log('A-DONE');
await renderFrames({ page, outDir: '/tmp/claude-0/-home-user/1aa30d49-56f8-5824-83e0-00fb58d4972c/scratchpad/aiwa3/n7b', seconds: 190, fps: 30, width: 1920, height: 1080, workers: 2, from: 900, to: 1501 });
console.log('B-DONE');
