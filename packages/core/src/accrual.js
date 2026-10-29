// A domain's position: committed capital b, and the epoch of its own last action. The epoch is always derived from
// the domain's own folded progression, never supplied by a caller (a caller-supplied reference epoch would let anyone
// claim t = currentEpoch forever).
//
// "Last action" mining: the position is what the domain's last action left it.
// 'accrual': { domain, b, T } is a burn's commitment. It REPLACES the position: b is the capital that now mines
//   (b = burned x (1 - T)), T the patience rate chosen at this burn for what follows. Before replacing it, what the
//   previous position accrued is PAID (an automatic claim), so a new burn never forfeits what the last one earned.
//   It resets the patience clock t.
// 'claim': { domain, amount } debits up to what is claimable into the domain's balance, and resets t. T stays the one
//   chosen at the last burn.
// t, the time since the last action, resets on every accrual or claim. The domain's age (the reward's denominator
// reference) never resets.
//
// Both are signed by the key that owns `domain` (signing.js): the outer event's `author` is stripped before a reducer
// sees it (adapt-event.js), so the signature is embedded in the payload. Without it anyone could reset another
// domain's patience clock.

import { verifyBurnRecordFor } from './burn-record.js';
import { applyProgressionEvent, initialProgressionState } from './progression.js';
import { rewardFixed, domainAge } from './reward.js';
import { toUnits, fixedToUnits } from './units.js';
import { ACTIONS, signAction, verifyAction, signDelegatedAction, verifyDelegatedAction } from './signing.js';

/** A domain-signed commitment of capital `b` (and optionally `T`) to the domain's own position. */
export const buildSignedAccrualEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.accrual, fields, signerSeed, signerPubkeyBytes, options);

/** A domain-signed claim, moving `amount` from the domain's accrued position into its spendable balance. */
export const buildSignedClaimEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.claim, fields, signerSeed, signerPubkeyBytes, options);

/** A claim signed by a delegate's key (see signing.js) for the delegation's owner, whose domain receives the value. */
export const buildSignedDelegatedClaimEvent = (delegation, fields, delegateSeed, delegatePubkeyBytes, options) =>
  signDelegatedAction(ACTIONS.claim, delegation, fields, delegateSeed, delegatePubkeyBytes, options);

// burns: what this READER has confirmed about burns. `records` is seeded by the caller (signature -> the
// record fetchBurnRecord returned: the reader's own check against Solana); `covered` (domain -> lamports) and
// `used` (signature -> true) are derived by folding 'burn-record' events. A reducer never reaches Solana: what
// it may count is exactly what the reader put in `records`.
// `consumed` (domain -> lamports): what the domain's commitments have used of what it burned. A burn backs a
// commitment once: it is spent by it, even though the next commitment replaces the position.
// `feeCovered` / `feeConsumed` (domain -> lamports): the same for the creator fee, when the deployment has one
// (rewardParams.creatorFee): what the confirmed burns paid to the creator address, and what commitments have used.
export function initialBurnsState() {
  return { records: {}, covered: {}, used: {}, consumed: {}, feeCovered: {}, feeConsumed: {} };
}

// `chain` (domain -> id): the domain's last accepted mining event — progression, accrual, claim. A work-bound
// deployment (rewardParams.epochIterations) makes these events a chain: each one names, in its signed payload, the one
// it follows (`previous`), and a progression event's work starts from it. See chainViolation.
export function initialAccrualState() {
  return { progression: initialProgressionState(), positions: {}, balances: {}, usedNonces: {}, rejections: [], burns: initialBurnsState(), chain: {} };
}

const isWorkBound = (rewardParams) => Number.isInteger(rewardParams?.epochIterations) && rewardParams.epochIterations > 0;

/**
 * Work-bound deployments: why this domain's mining event does not follow its chain, or null if it does. The events
 * of a domain are a line, and the line is signed: an event that names another predecessor than the last accepted one
 * is a second history (a fork) or a skipped step (an action left out), and is refused. Which of two events naming
 * the same predecessor is the one is not for the reader to guess: the first folded is kept, and whoever shows
 * the other history has to hold work that starts from it.
 */
function chainViolation(rewardParams, state, payload) {
  if (!isWorkBound(rewardParams)) return null;
  if (payload.previous === undefined || (payload.previous !== null && typeof payload.previous !== 'string')) {
    return 'must name the mining event it follows (previous: an id, or null before the first)';
  }
  const head = state.chain?.[payload.domain] ?? null;
  if (payload.previous !== head) return `follows ${payload.previous}, but this domain's last mining event is ${head}`;
  return null;
}

/** The id of `domain`'s last accepted mining event in `accrualState`, or null — what a new one must name as `previous`. */
export function miningChainHead(accrualState, domain) {
  return accrualState.chain?.[domain] ?? null;
}

const LAMPORTS_PER_UNIT = 1_000_000_000;
export const MAX_PATIENCE_RATE = 0.4;

/**
 * What a commitment of capital `b` at patience rate `T` costs, in lamports of confirmed burn: the capital that
 * counts is what is left of the burn after T of it is destroyed without counting — b = burned x (1 - T), so
 * burned = ceil(b / (1 - T)). T is therefore a choice: a larger T makes the reward curve more generous, and
 * costs that share of the burn. The share is destroyed, except for the creator fee when the deployment has one (below).
 */
export function commitmentPriceLamports(b, T = 0) {
  const lamports = Math.round(b * LAMPORTS_PER_UNIT);
  if (!T) return lamports;
  return Math.ceil(lamports / (1 - T) - 1e-6);
}

/**
 * The creator fee (yellow paper §11): instead of destroying all of the T share of a burn, a small fixed part of it goes
 * to ONE address that is a constant of the deployment (`rewardParams.creatorFee = { address, rateOfT }`) — never chosen
 * by an application or by the user. For a burn of `burnedLamports` at patience rate `T` the fee is
 * floor(burned x T x rateOfT) lamports, computed in integers (parts per million), so every reader gets the same number.
 * A deployment without `creatorFee`, or a burn at T = 0, owes nothing.
 */
export function creatorFeeLamports(burnedLamports, T, creatorFee) {
  if (!creatorFee || !T || !(creatorFee.rateOfT > 0)) return 0;
  const tPpm = BigInt(Math.round(T * 1e6));
  const ratePpm = BigInt(Math.round(creatorFee.rateOfT * 1e6));
  return Number((BigInt(burnedLamports) * tPpm * ratePpm) / 1_000_000_000_000n);
}

/**
 * What a burn of `lamports` at patience rate `T` does, in lamports — what a wallet shows before the user burns.
 * `toCreator` and `toIncinerator` add up to `lamports` (the wallet's debit, network fee aside); `capital` is what counts
 * as mining capital; `destroyedWithoutCounting` is the part of the T share that is neither capital nor paid to the creator.
 */
export function burnQuote({ lamports, T = 0, creatorFee }) {
  const toCreator = creatorFeeLamports(lamports, T, creatorFee);
  const capital = Math.floor(lamports * (1 - T));
  return { lamports, T, toCreator, toIncinerator: lamports - toCreator, capital, destroyedWithoutCounting: lamports - capital - toCreator };
}

// Straight from rewardFixed()'s own reproducible Q128 BigInt to real
// on-chain base units — no JS Number in between. This is the actual
// point of rewardFixed existing: a claim is a balance credit, and
// routing it through a float first (the old reward()+fromFloat path)
// would reintroduce the one non-reproducible step a future Rust node
// would disagree with a JS one on.
function currentlyClaimableUnits(rewardParams, state, domain) {
  const position = state.positions[domain];
  if (!position) return 0n;
  const currentEpoch = domainAge(state.progression, domain);
  const t = Math.max(0, currentEpoch - position.lastActionEpoch);
  const fixed = rewardFixed(position.b, t, currentEpoch, position.T ?? 0, rewardParams);
  return fixed === null ? 0n : fixedToUnits(fixed);
}

export async function applyAccrualEvent(rewardParams, state, event, verifyFn) {
  const payload = event.payload;
  if (!payload || typeof payload.type !== 'string') return state;

  if (payload.type === 'progression') {
    const workBound = isWorkBound(rewardParams);
    const progression = await applyProgressionEvent(state.progression, event, verifyFn, {
      epochIterations: rewardParams?.epochIterations,
      chainHead: workBound ? (state.chain?.[payload.domain] ?? null) : undefined,
    });
    // the chain moves on only if the event was accepted
    const accepted = progression.rejections.length === state.progression.rejections.length;
    const chain = accepted && typeof payload.domain === 'string' ? { ...(state.chain ?? {}), [payload.domain]: event.id } : state.chain;
    return { ...state, progression, chain };
  }

  if (payload.type === 'accrual') {
    const { domain, b, T, nonce, signerPubkey, signature } = payload;
    const reject = (reason) => ({ ...state, rejections: [...state.rejections, { eventId: event.id, domain: domain ?? null, reason }] });
    if (typeof domain !== 'string' || !domain) return reject('missing domain');
    if (!Number.isFinite(b) || b < 0) return reject('b must be a finite number >= 0');
    if (typeof nonce !== 'string' || !nonce || typeof signerPubkey !== 'string' || typeof signature !== 'string') {
      return reject('malformed accrual payload');
    }
    if (state.usedNonces[nonce]) return reject('nonce already used');
    if (!(await verifyAction(ACTIONS.accrual, payload))) return reject('invalid signature: only the domain itself can commit capital to its own position');

    const rate = T === undefined || T === null ? 0 : T;
    if (!Number.isFinite(rate) || rate < 0 || rate > MAX_PATIENCE_RATE) return reject(`T must be between 0 and ${MAX_PATIENCE_RATE}`);
    const brokenChain = chainViolation(rewardParams, state, payload);
    if (brokenChain) return reject(brokenChain);

    const currentEpoch = domainAge(state.progression, domain);
    const price = commitmentPriceLamports(b, rate);
    const consumed = state.burns?.consumed?.[domain] ?? 0;
    // The genesis commitment (yellow paper §9): capital is what a burn covers. What this domain's commitments have
    // used, plus this one's price, may not exceed what burns THIS READER has confirmed for it (see 'burn-record'
    // below). The deployment may opt out explicitly — `rewardParams.commitmentBacking: 'none'` — for tests, demos,
    // private economies; leaving it out means mandatory.
    if (rewardParams?.commitmentBacking !== 'none') {
      const covered = state.burns?.covered?.[domain] ?? 0;
      if (consumed + price > covered) {
        return reject(`commitment of ${b} at T=${rate} is not covered by a confirmed burn: it costs ${price} lamports, ${covered - consumed} are left (${covered} confirmed for this domain, ${consumed} already used)`);
      }
    }
    // The creator fee owed for this commitment, when the deployment has one: covered by what the confirmed burns paid
    // to the creator address, each lamport once. A burn at T = 0 owes nothing.
    const feeDue = rewardParams?.commitmentBacking !== 'none' ? creatorFeeLamports(price, rate, rewardParams?.creatorFee) : 0;
    const feeConsumed = state.burns?.feeConsumed?.[domain] ?? 0;
    if (feeDue > 0) {
      const feeCovered = state.burns?.feeCovered?.[domain] ?? 0;
      if (feeConsumed + feeDue > feeCovered) {
        return reject(`commitment of ${b} at T=${rate} owes the creator ${feeDue} lamports: ${feeCovered - feeConsumed} are left (${feeCovered} paid to the creator address in confirmed burns, ${feeConsumed} already used)`);
      }
    }
    // The claimable accrued so far is paid before the position is replaced.
    const pending = currentlyClaimableUnits(rewardParams, state, domain);
    const balance = state.balances[domain] ?? 0n;
    return {
      ...state,
      positions: { ...state.positions, [domain]: { b, lastActionEpoch: currentEpoch, T: rate } },
      balances: pending > 0n ? { ...state.balances, [domain]: balance + pending } : state.balances,
      burns: {
        ...(state.burns ?? initialBurnsState()),
        consumed: { ...(state.burns?.consumed ?? {}), [domain]: consumed + price },
        feeConsumed: { ...(state.burns?.feeConsumed ?? {}), [domain]: feeConsumed + feeDue },
      },
      usedNonces: { ...state.usedNonces, [nonce]: true },
      chain: { ...(state.chain ?? {}), [domain]: event.id },
    };
  }

  // A domain pointing at a burn it made: { type: 'burn-record', domain, signature } — the Solana transaction
  // signature, nothing else. What the burn was worth is NOT read from the event (anyone can write anything in
  // an event): it is read from the record this reader fetched from Solana itself (state.burns.records), and the
  // burn counts for `domain` only if that record is a finalized burn paid by the domain's own key. One
  // signature counts once.
  if (payload.type === 'burn-record') {
    const { domain, signature } = payload;
    const reject = (reason) => ({ ...state, rejections: [...state.rejections, { eventId: event.id, domain: domain ?? null, reason }] });
    if (typeof domain !== 'string' || !domain) return reject('missing domain');
    if (typeof signature !== 'string' || !signature) return reject('missing transaction signature');
    const burns = state.burns ?? initialBurnsState();
    if (burns.used[signature]) return reject(`burn ${signature} already counted`);
    const record = burns.records[signature];
    if (!record) return reject(`burn ${signature} is not confirmed by this reader (no finalized transaction record)`);
    const check = await verifyBurnRecordFor(domain, record);
    if (!check.valid) return reject(check.reason);
    // What reached the creator address in this transaction (0 unless the reader asked for it: see fetchBurnRecord) is
    // part of what the burn covers, and of what the creator fee is paid from.
    const toCreator = record.creatorBalanceDeltaLamports ?? 0;
    return {
      ...state,
      burns: {
        ...burns,
        covered: { ...burns.covered, [domain]: (burns.covered[domain] ?? 0) + record.incineratorBalanceDeltaLamports + toCreator },
        feeCovered: { ...(burns.feeCovered ?? {}), [domain]: (burns.feeCovered?.[domain] ?? 0) + toCreator },
        used: { ...burns.used, [signature]: true },
      },
    };
  }

  if (payload.type === 'claim') {
    const { domain, nonce, signerPubkey, signature } = payload;
    const reject = (reason) => ({ ...state, rejections: [...state.rejections, { eventId: event.id, domain: domain ?? null, reason }] });
    if (typeof domain !== 'string' || !domain) return reject('missing domain');
    if (!state.positions[domain]) return reject('no committed capital for this domain');
    if (typeof nonce !== 'string' || !nonce || typeof signerPubkey !== 'string' || typeof signature !== 'string') {
      return reject('malformed claim payload');
    }
    if (state.usedNonces[nonce]) return reject('nonce already used');
    if (!(await verifyAction(ACTIONS.claim, payload))) return reject('invalid signature: only the domain itself can claim its own accrued balance');

    const brokenChain = chainViolation(rewardParams, state, payload);
    if (brokenChain) return reject(brokenChain);
    const claimableUnits = currentlyClaimableUnits(rewardParams, state, domain);

    let amount;
    try {
      amount = toUnits(payload.amount);
    } catch {
      return reject('malformed amount');
    }
    if (!(amount > 0n)) return reject('amount must be positive');
    if (amount > claimableUnits) return reject(`insufficient claimable: has ${claimableUnits}, tried to claim ${amount}`);

    const currentEpoch = domainAge(state.progression, domain);
    const currentBalance = state.balances[domain] ?? 0n;
    return {
      ...state,
      positions: { ...state.positions, [domain]: { ...state.positions[domain], lastActionEpoch: currentEpoch } },
      balances: { ...state.balances, [domain]: currentBalance + amount },
      usedNonces: { ...state.usedNonces, [nonce]: true },
      chain: { ...(state.chain ?? {}), [domain]: event.id },
    };
  }

  if (payload.type === 'delegated-claim') {
    const { domain, nonce, delegate, ownerPubkey, delegationSignature, signerPubkey, signature } = payload;
    const reject = (reason) => ({ ...state, rejections: [...state.rejections, { eventId: event.id, domain: domain ?? null, reason }] });
    if (typeof domain !== 'string' || !domain) return reject('missing domain');
    if (!state.positions[domain]) return reject('no committed capital for this domain');
    if (![nonce, delegate, ownerPubkey, delegationSignature, signerPubkey, signature].every((v) => typeof v === 'string' && v)) {
      return reject('malformed delegated-claim payload');
    }
    if (state.usedNonces[nonce]) return reject('nonce already used');
    if (!(await verifyDelegatedAction(ACTIONS.claim, payload))) return reject('invalid delegated signature');

    const brokenChain = chainViolation(rewardParams, state, payload);
    if (brokenChain) return reject(brokenChain);
    const claimableUnits = currentlyClaimableUnits(rewardParams, state, domain);

    let amount;
    try {
      amount = toUnits(payload.amount);
    } catch {
      return reject('malformed amount');
    }
    if (!(amount > 0n)) return reject('amount must be positive');
    if (amount > claimableUnits) return reject(`insufficient claimable: has ${claimableUnits}, tried to claim ${amount}`);

    const currentEpoch = domainAge(state.progression, domain);
    const currentBalance = state.balances[domain] ?? 0n;
    return {
      ...state,
      positions: { ...state.positions, [domain]: { ...state.positions[domain], lastActionEpoch: currentEpoch } },
      balances: { ...state.balances, [domain]: currentBalance + amount },
      usedNonces: { ...state.usedNonces, [nonce]: true },
      chain: { ...(state.chain ?? {}), [domain]: event.id },
    };
  }

  return state;
}

export async function materializeAccrual(rewardParams, orderedEvents, verifyFn) {
  let state = initialAccrualState();
  for (const event of orderedEvents) state = await applyAccrualEvent(rewardParams, state, event, verifyFn);
  return state;
}

export function claimableNow(rewardParams, state, domain) {
  return currentlyClaimableUnits(rewardParams, state, domain);
}

/**
 * `walletState` with the burn records a reader has confirmed put where the reducer looks for them
 * (accrual.burns.records: signature -> fetchBurnRecord's result). Fold 'burn-record' events on top of the state this
 * returns. Records are added to, never replaced: what was confirmed stays confirmed.
 */
export function withConfirmedBurns(walletState, records) {
  const accrual = walletState.accrual ?? initialAccrualState();
  const burns = accrual.burns ?? initialBurnsState();
  return { ...walletState, accrual: { ...accrual, burns: { ...burns, records: { ...burns.records, ...records } } } };
}
