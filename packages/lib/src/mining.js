// A wallet's mining: commit capital, advance the progression (the proof of work that makes the claimable grow), claim.
//
// A deployment that fixes the work of an epoch (rewardParams.epochIterations) makes a domain's mining events one signed
// chain: each names the one it follows (`previous`), and the work of an epoch starts from it. So an action and a
// stretch of work must never be built from the same predecessor: one at a time reads the chain's head and appends,
// under a lock.

import {
  progressionParents, buildSignedProgressionEvent, buildSignedAccrualEvent, buildSignedClaimEvent, computeSuccinctEpochs,
  vdfSeed, computeVdfChain, commitmentPriceLamports, creatorFeeLamports, MAX_PATIENCE_RATE, miningChainHead, progressionSeed,
  miningState, rankingFigure,
} from 'aiwa-core';
import { signerOf } from './signer.js';
import { Ticker } from './ticker.js';

export function checkPatienceRate(T) {
  if (!Number.isFinite(T) || T < 0 || T > MAX_PATIENCE_RATE) {
    throw new Error(`AIWA: T (the patience rate, chosen at the burn) must be between 0 and ${MAX_PATIENCE_RATE}.`);
  }
}

export class Mining {
  constructor(wallet) {
    this.wallet = wallet;
    this._lock = Promise.resolve();
    this._ticker = new Ticker();
  }

  get chained() {
    const epochIterations = this.wallet.rewardParams.epochIterations;
    return Number.isInteger(epochIterations) && epochIterations > 0;
  }

  withLock(fn) {
    const next = this._lock.then(() => fn());
    this._lock = next.then(() => {}, () => {});
    return next;
  }

  /** What the next mining event must name as `previous`: the id of this domain's last one, null before the first, undefined when the deployment does not chain them. */
  async previous() {
    if (!this.chained) return undefined;
    const { accrual } = await this.wallet.ledger.state();
    return miningChainHead(accrual, this.wallet.identity.id);
  }

  /**
   * Commits capital `b` to the wallet's own position, so that it starts earning something to claim as the progression
   * advances. Typically right after a burn, which is what covers it.
   */
  recordCommitment({ b, T = 0 } = {}) {
    this.wallet.requireConnected();
    checkPatienceRate(T);
    return this.withLock(() => this._commit({ b, T }));
  }

  async _commit({ b, T }) {
    const { wallet } = this;
    const { rewardParams, ledger } = wallet;
    // Capital is what a confirmed burn covers: refuse here, with the reason, rather than append an event every reader
    // would reject. A commitment costs ceil(b / (1 - T)) lamports of burn that no earlier commitment used.
    if (rewardParams.commitmentBacking !== 'none') {
      const { accrual } = await ledger.state();
      const me = wallet.identity.id;
      const price = commitmentPriceLamports(b, T);
      const covered = accrual.burns?.covered?.[me] ?? 0;
      const consumed = accrual.burns?.consumed?.[me] ?? 0;
      if (consumed + price > covered) {
        throw new Error(`AIWA: a commitment of ${b} at T=${T} is not covered by the burns confirmed for this wallet: it costs ${price} lamports, ${covered - consumed} are left (${covered} confirmed, ${consumed} already used). Burn first — burn(lamports, connection) or recordBurn(signature, connection).`);
      }
      const feeDue = creatorFeeLamports(price, T, rewardParams.creatorFee);
      if (feeDue > 0) {
        const feeCovered = accrual.burns?.feeCovered?.[me] ?? 0;
        const feeConsumed = accrual.burns?.feeConsumed?.[me] ?? 0;
        if (feeConsumed + feeDue > feeCovered) {
          throw new Error(`AIWA: a commitment of ${b} at T=${T} owes the creator ${feeDue} lamports: ${feeCovered - feeConsumed} are left (${feeCovered} paid to the creator address in the burns confirmed for this wallet, ${feeConsumed} already used). Burn with burn(lamports, connection, { T }), which pays it.`);
        }
      }
    }
    const signed = await buildSignedAccrualEvent({ domain: wallet.identity.id, b, T, previous: await this.previous() }, ...signerOf(wallet.keypair));
    const event = await ledger.append(wallet.identity, 'accrual', signed);
    return { eventId: event.id };
  }

  /**
   * Advances the wallet's own progression: real sequential work, bounding the RATE of advancement rather than calendar
   * time. This is what makes claimable() grow. Call it periodically (startProgressLoop) while the wallet is open.
   */
  async advance({ vdfIterations = 100_000, epochs = 1 } = {}) {
    this.wallet.requireConnected();
    // A deployment that fixes the work of an epoch gets the succinct kind, chained to the domain's last mining event:
    // `epochs` epochs in one event and ONE proof that anyone checks in milliseconds.
    if (this.chained) return this._advanceChained({ epochs });
    // Otherwise the original: one epoch, a hash chain of `vdfIterations`.
    const { wallet } = this;
    const me = wallet.identity.id;
    const state = await wallet.ledger.state();
    const current = state.accrual.progression.domains[me] ?? { epoch: 0, vdfOutput: null, lastId: null };
    const epoch = current.epoch + 1;
    const vdfOutput = await computeVdfChain(vdfSeed(me, current.vdfOutput ?? 'genesis'), vdfIterations);
    // The progression's last event must be a DIRECT parent: if anything else was appended since (a commitment, a
    // checkpoint), the log's head is that event, and without this every later progression would be rejected for good.
    // Read after the work, which can take a while.
    const parents = progressionParents(await wallet.ledger.log.head(), current.lastId);
    const signed = await buildSignedProgressionEvent({ domain: me, epoch, vdfIterations, vdfOutput }, ...signerOf(wallet.keypair));
    const event = await wallet.ledger.append(wallet.identity, 'progression', signed, { parents });
    return { epoch, eventId: event.id };
  }

  // The work starts from the domain's last mining event, so it is only good if that is still the last one when it ends:
  // an action made meanwhile (a burn, a claim) moves the chain on, and this work is dropped and done again from the new
  // head (a few seconds at most). `eventId: null, discarded: true` if the chain would not hold still.
  async _advanceChained({ epochs }) {
    const { wallet } = this;
    const me = wallet.identity.id;
    const iterations = epochs * wallet.rewardParams.epochIterations;
    let epoch = 0;
    for (let attempt = 0; attempt < 3; attempt++) {
      const state = await wallet.ledger.state();
      const current = state.accrual.progression.domains[me] ?? { epoch: 0, vdfOutput: null, lastId: null };
      const previous = miningChainHead(state.accrual, me);
      epoch = current.epoch + epochs;
      const { vdfOutput, vdfProof } = await computeSuccinctEpochs(progressionSeed(me, current.vdfOutput, previous), iterations);
      const made = await this.withLock(async () => {
        if ((await this.previous()) !== previous) return null;
        const signed = await buildSignedProgressionEvent({ domain: me, epoch, vdfIterations: iterations, vdfOutput, previous }, ...signerOf(wallet.keypair));
        const event = await wallet.ledger.append(wallet.identity, 'progression', { ...signed, vdfProof });
        return { epoch, eventId: event.id };
      });
      if (made) return made;
    }
    return { epoch: epoch - epochs, eventId: null, discarded: true };
  }

  /**
   * advance() until stopLoop(): how a wallet keeps its claimable growing while open. Errors go to `onError`.
   *
   * With `eventMs`, in a deployment that fixes the work of an epoch, the wallet does not wait: it works back to back,
   * as fast as the device can, and signs one event for what it worked in about `eventMs`, so the log grows as slowly as
   * with a timer while a faster device works more epochs. Nothing in the protocol paces a wallet, and a wallet that
   * waits earns less than one that does not. It does not work before its first commitment: those epochs earn nothing
   * and only raise its age (q_tot), which slows what it accrues afterwards.
   *
   * Without `eventMs`: one advance() every `intervalMs`.
   */
  startLoop({ intervalMs = 30_000, vdfIterations = 100_000, epochs = 1, eventMs = 0, onError } = {}) {
    if (!(eventMs > 0) || !this.chained) {
      this._ticker.start(intervalMs, () => this.advance({ vdfIterations, epochs }), onError);
      return;
    }
    let perEvent = 1; // epochs per event, adapted so that one event is about eventMs of work on this device
    this._ticker.start(50, async () => {
      if (!(await this.state())) { await new Promise((resolve) => setTimeout(resolve, 1000)); return; }
      const started = Date.now();
      const made = await this.advance({ epochs: perEvent });
      if (made.discarded) return;
      perEvent = Math.max(1, Math.round(eventMs / (Math.max(1, Date.now() - started) / perEvent)));
    }, onError);
  }

  stopLoop() {
    this._ticker.stop();
  }

  /** Moves `amount` (decimal string) from claimable into a spendable claim the wallet owns. */
  claim(amount) {
    this.wallet.requireConnected();
    return this.withLock(async () => {
      const { wallet } = this;
      const claimId = crypto.randomUUID();
      const signed = await buildSignedClaimEvent({ domain: wallet.identity.id, amount, claimId, previous: await this.previous() }, ...signerOf(wallet.keypair));
      const event = await wallet.ledger.append(wallet.identity, 'claim', signed);
      return { claimId, eventId: event.id };
    });
  }

  /** The mining state: the capital that mines, T, the epoch of the last action, the age, the claimable now. Null before the first burn. */
  async state() {
    this.wallet.requireConnected();
    return miningState(this.wallet.rewardParams, await this.wallet.ledger.state(), this.wallet.identity.id);
  }

  /** The ranking figure — { score, laps, epoch } — what an app ranks by. Null before the first burn. */
  async ranking() {
    return rankingFigure(await this.state());
  }
}
