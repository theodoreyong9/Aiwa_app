// Hex and hashing helpers, shared by every module.

export const toHex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');

export function fromHex(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

const utf8 = new TextEncoder();

/** SHA-256 of bytes or of a string's UTF-8, as hex. */
export async function sha256Hex(input) {
  const bytes = typeof input === 'string' ? utf8.encode(input) : input;
  return toHex(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)));
}
