// A key-value view over an event log. Never the source of truth: the log is, and this is rebuilt from it.

import { createEvent } from './event.js';
import { defaultKvMaterializer } from './materializer.js';

export class DataStore {
  constructor({ identity, domain, log, materializer = defaultKvMaterializer }) {
    this.identity = identity;
    this.domain = domain;
    this.log = log;
    this.materializer = materializer;
    this._state = materializer.initialState();
    this._listeners = new Set();
  }

  async get(key) { return this._state[key]; }
  async has(key) { return key in this._state; }
  async keys() { return Object.keys(this._state); }

  /** Every write is an event appended to the log, then applied. */
  async set(key, value) { await this._commit({ type: 'kv.set', payload: { key, value } }); }
  async delete(key) { await this._commit({ type: 'kv.delete', payload: { key } }); }

  /** All the writes made inside `fn` become ONE event. */
  async transact(fn) {
    const ops = [];
    fn({
      set: (key, value) => ops.push({ type: 'kv.set', payload: { key, value } }),
      delete: (key) => ops.push({ type: 'kv.delete', payload: { key } }),
    });
    await this._commit({ type: 'kv.transaction', payload: { ops } });
  }

  async _commit(partial) {
    const event = await createEvent(this.identity, { domain: this.domain, parents: await this.log.head(), ...partial });
    await this.log.append(event);
    await this._apply(event);
  }

  /** Applies an event already in the log: our own write, or one that arrived by replication. */
  async _apply(event) {
    if (event.type === 'kv.transaction') for (const op of event.payload.ops) this._state = this.materializer.apply(this._state, op);
    else this._state = this.materializer.apply(this._state, event);
    for (const fn of this._listeners) fn({ event, state: this._state });
  }

  /** Rebuilds from the whole log, parents first. */
  async rebuild() {
    this._state = this.materializer.initialState();
    const pending = await Promise.all((await this.log.backend.allIds()).map((id) => this.log.get(id)));
    const applied = new Set();
    for (let progressed = true; pending.length > 0 && progressed;) {
      progressed = false;
      for (let i = pending.length - 1; i >= 0; i--) {
        if (!pending[i].parents.every((p) => applied.has(p))) continue;
        await this._apply(pending[i]);
        applied.add(pending[i].id);
        pending.splice(i, 1);
        progressed = true;
      }
    }
  }

  subscribe(handler) {
    this._listeners.add(handler);
    return () => this._listeners.delete(handler);
  }
}
