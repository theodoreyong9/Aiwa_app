// What a wallet hands an app that wants to verify it (a registry, a leaderboard): its own mining events, and what it
// holds of other domains' mining. aiwa-core's assessSubmission is the other side.

import { readWorld, heldProgressions } from './observation.js';
import { knownAncestors, isMiningEvent } from './ledger.js';

/**
 * This domain's own burn-record, progression, accrual and claim events: what a validator needs to derive its mining
 * state without trusting it. Both what is still in the log and what pruning set aside, each once, ordered by creation
 * time (a validator orders them itself anyway).
 * @param {object} [options]
 * @param {string} [options.after] the id of the last mining event the validator holds (its baseline's `chainHead`):
 * only what follows is returned — the chain of progression, accrual and claim events from there, and the burn records made since
 * @param {number} [options.afterEpoch] leave out the progression events up to this epoch (when `after` is not known)
 */
export async function exportMiningEvents(wallet, { afterEpoch = 0, after = null } = {}) {
  wallet.requireConnected();
  const { ledger } = wallet;
  const me = wallet.identity.id;
  const byId = new Map();
  for (const event of await knownAncestors(ledger.log, await ledger.log.head())) {
    if (isMiningEvent(event, me)) byId.set(event.id, event);
  }
  if (ledger.miningArchive) {
    for (const id of await ledger.miningArchive.allIds()) {
      const event = await ledger.miningArchive.getEvent(id);
      if (event) byId.set(event.id, event);
    }
  }
  let events = [...byId.values()];
  if (after) {
    // walk the chain back from its head to `after`: what the validator does not hold yet
    const tail = new Set();
    let id = wallet.miner.chained ? await wallet.miner.previous() : null;
    while (id && id !== after && byId.has(id) && !tail.has(id)) {
      tail.add(id);
      id = byId.get(id).payload.previous ?? null;
    }
    // Burn records are not in the chain: the ones made before the validator's own last event were in what it already
    // folded, so only the later ones go again (a burn made after its baseline must, to cover what follows).
    const known = byId.get(after);
    events = events.filter((e) => tail.has(e.id) || (e.type === 'burn-record' && (!known || e.createdAt > known.createdAt)));
  } else {
    events = events.filter((e) => e.type !== 'progression' || e.payload.epoch > afterEpoch);
  }
  return events.sort((a, b) => a.createdAt - b.createdAt);
}

/**
 * What this wallet holds of OTHER domains' mining: for each foreign domain whose progression this log holds, the
 * highest trusted progression event, signed by that domain, which is what makes it a proof. A registry that keeps it
 * asks that domain, the next time it submits, to show a history that contains it: a wallet cannot keep two histories
 * and show only the favourable one once someone else holds the other. Nothing here is signed by this wallet.
 * @param {{ max?: number }} [options] at most this many domains (the ones furthest along first)
 */
export async function witnesses(wallet, { max = 20 } = {}) {
  wallet.requireConnected();
  const world = await readWorld(wallet.ledger.log);
  const held = await heldProgressions(world, wallet.identity.id, { epochIterations: wallet.rewardParams.epochIterations });
  const byId = new Map(world.wire.map((e) => [e.id, e]));
  return held
    .sort((a, b) => b.epoch - a.epoch)
    .slice(0, max)
    .map((h) => byId.get(h.eventId))
    .filter(Boolean);
}

/**
 * The evidence an app takes: `{ version, domain, afterEpoch, events, witnesses }`, ready to be sent as is.
 * @param {number} [options.afterEpoch] the epoch of the app's baseline for this domain (0 if it has none)
 * @param {string} [options.after] the chain head of that baseline (`baseline.head`): only what follows is returned
 * @param {number} [options.maxWitnesses]
 */
export async function submissionEvidence(wallet, { afterEpoch = 0, after = null, maxWitnesses = 20 } = {}) {
  wallet.requireConnected();
  return {
    version: 1,
    domain: wallet.identity.id,
    afterEpoch,
    events: await exportMiningEvents(wallet, { afterEpoch, after }),
    witnesses: await witnesses(wallet, { max: maxWitnesses }),
  };
}
