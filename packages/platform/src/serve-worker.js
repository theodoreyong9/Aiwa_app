// Turns "a bundle was published and can be reconstructed" into "a
// browser can actually run it": a service worker's own fetch
// handler, resolving requests under a given scope from a real,
// locally-reconstructed AIWA bundle (aiwa-core's IndexedDB-backed
// EventLog + this package's own latestBundle) instead of the network.
//
// A fresh EventLog is constructed on every single resolution, on
// purpose: a service worker's own lifecycle is "the browser kills
// and restarts it whenever it wants" — there is no long-lived instance
// to hold state in. This only works correctly because EventLog.head()
// (and therefore latestBundle) is itself correct from a fresh instance
// over a persisted backend — see aiwa-core's own README for the real
// restart bug this used to have, found while building this file.
//
// HONEST LIMIT: this resolves and serves; it does not bootstrap itself
// into existence. The very first HTML page and this worker script
// itself still have to be fetched from *somewhere* the first time —
// see this package's own README, "the bootstrap problem", deliberately
// not solved here.

import { EventLog, createIndexedDbBackend } from 'aiwa-core';
import { latestBundle } from './bundle.js';

const CONTENT_TYPES = {
  html: 'text/html; charset=utf-8',
  css: 'text/css; charset=utf-8',
  js: 'application/javascript; charset=utf-8',
  mjs: 'application/javascript; charset=utf-8',
  json: 'application/json; charset=utf-8',
  svg: 'image/svg+xml',
};

function contentTypeFor(path) {
  const ext = path.split('.').pop();
  return CONTENT_TYPES[ext] ?? 'application/octet-stream';
}

/**
 * Resolves `pathname` (already relative to whatever scope the caller
 * strips) against the latest bundle published to `domain` in
 * `log`. Returns a `Response` on a hit, or null — a honest
 * "not published (yet)" — on a miss. Never throws for an ordinary
 * not-found; `latestBundle`'s own real-fork error still propagates,
 * since that needs a caller/operator to resolve it.
 */
export async function resolveFromBundle(log, domain, pathname) {
  const bundle = await latestBundle(log, domain);
  if (!bundle) return null;
  const relPath = pathname === '' || pathname === '/' ? 'index.html' : pathname.replace(/^\//, '');
  const content = bundle.files[relPath];
  if (content === undefined) return null;
  return new Response(content, { status: 200, headers: { 'Content-Type': contentTypeFor(relPath) } });
}

/**
 * Builds a fetch-event handler for `self.addEventListener('fetch', ...)`
 * inside an service worker. Only intercepts (calls
 * `event.respondWith`) requests whose path falls under `scope` — every
 * other request is left alone for the browser's own normal handling,
 * so this can share a service worker with unrelated same-origin
 * traffic without interfering with it.
 *
 * `createLog` is injectable (defaults to a `createIndexedDbBackend`)
 * purely so this can be exercised with an in-memory `EventLog` in
 * `node --test` — `ServiceWorkerGlobalScope`/`indexedDB` don't exist in
 * Node, the same honest limit `webrtc-transport.js` documents for
 * `RTCPeerConnection`.
 */
export function createFetchHandler({ domain, dbName = 'aiwa-platform-bundle', scope, createLog = () => new EventLog(createIndexedDbBackend(dbName)) } = {}) {
  if (!domain) throw new Error('createFetchHandler: domain is required.');
  if (!scope) throw new Error('createFetchHandler: scope is required.');
  return function handleFetchEvent(event) {
    const url = new URL(event.request.url);
    if (!url.pathname.startsWith(scope)) return; // not ours — let the browser handle it normally
    const relPath = url.pathname.slice(scope.length);
    event.respondWith(
      (async () => {
        const log = createLog();
        const response = await resolveFromBundle(log, domain, relPath);
        return response ?? new Response('Not found in the published bundle.', { status: 404 });
      })(),
    );
  };
}
