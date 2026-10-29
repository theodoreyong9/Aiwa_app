// The Transport — knows nothing of profiles, DAGs, AIWA,
// messages, users, or transactions. Only bytes, to peers.
// No third-party transport is used anywhere
// in this package — see webrtc-transport.js for the relay-free
// WebRTC implementation, and LoopbackTransport below for tests.
//
// Every transport in this package (and any future one — a
// WebSocket relay, LAN discovery, ...) implements the identical, real,
// five-method contract, so nothing above it (Replicator) ever changes:
// connect(), disconnect(), peers(), send(peer, bytes),
// broadcast(bytes), onMessage(handler), onPeerJoin(handler),
// onPeerLeave(handler)

/** An in-process, in-memory transport — for deterministic tests, never for two separate devices. */
export class LoopbackTransport {
  static _registry = new Map();

  constructor(peerId) {
    this.peerId = peerId;
    this._onMessageHandlers = new Set();
    this._onJoinHandlers = new Set();
    this._onLeaveHandlers = new Set();
  }
  async connect() {
    for (const [id] of LoopbackTransport._registry) {
      for (const h of this._onJoinHandlers) h(id);
      for (const h of LoopbackTransport._registry.get(id)._onJoinHandlers) h(this.peerId);
    }
    LoopbackTransport._registry.set(this.peerId, this);
  }
  async disconnect() {
    LoopbackTransport._registry.delete(this.peerId);
    for (const [, t] of LoopbackTransport._registry) for (const h of t._onLeaveHandlers) h(this.peerId);
  }
  peers() { return [...LoopbackTransport._registry.keys()].filter((id) => id !== this.peerId); }
  async send(peer, bytes) {
    const target = LoopbackTransport._registry.get(peer);
    if (target) for (const h of target._onMessageHandlers) h(this.peerId, bytes);
  }
  async broadcast(bytes) {
    for (const peer of this.peers()) await this.send(peer, bytes);
  }
  onMessage(handler) { this._onMessageHandlers.add(handler); return () => this._onMessageHandlers.delete(handler); }
  onPeerJoin(handler) { this._onJoinHandlers.add(handler); return () => this._onJoinHandlers.delete(handler); }
  onPeerLeave(handler) { this._onLeaveHandlers.add(handler); return () => this._onLeaveHandlers.delete(handler); }
}
