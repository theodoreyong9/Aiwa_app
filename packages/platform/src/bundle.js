// Publishing a multi-file application bundle (an entire app —
// index.html, css/, js/ — not just one contract's source string, the
// way aiwa-core's own contract-registry.js does for a single file) as
// verifiable, content-addressed AIWA events, so a peer can receive,
// verify, and reconstruct it via replication alone — no GitHub Pages,
// no fixed hosting for the app's own bytes.
//
// Two kinds of event, deliberately different in shape:
//
// - `bundle.file`: one per file, PARENTLESS and createdAt=0 on
// purpose. A file's own bytes don't causally depend on when or by
// whom they were published — only their content does, and content
// addressing already captures that. Fixing createdAt removes the
// one source of non-determinism event.js's own id computation
// would otherwise have, so publishing the SAME file content again
// (an unchanged file across two app versions) yields the identical
// event id and is a no-op (`EventLog.append`'s own dedup) —
// never retransmitted or restored twice. HONEST LIMIT: this only
// dedups a byte-identical file; a one-byte change is a wholly new
// event, same as any other content-addressed store.
// - `bundle.manifest`: the signed, timestamped "domain X
// publishes app version Y, consisting of these exact files"
// statement. Its parents are every file event it references
// PLUS the domain's own prior heads, so `EventLog.head()` naturally
// resolves to the latest manifest and `since()` naturally computes
// the minimal update between two versions.

import { createEvent } from 'aiwa-core';

/**
 * @param {import('aiwa-core').Identity} identity
 * @param {import('aiwa-core').EventLog} log
 * @param {string} domain
 * @param {{ name: string, version: string, files: Array<{path: string, content: string}> }} bundle content is a UTF-8 string; base64-encode binary files before calling this.
 * @returns {Promise<{ manifestEventId: string, fileEventIds: Record<string, string> }>}
 */
export async function publishBundle(identity, log, domain, { name, version, files }) {
  const fileEventIds = {};
  for (const { path, content } of files) {
    const event = await createEvent(identity, { domain, parents: [], type: 'bundle.file', payload: { path, content }, createdAt: 0 });
    if (!(await log.has(event.id))) await log.append(event);
    fileEventIds[path] = event.id;
  }

  const priorHeads = await log.head();
  const manifestEvent = await createEvent(identity, {
    domain,
    parents: [...new Set([...Object.values(fileEventIds), ...priorHeads])],
    type: 'bundle.manifest',
    payload: { name, version, files: fileEventIds },
  });
  await log.append(manifestEvent);
  return { manifestEventId: manifestEvent.id, fileEventIds };
}

/**
 * Reconstructs a published bundle from its manifest event id —
 * every file's own content, keyed by path. Every event involved
 * was already cryptographically verified on `EventLog.append()`
 * (content-addressing + signature) — this function only reassembles,
 * it never re-verifies.
 *
 * @returns {Promise<{ name: string, version: string, files: Record<string, string> } | null>} null if the manifest (or any file it references) isn't in `log` yet — a honest "not fully synced", never a partial or corrupted result.
 */
export async function readBundle(log, manifestEventId) {
  const manifestEvent = await log.get(manifestEventId);
  if (!manifestEvent || manifestEvent.type !== 'bundle.manifest') return null;

  const { name, version, files: fileEventIds } = manifestEvent.payload;
  const files = {};
  for (const [path, eventId] of Object.entries(fileEventIds)) {
    const fileEvent = await log.get(eventId);
    if (!fileEvent || fileEvent.type !== 'bundle.file') return null; // not yet synced — an honest absence, not an error
    files[path] = fileEvent.payload.content;
  }
  return { name, version, files };
}

/** The current published version for a domain — the manifest event among the log's own heads, or null if none has been published yet. Throws if more than one manifest head exists (a fork — the caller must resolve which to trust, never silently picked for them). */
export async function latestBundle(log, domain) {
  const heads = await log.head();
  const manifests = [];
  for (const id of heads) {
    const event = await log.get(id);
    if (event?.type === 'bundle.manifest' && event.domain === domain) manifests.push(event);
  }
  if (manifests.length === 0) return null;
  if (manifests.length > 1) throw new Error(`Multiple, unresolved manifest heads for domain '${domain}' — a real fork (${manifests.map((m) => m.id).join(', ')}); the caller must resolve which to trust.`);
  return readBundle(log, manifests[0].id);
}

/**
 * Every published version whose manifest was really signed by
 * `author` — "find published code by its creator's address"
 * needs no new protocol: every event's `author` is already a real,
 * cryptographically verified field (aiwa-core's own event.js), so this
 * just scans for it. Returns manifest SUMMARIES (domain, name,
 * version, manifestEventId, createdAt), not full file content — the
 * caller resolves whichever ones it actually wants to open via
 * readBundle()/latestBundle(). Every version this author ever
 * published is included, not just the current head per domain — a
 * publish history, not a directory of "latest only"; the caller
 * decides what "current" means for its own listing.
 */
export async function listBundlesByAuthor(log, author) {
  const results = [];
  for await (const event of log.since([])) {
    if (event.type === 'bundle.manifest' && event.author === author) {
      results.push({
        domain: event.domain,
        manifestEventId: event.id,
        name: event.payload.name,
        version: event.payload.version,
        createdAt: event.createdAt,
      });
    }
  }
  return results;
}
