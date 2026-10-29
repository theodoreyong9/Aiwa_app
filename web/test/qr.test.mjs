import { test } from 'node:test';
import assert from 'node:assert/strict';
import QRCode from 'qrcode';
import { decodeFrame } from '../src/qr.js';

// The decoder the camera scan uses, on a QR code made by the library that draws them, as pixels (what a canvas holds).
function pixelsOf(text, { scale = 4, margin = 4, errorCorrectionLevel = 'L' } = {}) {
  const { size, data } = QRCode.create(text, { errorCorrectionLevel }).modules;
  const side = (size + 2 * margin) * scale;
  const pixels = new Uint8ClampedArray(side * side * 4).fill(255);
  for (let row = 0; row < size; row++) {
    for (let col = 0; col < size; col++) {
      if (!data[row * size + col]) continue;
      for (let y = 0; y < scale; y++) for (let x = 0; x < scale; x++) {
        const at = (((margin + row) * scale + y) * side + (margin + col) * scale + x) * 4;
        pixels[at] = pixels[at + 1] = pixels[at + 2] = 0;
      }
    }
  }
  return { pixels, side };
}

test('a code is read back from its pixels, short or as long as a duel code', async () => {
  const long = `duel1.${Buffer.from(Array.from({ length: 700 }, (_, i) => (i * 37 + 11) % 251)).toString('base64url')}`;
  for (const text of ['hello', long]) {
    const { pixels, side } = pixelsOf(text);
    assert.equal(await decodeFrame(pixels, side, side), text);
  }
});

test('a frame with no code gives null', async () => {
  assert.equal(await decodeFrame(new Uint8ClampedArray(200 * 200 * 4).fill(128), 200, 200), null);
});
