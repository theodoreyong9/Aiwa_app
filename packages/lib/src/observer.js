// What the wallet says about OTHER domains (the Mirror), and where they stand.
//
// When events from another domain arrive (a live sync, an offline bundle), the wallet signs a reception commitment for
// them: the recurring, signed "I received this of X" that gives the proofs of position() their witnesses. It runs by
// itself after a sync unless `autoObserve` was turned off.

import { buildReceptionCommitment, assessPosition, identityCostFromCommitments, identityCostFromBurns } from 'aiwa-core';
import { readWorld, observations, nextReceptionEpoch, foreignDomains, paceOf } from './observation.js';

export class Observer {
  constructor(wallet) {
    this.wallet = wallet;
    this._running = null;
    this._again = false;
  }

  /**
   * Signs and appends a reception commitment for every other domain whose progression this log holds beyond what this
   * wallet already committed to having seen. Only trusted events are cited (observation.js). Idempotent: nothing new,
   * nothing appended.
   * @returns {Promise<{ committed: Array<{ sourceDomain: string, eventId: string, epoch: number }> }>}
   */
  async observe() {
    const { wallet } = this;
    wallet.requireConnected();
    const me = wallet.identity.id;
    const world = await readWorld(wallet.ledger.log);
    let sequence = nextReceptionEpoch(world.mirror, me);
    const committed = [];
    for (const found of await observations(world, me, { epochIterations: wallet.rewardParams.epochIterations })) {
      const payload = await buildReceptionCommitment(wallet.keypair, me, sequence++, found.sourceDomain, [found.eventId]);
      const event = await wallet.ledger.append(wallet.identity, 'reception', payload);
      // The observed domain and everyone else only count this as a witness once they hold it.
      await wallet.publish([event.id]);
      committed.push(found);
    }
    return { committed };
  }

  /** One background observe() at a time; a request that arrives meanwhile is folded into one more run. */
  schedule() {
    const { wallet } = this;
    if (!wallet.autoObserve || !wallet.identity) return;
    if (this._running) { this._again = true; return; }
    this._running = (async () => {
      try {
        do {
          this._again = false;
          if (wallet.connection) await wallet.confirmBurns(wallet.connection);
          if (wallet.identity) await this.observe();
        } while (this._again);
      } catch (err) {
        if (wallet.onObserveError) wallet.onObserveError(err); else console.error('AIWA: observe() failed:', err);
      } finally {
        this._running = null;
      }
    })();
  }

  /** Resolves once any background observe() has finished. */
  async settled() {
    while (this._running) await this._running;
  }

  /**
   * Where `domain` stands, from everything this log holds (aiwa-core's assessPosition): a position that never goes
   * below what observers provably received, a rewind or a fork only when there is proof, the weighted median as the
   * estimate. `selfReportedEpoch`, if the domain reported one, is judged against it. A witness weighs what it
   * committed: the burns THIS wallet confirmed for it (a deployment that opted out of backed commitments uses the
   * capital the domain signed into its own position). Read-only: needs no unlocked key.
   */
  async position(domain, { selfReportedEpoch = null, tolerance, verifyChain } = {}) {
    const world = await readWorld(this.wallet.ledger.log);
    const { accrual } = await this.wallet.ledger.state();
    return this._assess(world, accrual, domain, { selfReportedEpoch, tolerance, verifyChain });
  }

  _assess(world, accrual, domain, { selfReportedEpoch = null, tolerance, verifyChain } = {}) {
    const { wallet } = this;
    return assessPosition({
      mirrorState: world.mirror,
      identityCostState: wallet.rewardParams.commitmentBacking === 'none' ? identityCostFromCommitments(accrual.positions) : identityCostFromBurns(accrual.burns),
      orderedEvents: world.events,
      targetDomain: domain, selfReportedEpoch, epochIterations: wallet.rewardParams.epochIterations,
      ...(tolerance === undefined ? {} : { tolerance }), ...(verifyChain === undefined ? {} : { verifyChain }),
    });
  }

  /**
   * The other domains this log holds PROOF against: two unrelated histories of one domain, both signed by it (a fork).
   * Proofs only, so it cannot accuse an honest domain whose payment merely travelled slowly or whose view is old: a
   * rewind is judged against what a domain reports NOW, which a log of past events does not have. Read-only.
   * @returns {Promise<Array<{ domain: string, reason: 'fork', forks: object[] }>>}
   */
  async accusations() {
    const { wallet } = this;
    const me = wallet.identity?.id ?? null;
    const world = await readWorld(wallet.ledger.log);
    const { accrual } = await wallet.ledger.state();
    const accused = [];
    for (const domain of foreignDomains(world, me)) {
      const where = await this._assess(world, accrual, domain);
      if (where.forks.length > 0) accused.push({ domain, reason: 'fork', forks: where.forks });
    }
    return accused;
  }

  /**
   * Where another domain stands, in what a person can read: its position (the proven lower bound or the weighted median, whichever is
   * higher), what is PROVEN of it, the median that is only a vote, whether it signed two histories, and how fast it progresses
   * compared with this wallet (`pace`, §19.4). Reported, never applied: nothing here changes what anyone earns. Read-only.
   * @returns {Promise<{ domain: string, epoch: number|null, provenAtLeast: number|null, median: number|null, witnesses: number,
   *   forked: boolean, verification: 'chain'|'signature', pace: { ratio: number, mine: number[], theirs: number[] }|null }>}
   */
  async standing(domain) {
    const world = await readWorld(this.wallet.ledger.log);
    const { accrual } = await this.wallet.ledger.state();
    return this._standing(world, accrual, domain);
  }

  /** `standing()` of every other domain this log holds progression of, the furthest first. */
  async standings() {
    const world = await readWorld(this.wallet.ledger.log);
    const { accrual } = await this.wallet.ledger.state();
    const all = [];
    for (const domain of foreignDomains(world, this.wallet.identity?.id ?? null)) all.push(await this._standing(world, accrual, domain));
    return all.sort((a, b) => (b.epoch ?? 0) - (a.epoch ?? 0));
  }

  async _standing(world, accrual, domain) {
    const where = await this._assess(world, accrual, domain);
    return {
      domain,
      epoch: where.position,
      provenAtLeast: where.proof ? where.proof.lowerBound : null,
      median: where.estimate ? where.estimate.tick : null,
      witnesses: where.estimate ? where.estimate.observationCount : 0,
      forked: where.forks.length > 0,
      verification: where.verification,
      pace: paceOf(world, this.wallet.identity?.id ?? null, domain),
    };
  }
}
