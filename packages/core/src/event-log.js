// The event log: stores verified events and nothing else. A device can run it alone, with no network and no server.
// The storage backend is pluggable: memory (tests, servers) or IndexedDB (browsers).

import { verifyEvent } from './event.js';
import { verifyCheckpoint } from './checkpoint.js';

/** The storage contract a backend satisfies: putEvent, getEvent, hasEvent, allIds, deleteEvent. */
export function createMemoryBackend() {
  const events = new Map();
  return {
    async putEvent(event) { events.set(event.id, event); },
    async getEvent(id) { return events.get(id) ?? null; },
    async hasEvent(id) { return events.has(id); },
    async allIds() { return [...events.keys()]; },
    async deleteEvent(id) { events.delete(id); },
  };
}

export function createIndexedDbBackend(dbName = 'aiwa-core-event-log') {
  let opening = null;
  const open = () => (opening ??= new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('events', { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => { opening = null; reject(request.error); };
  }));
  // One request in one transaction; resolves with the request's result once the transaction is complete.
  const run = async (mode, fn) => {
    const tx = (await open()).transaction('events', mode);
    const request = fn(tx.objectStore('events'));
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve(request.result ?? null);
      tx.onerror = () => reject(tx.error);
    });
  };
  return {
    putEvent: (event) => run('readwrite', (store) => store.put(event)).then(() => undefined),
    getEvent: (id) => run('readonly', (store) => store.get(id)),
    hasEvent: async (id) => (await run('readonly', (store) => store.get(id))) !== null,
    allIds: async () => (await run('readonly', (store) => store.getAllKeys())) ?? [],
    deleteEvent: (id) => run('readwrite', (store) => store.delete(id)).then(() => undefined),
  };
}

export class EventLog {
  constructor(backend = createMemoryBackend()) {
    this.backend = backend;
  }

  /**
   * Verifies, then stores. Verification is unconditional, whatever the event's source. An event whose parents are not
   * all known is refused — except a domain's own checkpoint, which may name parents this log has already pruned
   * (verifyCheckpoint requires its signer to be the domain it summarizes, so this is no general bypass).
   */
  async append(event) {
    if (await this.backend.hasEvent(event.id)) return;
    const verification = await verifyEvent(event);
    if (!verification.valid) throw new Error(`Cannot append: event ${event.id} failed verification (${verification.reason})`);
    if (!verifyCheckpoint(event)) {
      for (const parent of event.parents) {
        if (!(await this.backend.hasEvent(parent))) throw new Error(`Cannot append: parent ${parent} is not yet known; request it first.`);
      }
    }
    await this.backend.putEvent(event);
  }

  /** Appends a batch in any order: an event waits until its parents, possibly in the same batch, are in. */
  async appendMany(events) {
    const pending = [...events];
    for (let progressed = true; pending.length > 0 && progressed;) {
      progressed = false;
      for (let i = pending.length - 1; i >= 0; i--) {
        const event = pending[i];
        const ready = verifyCheckpoint(event) || (await Promise.all(event.parents.map((p) => this.backend.hasEvent(p)))).every(Boolean);
        if (!ready) continue;
        await this.append(event);
        pending.splice(i, 1);
        progressed = true;
      }
    }
    if (pending.length > 0) throw new Error(`appendMany: ${pending.length} event(s) have parents that never arrive.`);
  }

  /**
   * Deletes every event the checkpoint's own state already accounts for; the checkpoint becomes the root of local
   * storage. Bounds the growth of a domain that runs for good. The trade-off (checkpoint.js): someone who never saw the
   * pruned events cannot re-verify them from genesis, only trust the checkpoint's signature.
   */
  async pruneBeforeCheckpoint(checkpointEventId) {
    const checkpoint = await this.get(checkpointEventId);
    if (!checkpoint) throw new Error(`pruneBeforeCheckpoint: checkpoint ${checkpointEventId} is not in this log.`);
    if (!verifyCheckpoint(checkpoint)) throw new Error(`pruneBeforeCheckpoint: ${checkpointEventId} is not a self-authored checkpoint.`);
    const doomed = new Set();
    const stack = [...checkpoint.payload.coveredHeads];
    while (stack.length > 0) {
      const id = stack.pop();
      if (doomed.has(id) || id === checkpointEventId) continue;
      doomed.add(id);
      const event = await this.get(id);
      if (event) stack.push(...event.parents);
    }
    for (const id of doomed) await this.backend.deleteEvent(id);
    return doomed.size;
  }

  get(id) { return this.backend.getEvent(id); }
  has(id) { return this.backend.hasEvent(id); }

  async getParents(id) {
    const event = await this.get(id);
    return event ? Promise.all(event.parents.map((p) => this.get(p))) : [];
  }

  /**
   * The heads: known events that are nobody's parent. Computed from the backend at every call, never cached: a persisted
   * backend outlives any one EventLog (a reload, a restart builds a new one over the same storage).
   */
  async head() {
    const ids = await this.backend.allIds();
    const parents = new Set();
    for (const id of ids) for (const parent of (await this.backend.getEvent(id)).parents) parents.add(parent);
    return ids.filter((id) => !parents.has(id));
  }

  /** The events that are not ancestors of `knownIds`: the minimal set a peer announcing `knownIds` as its heads is missing. */
  async *since(knownIds) {
    const known = new Set();
    const stack = [...knownIds];
    while (stack.length > 0) {
      const id = stack.pop();
      if (known.has(id)) continue;
      known.add(id);
      const event = await this.get(id);
      if (event) stack.push(...event.parents);
    }
    for (const id of await this.backend.allIds()) if (!known.has(id)) yield await this.get(id);
  }
}
