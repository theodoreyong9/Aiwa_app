// Our own, relay-free P2P transport — no Nostr relay, no
// signaling server, no third-party dependency of any kind. Real,
// direct RTCPeerConnection, STUN-only for NAT traversal (STUN servers
// never see application data and never even see that two peers are
// related — they only ever answer "what's my own public address").
// The one signaling exchange every new connection needs still has
// to travel over SOME out-of-band channel — pasted text, a QR
// code, a shared file, an already-open connection to a third peer —
// but this class never picks or uses one itself: createOfferFor() /
// acceptOffer() / completeConnection() only ever hand back or accept
// an opaque, signal blob (see signaling-codec.js).
//
// Implements the identical five-method Transport contract every other
// transport in this package satisfies (connect/disconnect/peers/send/
// broadcast + join/leave/message handlers), so Replicator works with
// this unchanged — just built from many individual direct connections
// instead of one shared relay-based room.
//
// HONEST LIMIT: RTCPeerConnection doesn't exist in Node, so the real
// network path (ICE negotiation, SDP, data flow) has no
// meaningful test here — see webrtc-transport.test.mjs for what IS
// covered (this class's own connection bookkeeping and
// validation, against a minimal, deliberately fake PC) and what isn't.
//
// Verified with two separate browser tabs (Playwright, real
// Chromium, RTCPeerConnection) in this environment: full ICE
// gathering (waiting for iceGatheringState === 'complete') hung
// indefinitely — STUN traffic (UDP) appears to be blocked by this
// sandbox's network policy, so the srflx candidate never resolves and
// gathering never reaches 'complete' on its own. `waitForIceGatheringComplete`
// is bounded by a timeout for exactly this reason: send the offer/answer
// with whatever candidates (host, and srflx if it arrived) were gathered
// in time, rather than waiting forever for one that may never come. This
// is not a workaround specific to this sandbox — deployments hit the
// same failure mode against restrictive firewalls, so a bounded wait is
// the correct behavior in general, not just here.

import { encodeSignal, decodeSignal } from './signaling-codec.js';

const DEFAULT_ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }];
const DEFAULT_ICE_GATHERING_TIMEOUT_MS = 3000;

function waitForIceGatheringComplete(pc, timeoutMs = DEFAULT_ICE_GATHERING_TIMEOUT_MS) {
  if (pc.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve) => {
    let settled = false;
    function finish() {
      if (settled) return;
      settled = true;
      pc.removeEventListener('icegatheringstatechange', check);
      clearTimeout(timer);
      resolve();
    }
    function check() {
      if (pc.iceGatheringState === 'complete') finish();
    }
    pc.addEventListener('icegatheringstatechange', check);
    const timer = setTimeout(finish, timeoutMs);
  });
}

export class WebrtcTransport {
  constructor({
    selfId = crypto.randomUUID(),
    iceServers = DEFAULT_ICE_SERVERS,
    dataChannelLabel = 'aiwa-platform',
    iceGatheringTimeoutMs = DEFAULT_ICE_GATHERING_TIMEOUT_MS,
    createPeerConnection = (config) => new RTCPeerConnection(config),
  } = {}) {
    this.selfId = selfId;
    this._iceServers = iceServers;
    this._dataChannelLabel = dataChannelLabel;
    this._iceGatheringTimeoutMs = iceGatheringTimeoutMs;
    this._createPeerConnection = createPeerConnection;
    this._links = new Map(); // peerId -> { pc, channel } — both pending (not yet open) and open connections
    this._openPeers = new Set(); // the subset of _links whose channel has opened
    this._onMessageHandlers = new Set();
    this._onJoinHandlers = new Set();
    this._onLeaveHandlers = new Set();
  }

  // Nothing to "join" without a relay — connections are made one
  // at a time via createOfferFor/acceptOffer/completeConnection.
  async connect() {}
  async disconnect() {
    for (const peerId of [...this._links.keys()]) this._closeLink(peerId);
  }

  peers() {
    return [...this._openPeers];
  }

  /** Every peer there is a link to, open or still being made: what a new introduction must not offer again. */
  linked() {
    return [...this._links.keys()];
  }

  /** Gives up the link to `peerId` only if it never opened (an introduction that failed leaves one behind, and it blocks the next try). */
  closePending(peerId) {
    if (this._links.has(peerId) && !this._openPeers.has(peerId)) this._closeLink(peerId);
  }

  async send(peerId, bytes) {
    const link = this._links.get(peerId);
    if (link?.channel?.readyState === 'open') link.channel.send(bytes);
  }
  async broadcast(bytes) {
    for (const peerId of this.peers()) await this.send(peerId, bytes);
  }

  onMessage(handler) { this._onMessageHandlers.add(handler); return () => this._onMessageHandlers.delete(handler); }
  onPeerJoin(handler) { this._onJoinHandlers.add(handler); return () => this._onJoinHandlers.delete(handler); }
  onPeerLeave(handler) { this._onLeaveHandlers.add(handler); return () => this._onLeaveHandlers.delete(handler); }

  _wireChannel(peerId, pc, channel) {
    this._links.set(peerId, { pc, channel });
    const opened = () => {
      if (this._openPeers.has(peerId)) return;
      this._openPeers.add(peerId);
      for (const h of this._onJoinHandlers) h(peerId);
    };
    channel.onopen = opened;
    // A channel the other side opened (ondatachannel) may already be open when it reaches us: its 'open' event is not coming.
    // Found by linking two real browser pages: the answering phone never knew the link was up.
    if (channel.readyState === 'open') queueMicrotask(opened);
    channel.onmessage = (e) => {
      const bytes = e.data instanceof Uint8Array ? e.data : new Uint8Array(e.data);
      for (const h of this._onMessageHandlers) h(peerId, bytes);
    };
    channel.onclose = () => this._closeLink(peerId);
  }

  /** Gives up the link to `peerId`, open or not (a link started and never completed would otherwise wait for ever). */
  closePeer(peerId) { this._closeLink(peerId); }

  _closeLink(peerId) {
    const link = this._links.get(peerId);
    if (!link) return;
    this._links.delete(peerId);
    const wasOpen = this._openPeers.delete(peerId);
    try { link.channel?.close(); } catch { /* already closing */ }
    try { link.pc.close(); } catch { /* already closed */ }
    if (wasOpen) for (const h of this._onLeaveHandlers) h(peerId);
  }

  /** The initiating side: opens a data channel, gathers an offer, returns an opaque blob to send `remotePeerId` over any out-of-band channel. */
  async createOfferFor(remotePeerId) {
    if (this._links.has(remotePeerId)) throw new Error(`Already connected (or connecting) to '${remotePeerId}'.`);
    const pc = this._createPeerConnection({ iceServers: this._iceServers });
    const channel = pc.createDataChannel(this._dataChannelLabel);
    this._wireChannel(remotePeerId, pc, channel);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIceGatheringComplete(pc, this._iceGatheringTimeoutMs);
    return encodeSignal('offer', this.selfId, pc.localDescription.sdp);
  }

  /**
   * The responding side: accepts an offer blob received out-of-band,
   * returns an answer blob to send back over the same channel.
   * Registers the new connection under the offer's own `originId`
   * unless `peerId` overrides it.
   */
  async acceptOffer(offerBlob, { peerId } = {}) {
    const decoded = decodeSignal(offerBlob);
    if (decoded.kind !== 'offer') throw new Error('acceptOffer: expected an offer, not an answer.');
    const id = peerId ?? decoded.originId;
    if (this._links.has(id)) throw new Error(`Already connected (or connecting) to '${id}'.`);
    const pc = this._createPeerConnection({ iceServers: this._iceServers });
    pc.ondatachannel = (e) => this._wireChannel(id, pc, e.channel);
    await pc.setRemoteDescription({ type: 'offer', sdp: decoded.sdp });
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    await waitForIceGatheringComplete(pc, this._iceGatheringTimeoutMs);
    return encodeSignal('answer', this.selfId, pc.localDescription.sdp);
  }

  /** The initiating side: completes a connection previously started with createOfferFor, using the answer blob received back out-of-band. */
  async completeConnection(remotePeerId, answerBlob) {
    const link = this._links.get(remotePeerId);
    if (!link) throw new Error(`No pending connection to '${remotePeerId}' — call createOfferFor(remotePeerId) first.`);
    const decoded = decodeSignal(answerBlob);
    if (decoded.kind !== 'answer') throw new Error('completeConnection: expected an answer, not an offer.');
    await link.pc.setRemoteDescription({ type: 'answer', sdp: decoded.sdp });
  }
}
