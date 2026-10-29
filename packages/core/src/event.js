// An event is signed and content-addressed. Its id and its signature cover the same bytes:
// { domain, author, authorPublicKey, parents (sorted), type, payload (keys sorted), createdAt }.
// `parents` encode causal dependency (B depends on A); a timestamp would only encode arrival order.
// The public key travels in the event: `author` is a hash and cannot be turned back into a key, so a verifier
// recomputes the id from the key and never looks it up elsewhere.

import { ed25519 } from '@noble/curves/ed25519.js';
import { fromHex, sha256Hex } from './bytes.js';

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    const sorted = {};
    for (const key of Object.keys(value).sort()) sorted[key] = canonicalize(value[key]);
    return sorted;
  }
  return value;
}

function coreBytes({ domain, author, authorPublicKey, parents, type, payload, createdAt }) {
  const core = { domain, author, authorPublicKey, parents: [...parents].sort(), type, payload: canonicalize(payload), createdAt };
  return new TextEncoder().encode(JSON.stringify(core));
}

export const computeEventId = (bytes) => sha256Hex(bytes);

/** Builds a signed event. `identity` must hold its secret key. */
export async function createEvent(identity, { domain, parents = [], type, payload, createdAt = Date.now() }) {
  const author = identity.id;
  const authorPublicKey = identity.publicKey;
  const bytes = coreBytes({ domain, author, authorPublicKey, parents, type, payload, createdAt });
  return { id: await computeEventId(bytes), domain, author, authorPublicKey, parents, type, payload, createdAt, signature: await identity.sign(bytes) };
}

/**
 * Self-contained verification, three checks: the embedded key derives `author`; the recomputed id matches
 * (the content was not changed); the signature verifies against the embedded key.
 */
export async function verifyEvent(event) {
  if ((await sha256Hex(fromHex(event.authorPublicKey))) !== event.author) {
    return { valid: false, reason: 'the embedded public key does not derive the claimed author id' };
  }
  const bytes = coreBytes(event);
  if ((await computeEventId(bytes)) !== event.id) return { valid: false, reason: 'the recomputed id does not match: the content was changed' };
  let signed = false;
  try { signed = ed25519.verify(fromHex(event.signature), bytes, fromHex(event.authorPublicKey)); } catch { /* malformed */ }
  return signed ? { valid: true } : { valid: false, reason: 'the signature does not verify' };
}
