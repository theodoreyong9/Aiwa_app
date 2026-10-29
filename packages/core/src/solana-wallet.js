// Solana keypair management and burn-transaction construction.
// Key generation, encryption, signing are fully offline; broadcasting
// is the one network boundary.
//
// This module's own lightweight keypair shape exists for Solana
// interop (burn/transfer transactions need a Solana-Keypair-
// shaped object) — it is a DIFFERENT representation from this
// package's own identity.js Identity class. `toIdentity` bridges the
// two: the same Ed25519 seed underlies both, so a domain derived
// here (via BIP39, a passphrase, or freshly generated) can act as an
// Identity too, for signing events/capabilities, without a second,
// separate derivation.

import { SOLANA_INCINERATOR_ADDRESS } from './identity-cost.js';
import { toHex } from './bytes.js';
import { base58Encode } from './base58.js';

const PBKDF2_ITERATIONS = 200_000;

// A minimal, Solana-Keypair-SHAPED object — sufficient for
// identity derivation and display — generated using only
// @noble/curves/ed25519.js, already proven to load reliably. Deliberately
// avoids requiring the full, heavy @solana/web3.js library
// (many transitive dependencies — buffer, crypto polyfills, websockets)
// just to create an identity, which is the FIRST, most critical
// interaction a new person has with this app. The full library is
// loaded lazily, later, only when actually broadcasting a real
// transaction.
function wrapAsKeypairShape(secretKey32, publicKey32) {
  const secretKey = new Uint8Array(64);
  secretKey.set(secretKey32, 0);
  secretKey.set(publicKey32, 32);
  const base58 = base58Encode(publicKey32);
  return {
    secretKey,
    publicKey: { toBytes: () => publicKey32, toBase58: () => base58, toString: () => base58 },
  };
}

export async function generateLightweightKeypair() {
  const { ed25519 } = await import('@noble/curves/ed25519.js');
  const secretKey32 = ed25519.utils.randomSecretKey();
  const publicKey32 = ed25519.getPublicKey(secretKey32);
  return wrapAsKeypairShape(secretKey32, publicKey32);
}

/** The keypair of a 32-byte seed. */
export async function lightweightKeypairFromSeed(seed32) {
  const { ed25519 } = await import('@noble/curves/ed25519.js');
  return wrapAsKeypairShape(seed32, ed25519.getPublicKey(seed32));
}

export async function lightweightKeypairFromSecretKey(secretKeyBytes) {
  const { ed25519 } = await import('@noble/curves/ed25519.js');
  if (secretKeyBytes.length !== 64) throw new Error(`Expected a 64-byte secret key, got ${secretKeyBytes.length}`);
  const secretKey32 = secretKeyBytes.slice(0, 32);
  const publicKey32 = ed25519.getPublicKey(secretKey32);
  // The embedded public key half must really match what this seed derives — catches a corrupted or non-matching import early.
  if (base58Encode(publicKey32) !== base58Encode(secretKeyBytes.slice(32, 64))) {
    throw new Error('Secret key is malformed: embedded public key does not match the derived one.');
  }
  return wrapAsKeypairShape(secretKey32, publicKey32);
}

// A deterministic identity from a passphrase alone — the same
// passphrase always derives the identical keypair, anywhere,
// with nothing else to carry or transport. A fixed, application-
// specific salt is used deliberately: reproducibility from the
// passphrase ALONE is the entire point (a random salt would make that
// impossible), at the honest cost of losing the extra defense a
// random salt gives against a precomputed attack — the passphrase
// itself is the only secret here, exactly like a private key
// written down in words instead of bytes. A weak, guessable
// passphrase is exactly as unsafe as a weak, guessable private key.
//
// This is an app-specific derivation — NOT BIP39, NOT compatible
// with an existing Solana wallet's seed phrase. Typing an
// existing wallet's words here derives a but different and
// unrelated, identity, never that wallet's funds.
const PASSPHRASE_SALT = new TextEncoder().encode('aiwa-core-passphrase-identity-v1');
const PASSPHRASE_ITERATIONS = 600_000;

export async function deriveKeypairFromPassphrase(passphrase) {
  const { ed25519 } = await import('@noble/curves/ed25519.js');
  const keyMaterial = await crypto.subtle.importKey('raw', new TextEncoder().encode(passphrase), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: PASSPHRASE_SALT, iterations: PASSPHRASE_ITERATIONS, hash: 'SHA-256' }, keyMaterial, 256);
  const secretKey32 = new Uint8Array(bits);
  const publicKey32 = ed25519.getPublicKey(secretKey32);
  return wrapAsKeypairShape(secretKey32, publicKey32);
}

// A standard BIP39 + SLIP-0010 derivation — the identical real
// algorithm Phantom, Solflare, and the Solana CLI use, at the same
// standard path (m/44'/501'/account'/0'). Typing an existing
// Solana wallet's seed phrase here derives the SAME real
// address that wallet already shows. This is a different,
// mechanism from deriveKeypairFromPassphrase above — that one is
// intentionally app-specific and NOT standard; this one is standard
// and NOT app-specific. Never conflate the two.
const SLIP10_ED25519_SEED_KEY = new TextEncoder().encode('ed25519 seed');

async function slip10MasterKey(seed) {
  const { hmac } = await import('@noble/hashes/hmac.js');
  const { sha512 } = await import('@noble/hashes/sha2.js');
  const I = hmac(sha512, SLIP10_ED25519_SEED_KEY, seed);
  return { key: I.slice(0, 32), chainCode: I.slice(32, 64) };
}

async function slip10DeriveHardened(parentKey, parentChainCode, index) {
  const { hmac } = await import('@noble/hashes/hmac.js');
  const { sha512 } = await import('@noble/hashes/sha2.js');
  const hardenedIndex = index + 0x80000000;
  const data = new Uint8Array(37);
  data[0] = 0x00;
  data.set(parentKey, 1);
  new DataView(data.buffer).setUint32(33, hardenedIndex, false); // big-endian, per the SLIP-0010 spec
  const I = hmac(sha512, parentChainCode, data);
  return { key: I.slice(0, 32), chainCode: I.slice(32, 64) };
}

async function deriveSlip10Path(seed, pathIndices) {
  let { key, chainCode } = await slip10MasterKey(seed);
  for (const index of pathIndices) {
    ({ key, chainCode } = await slip10DeriveHardened(key, chainCode, index));
  }
  return key;
}

export async function validateBip39Mnemonic(mnemonic) {
  const { validateMnemonic } = await import('@scure/bip39');
  const { wordlist } = await import('@scure/bip39/wordlists/english.js');
  return validateMnemonic(mnemonic.trim(), wordlist);
}

/** A fresh BIP39 recovery phrase (English wordlist): 12 words by default, 24 on request. Random from the platform's own source. */
export async function generateBip39Mnemonic(wordCount = 12) {
  if (wordCount !== 12 && wordCount !== 24) throw new Error('generateBip39Mnemonic: 12 or 24 words');
  const { generateMnemonic } = await import('@scure/bip39');
  const { wordlist } = await import('@scure/bip39/wordlists/english.js');
  return generateMnemonic(wordlist, wordCount === 12 ? 128 : 256);
}

export async function deriveKeypairFromBip39Mnemonic(mnemonic, accountIndex = 0) {
  const { ed25519 } = await import('@noble/curves/ed25519.js');
  if (!(await validateBip39Mnemonic(mnemonic))) {
    throw new Error('Not a valid BIP39 mnemonic (wrong word, wrong count, or bad checksum).');
  }
  const { mnemonicToSeedSync } = await import('@scure/bip39');
  const seed = mnemonicToSeedSync(mnemonic.trim());
  const secretKey32 = await deriveSlip10Path(seed, [44, 501, accountIndex, 0]);
  const publicKey32 = ed25519.getPublicKey(secretKey32);
  return wrapAsKeypairShape(secretKey32, publicKey32);
}

export function generateKeypair(solanaWeb3) {
  return solanaWeb3.Keypair.generate();
}

export function keypairFromSecretKey(solanaWeb3, secretKeyBytes) {
  return solanaWeb3.Keypair.fromSecretKey(secretKeyBytes);
}

export async function encryptSecretKey(secretKeyBytes, password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const keyMaterial = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' }, keyMaterial, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, secretKeyBytes);
  return { salt: Array.from(salt), iv: Array.from(iv), ciphertext: Array.from(new Uint8Array(ciphertext)) };
}

export async function decryptSecretKey(record, password) {
  const salt = new Uint8Array(record.salt);
  const iv = new Uint8Array(record.iv);
  const ciphertext = new Uint8Array(record.ciphertext);
  const keyMaterial = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' }, keyMaterial, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
  try {
    const plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
    return new Uint8Array(plaintext);
  } catch {
    throw new Error('Wrong password');
  }
}

// `lamports` is what leaves the wallet in this burn. With a creator fee (aiwa-core's creatorFeeLamports), `creatorFeeLamports`
// of it goes to `creatorAddress` and the rest to the incinerator: two transfers in one transaction, so both happen or neither.
export function buildBurnTransaction(solanaWeb3, { fromPubkey, lamports, recentBlockhash, creatorAddress, creatorFeeLamports = 0 }) {
  if (!Number.isInteger(lamports) || lamports <= 0) throw new RangeError(`lamports must be a positive integer, got ${lamports}`);
  if (!Number.isInteger(creatorFeeLamports) || creatorFeeLamports < 0 || creatorFeeLamports >= lamports) throw new RangeError(`the creator fee must be a whole number of lamports, smaller than the burn, got ${creatorFeeLamports}`);
  if (creatorFeeLamports > 0 && !creatorAddress) throw new Error('a creator fee needs the creator address');
  const tx = new solanaWeb3.Transaction();
  tx.add(solanaWeb3.SystemProgram.transfer({ fromPubkey, toPubkey: new solanaWeb3.PublicKey(SOLANA_INCINERATOR_ADDRESS), lamports: lamports - creatorFeeLamports }));
  if (creatorFeeLamports > 0) tx.add(solanaWeb3.SystemProgram.transfer({ fromPubkey, toPubkey: new solanaWeb3.PublicKey(creatorAddress), lamports: creatorFeeLamports }));
  tx.recentBlockhash = recentBlockhash;
  tx.feePayer = fromPubkey;
  return tx;
}

// A transfer to any chosen recipient — distinct from
// buildBurnTransaction's own fixed, irreversible destination.
export function buildTransferTransaction(solanaWeb3, { fromPubkey, toAddress, lamports, recentBlockhash }) {
  if (!Number.isInteger(lamports) || lamports <= 0) throw new RangeError(`lamports must be a positive integer, got ${lamports}`);
  let toPubkey;
  try {
    toPubkey = new solanaWeb3.PublicKey(toAddress);
  } catch {
    throw new Error(`'${toAddress}' is not a real, valid Solana address.`);
  }
  const tx = new solanaWeb3.Transaction();
  tx.add(solanaWeb3.SystemProgram.transfer({ fromPubkey, toPubkey, lamports }));
  tx.recentBlockhash = recentBlockhash;
  tx.feePayer = fromPubkey;
  return tx;
}

export function signAndSerialize(tx, keypair) {
  tx.sign(keypair);
  return tx.serialize();
}

export async function broadcastBurnTransaction(solanaWeb3, connection, keypair, lamports, { creatorAddress, creatorFeeLamports = 0 } = {}) {
  const { blockhash } = await connection.getLatestBlockhash('finalized');
  const tx = buildBurnTransaction(solanaWeb3, { fromPubkey: keypair.publicKey, lamports, recentBlockhash: blockhash, creatorAddress, creatorFeeLamports });
  const raw = signAndSerialize(tx, keypair);
  const signature = await connection.sendRawTransaction(raw);
  await connection.confirmTransaction(signature, 'finalized');
  return signature;
}

export async function broadcastTransferTransaction(solanaWeb3, connection, keypair, toAddress, lamports) {
  const { blockhash } = await connection.getLatestBlockhash('finalized');
  const tx = buildTransferTransaction(solanaWeb3, { fromPubkey: keypair.publicKey, toAddress, lamports, recentBlockhash: blockhash });
  const raw = signAndSerialize(tx, keypair);
  const signature = await connection.sendRawTransaction(raw);
  await connection.confirmTransaction(signature, 'finalized');
  return signature;
}

export async function loadSolanaWeb3() {
  if (typeof window !== 'undefined' && window.solanaWeb3) return window.solanaWeb3;
  const timeout = (ms) => new Promise((_, reject) => setTimeout(() => reject(new Error(`Loading @solana/web3.js timed out after ${ms / 1000}s`)), ms));
  const mod = await Promise.race([import('https://esm.sh/@solana/web3.js@1.98.0'), timeout(15000)]);
  if (typeof window !== 'undefined') window.solanaWeb3 = mod;
  return mod;
}

// Bridges this module's Solana-shaped keypair into this package's own
// event/capability Identity (identity.js) — same Ed25519 seed,
// the canonical shape aiwa-core and aiwa-platform (events,
// capabilities) actually expect.
export async function toIdentity(keypair) {
  const { identityFromSecretKey } = await import('./identity.js');
  return identityFromSecretKey(toHex(keypair.secretKey.slice(0, 32)));
}
