import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.setContent('<html><body style="margin:0;background:transparent"><div style="position:absolute;left:0;right:0;bottom:14px;text-align:center;font:500 17px Liberation Sans,Arial,sans-serif;color:rgba(255,255,255,.42);letter-spacing:.3px">Musique : « The Complex », Kevin MacLeod (incompetech.com), CC BY 4.0 · Lunettes et lumière 3D : Poly Haven, CC0</div></body></html>');
await p.screenshot({ path: process.argv[2], omitBackground: true });
await b.close();
