import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const fixture = (name) => readFileSync(join(here, 'fixtures', name), 'utf8');

/** A local web server for the fixture pages (and a listing/project page for each registry). */
export async function serve() {
  let port;
  const server = createServer((req, res) => {
    const path = new URL(req.url, 'http://x').pathname;
    const files = { '/cinematic.html': 'cinematic.html', '/plain.html': 'plain.html' };
    if (path === '/robots.txt') { res.writeHead(200, { 'content-type': 'text/plain' }); return res.end('User-agent: *\nDisallow: /private\n'); }
    const name = files[path];
    if (!name) { res.writeHead(404); return res.end('no'); }
    res.writeHead(200, { 'content-type': 'text/html' });
    res.end(fixture(name));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  port = server.address().port;
  return { port, base: `http://localhost:${port}`, baseIp: `http://127.0.0.1:${port}`, close: () => new Promise((resolve) => server.close(resolve)) };
}

/** A fetch that answers the registries' pages from the fixtures. */
export function fakeFetch(port) {
  return async (url) => {
    const u = String(url);
    const text = (t, status = 200) => ({ ok: status < 400, status, text: async () => t });
    if (u.endsWith('/robots.txt')) return text('', 404);
    if (u.includes('awwwards.com/websites/sites_of_the_day')) return text(fixture('listing-awwwards.html'));
    if (u.includes('awwwards.com/sites/maison-nuit')) return text(fixture('project-awwwards.html').replaceAll('__PORT__', port));
    if (u.includes('awwwards.com/sites/cafe-du-coin')) return text(`<html><head><meta property="og:title" content="Café du coin | Awwwards"></head><body><a href="http://127.0.0.1:${port}/plain.html?utm_source=awwwards">Visit</a></body></html>`);
    if (u.includes('csswinner.com/winners')) return text(fixture('listing-csswinner.html'));
    if (u.includes('csswinner.com/details/maison-nuit/19462')) return text(fixture('project-csswinner.html').replaceAll('__PORT__', port));
    return text('', 404);
  };
}
