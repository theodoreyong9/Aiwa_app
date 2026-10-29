// The Replicator — uses a Transport (never knows which
// one) to sync an EventLog with peers, sending only the
// minimal set of missing events — never "here is my entire
// database." The HELLO / EVENTS / ACK protocol, kept
// deliberately simple for this v0.1.

function encode(msg) { return new TextEncoder().encode(JSON.stringify(msg)); }
function decode(bytes) { return JSON.parse(new TextDecoder().decode(bytes)); }

// A minimal topological pass — matches EventLog.appendMany's own
// approach (same "keep retrying" shape). Needed here because
// log.since()'s own output order is whatever the backend's
// allIds() happens to return, never guaranteed parents-before-children
// — fine for a single appendMany() call (its own internal retry loop
// already tolerates any order), but NOT fine once that same list gets
// split across several separate EVENTS messages: a child sent in an
// earlier chunk than its parent would make THAT chunk's own
// appendMany() fail with an unresolvable-parent error on the
// receiving side. Sorting once here, before chunking, is what keeps
// every individual chunk self-consistent (or dependent only on
// something the receiver already has, or an earlier chunk already
// delivered).
function topologicalOrder(events) {
  const byId = new Set(events.map((e) => e.id));
  const resolved = new Set();
  const ordered = [];
  const pending = [...events];
  let progressed = true;
  while (pending.length > 0 && progressed) {
    progressed = false;
    for (let i = pending.length - 1; i >= 0; i--) {
      const event = pending[i];
      // A parent this batch doesn't itself contain must already be
      // resolvable on the receiving side (already in their log, or a
      // checkpoint bypassing the parent check entirely) — never a
      // reason to hold this event back from an early chunk.
      if (event.parents.every((p) => resolved.has(p) || !byId.has(p))) {
        ordered.push(event);
        resolved.add(event.id);
        pending.splice(i, 1);
        progressed = true;
      }
    }
  }
  // Any unresolvable cycle within this exact batch (should never
  // happen — EventLog's own DAG has no cycles) is appended as-is
  // rather than silently dropped; the receiving appendMany() surfaces
  // the error if something is broken.
  return [...ordered, ...pending];
}

export class Replicator {
  // chunkSize: the most events in one message. maxChunkBytes: the most bytes in one message (a data channel carries a message of 256 KiB at
  // most, and a bigger one closes the link: found linking two real browser pages, whose chunks of 100 events came to 300 KB).
  constructor({ transport, log, domain, chunkSize = 100, maxChunkBytes = 64 * 1024 }) {
    this.transport = transport;
    this.log = log;
    this.domain = domain;
    this.chunkSize = chunkSize;
    this.maxChunkBytes = maxChunkBytes;
    this._onEventHandlers = new Set();
    this._onSyncHandlers = new Set();
    // per-peer outbound backpressure for a full sync: see
    // _sendChunked's own header for why a single HELLO/HELLO_ACK can no
    // longer just dump the entire missing set into one message.
    this._pendingChunks = new Map(); // peer -> event[][] still queued
    this._lastSentChunkIds = new Map(); // peer -> Set(ids) of the chunk currently awaiting an ACK
    // bug found while chunking this: the existing HELLO/HELLO_ACK
    // exchange already computes and sends "what's missing" TWICE per
    // connection (once handling their HELLO, again handling their
    // own HELLO_ACK — same announced heads, since nothing changes for
    // them in between) — harmless before chunking (EventLog.append()'s
    // own idempotency silently absorbs the redundant resend), but a
    // bug once chunked: a second _sendChunked() call for a peer
    // already mid-sync would clobber _pendingChunks/_lastSentChunkIds
    // and put two chunks in flight at once, defeating the
    // whole point. _syncInFlight skips the redundant second call
    // outright — the in-progress sync already covers the same ground.
    this._syncInFlight = new Set();
  }

  async start() {
    this._queue = Promise.resolve(); // a simple, sequential queue — messages must never interleave mid-handling, or a race (computing our own heads before a concurrently-arriving EVENTS message finishes appending) can silently corrupt a sync round
    this._unsubMessage = this.transport.onMessage((peer, bytes) => {
      this._queue = this._queue.then(() => this._handleMessage(peer, bytes)).catch((err) => console.error('Real replicator message handling failed:', err));
    });
    this._unsubJoin = this.transport.onPeerJoin((peer) => {
      this._queue = this._queue.then(() => this._sayHello(peer)).catch((err) => console.error('Real replicator hello failed:', err));
    });
    await this.transport.connect();
  }

  async stop() {
    this._unsubMessage?.();
    this._unsubJoin?.();
    await this.transport.disconnect();
    this._pendingChunks.clear();
    this._lastSentChunkIds.clear();
    this._syncInFlight.clear();
  }

  async _sayHello(peer) {
    const heads = await this.log.head();
    await this.transport.send(peer, encode({ type: 'HELLO', domain: this.domain, heads }));
  }

  /**
   * Sends `events` (already topologically ordered) to `peer` in
   * bounded chunks, one at a time — never the whole backlog in a
   * single message. The previously-unaddressed limit this closes
   * (yellow paper §14.3): a domain that has been offline a long time,
   * or a brand-new peer receiving a long history, used to receive
   * every missing event in ONE unbounded message — a memory
   * and bandwidth spike proportional to total history size, on both the
   * sender (building it) and the receiver (buffering it before a single
   * appendMany() call). Only the first chunk is sent immediately; the
   * rest queue in _pendingChunks and are released one at a time, each
   * only once the previous chunk's own ACK arrives (see
   * the ACK handler below) — backpressure, not a fixed delay.
   */
  async _sendChunked(peer, events) {
    if (events.length === 0) return;
    // See _syncInFlight's own comment in the constructor: HELLO and
    // HELLO_ACK both independently call this for the same peer with the
    // same missing set — the second call is redundant, and would
    // otherwise clobber the first one's still-in-progress queue.
    if (this._syncInFlight.has(peer)) return;
    const ordered = topologicalOrder(events);
    const chunks = [];
    let current = [];
    let bytes = 0;
    for (const event of ordered) {
      const size = new TextEncoder().encode(JSON.stringify(event)).length;
      if (current.length > 0 && (current.length >= this.chunkSize || bytes + size > this.maxChunkBytes)) {
        chunks.push(current);
        current = [];
        bytes = 0;
      }
      current.push(event);        // an event larger than the bound goes alone: it cannot be split
      bytes += size;
    }
    if (current.length > 0) chunks.push(current);
    this._syncInFlight.add(peer);
    this._pendingChunks.set(peer, chunks.slice(1));
    await this._sendChunk(peer, chunks[0]);
  }

  async _sendChunk(peer, chunk) {
    this._lastSentChunkIds.set(peer, new Set(chunk.map((e) => e.id)));
    await this.transport.send(peer, encode({ type: 'EVENTS', domain: this.domain, events: chunk }));
  }

  /**
   * Releases the next queued chunk for `peer`, but only once `ackedIds`
   * really is the exact chunk we're currently waiting on — an ACK for
   * something else entirely (an ordinary publish() broadcast, arriving
   * mid-sync) must never make this fire early, and must never be
   * mistaken for progress on a sync that isn't even running.
   */
  async _advanceChunkQueue(peer, ackedIds) {
    const awaiting = this._lastSentChunkIds.get(peer);
    if (!awaiting) return; // no chunked sync in flight for this peer at all
    if (ackedIds.length !== awaiting.size || !ackedIds.every((id) => awaiting.has(id))) return;

    const queue = this._pendingChunks.get(peer) ?? [];
    if (queue.length === 0) {
      // The final chunk of this sync just got acked — done.
      this._pendingChunks.delete(peer);
      this._lastSentChunkIds.delete(peer);
      this._syncInFlight.delete(peer);
      return;
    }
    const next = queue.shift(); // mutates the same array _pendingChunks already holds for this peer
    if (queue.length === 0) this._pendingChunks.delete(peer);
    await this._sendChunk(peer, next);
  }

  async _handleMessage(peer, bytes) {
    const msg = decode(bytes);
    if (msg.domain !== this.domain) return; // different domain — not this replicator's concern

    if (msg.type === 'HELLO') {
      // The minimal-missing-ancestor computation: every real
      // event this side has that is not reachable from the real,
      // announced heads is a plausible gap on their side.
      const missing = [];
      for await (const event of this.log.since(msg.heads)) missing.push(event);
      await this._sendChunked(peer, missing);
      // Also tell them our own heads, so a one-sided HELLO becomes a two-way exchange.
      const heads = await this.log.head();
      await this.transport.send(peer, encode({ type: 'HELLO_ACK', domain: this.domain, heads }));
    }

    if (msg.type === 'HELLO_ACK') {
      const missing = [];
      for await (const event of this.log.since(msg.heads)) missing.push(event);
      await this._sendChunked(peer, missing);
    }

    if (msg.type === 'EVENTS') {
      await this.log.appendMany(msg.events);
      for (const event of msg.events) for (const h of this._onEventHandlers) h(event);
      await this.transport.send(peer, encode({ type: 'ACK', domain: this.domain, ids: msg.events.map((e) => e.id) }));
      for (const h of this._onSyncHandlers) h({ peer, receivedCount: msg.events.length });
    }

    if (msg.type === 'ACK') {
      for (const h of this._onSyncHandlers) h({ peer, ackedIds: msg.ids });
      await this._advanceChunkQueue(peer, msg.ids);
    }
  }

  /** explicit publish — pushes given events to every currently-connected peer. Never chunked: publish() is for a small, deliberate set of new events (a transfer, a claim), not a full-history catch-up sync — see _sendChunked for that. */
  async publish(events) {
    await this.transport.broadcast(encode({ type: 'EVENTS', domain: this.domain, events }));
  }

  onEvent(handler) { this._onEventHandlers.add(handler); return () => this._onEventHandlers.delete(handler); }
  onSync(handler) { this._onSyncHandlers.add(handler); return () => this._onSyncHandlers.delete(handler); }
}
