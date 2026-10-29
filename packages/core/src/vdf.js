// The sequential hash chain: h_0 = SHA-256(seed), h_i = SHA-256(h_{i-1}). Each step needs the one before it, so no amount
// of parallel hardware shortcuts it: it bounds the rate at which a domain advances, not calendar time.
// Verifying costs what producing costs (the succinct proof of wesolowski-vdf.js is what makes verification cheap).

import { toHex } from './bytes.js';

const sha256 = async (bytes) => new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));

// A browser cannot paint or take input while microtasks run back to back: yield to the macrotask queue now and then.
const yieldToMain = () => new Promise((resolve) => setTimeout(resolve, 0));

/** The chain starts from the domain and the previous epoch's output ('genesis' for the first): epoch N cannot start before N-1 is done. */
export const vdfSeed = (domain, previousOutput) => `${domain}:${previousOutput}`;

export async function computeVdfChain(seed, iterations) {
  let h = await sha256(new TextEncoder().encode(seed));
  for (let i = 1; i < iterations; i++) {
    h = await sha256(h);
    if (i % 200 === 0) await yieldToMain();
  }
  return toHex(h);
}

export async function verifyVdfChain(seed, iterations, claimedOutput) {
  if (typeof claimedOutput !== 'string' || !/^[0-9a-f]{64}$/.test(claimedOutput)) return false;
  return (await computeVdfChain(seed, iterations)) === claimedOutput;
}
