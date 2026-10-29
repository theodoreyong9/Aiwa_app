// The history of a wallet: keeping it, and getting it back.
//
// Everything a wallet is — its mining (epochs, position, chain head), its claimed AIWA, what it received — is folded
// from its log. The key comes back from the recovery phrase; the log does not, unless someone holds it. A CHECKPOINT
// is the wallet's state signed by its own key, small whatever the history, and a wallet that has one is back where it
// was. The ways to hold it:
//   exportBackup / importBackup   a file (or a QR, a note) the owner keeps
//   adoptState                    a source that holds the STATE but not the events (a registry's baseline)
//   archiveNow / restoreFromArchive / startAutoArchive   archive nodes, always on, that hold the backup for you
// The tradeoff is that of every checkpoint: whoever only sees the backup trusts its signature instead of re-deriving
// the history from genesis.

import { findLatestCheckpoint, buildCheckpointEvent, deserializeWalletState } from 'aiwa-core';
import { pushToNodes, fetchFromNodes } from 'aiwa-platform';
import { sameHeadSet } from './ledger.js';
import { Ticker } from './ticker.js';

const nodeList = (nodes) => (typeof nodes === 'function' ? nodes() : nodes) ?? [];

export class Backup {
  constructor(wallet) {
    this.wallet = wallet;
    this._checkpointTicker = new Ticker();
    this._archiveTicker = new Ticker();
  }

  /**
   * A backup of this wallet: its state as of now, signed by its key (a checkpoint, plus anything after it). Small
   * however long the history, and safe to keep anywhere: it holds no secret, only what is public anyway (balances,
   * mining state); spending still needs the key. Restore it with importBackup() after connecting with the same phrase.
   * @returns {Promise<{ version: number, kind: string, domain: string, address: string, createdAt: number, epoch: number, events: object[] }>}
   */
  async export() {
    const { wallet } = this;
    wallet.requireConnected();
    const { ledger } = wallet;
    const domain = wallet.identity.id;
    let checkpoint = await findLatestCheckpoint(ledger.log, domain);
    const heads = await ledger.log.head();
    // a checkpoint that is already the whole of the log is the backup as it stands
    if (!checkpoint || !(heads.length === 1 && heads[0] === checkpoint.id)) {
      const made = await ledger.checkpoint(wallet.identity);
      checkpoint = await ledger.log.get(made.eventId);
    }
    const mining = await wallet.miner.state();
    return { version: 1, kind: 'aiwa-backup', domain, address: wallet.address, createdAt: Date.now(), epoch: mining ? mining.epoch : 0, events: [checkpoint] };
  }

  /**
   * Puts a backup back: after connecting with the same recovery phrase the wallet is where the backup left it.
   * Refused if the backup is of another identity; never rolls a wallet back.
   * @returns {Promise<{ epoch: number, restored: boolean }>}
   */
  async import(backup) {
    const { wallet } = this;
    wallet.requireConnected();
    if (!backup || backup.kind !== 'aiwa-backup' || !Array.isArray(backup.events)) throw new Error('AIWA: this is not an Aiwa backup.');
    if (backup.domain !== wallet.identity.id) throw new Error('AIWA: this backup is of another identity — connect with its recovery phrase first.');
    const before = (await wallet.miner.state())?.epoch ?? 0;
    if (backup.events.some((e) => e.author !== wallet.identity.id)) throw new Error('AIWA: a backup holds only this identity\'s own events.');
    if (backup.epoch <= before && before > 0) return { epoch: before, restored: false };
    await wallet.ledger.log.appendMany(backup.events);
    wallet.ledger.reset();
    return { epoch: (await wallet.miner.state())?.epoch ?? 0, restored: true };
  }

  /**
   * For a source that holds this wallet's STATE but not its events: a registry that kept what it derived from the
   * wallet's submissions (the assessSubmission baseline). Writes that state as a checkpoint signed by this key. Trusts
   * the source completely, so take it only from one you trust; refused unless strictly further along than the wallet
   * already is. What such a state lacks is what the source never saw (value received from others): that comes from a
   * backup or from peers.
   * @param {string|object} serializedState a wallet state as aiwa-core's serializeWalletState wrote it
   * @returns {Promise<{ epoch: number, adopted: boolean }>}
   */
  async adopt(serializedState) {
    const { wallet } = this;
    wallet.requireConnected();
    const me = wallet.identity.id;
    const state = deserializeWalletState(serializedState);
    const epoch = state?.accrual?.progression?.domains?.[me]?.epoch ?? 0;
    if (!state?.accrual || (epoch === 0 && !state.accrual.positions?.[me])) throw new Error('AIWA: this state holds nothing of this identity.');
    const before = (await wallet.miner.state())?.epoch ?? 0;
    if (epoch <= before) return { epoch: before, adopted: false };
    const heads = await wallet.ledger.log.head();
    const event = await buildCheckpointEvent(wallet.identity, { logDomain: wallet.logDomain, parents: heads, coveredHeads: heads, walletState: state });
    await wallet.ledger.log.append(event);
    wallet.ledger.reset();
    return { epoch: (await wallet.miner.state())?.epoch ?? epoch, adopted: true };
  }

  /**
   * Pushes the current backup to the archive nodes (addresses, or a function returning them): to all of them, and one
   * that is down does not stop the others.
   * @returns {Promise<{ ok: Array, failed: Array, skipped?: boolean }>}
   */
  async archiveNow(nodes) {
    const { wallet } = this;
    wallet.requireConnected();
    const list = nodeList(nodes);
    if (list.length === 0) return { ok: [], failed: [], skipped: true };
    const backup = await this.export();
    const result = await pushToNodes(list, backup);
    this._lastArchivedHeads = await wallet.ledger.log.head();
    return { ...result, epoch: backup.epoch };
  }

  /**
   * After connecting with the recovery phrase on a new device: asks the archive nodes for this identity's backup,
   * takes the most recent, and imports it (never rolls a wallet back, refuses another identity).
   * @returns {Promise<{ found: boolean, node?: string, epoch?: number, restored?: boolean }>}
   */
  async restoreFromArchive(nodes) {
    const { wallet } = this;
    wallet.requireConnected();
    const list = nodeList(nodes);
    if (list.length === 0) throw new Error('AIWA: no archive node to ask — add the address of one.');
    const found = await fetchFromNodes(list, wallet.identity.id);
    if (!found) return { found: false };
    return { found: true, node: found.node, ...(await this.import(found.backup)) };
  }

  /**
   * Keeps the archive up to date: every `intervalMs`, if the wallet changed since the last time, its backup goes to the
   * nodes. `nodes` may be a function, so that a node added later is used. Nothing happens while the list is empty.
   */
  startAutoArchive({ nodes, intervalMs = 5 * 60_000, onError, onArchived } = {}) {
    this._archiveTicker.start(intervalMs, async () => {
      const { wallet } = this;
      const list = nodeList(nodes);
      if (!wallet.identity || list.length === 0) return;
      const heads = await wallet.ledger.log.head();
      if (this._lastArchivedHeads && sameHeadSet(this._lastArchivedHeads, heads)) return;
      onArchived?.(await this.archiveNow(list));
    }, onError);
  }

  stopAutoArchive() {
    this._archiveTicker.stop();
  }

  /**
   * checkpoint() + pruneToLastCheckpoint() on a timer: how a long-lived wallet keeps its next cold load (a reload, a
   * restart) fast and bounded instead of replaying from genesis. Skips the round when nothing changed since the last.
   */
  startAutoCheckpoint({ intervalMs = 5 * 60_000, onError } = {}) {
    this._checkpointTicker.start(intervalMs, async () => {
      const { wallet } = this;
      const heads = await wallet.ledger.log.head();
      if (this._lastCheckpointHeads && sameHeadSet(this._lastCheckpointHeads, heads)) return;
      await wallet.checkpoint();
      await wallet.pruneToLastCheckpoint();
      this._lastCheckpointHeads = heads;
    }, onError);
  }

  stopAutoCheckpoint() {
    this._checkpointTicker.stop();
  }
}
