// A Transport over a Trystero room: the wallets that are open find each other by themselves, with no code to swap and no
// server of ours. Trystero introduces two peers through a public relay (Nostr, by default) that sees only that someone
// is looking for peers in this room, never the data; the data then goes over a direct WebRTC channel between the two.
//
// It implements the same contract as every other transport of this package (connect, disconnect, peers, send, broadcast,
// onMessage, onPeerJoin, onPeerLeave), so the Replicator above it does not change. `joinRoom` is given by the caller
// (`import { joinRoom, selfId } from '@trystero-p2p/nostr'`): this package depends on no third-party transport, and a test can
// give it a fake room.
//
// HONEST LIMIT: the real path (a relay, ICE, a data channel) needs real browsers: apps/web's end-to-end test runs it between
// two pages with a relay of its own on the loopback address; what this package's tests cover is this class's bookkeeping,
// against a fake room.

const toBytes = (data) => {
  if (data instanceof Uint8Array) return data;
  if (ArrayBuffer.isView(data)) return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  if (typeof data === 'string') return new TextEncoder().encode(data);
  throw new Error('a message that is not bytes');
};

export class TrysteroTransport {
  /**
   * @param {object} options
   * @param {Function} options.joinRoom   Trystero's joinRoom (a strategy's own)
   * @param {string} options.appId        what tells this application's rooms from another's
   * @param {string} options.roomId       the room the wallets meet in
   * @param {string} [options.selfId]     this peer's own id in the room (Trystero's `selfId`)
   * @param {string[]} [options.relayUrls] relays to use instead of the strategy's own list
   * @param {object} [options.rtcConfig]  RTCPeerConnection's configuration (its ICE servers)
   * @param {boolean} [options.enabled]   false: connect() does nothing until `enabled` is set (a person who turned the network off)
   */
  constructor({ joinRoom, appId, roomId, selfId = null, relayUrls = null, rtcConfig = null, enabled = true }) {
    if (typeof joinRoom !== 'function') throw new Error('TrysteroTransport needs joinRoom');
    this._joinRoom = joinRoom;
    this._appId = appId;
    this._roomId = roomId;
    this.selfId = selfId;
    this._relayUrls = relayUrls;
    this._rtcConfig = rtcConfig;
    this.enabled = enabled;
    this._room = null;
    this._action = null;
    this._peers = new Set();
    this._onMessageHandlers = new Set();
    this._onJoinHandlers = new Set();
    this._onLeaveHandlers = new Set();
  }

  get connected() { return this._room !== null; }

  async connect() {
    if (this._room || !this.enabled) return;
    const config = { appId: this._appId };
    if (this._relayUrls) config.relayConfig = { urls: this._relayUrls };
    if (this._rtcConfig) config.rtcConfig = this._rtcConfig;
    const room = this._joinRoom(config, this._roomId);
    const action = room.makeAction('aiwa');
    action.onMessage = (data, context) => {
      let bytes;
      try { bytes = toBytes(data); } catch { return; }      // not ours: ignored
      for (const handler of this._onMessageHandlers) handler(context.peerId, bytes);
    };
    room.onPeerJoin = (peerId) => {
      if (this._peers.has(peerId)) return;
      this._peers.add(peerId);
      for (const handler of this._onJoinHandlers) handler(peerId);
    };
    room.onPeerLeave = (peerId) => {
      if (!this._peers.delete(peerId)) return;
      for (const handler of this._onLeaveHandlers) handler(peerId);
    };
    this._room = room;
    this._action = action;
  }

  async disconnect() {
    const room = this._room;
    if (!room) return;
    this._room = null;
    this._action = null;
    const gone = [...this._peers];
    this._peers.clear();
    try { await room.leave(); } catch { /* the room is gone either way */ }
    for (const peerId of gone) for (const handler of this._onLeaveHandlers) handler(peerId);
  }

  peers() { return [...this._peers]; }

  async send(peer, bytes) {
    if (!this._action || !this._peers.has(peer)) return;
    await this._action.send(bytes, { target: peer });
  }

  async broadcast(bytes) {
    if (!this._action || this._peers.size === 0) return;
    await this._action.send(bytes, { target: [...this._peers] });
  }

  onMessage(handler) { this._onMessageHandlers.add(handler); return () => this._onMessageHandlers.delete(handler); }
  onPeerJoin(handler) { this._onJoinHandlers.add(handler); return () => this._onJoinHandlers.delete(handler); }
  onPeerLeave(handler) { this._onLeaveHandlers.add(handler); return () => this._onLeaveHandlers.delete(handler); }
}
