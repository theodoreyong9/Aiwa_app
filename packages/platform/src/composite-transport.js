// Several transports used as one. A wallet has a single Replicator, and so a single transport; it meets other wallets in two ways
// (by itself, in a Trystero room, and by hand, with the two codes of a WebrtcTransport), and both feed the same log. This puts
// them behind the one contract: the peers are those of all of them, a message goes out by the transport its peer belongs to, and
// what comes in from any of them reaches the same handlers.

export class CompositeTransport {
  constructor(transports) {
    if (!Array.isArray(transports) || transports.length === 0) throw new Error('CompositeTransport needs at least one transport');
    this._transports = transports;
  }

  get selfId() { return this._transports.find((t) => t.selfId)?.selfId; }

  async connect() { await Promise.all(this._transports.map((t) => t.connect())); }
  async disconnect() { await Promise.all(this._transports.map((t) => t.disconnect())); }

  peers() { return [...new Set(this._transports.flatMap((t) => t.peers()))]; }

  async send(peer, bytes) {
    const owner = this._transports.find((t) => t.peers().includes(peer));
    if (owner) await owner.send(peer, bytes);
  }

  async broadcast(bytes) { await Promise.all(this._transports.map((t) => t.broadcast(bytes))); }

  // The signaling of a direct connection (an offer, an answer) goes to the transport that makes them: with these, an Introducer can
  // work over the composite, relaying through whichever peer is nearest and opening the new link where it can be opened.
  _signaling() { return this._transports.find((t) => typeof t.createOfferFor === 'function'); }
  createOfferFor(peer) { return this._need().createOfferFor(peer); }
  acceptOffer(blob, options) { return this._need().acceptOffer(blob, options); }
  completeConnection(peer, blob) { return this._need().completeConnection(peer, blob); }
  closePeer(peer) { this._signaling()?.closePeer?.(peer); }
  closePending(peer) { this._signaling()?.closePending?.(peer); }
  linked() { return this._signaling()?.linked?.() ?? []; }
  _need() {
    const transport = this._signaling();
    if (!transport) throw new Error('none of these transports makes direct connections');
    return transport;
  }

  onMessage(handler) { return this._all((t) => t.onMessage(handler)); }
  onPeerJoin(handler) { return this._all((t) => t.onPeerJoin(handler)); }
  onPeerLeave(handler) { return this._all((t) => t.onPeerLeave(handler)); }

  _all(register) {
    const removers = this._transports.map(register);
    return () => removers.forEach((remove) => remove());
  }
}
