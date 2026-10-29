// Payments of already-claimed AIWA: pay an identity, hand over a bundle a stranger can append with no prior sync, or
// hash-lock value behind a secret (a bearer voucher).
//
// The wallet's own key and a channel's delegate key do the same things, so each payment takes an ACTOR, who signs:
// `ownActor` signs with the wallet's key; `delegateActor` with a delegate's key, on an owner's delegation (the owner's
// key never signs again).

import {
  spendableClaims, toUnits, toHex, deriveVoucherAddress, buildSignedSplitEvent, buildSignedTransferEvent,
  buildSignedDelegatedSplitEvent, buildSignedDelegatedTransferEvent, buildSignedVoucherRedeemEvent,
} from 'aiwa-core';
import { collectAncestors } from './ancestors.js';
import { signerOf } from './signer.js';

export function ownActor(wallet) {
  const owner = wallet.identity.id;
  const signer = signerOf(wallet.keypair);
  return {
    owner,
    identity: wallet.identity,
    split: { type: 'split', build: (fields) => buildSignedSplitEvent({ ...fields, owner }, ...signer) },
    transfer: { type: 'transfer', build: (fields) => buildSignedTransferEvent({ ...fields, from: owner }, ...signer) },
  };
}

export function delegateActor(delegation, keypair, identity) {
  const signer = signerOf(keypair);
  return {
    owner: delegation.from,
    identity,
    split: { type: 'delegated-split', build: (fields) => buildSignedDelegatedSplitEvent(delegation, fields, ...signer) },
    transfer: { type: 'delegated-transfer', build: (fields) => buildSignedDelegatedTransferEvent(delegation, fields, ...signer) },
  };
}

/** What a voucher's QR code carries: 32 random bytes. Whoever reveals it first redeems the value it hash-locks. */
export function randomVoucherSecret() {
  return toHex(crypto.getRandomValues(new Uint8Array(32)));
}

/** `events` plus every ancestor the recipient needs to append them with no prior sync, in canonical order. */
export const bundleOf = (wallet, events) => collectAncestors(wallet.ledger.log, events.map((e) => e.id));

/**
 * A single active claim of the owner worth exactly `amount`: found, or made by splitting a bigger one. Limit (v1): one
 * active claim >= `amount` must exist; several smaller ones are not combined.
 */
async function spendableClaim(wallet, actor, amount) {
  const amountUnits = toUnits(amount);
  const claims = spendableClaims(await wallet.ledger.state(), actor.owner);
  const exact = claims.find((c) => c.amount === amountUnits);
  if (exact) return { sourceClaim: exact, events: [] };

  const bigEnough = claims.find((c) => c.amount > amountUnits);
  if (!bigEnough) throw new Error(`No single active claim covers ${amount} AIWA (v1 limitation — consolidate claims first).`);
  const firstId = crypto.randomUUID();
  const secondId = crypto.randomUUID();
  const signed = await actor.split.build({ claimId: bigEnough.id, firstAmount: amount, firstId, secondId });
  const split = await wallet.ledger.append(actor.identity, actor.split.type, signed);
  return { sourceClaim: { id: firstId, amount: amountUnits }, events: [split] };
}

/**
 * Pays `amount` to `to` (an identity, or a voucher address), splitting a claim first if none matches exactly. The new
 * events are published to every connected peer WITH their ancestors: a peer that lacks this history could not append
 * a bare transfer at all, and the handshake that syncs two peers happens only once, at connection.
 */
export async function pay(wallet, actor, to, amount) {
  const { sourceClaim, events } = await spendableClaim(wallet, actor, amount);
  const signed = await actor.transfer.build({ claimId: sourceClaim.id, to });
  const transfer = await wallet.ledger.append(actor.identity, actor.transfer.type, signed);
  events.push(transfer);
  await wallet.publish(events.map((e) => e.id));
  return { events, newClaimId: `activated:${sourceClaim.id}:${actor.owner}:${to}:0:identity` };
}

/** pay() plus every ancestor the transfer needs: a self-contained bundle. */
export async function payOffline(wallet, actor, to, amount) {
  const { events, newClaimId } = await pay(wallet, actor, to, amount);
  return { events: await bundleOf(wallet, events), newClaimId };
}

/**
 * A bearer voucher: `amount` of the owner's value hash-locked behind a fresh secret (the idea of a Lightning HTLC).
 * It is an ordinary transfer to an address nobody's key controls; whoever redeems it FIRST gets the value, and
 * copying the QR changes nothing since a claim, once moved, cannot be moved again. Put `secret`, `claimId` and
 * `events` in a QR code.
 */
export async function issueVoucher(wallet, actor, amount) {
  const secret = randomVoucherSecret();
  const { events, newClaimId } = await pay(wallet, actor, await deriveVoucherAddress(secret), amount);
  return { secret, claimId: newClaimId, events: await bundleOf(wallet, events) };
}

/** Redeems a bearer voucher into the wallet's own identity. Whoever redeems first gets it; redeeming a consumed voucher has no effect. */
export async function redeemVoucher(wallet, { secret, claimId, events }) {
  wallet.requireConnected();
  await wallet.ledger.log.appendMany(events);
  wallet.observer.schedule();
  const signed = await buildSignedVoucherRedeemEvent({ claimId, secret, to: wallet.identity.id }, ...signerOf(wallet.keypair));
  const event = await wallet.ledger.append(wallet.identity, 'voucher-redeem', signed);
  return { eventId: event.id };
}
