// A self-signed checkpoint: a domain's own materialized wallet state, as of a set of log heads, embedded in a signed
// event: "this is my state as of here".
//
// The event's own envelope signature covers everything, so no embedded signature is needed (unlike accrual.js, whose
// reducers see the payload with `author` already stripped). A checkpoint is read off the wire event, where the verified
// `event.author` is available. Every consumer must check event.author === event.payload.domain; otherwise anyone could
// inject a checkpoint claiming a fabricated state for a domain that never signed it.
//
// The limit, plainly: a checkpoint lets a domain vouch only for ITS OWN past. A peer who verified everything up to it
// loses nothing by trusting it. A new peer who receives ONLY a checkpoint (the history pruned) cannot re-derive that
// state from genesis: it trades full verifiability for the domain's signed word about its own past. That tradeoff is
// inherent to checkpoints (Ethereum's weak subjectivity makes the same one). A peer needing full verification fetches
// the history from a peer that still holds it, or does not prune.

import { createEvent } from './event.js';

const BIGINT_TAG = '__bigint__:';

function replacer(_key, value) {
  return typeof value === 'bigint' ? `${BIGINT_TAG}${value.toString()}` : value;
}
function reviver(_key, value) {
  return typeof value === 'string' && value.startsWith(BIGINT_TAG) ? BigInt(value.slice(BIGINT_TAG.length)) : value;
}

/** BigInt values (claim amounts, balances) have no JSON form: they are tagged, and revived to bigint on load, never coerced to a lossy float. */
export function serializeWalletState(state) {
  return JSON.stringify(state, replacer);
}
export function deserializeWalletState(serialized) {
  return JSON.parse(serialized, reviver);
}

/** A checkpoint event for `identity`'s own domain, summarizing `walletState` as of `coveredHeads` (the log's heads when the state was computed). */
export async function buildCheckpointEvent(identity, { logDomain, parents, coveredHeads, walletState }) {
  return createEvent(identity, {
    domain: logDomain,
    parents,
    type: 'checkpoint',
    payload: { domain: identity.id, coveredHeads, walletState: serializeWalletState(walletState) },
  });
}

/** Only a checkpoint whose verified signer IS the domain it summarizes can serve as a base for folding or pruning. */
export function verifyCheckpoint(event) {
  return !!event && event.type === 'checkpoint' && !!event.payload && event.author === event.payload.domain;
}

/**
 * The wallet state a valid checkpoint embeds, or null if `event` is not a self-authored checkpoint.
 *
 * The embedded progression's lastId names the progression event accepted BEFORE the checkpoint, which pruning is free
 * to delete. Once appended, the checkpoint is the domain's new causal frontier (every later progression event names it
 * as a parent), so lastId is repointed to event.id. Everything else is verified history and stays untouched.
 */
export function checkpointWalletState(event) {
  if (!verifyCheckpoint(event)) return null;
  return repointLastId(deserializeWalletState(event.payload.walletState), event);
}

function repointLastId(state, event) {
  const domain = event.payload.domain;
  const position = state.accrual?.progression?.domains?.[domain];
  if (!position) return state;
  return {
    ...state,
    accrual: {
      ...state.accrual,
      progression: {
        ...state.accrual.progression,
        domains: { ...state.accrual.progression.domains, [domain]: { ...position, lastId: event.id } },
      },
    },
  };
}

/**
 * Folds a checkpoint into wallet state already in progress (checkpointWalletState builds a fresh base from one). A
 * checkpoint appended mid-session, then pruned against, would otherwise be inert to the reducers: the cached lastId would
 * keep naming a deleted event, and the next progression event would cite it as a parent and fail to append. Every fold,
 * cold-load or incremental, goes through this one repointing.
 */
export function applyCheckpointEvent(state, event) {
  if (!verifyCheckpoint(event)) return state;
  return repointLastId(state, event);
}

/** The most recent self-authored checkpoint for `domain` in `log`, or null. A linear scan: checkpoints are rare, never a per-transaction cost. */
export async function findLatestCheckpoint(log, domain) {
  const ids = await log.backend.allIds();
  let latest = null;
  for (const id of ids) {
    const event = await log.get(id);
    if (event && event.type === 'checkpoint' && event.author === domain && verifyCheckpoint(event)) {
      if (!latest || event.createdAt > latest.createdAt) latest = event;
    }
  }
  return latest;
}
