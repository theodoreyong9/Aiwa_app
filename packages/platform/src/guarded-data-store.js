// Wires this package's own CapabilitySet (capability.js) into the one
// choke point every DataStore write already passes through —
// DataStore's own `_commit`, which `set`/`delete`/`transact` all
// call. capability.js is a tested, signed-grant primitive on
// its own; nothing enforces it anywhere on its own — that enforcement
// is this file's job.

import { DataStore } from 'aiwa-core';
import { assertCapability } from './capability-guard.js';

const defaultResourceOf = (partial, store) => store.domain;

export class GuardedDataStore extends DataStore {
  /**
   * @param {object} opts
   * @param {import('./capability.js').CapabilitySet} opts.capabilities an already-populated set — grants must already have been verified with verifyCapability before being added to it; this class only ever checks membership, never verifies a raw capability itself.
   * @param {(partial: object, store: GuardedDataStore) => string} [opts.resourceOf] what resource string a given commit is writing to — defaults to the store's own domain.
   * @param {string} [opts.action] the action every write here requires — defaults to 'write'.
   */
  constructor({ capabilities, resourceOf = defaultResourceOf, action = 'write', ...rest }) {
    super(rest);
    if (!capabilities) throw new Error('GuardedDataStore requires a real CapabilitySet — use DataStore directly for an ungated store.');
    this.capabilities = capabilities;
    this.resourceOf = resourceOf;
    this.action = action;
  }

  async _commit(partial) {
    assertCapability(this.capabilities, this.resourceOf(partial, this), this.action);
    return super._commit(partial);
  }
}
