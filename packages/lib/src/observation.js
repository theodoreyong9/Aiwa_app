// What the wallet knows about OTHER domains, and what it says about it.
//
// aiwa-core has the pure pieces — Mirror (a domain's own signed commitments about what it received from
// others) and `assessPosition` (proofs + the weighted median). Nothing produced their inputs: no component
// signed a reception commitment when peers synced, and the wallet never rebuilt Mirror state. This file is that
// missing half:
//
// readWorld(log) the log, read as core's reducers want it: the events and the Mirror state
// observations(world, me) what `me` could honestly commit to having received, per foreign domain
//
// AIWA.observe() signs those as 'reception' events; AIWA.position() hands the world to assessPosition.
//
// Only events that can be trusted are cited. A foreign 'progression' event sits in the log once its envelope
// verifies — that proves who wrote it, not that it is a valid step — so a commitment must cite the highest
// epoch that the domain's own chain ACCEPTS (replayProgression), or, when the log does not hold that domain's
// history from epoch 1 and the chain cannot be replayed, the highest one whose signature is genuine. Citing a
// forged one would make this wallet claim to have seen an epoch that does not exist, and every honest
// commitment after it would then "go backwards" and be rejected by Mirror's monotonicity rule.

import {
  toReducerEvents, deriveSourceEpochLookup, materializeMirror, canonicalReceptionMessage,
  replayProgression, signatureAuthentic,
} from 'aiwa-core';
import { collectAncestors } from './ancestors.js';

/**
 * The log, read as aiwa-core's reducers want it.
 * (The weight of a witness is not read here: it is the committed capital `b` each domain signed into its own
 * accrual position, which the wallet's own materialization already holds — see AIWA.position().)
 * @returns {Promise<{ wire: object[], events: object[], mirror: object }>}
 */
export async function readWorld(log) {
  const wire = await collectAncestors(log, await log.head(), { tolerant: true });
  const events = toReducerEvents(wire);
  const mirror = await materializeMirror(events, deriveSourceEpochLookup(events));
  return { wire, events, mirror };
}

/**
 * For each foreign domain, the highest trusted progression event this log holds (whatever `me` committed to).
 * `options.epochIterations`: the deployment's fixed work of an epoch, if it has one — without it the work-bound events
 * of such a deployment cannot be replayed, and only the signature is trusted.
 * @returns {Promise<Array<{ sourceDomain: string, eventId: string, epoch: number }>>}
 */
export async function heldProgressions(world, me, options = {}) {
  const foreign = new Set();
  for (const event of world.events) {
    const p = event.payload;
    if (p?.type === 'progression' && typeof p.domain === 'string' && p.domain !== me) foreign.add(p.domain);
  }
  const found = [];
  for (const domain of foreign) {
    const replay = await replayProgression(world.events, domain, undefined, options);
    let best = null;
    for (const event of world.events) {
      const p = event.payload;
      if (p?.type !== 'progression' || p.domain !== domain || !Number.isInteger(p.epoch)) continue;
      const trusted = replay.genesis ? replay.accepted.has(event.id) : await signatureAuthentic(event);
      if (trusted && (best === null || p.epoch > best.epoch)) best = { sourceDomain: domain, eventId: event.id, epoch: p.epoch };
    }
    if (best !== null) found.push(best);
  }
  return found;
}

/**
 * For each foreign domain, the highest trusted progression event this log holds, when it is higher than what
 * `me` already committed to having seen.
 * @returns {Promise<Array<{ sourceDomain: string, eventId: string, epoch: number }>>}
 */
export async function observations(world, me, options = {}) {
  const already = world.mirror.maxSeenEpoch[me] ?? {};
  return (await heldProgressions(world, me, options)).filter((best) => best.epoch > (already[best.sourceDomain] ?? 0));
}

/** This domain's next reception-commitment sequence number (its own counter, never the observed domain's epoch). */
export function nextReceptionEpoch(mirror, me) {
  return (mirror.commitments[me] ?? []).reduce((max, c) => Math.max(max, c.epoch), 0) + 1;
}

/** The other domains this log holds progression events of. */
export function foreignDomains(world, me) {
  const foreign = new Set();
  for (const event of world.events) {
    const p = event.payload;
    if (p?.type === 'progression' && typeof p.domain === 'string' && p.domain !== me) foreign.add(p.domain);
  }
  return [...foreign];
}

/**
 * How fast `target` progresses compared with `me`, from what `me` itself witnessed (yellow paper §19.4): two of its own
 * reception commitments about the target, and its own progression epoch when it signed each. The ratio is how many epochs
 * the target gained for each epoch `me` gained between the two, with no clock anywhere. Purely informational: it gates nothing.
 * Only commitments Mirror accepted count. `null` when there is nothing to compare: fewer than two observations, or `me` did
 * not progress between them.
 * @returns {{ ratio: number, mine: [number, number], theirs: [number, number] } | null}
 */
export function paceOf(world, me, target) {
  if (!me) return null;
  const accepted = new Set((world.mirror.commitments[me] ?? []).map((c) => canonicalReceptionMessage(c)));
  const lookup = deriveSourceEpochLookup(world.events);
  const seen = [];
  let myEpoch = 0;
  for (const event of world.events) {
    const p = event.payload;
    if (p?.type === 'progression' && p.domain === me && Number.isInteger(p.epoch)) myEpoch = Math.max(myEpoch, p.epoch);
    if (p?.type !== 'reception' || p.domain !== me || !accepted.has(canonicalReceptionMessage(p))) continue;
    for (const ref of p.receivedFrom) {
      if (ref.sourceDomain !== target) continue;
      const theirs = lookup(target, ref.eventId);
      if (Number.isInteger(theirs)) seen.push({ mine: myEpoch, theirs });
    }
  }
  if (seen.length < 2) return null;
  const first = seen[0];
  const last = seen[seen.length - 1];
  if (!(last.mine > first.mine) || last.theirs < first.theirs) return null;
  return { ratio: (last.theirs - first.theirs) / (last.mine - first.mine), mine: [first.mine, last.mine], theirs: [first.theirs, last.theirs] };
}
