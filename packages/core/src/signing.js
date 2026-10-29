// Every signed action of a domain (a transfer, a split, a burn commitment, a claim, a progression step...) is the
// same thing: a canonical JSON message, signed by the key whose id owns the action. This file is the one place
// that knows how; the action types below only say which fields they sign.
//
// The messages are part of the protocol: their bytes are frozen. A message lists its fields in a fixed order, and
// a field that is undefined is left out by JSON.stringify.
//
// A delegated action is signed by a delegate's key instead of the owner's. It carries, besides its own signature, the
// owner's one-time delegation ({ delegate, from }), so anyone can check both: the owner authorised this delegate,
// and the delegate signed this very action.

import { ed25519 } from '@noble/curves/ed25519.js';
import { toHex, fromHex, sha256Hex } from './bytes.js';

const utf8 = new TextEncoder();

/** True iff `signatureHex` is a valid signature of `message` (bytes) by `pubkeyHex`. Never throws. */
export function verifyHex(message, signatureHex, pubkeyHex) {
  try {
    return ed25519.verify(fromHex(signatureHex), message, fromHex(pubkeyHex));
  } catch {
    return false;
  }
}

/** Signs `message` (bytes) with a 32-byte seed; the signature as hex. */
export const signHex = (message, seed) => toHex(ed25519.sign(message, seed));

const idOfPubkey = (pubkeyHex) => sha256Hex(fromHex(pubkeyHex));
const isText = (v) => typeof v === 'string' && v !== '';

// What each action signs. `keys` is its canonical message; `owner` names the field that holds the identity the
// signer must be (the delegated form inserts `delegate` before the nonce). `nullable` fields sign null when absent.
// `required` (besides the signature fields) must be present text in an event; `label` completes its rejection
// reasons.
export const ACTIONS = {
  transfer: { keys: ['claimId', 'from', 'to', 'nonce', 'timestamp'], owner: 'from', required: ['claimId', 'from', 'to'], label: 'signature' },
  split: {
    keys: ['claimId', 'owner', 'firstAmount', 'firstId', 'secondId', 'nonce', 'timestamp'], owner: 'owner',
    required: ['claimId', 'owner', 'firstId', 'secondId'], label: 'signature',
  },
  voucherRedeem: { keys: ['claimId', 'secret', 'to', 'nonce', 'timestamp'], owner: 'to', required: ['claimId', 'secret', 'to'], label: 'redeemer signature' },
  accrual: { keys: ['domain', 'b', 'T', 'nonce', 'timestamp', 'previous'], owner: 'domain', nullable: ['T'] },
  claim: { keys: ['domain', 'amount', 'claimId', 'nonce', 'timestamp', 'previous'], owner: 'domain', nullable: ['claimId'] },
  progression: { keys: ['domain', 'epoch', 'vdfIterations', 'vdfOutput', 'nonce', 'timestamp', 'previous'], owner: 'domain' },
};

function messageKeys(action, delegated) {
  return delegated ? action.keys.flatMap((k) => (k === 'nonce' ? ['delegate', k] : [k])) : action.keys;
}

/** The bytes an action signs, from the fields of an event (any extra field is ignored). */
export function canonicalMessage(action, fields, delegated = false) {
  const message = {};
  for (const key of messageKeys(action, delegated)) message[key] = action.nullable?.includes(key) ? (fields[key] ?? null) : fields[key];
  return utf8.encode(JSON.stringify(message));
}

const delegationMessage = ({ delegate, from }) => utf8.encode(JSON.stringify({ delegate, from }));

const meta = ({ now = Date.now(), nonce = crypto.randomUUID() } = {}) => ({ nonce, timestamp: now });

/** The signed fields of an action by its owner's own key: `fields` plus nonce and timestamp, the signer's key and the signature. */
export async function signAction(action, fields, signerSeed, signerPubkeyBytes, options) {
  const withMeta = { ...fields, ...meta(options) };
  return { ...withMeta, signerPubkey: toHex(signerPubkeyBytes), signature: signHex(canonicalMessage(action, withMeta), signerSeed) };
}

/** True iff `event` carries a valid signature by the key whose id is its owner field. */
export async function verifyAction(action, event) {
  const { signerPubkey, signature } = event;
  if (!isText(signerPubkey) || !isText(signature)) return false;
  if ((await idOfPubkey(signerPubkey)) !== event[action.owner]) return false;
  return verifyHex(canonicalMessage(action, event), signature, signerPubkey);
}

/**
 * The one-time delegation: the owner signs { delegate, from } once — no amount, no expiry. A deployment that wants
 * either layers it into a contract verifier instead of forcing it on every caller.
 */
export async function issueDelegation(ownerSeed, ownerPubkeyBytes, delegatePubkeyBytes) {
  const delegate = toHex(delegatePubkeyBytes);
  const from = await sha256Hex(ownerPubkeyBytes);
  return { delegate, from, ownerPubkey: toHex(ownerPubkeyBytes), delegationSignature: signHex(delegationMessage({ delegate, from }), ownerSeed) };
}

/** Independently verifiable, from the object alone: `delegation.from` really authorised `delegation.delegate`. */
export async function verifyDelegation(delegation) {
  const { delegate, from, ownerPubkey, delegationSignature } = delegation ?? {};
  if (![delegate, from, ownerPubkey, delegationSignature].every(isText)) return false;
  if ((await idOfPubkey(ownerPubkey)) !== from) return false;
  return verifyHex(delegationMessage({ delegate, from }), delegationSignature, ownerPubkey);
}

/**
 * An action signed by a delegate's key for the delegation's owner, which lands in the action's owner field.
 * Only the fields the action signs are taken from `fields`; the delegation's proof travels with the event.
 */
export async function signDelegatedAction(action, delegation, fields, delegateSeed, delegatePubkeyBytes, options) {
  const own = meta(options);
  const withMeta = {};
  for (const key of messageKeys(action, true)) {
    if (key === action.owner) withMeta[key] = delegation.from;
    else if (key === 'delegate') withMeta[key] = delegation.delegate;
    else if (key in own) withMeta[key] = own[key];
    else withMeta[key] = fields[key];
  }
  return {
    ...withMeta,
    ownerPubkey: delegation.ownerPubkey,
    delegationSignature: delegation.delegationSignature,
    signerPubkey: toHex(delegatePubkeyBytes),
    signature: signHex(canonicalMessage(action, withMeta, true), delegateSeed),
  };
}

/** True iff the owner really authorised this delegate AND the delegate really signed this very action. */
export async function verifyDelegatedAction(action, event) {
  const { delegate, ownerPubkey, delegationSignature, signerPubkey, signature } = event;
  if (![delegate, ownerPubkey, delegationSignature, signerPubkey, signature].every(isText)) return false;
  const owner = event[action.owner];
  if ((await idOfPubkey(ownerPubkey)) !== owner) return false; // the owner field must derive from the embedded owner key
  if (toHex(fromHex(signerPubkey)) !== delegate) return false; // the signer must be exactly the delegated key
  if (!verifyHex(delegationMessage({ delegate, from: owner }), delegationSignature, ownerPubkey)) return false; // the owner never authorised this delegate
  return verifyHex(canonicalMessage(action, event, true), signature, signerPubkey);
}
