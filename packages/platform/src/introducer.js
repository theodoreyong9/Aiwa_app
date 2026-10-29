// The concrete answer to the part of "the bootstrap problem"
// that's actually solvable: once a brand-new peer has its very first
// connection — obtained via ANY out-of-band exchange (a
// pasted link, a QR code, in person; see webrtc-transport.js's own
// createOfferFor/acceptOffer, which deliberately never picks that
// channel itself) — it can grow the rest of its connections with zero
// fixed server, zero directory, ever: ask that first peer (a
// "mediator") to introduce it to one of the mediator's OTHER real
// peers, exactly the way a person introduces two friends who don't
// know each other. The mediator relays a WebRTC offer/answer
// between the two over its own two already-open data channels — a
// working, automatic substitute for a human manually
// copy-pasting a signal blob — after which the two have a genuinely
// DIRECT connection; the mediator is not in that connection's data
// path at all once it's done.
//
// HONEST LIMIT: this only ever GROWS an existing connection. The very
// first connection of a brand-new peer — or the first two peers of a
// brand-new network, with nobody around yet to mediate — still needs
// an out-of-band exchange. No P2P system of any kind
// (BitTorrent's own magnet link, a DHT's bootstrap nodes, Bitcoin's
// own seed nodes) escapes this; it isn't specific to AIWA, and isn't
// solved here.
//
// Only meaningful with WebrtcTransport (or any transport exposing the
// same createOfferFor/acceptOffer/completeConnection signaling
// methods) — a relay-based transport where every peer already shares
// one room (LoopbackTransport) has no "introduction" to make.

const PROTOCOL = 'aiwa-platform-introduction-v1';

function encode(msg) { return new TextEncoder().encode(JSON.stringify({ protocol: PROTOCOL, ...msg })); }
function decode(bytes) {
  let msg;
  try { msg = JSON.parse(new TextDecoder().decode(bytes)); } catch { return null; }
  return msg && msg.protocol === PROTOCOL ? msg : null;
}

export class Introducer {
  constructor({ transport }) {
    this.transport = transport;
    this._requests = new Map(); // sessionId -> { resolve, reject } — our own pending requestIntroduction() calls
    this._mediating = new Map(); // sessionId -> { a, b } — two peer ids we're relaying between, as a mediator
    this._roles = new Map(); // sessionId -> { role, peerId } — our own role when WE are one of the two being introduced
    // Two independent connections (mediator<->A, mediator<->P) give
    // no cross-channel delivery-order guarantee: an INTRO_RELAY can
    // arrive here before the INTRO_ASSIGN that explains it.
    // Buffered here until the matching ASSIGN tells us what to do with it.
    this._bufferedRelays = new Map(); // sessionId -> { from, payload }
  }

  start() {
    this._unsub = this.transport.onMessage((peerId, bytes) => this._handleMessage(peerId, bytes));
  }

  stop() {
    this._unsub?.();
  }

  /**
   * Asks `mediatorPeerId` (an existing, currently-open peer) to
   * introduce us to one of ITS other peers. Resolves with the new
   * peer's id once a direct connection is established;
   * rejects if the mediator has nobody new to offer, or the real
   * connection attempt itself fails.
   */
  requestIntroduction(mediatorPeerId, { exclude = [] } = {}) {
    const sessionId = crypto.randomUUID();
    const result = new Promise((resolve, reject) => this._requests.set(sessionId, { resolve, reject }));
    this.transport.send(mediatorPeerId, encode({ type: 'INTRO_REQUEST', sessionId, exclude }));
    return result;
  }

  async _handleMessage(peerId, bytes) {
    const msg = decode(bytes);
    if (!msg) return;

    if (msg.type === 'INTRO_REQUEST') {
      const exclude = new Set([...(msg.exclude ?? []), peerId, this.transport.selfId]);
      const candidate = this.transport.peers().find((id) => !exclude.has(id));
      if (!candidate) {
        await this.transport.send(peerId, encode({ type: 'INTRO_FAILED', sessionId: msg.sessionId, reason: 'The mediator has no other real peer to introduce.' }));
        return;
      }
      this._mediating.set(msg.sessionId, { a: peerId, b: candidate });
      await this.transport.send(peerId, encode({ type: 'INTRO_ASSIGN', sessionId: msg.sessionId, role: 'offerer', peerId: candidate }));
      await this.transport.send(candidate, encode({ type: 'INTRO_ASSIGN', sessionId: msg.sessionId, role: 'answerer', peerId }));
      return;
    }

    if (msg.type === 'INTRO_ASSIGN') {
      if (this.transport.linked?.().includes(msg.peerId)) {
        await this.transport.send(peerId, encode({ type: 'INTRO_FAILED', sessionId: msg.sessionId, reason: `Already connected (or connecting) to '${msg.peerId}'.` }));
        this._requests.get(msg.sessionId)?.reject(new Error(`Already connected (or connecting) to '${msg.peerId}'.`));
        this._requests.delete(msg.sessionId);
        return;
      }
      this._roles.set(msg.sessionId, { role: msg.role, peerId: msg.peerId, mediator: peerId });
      if (msg.role === 'offerer') {
        try {
          const offerBlob = await this.transport.createOfferFor(msg.peerId);
          await this.transport.send(peerId, encode({ type: 'INTRO_RELAY', sessionId: msg.sessionId, payload: offerBlob }));
        } catch (err) {
          await this._fail(msg.sessionId, peerId, err.message);
        }
        return;
      }
      // role === 'answerer': the offer normally arrives next, via
      // INTRO_RELAY — but it may already have (see this._bufferedRelays).
      const buffered = this._bufferedRelays.get(msg.sessionId);
      if (buffered) {
        this._bufferedRelays.delete(msg.sessionId);
        await this._processRelay(msg.sessionId, buffered.payload);
      }
      return;
    }

    if (msg.type === 'INTRO_RELAY') {
      // We are the mediator: forward verbatim to the OTHER participant in this session.
      const pair = this._mediating.get(msg.sessionId);
      if (pair) {
        const other = pair.a === peerId ? pair.b : pair.a;
        await this.transport.send(other, encode({ type: 'INTRO_RELAY', sessionId: msg.sessionId, payload: msg.payload }));
        return;
      }
      // We are one of the two being introduced. If our own INTRO_ASSIGN
      // (a different connection) hasn't arrived yet, buffer this —
      // no ordering is guaranteed across two independent connections.
      if (!this._roles.has(msg.sessionId)) {
        this._bufferedRelays.set(msg.sessionId, { payload: msg.payload });
        return;
      }
      await this._processRelay(msg.sessionId, msg.payload);
      return;
    }

    if (msg.type === 'INTRO_FAILED') {
      // Forward to the other participant if we're mediating this session, so it doesn't hang waiting forever.
      const pair = this._mediating.get(msg.sessionId);
      if (pair) {
        const other = pair.a === peerId ? pair.b : pair.a;
        await this.transport.send(other, encode({ type: 'INTRO_FAILED', sessionId: msg.sessionId, reason: msg.reason }));
        this._mediating.delete(msg.sessionId);
        return;
      }
      const role = this._roles.get(msg.sessionId);
      if (role) this.transport.closePending?.(role.peerId);       // the link started for it will never open, and would block the next try
      this._requests.get(msg.sessionId)?.reject(new Error(msg.reason));
      this._requests.delete(msg.sessionId);
      this._roles.delete(msg.sessionId);
    }
  }

  async _processRelay(sessionId, payload) {
    const role = this._roles.get(sessionId);
    if (!role) return; // a stray/duplicate relay for a session we no longer track
    try {
      if (role.role === 'answerer') {
        const answerBlob = await this.transport.acceptOffer(payload, { peerId: role.peerId });
        await this.transport.send(role.mediator, encode({ type: 'INTRO_RELAY', sessionId, payload: answerBlob }));
      } else {
        await this.transport.completeConnection(role.peerId, payload);
        this._requests.get(sessionId)?.resolve(role.peerId);
        this._requests.delete(sessionId);
      }
    } catch (err) {
      this.transport.closePending?.(role.peerId);
      await this._fail(sessionId, role.mediator, err.message);
    } finally {
      this._roles.delete(sessionId);
    }
  }

  async _fail(sessionId, relayTo, reason) {
    await this.transport.send(relayTo, encode({ type: 'INTRO_FAILED', sessionId, reason }));
    this._requests.get(sessionId)?.reject(new Error(reason));
    this._requests.delete(sessionId);
  }
}
