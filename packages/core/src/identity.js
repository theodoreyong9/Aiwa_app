// An identity is an Ed25519 key. Its id is the SHA-256 of the public key; the same key is also the holder's Solana address.

import { ed25519 } from '@noble/curves/ed25519.js';
import { toHex, fromHex, sha256Hex } from './bytes.js';

/** The id of a public key: SHA-256 of its bytes, hex. */
export const deriveId = (publicKeyBytes) => sha256Hex(publicKeyBytes);

export class Identity {
  constructor({ id, secretKeyHex, publicKeyHex }) {
    this.id = id;
    this.publicKey = publicKeyHex;
    this._secretKey = secretKeyHex;
  }

  /** The secret key, hex: for an app that keeps its own identity between two openings (aiwa-lib's loadOrCreateIdentity). Null for a remote identity. */
  exportSecretKey() { return this._secretKey ?? null; }

  /** Signs bytes; hex signature. An identity without its secret key can only verify. */
  async sign(bytes) {
    if (!this._secretKey) throw new Error('This identity has no secret key: it can verify, never sign.');
    return toHex(ed25519.sign(bytes, fromHex(this._secretKey)));
  }

  async verify(bytes, signatureHex) {
    try {
      return ed25519.verify(fromHex(signatureHex), bytes, fromHex(this.publicKey));
    } catch {
      return false;
    }
  }
}

export async function generateIdentity() {
  return identityFromSecretKey(toHex(ed25519.utils.randomSecretKey()));
}

export async function identityFromSecretKey(secretKeyHex) {
  const publicKey = ed25519.getPublicKey(fromHex(secretKeyHex));
  return new Identity({ id: await deriveId(publicKey), secretKeyHex, publicKeyHex: toHex(publicKey) });
}

/** A remote identity known by its public key only: it can verify, never sign. */
export async function publicIdentity(publicKeyHex) {
  return new Identity({ id: await deriveId(fromHex(publicKeyHex)), secretKeyHex: null, publicKeyHex });
}
