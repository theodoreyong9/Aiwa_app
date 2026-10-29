// A domain's progression advances only through a valid transition: monotonic, carrying a sequential proof of work
// (vdf.js, succinct-vdf.js) that bounds the RATE of advancement rather than calendar time, and signed by the key
// that owns the domain. The proof alone proves nothing about who submitted it (its seed is public), so without the
// signature anyone could advance a domain's age, and permanently lower its own future reward.
//
// Events use this package's internal shape {id, parents, payload}; adapt-event.js bridges from the wire event.

import { vdfSeed, verifyVdfChain } from './vdf.js';
import { verifySuccinctEpochs } from './succinct-vdf.js';
import { ACTIONS, signAction, verifyAction } from './signing.js';

/**
 * Where the work of a work-bound progression event starts: the domain, its previous output, AND the mining event
 * this one follows (`previous`: the id of the domain's last progression, accrual or claim; null before the first).
 *
 * Why the last one is in it. The work used to start from the previous output alone, so one stretch of proven work
 * could be re-signed over any history: an action (a burn, a claim) could be left out, or two histories kept side by
 * side, at no cost. Starting the work from the event it follows ties it to that exact history: showing a history
 * without an action means redoing, from that action on, all the work the other one holds.
 */
export function progressionSeed(domain, previousOutput, previous) {
  return `${vdfSeed(domain, previousOutput ?? 'genesis')}:${previous ?? 'none'}`;
}

/** A domain-signed progression transition: the only kind applyProgressionEvent accepts. */
export const buildSignedProgressionEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.progression, fields, signerSeed, signerPubkeyBytes, options);

/** True only if the payload carries a valid signature by the key whose id IS its `domain`. */
export const verifyProgressionAuthorization = (payload) => verifyAction(ACTIONS.progression, payload);

export function initialProgressionState() {
  return { domains: {}, rejections: [] };
}

/**
 * The parents a NEW progression event must declare. The domain's last accepted progression event has to be a DIRECT
 * parent, but a log's heads only include it when nothing else was appended since (an accrual, a claim, a checkpoint
 * make another event the sole head, and the chain would then be lost for good). The event honestly depends on both
 * the log's tip and its own type's last transition, so it names both.
 */
export function progressionParents(heads, lastId) {
  return lastId && !heads.includes(lastId) ? [...heads, lastId] : heads;
}

// `verifyFn` defaults to the main-thread verifyVdfChain; a caller catching up on a large backlog can inject a
// worker-backed one. `chainHead` (work-bound deployments): the id of the domain's last mining event as the caller
// folded it (accrual.js passes it); a caller folding progression events alone leaves it out, and `previous` is taken
// as the event states it.
export async function applyProgressionEvent(state, event, verifyFn = verifyVdfChain, { epochIterations, chainHead } = {}) {
  verifyFn ??= verifyVdfChain;
  const payload = event.payload;
  if (!payload || payload.type !== 'progression') return state;

  const { domain, epoch, vdfIterations, vdfOutput } = payload;
  const reject = (reason) => ({
    ...state,
    rejections: [...state.rejections, { eventId: event.id, domain, reason }],
  });

  // A deployment that fixes the work of one epoch (rewardParams.epochIterations) gets succinct events: k epochs at
  // once, k x epochIterations squarings, one proof checked in milliseconds. Without it, the original rule: +1 per
  // event, a hash chain of whatever length the signer wrote, verified by recomputing it.
  const workBound = Number.isInteger(epochIterations) && epochIterations > 0;

  if (typeof domain !== 'string' || domain.length === 0) return reject('missing domain');
  if (!Number.isInteger(epoch) || epoch < 1) return reject('epoch must be a positive integer');

  const current = state.domains[domain] ?? { epoch: 0, lastId: null, vdfOutput: null };

  if (workBound) {
    if (epoch <= current.epoch) return reject(`epoch must go past ${current.epoch}, got ${epoch}`);
    const step = epoch - current.epoch;
    if (vdfIterations !== step * epochIterations) {
      return reject(`${step} epoch(s) are ${step * epochIterations} iterations (an epoch is ${epochIterations}); got ${vdfIterations}`);
    }
    // The chain is the signed `previous`, not the event's `parents`: parents are whatever the log's heads were (a
    // checkpoint, a reception commitment) and can name events that pruning later removes; `previous` always names
    // the last mining event, wherever it is kept.
    if (payload.previous === undefined || (payload.previous !== null && typeof payload.previous !== 'string')) {
      return reject('a progression event names the mining event it follows (previous: an id, or null before the first)');
    }
    if (chainHead !== undefined && payload.previous !== chainHead) {
      return reject(`follows ${payload.previous}, but this domain's last mining event is ${chainHead}`);
    }
  } else {
    if (epoch !== current.epoch + 1) return reject(`expected epoch ${current.epoch + 1}, got ${epoch}`);
    if (current.lastId !== null && !event.parents.includes(current.lastId)) {
      return reject(`does not chain from this domain's last accepted transition ${current.lastId}`);
    }
  }
  if (!Number.isInteger(vdfIterations) || vdfIterations < 1) return reject('vdfIterations must be a positive integer');
  if (typeof payload.nonce !== 'string' || !payload.nonce || typeof payload.signerPubkey !== 'string' || typeof payload.signature !== 'string') {
    return reject('malformed progression payload — missing real signature fields');
  }
  if (!(await verifyProgressionAuthorization(payload))) {
    return reject('invalid signature: only the domain itself can advance its own progression');
  }

  const seed = workBound ? progressionSeed(domain, current.vdfOutput, payload.previous) : vdfSeed(domain, current.vdfOutput ?? 'genesis');
  if (workBound) {
    if (!(await verifySuccinctEpochs(seed, vdfIterations, vdfOutput, payload.vdfProof))) {
      return reject('the proof of the work of these epochs does not verify');
    }
  } else if (!(await verifyFn(seed, vdfIterations, vdfOutput))) {
    return reject('VDF proof does not verify against the recomputed chain');
  }

  return { ...state, domains: { ...state.domains, [domain]: { epoch, lastId: event.id, vdfOutput } } };
}

export async function materializeProgression(orderedEvents, verifyFn = verifyVdfChain, options) {
  verifyFn ??= verifyVdfChain;
  let state = initialProgressionState();
  for (const event of orderedEvents) state = await applyProgressionEvent(state, event, verifyFn, options);
  return state;
}
