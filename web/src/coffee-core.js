// « Un café »: what is checked before AIWA is sent to the person of a profile. Pure functions.
import { deriveId, fromHex } from 'aiwa-core';

/** The identity id of the person whose signed card carries `publicKeyHex` (an Ed25519 key, 64 hex characters), or null when it is not one (async: the id is a hash). The profile itself says nothing. */
export async function coffeeTarget(publicKeyHex) {
  const hex = String(publicKeyHex || '').trim();
  if (!/^[0-9a-f]{64}$/.test(hex)) return null;
  try { return await deriveId(fromHex(hex)); } catch { return null; }
}

/** The amount typed, as the wallet wants it (a plain decimal, above zero, no more than 9 digits before the point and 8 after), or '' when it is not one. */
export function coffeeAmount(text) {
  const v = String(text || '').trim().replace(',', '.');
  return /^(?:0|[1-9]\d{0,8})(?:\.\d{1,8})?$/.test(v) && Number(v) > 0 ? v : '';
}
