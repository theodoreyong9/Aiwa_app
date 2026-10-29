// A code on screen, and a code read by the camera: shared by the wallet (payments) and by the door apps use (pairing).
//
// The camera is read frame by frame and decoded in JavaScript (jsQR), not with the browser's BarcodeDetector: a WebView does not
// have it on every phone, and one way to read a code is one way to test.

/** Draws `text` as a QR code into `container` (an element), as wide as `width` CSS pixels. */
export async function drawQr(container, text, width = 240) {
  const QRCode = (await import('qrcode')).default;
  const canvas = document.createElement('canvas');
  await QRCode.toCanvas(canvas, text, { width, margin: 2, errorCorrectionLevel: 'L' });
  container.replaceChildren(canvas);
}

/** True when this browser can open the camera. */
export const canScan = () => !!navigator.mediaDevices?.getUserMedia;

/** The text of the QR code in RGBA pixels (as a canvas gives them), or null. */
export async function decodeFrame(pixels, width, height) {
  const jsQR = (await import('jsqr')).default;
  return jsQR(pixels, width, height, { inversionAttempts: 'attemptBoth' })?.data ?? null;
}

/**
 * Reads one QR code with the camera, showing it in `video`. Resolves with its text, or with null when `signal` aborts or the
 * camera is not available (refused, none). Never throws: a scan that cannot happen is a code to paste instead.
 */
export async function scanQr(video, signal) {
  if (!canScan()) return null;
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }); } catch { return null; }
  if (signal?.aborted) { stream.getTracks().forEach((t) => t.stop()); return null; }
  video.srcObject = stream;
  video.hidden = false;
  try { await video.play(); } catch { /* the first frame decides */ }
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  return new Promise((resolve) => {
    let busy = false;
    let done = false;
    const stop = (value) => {
      if (done) return;
      done = true;
      clearInterval(timer);
      stream.getTracks().forEach((t) => t.stop());
      video.srcObject = null;
      video.hidden = true;
      resolve(value);
    };
    const timer = setInterval(async () => {
      if (busy || done || !video.videoWidth) return;
      busy = true;
      try {
        const scale = Math.min(1, 800 / video.videoWidth);      // a denser code needs more pixels, a bigger frame costs more time
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const text = await decodeFrame(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
        if (text) stop(text);
      } catch { /* this frame: the next */ } finally { busy = false; }
    }, 150);
    signal?.addEventListener('abort', () => stop(null), { once: true });
  });
}
