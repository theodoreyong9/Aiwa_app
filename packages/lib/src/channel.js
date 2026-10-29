// "Sign once, click many times": a channel is a per-peer delegation. The owner signs ONE delegation authorising a
// session key, and every later payment through the channel is signed by that session key alone: the owner's root key
// is never touched again for this peer. Nothing is escrowed or pre-funded; the delegate only authorises moving what
// the owner already owns, one action at a time. Once the delegation exists, nothing here needs a network.
//
// Two ways to open one:
// - openChannel(): UNILATERAL. The owner alone decides; the peer consents to nothing.
// - requestChannel() / acceptChannelRequest() / channel.confirm(): the peer's consent is real. The request travels as
//   a blob over any channel (a message, a QR code, NFC); the peer verifies it and answers with a signed acceptance; the
//   requester's channel stays PENDING, refusing every action, until that acceptance checks out.
//
// Limit: there is no revocation. A delegation has no expiry or cap, by design, so it stays valid as long as the owner
// keeps the same root identity. close() only lets an application stop showing the channel as open.

import {
  toIdentity, issueDelegation, verifyDelegation, deriveId, fromHex, verifyHex, totalBalance, fromUnits, lightweightKeypairFromSeed,
  buildSignedDelegatedClaimEvent, buildSignedDelegatedVoucherRedeemEvent,
} from 'aiwa-core';
import { delegateActor, issueVoucher, pay, payOffline } from './payments.js';
import { encodeOfflineBundle, decodeOfflineBundle } from './offline-bundle.js';
import { signerOf } from './signer.js';

const utf8 = new TextEncoder();

// A DETERMINISTIC per-(root, peer) session key: HMAC-SHA256 keyed by the root secret, so it is always recoverable (never
// a lost throwaway) and unique per peer (a compromised one affects no other channel).
async function sessionKeypairFor(rootKeypair, peerId) {
  const key = await crypto.subtle.importKey('raw', rootKeypair.secretKey.slice(0, 32), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = await crypto.subtle.sign('HMAC', key, utf8.encode(`aiwa-lib-channel-session-v1:${peerId}`));
  return lightweightKeypairFromSeed(new Uint8Array(mac));
}

// What the accepting side signs. Only the request id and who is accepting what: the request's own delegation is already
// a complete proof of who asks and for which session key.
const acceptMessage = ({ requestId, from, accepting, timestamp }) => utf8.encode(JSON.stringify({ requestId, from, accepting, timestamp }));

async function newChannel(wallet, peerId, status, requestId = null) {
  const sessionKeypair = await sessionKeypairFor(wallet.keypair, peerId);
  const delegation = await issueDelegation(...signerOf(wallet.keypair), sessionKeypair.publicKey.toBytes());
  const channel = new Channel({ aiwa: wallet, peerId, sessionKeypair, sessionIdentity: await toIdentity(sessionKeypair), delegation, status, requestId });
  return { channel, delegation };
}

/** A usable channel with `peerId` (unilateral). Requires a live network session unless `requireNetwork: false`. */
export async function openChannel(wallet, peerId, { requireNetwork = true } = {}) {
  wallet.requireConnected();
  if (requireNetwork && !wallet.replicator) {
    throw new Error('openChannel: no live network session — call joinNetwork() first. Once open, the channel itself works fully offline.');
  }
  return (await newChannel(wallet, peerId, 'confirmed')).channel;
}

/**
 * Step 1 of the handshake. Returns the request as a portable blob to hand to `peerId` over any channel, and the
 * channel itself, PENDING until the peer's acceptance is given to channel.confirm().
 */
export async function requestChannel(wallet, peerId) {
  wallet.requireConnected();
  const requestId = crypto.randomUUID();
  const { channel, delegation } = await newChannel(wallet, peerId, 'pending', requestId);
  const request = { type: 'channel-request', requestId, peerId, delegation, timestamp: Date.now() };
  return { blob: encodeOfflineBundle(request), channel };
}

/**
 * Step 2, on the peer's side: verifies a requestChannel() blob (from the delegation alone: no log, no state, so it works
 * offline) and signs an acceptance proving THIS identity deliberately consents to a channel with the requester. Hand the
 * blob back over the same channel. Accepting appends nothing: it is not an economic action.
 */
export async function acceptChannelRequest(wallet, requestBlob) {
  wallet.requireConnected();
  const request = decodeOfflineBundle(requestBlob);
  if (request?.type !== 'channel-request') throw new Error('acceptChannelRequest: not a real channel-request blob.');
  if (!(await verifyDelegation(request.delegation))) {
    throw new Error('acceptChannelRequest: the embedded delegation does not really verify — refusing to accept.');
  }
  const timestamp = Date.now();
  const accepting = request.delegation.from;
  const signature = await wallet.identity.sign(acceptMessage({ requestId: request.requestId, from: wallet.identity.id, accepting, timestamp }));
  return encodeOfflineBundle({
    type: 'channel-accept', requestId: request.requestId, from: wallet.identity.id, accepting,
    timestamp, signerPubkey: wallet.identity.publicKey, signature,
  });
}

export class Channel {
  constructor({ aiwa, peerId, sessionKeypair, sessionIdentity, delegation, status = 'confirmed', requestId = null }) {
    this._aiwa = aiwa;
    this.peerId = peerId;
    this._keypair = sessionKeypair;
    this.identity = sessionIdentity;
    this._delegation = delegation;
    this.status = status; // 'pending' (from requestChannel(), needs confirm()) or 'confirmed' (usable)
    this._requestId = requestId;
    this._actor = delegateActor(delegation, sessionKeypair, sessionIdentity);
  }

  /** This channel's own session address: distinct from the owner's root address, one per peer. */
  get address() { return this._keypair.publicKey.toBase58(); }

  /** The owner's log, for aiwa-platform functions that take a log directly. Works whether or not the owner's root identity is connected. */
  get log() { return this._aiwa.ledger.log; }

  _requireConfirmed() {
    if (this.status !== 'confirmed') {
      throw new Error('Channel: not confirmed yet — the peer has not accepted this channel request (see AIWA.requestChannel()/acceptChannelRequest(), and this channel\'s own confirm()).');
    }
  }

  /**
   * Step 3: verifies the peer's acceptance and, only if it checks out, marks the channel confirmed. Everything else
   * refuses to run before this. Checked, all of it load-bearing:
   * - the acceptance answers THIS channel's request, not some other;
   * - the signature verifies and its signer derives `accept.from`;
   * - `accept.from` is the peer this channel was opened for: otherwise anyone who merely obtained the request blob
   *   (never secret) could "accept" a channel meant for someone else.
   */
  async confirm(acceptBlob) {
    const accept = decodeOfflineBundle(acceptBlob);
    if (accept?.type !== 'channel-accept') throw new Error('Channel.confirm: not a real channel-accept blob.');
    if (accept.requestId !== this._requestId) throw new Error('Channel.confirm: this accept is for a different channel request.');
    if (accept.accepting !== this._delegation.from) throw new Error('Channel.confirm: this accept was not addressed to you.');
    if (accept.from !== this.peerId) throw new Error('Channel.confirm: accepted by someone other than the real peer this channel was opened for.');
    if ((await deriveId(fromHex(accept.signerPubkey))) !== accept.from) throw new Error('Channel.confirm: the signer does not really derive the claimed identity.');
    const { requestId, from, accepting, timestamp } = accept;
    if (!verifyHex(acceptMessage({ requestId, from, accepting, timestamp }), accept.signature, accept.signerPubkey)) {
      throw new Error('Channel.confirm: the real signature does not verify.');
    }
    this.status = 'confirmed';
  }

  /** What the owner has available through this or any channel: a delegation authorises moving the balance, never partitions it. Read from the delegation, so it works after the owner disconnects. */
  async balance() {
    const wallet = this._aiwa;
    return fromUnits(totalBalance(wallet.rewardParams, await wallet.ledger.state(), this._delegation.from));
  }

  /** A delegate-signed payment of `amount` to the channel's peer; splits a claim first if needed. Works after the owner's root identity disconnects. */
  async send(amount) {
    this._requireConfirmed();
    return pay(this._aiwa, this._actor, this.peerId, amount);
  }

  /** send() plus every ancestor the transfer needs: works over QR/NFC/Bluetooth like any other payment. */
  async sendOfflineBundle(amount) {
    this._requireConfirmed();
    return payOffline(this._aiwa, this._actor, this.peerId, amount);
  }

  /** A bearer voucher issued through this channel, same shape as AIWA.issueVoucher(). */
  async issueVoucher(amount) {
    this._requireConfirmed();
    return issueVoucher(this._aiwa, this._actor, amount);
  }

  /**
   * Redeems a bearer voucher through this channel, landing the value in the OWNER's identity, never the session's. An
   * ordinary voucher-redeem needs the signer to derive the destination, which a session key never does by construction;
   * the same delegation closes that gap.
   */
  async redeemVoucher({ secret, claimId, events }) {
    this._requireConfirmed();
    const wallet = this._aiwa;
    await wallet.ledger.log.appendMany(events);
    const signed = await buildSignedDelegatedVoucherRedeemEvent(this._delegation, { claimId, secret }, ...signerOf(this._keypair));
    const event = await wallet.ledger.append(this.identity, 'delegated-voucher-redeem', signed);
    await wallet.publish([event.id]);
    return { eventId: event.id };
  }

  /**
   * Claims claimable value into a spendable claim of the owner, through this channel. A session key is a different
   * keypair from the owner's root, so it cannot satisfy a plain 'claim' (whose signer must derive the domain): the
   * delegation does, as for every other action.
   */
  async claim(amount) {
    this._requireConfirmed();
    const wallet = this._aiwa;
    const claimId = crypto.randomUUID();
    const event = await wallet.miner.withLock(async () => {
      const signed = await buildSignedDelegatedClaimEvent(this._delegation, { claimId, amount, previous: await wallet.miner.previous() }, ...signerOf(this._keypair));
      return wallet.ledger.append(this.identity, 'delegated-claim', signed);
    });
    await wallet.publish([event.id]);
    return { claimId, eventId: event.id };
  }

  close() {}
}
