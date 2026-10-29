// A nested/graph-shaped DataStore — same source-of-truth
// split as aiwa-core's own DataStore (a rebuildable projection over
// the EventLog, never itself the source of truth), just with
// graphMaterializer.js's own node/field/reference shape instead of
// flat key-value. `get`/`has`/`node` intentionally shadow the parent
// DataStore's own key-value-shaped versions — they take a different,
// shape of argument here, and `transact()` (the parent's own
// kv.transaction-based batching) is refused outright rather than
// silently producing kv-shaped sub-events this store's own materializer
// would never recognize.

import { DataStore } from 'aiwa-core';
import { graphMaterializer, isRef } from './graph-materializer.js';
import { assertCapability } from './capability-guard.js';

const defaultResourceOf = (partial, store) => `${store.domain}:${partial.payload.node}.${partial.payload.field}`;

export class GraphStore extends DataStore {
  /**
   * @param {object} opts
   * @param {import('./capability.js').CapabilitySet} [opts.capabilities] optional — omit for an ungated store (matches plain DataStore's own default), pass to require a granted capability on every write.
   * @param {(partial: object, store: GraphStore) => string} [opts.resourceOf] defaults to `${domain}:${node}.${field}`.
   * @param {string} [opts.action] defaults to 'write'.
   */
  constructor({ capabilities = null, resourceOf = defaultResourceOf, action = 'write', ...rest }) {
    super({ ...rest, materializer: graphMaterializer });
    this.capabilities = capabilities;
    this.resourceOf = resourceOf;
    this.action = action;
  }

  async _commit(partial) {
    if (this.capabilities) assertCapability(this.capabilities, this.resourceOf(partial, this), this.action);
    return super._commit(partial);
  }

  async put(node, field, value) {
    await this._commit({ type: 'graph.put', payload: { node, field, value } });
  }
  async unset(node, field) {
    await this._commit({ type: 'graph.unset', payload: { node, field } });
  }

  /** single-hop-resolving read: a $ref value returns the referenced node's own full field map — callers needing a multi-hop chase call get() again with the resolved id. Never a value for a field that was never set. */
  async get(node, field) {
    const value = this._state.nodes[node]?.[field];
    return isRef(value) ? this._state.nodes[value.$ref] : value;
  }

  async has(node, field) {
    return Boolean(this._state.nodes[node] && field in this._state.nodes[node]);
  }

  /** Every field on a node, references left unresolved (as {$ref}) — the caller decides whether, and how far, to follow them. An empty object for a node with no fields yet, never undefined. */
  node(nodeId) {
    return this._state.nodes[nodeId] ?? {};
  }

  async nodeIds() {
    return Object.keys(this._state.nodes);
  }

  async transact() {
    throw new Error('GraphStore does not support transact() — it batches kv.set/kv.delete ops the graph materializer would silently ignore. Call put()/unset() directly.');
  }
}
