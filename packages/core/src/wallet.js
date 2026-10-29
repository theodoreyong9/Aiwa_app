// Composes accrual.js and conservation.js into one materialized wallet state. A 'claim' debits the accrued balance AND
// creates the matching spendable claim in the same pass, both checked before either is applied, so they never drift.
// Moving or dividing a claim ('transfer', 'split', 'voucher-redeem') requires the signature of whoever controls it,
// directly or through a delegation (signing.js).

import { applyAccrualEvent, initialAccrualState, claimableNow } from './accrual.js';
import { initialConservationState, issueClaim, transfer, splitClaim, identityDerivation } from './conservation.js';
import { toUnits } from './units.js';
import { applyCheckpointEvent, verifyCheckpoint } from './checkpoint.js';
import { toReducerEvents } from './adapt-event.js';
import { sha256Hex } from './bytes.js';
import { ACTIONS, signAction, verifyAction, signDelegatedAction, verifyDelegatedAction } from './signing.js';

export { issueDelegation, verifyDelegation } from './signing.js';

const derivations = { identity: identityDerivation };

export function initialWalletState() {
  return { accrual: initialAccrualState(), conservation: initialConservationState(), usedNonces: {}, rejections: [] };
}

// The signed builders: ordinary ones are signed by the owner's key; delegated ones by a delegate's key, reusing
// an already-issued delegation (see issueDelegation), so the owner's own key signs once however many actions follow.
export const buildSignedTransferEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.transfer, fields, signerSeed, signerPubkeyBytes, options);
export const buildSignedSplitEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.split, fields, signerSeed, signerPubkeyBytes, options);
export const buildSignedVoucherRedeemEvent = (fields, signerSeed, signerPubkeyBytes, options) =>
  signAction(ACTIONS.voucherRedeem, fields, signerSeed, signerPubkeyBytes, options);
export const buildSignedDelegatedTransferEvent = (delegation, fields, delegateSeed, delegatePubkeyBytes, options) =>
  signDelegatedAction(ACTIONS.transfer, delegation, fields, delegateSeed, delegatePubkeyBytes, options);
export const buildSignedDelegatedSplitEvent = (delegation, fields, delegateSeed, delegatePubkeyBytes, options) =>
  signDelegatedAction(ACTIONS.split, delegation, fields, delegateSeed, delegatePubkeyBytes, options);
/** Redeems a voucher into the delegation owner's identity (delegation.from), not the delegate's own. */
export const buildSignedDelegatedVoucherRedeemEvent = (delegation, fields, delegateSeed, delegatePubkeyBytes, options) =>
  signDelegatedAction(ACTIONS.voucherRedeem, delegation, fields, delegateSeed, delegatePubkeyBytes, options);

/**
 * A voucher is redeemable by whoever shows up first: an ordinary signed transfer to a SYNTHETIC address (the hash of a
 * secret, not any identity's id), then a 'voucher-redeem' that reveals the secret. The classic hash lock. Copying the
 * QR is harmless because only the first redemption succeeds: a claim, once transferred, is consumed, and moving it
 * again is rejected like any replayed transfer.
 */
export async function deriveVoucherAddress(secret) {
  return `voucher:${await sha256Hex(secret)}`;
}

// The wallet's own signed moves of an already-owned claim, all guarded by a one-time nonce. `signed` is the kind of
// action signed (signing.js); `move` computes the new conservation state from the payload.
const asTransfer = async (state, { claimId, from, to }, source = from) =>
  transfer(state.conservation, { claimId, from: source, to, n: 0, derivation: 'identity' }, derivations).state;

const MOVES = {
  transfer: { action: ACTIONS.transfer, move: (state, p) => asTransfer(state, p) },
  'delegated-transfer': { action: ACTIONS.transfer, delegated: true, move: (state, p) => asTransfer(state, p) },
  split: { action: ACTIONS.split, move: (state, p) => splitPayload(state, p) },
  'delegated-split': { action: ACTIONS.split, delegated: true, move: (state, p) => splitPayload(state, p) },
  'voucher-redeem': { action: ACTIONS.voucherRedeem, move: async (state, p) => asTransfer(state, p, await deriveVoucherAddress(p.secret)) },
  'delegated-voucher-redeem': { action: ACTIONS.voucherRedeem, delegated: true, move: async (state, p) => asTransfer(state, p, await deriveVoucherAddress(p.secret)) },
};

const splitPayload = (state, { claimId, firstAmount, firstId, secondId }) =>
  splitClaim(state.conservation, { claimId, firstAmount: toUnits(firstAmount), firstId, secondId });

const reject = (state, event, reason) => ({ ...state, rejections: [...state.rejections, { eventId: event.id, reason }] });
const isText = (v) => typeof v === 'string' && v;

// A rejected move: a wrong secret (the claim's owner mismatches) and a double redemption (the claim is already
// consumed) both surface here as the conservation error.
async function spend(state, event, nonce, compute) {
  try {
    return { ...state, conservation: await compute(), usedNonces: { ...state.usedNonces, [nonce]: true } };
  } catch (e) {
    return reject(state, event, e.message);
  }
}

async function applyMove(state, event, type) {
  const { action, delegated, move } = MOVES[type];
  const payload = event.payload;
  const required = [...action.required, 'nonce', 'signerPubkey', 'signature', ...(delegated ? ['delegate', 'ownerPubkey', 'delegationSignature'] : [])];
  if (!required.every((key) => isText(payload[key]))) return reject(state, event, `malformed ${type} payload`);
  if (state.usedNonces[payload.nonce]) return reject(state, event, 'nonce already used');
  const valid = await (delegated ? verifyDelegatedAction : verifyAction)(action, payload);
  if (!valid) return reject(state, event, `invalid ${delegated ? 'delegated ' : ''}${action.label}`);
  return spend(state, event, payload.nonce, () => move(state, payload));
}

export async function applyWalletEvent(rewardParams, state, event, verifyFn, contractVerifiers = {}) {
  const payload = event.payload;
  if (!payload || typeof payload.type !== 'string') return state;
  const { type } = payload;

  if (type === 'progression' || type === 'burn-record') {
    return { ...state, accrual: await applyAccrualEvent(rewardParams, state.accrual, event, verifyFn) };
  }

  // A burn's commitment replaces the position, and pays what the previous one had accrued first (accrual.js): that
  // payment is a claim owned by the domain, spendable like any other. Its id comes from the event's own nonce, so
  // every reader names it the same.
  if (type === 'accrual') {
    const { domain, nonce } = payload;
    const accrual = await applyAccrualEvent(rewardParams, state.accrual, event, verifyFn);
    const paid = (accrual.balances[domain] ?? 0n) - (state.accrual.balances[domain] ?? 0n);
    if (paid === 0n) return { ...state, accrual };
    return { ...state, accrual, conservation: issueClaim(state.conservation, { id: `auto:${nonce}`, kind: 'AIWA', amount: paid, owner: domain }) };
  }

  // A checkpoint is not handled here: events reach this function adapted (adapt-event.js strips the wire event's
  // `author`), and verifying a checkpoint needs it. materializeWalletFromWireEvents folds batches that may hold one.
  if (type === 'checkpoint') return state;

  // 'delegated-claim' shares this body: whether the domain's owner or a delegate signed is decided inside
  // applyAccrualEvent, so by the time either reaches issueClaim it is authenticated.
  if (type === 'claim' || type === 'delegated-claim') {
    const { domain, claimId } = payload;
    if (typeof claimId !== 'string' || !claimId) return reject(state, event, 'missing claimId');
    if (state.conservation.claims[claimId]) return reject(state, event, `claim id already exists: ${claimId}`);
    const accrual = await applyAccrualEvent(rewardParams, state.accrual, event, verifyFn);
    if ((accrual.balances[domain] ?? 0n) === (state.accrual.balances[domain] ?? 0n)) return { ...state, accrual };
    const conservation = issueClaim(state.conservation, { id: claimId, kind: 'AIWA', amount: toUnits(payload.amount), owner: domain });
    return { ...state, accrual, conservation };
  }

  if (type in MOVES) return applyMove(state, event, type);

  // The extension point for external contracts: any contract that moves already-owned AIWA conditionally registers
  // its own `verifyPayout(payload)` under its `contractId` in `contractVerifiers`. The wallet only guarantees what
  // every such contract shares: the pre-signed transfer's signature is valid, checked as for an ordinary transfer,
  // before the contract is asked whether its own conditions were met.
  if (type === 'contract-payout') {
    const { contractId, claimId, from, to, nonce, signature } = payload;
    if (!isText(contractId)) return reject(state, event, 'missing contractId');
    const verifier = contractVerifiers[contractId];
    if (!verifier) return reject(state, event, `unregistered contract: ${contractId}`);
    if (![claimId, from, to, nonce, payload.signerPubkey, signature].every(isText)) return reject(state, event, 'malformed contract-payout transfer fields');
    if (state.usedNonces[nonce]) return reject(state, event, 'nonce already used');
    if (!(await verifyAction(ACTIONS.transfer, payload))) return reject(state, event, 'invalid transfer signature');
    const verified = await verifier(payload);
    if (!verified) return reject(state, event, `contract '${contractId}' rejected its own real conditions`);
    if (verified.claimId !== claimId || verified.from !== from || verified.to !== to || verified.nonce !== nonce || verified.signature !== signature) {
      return reject(state, event, 'contract verifier returned fields not matching the real, submitted event');
    }
    return spend(state, event, nonce, () => asTransfer(state, payload));
  }

  return state;
}

// `baseState`, if given, is a state already materialized from a prior prefix of the same log: only the events
// appended since are folded onto it, instead of replaying everything. It is the caller's responsibility that it
// really is the materialization of every event causally before `orderedEvents[0]`.
export async function materializeWallet(rewardParams, orderedEvents, onProgress, verifyFn, contractVerifiers = {}, baseState) {
  let state = baseState ?? initialWalletState();
  // Progress is throttled by elapsed time, not by event count: one slow event (a VDF re-verification) can take longer
  // than a whole backlog of cheap ones, and a fixed cadence would then look like a freeze.
  let lastReportedAt = 0;
  for (let i = 0; i < orderedEvents.length; i++) {
    state = await applyWalletEvent(rewardParams, state, orderedEvents[i], verifyFn, contractVerifiers);
    const now = Date.now();
    if (onProgress && (i === 0 || now - lastReportedAt >= 150)) {
      onProgress(i + 1, orderedEvents.length);
      lastReportedAt = now;
    }
  }
  if (onProgress) onProgress(orderedEvents.length, orderedEvents.length);
  return state;
}

/**
 * Like materializeWallet, but takes RAW wire events ({id, domain, author, authorPublicKey, parents, type, payload,
 * createdAt, signature}, e.g. straight from EventLog.get) instead of adapted ones. A checkpoint's authenticity needs
 * the wire event's `author`, which adaptation strips, so a batch that may hold a checkpoint has to be folded from
 * here: the check runs at the checkpoint's own position, and progression's last id is repointed there.
 */
export async function materializeWalletFromWireEvents(rewardParams, events, onProgress, verifyFn, contractVerifiers = {}, baseState) {
  let state = baseState ?? initialWalletState();
  let segment = [];
  const flushSegment = async () => {
    if (segment.length === 0) return;
    state = await materializeWallet(rewardParams, toReducerEvents(segment), null, verifyFn, contractVerifiers, state);
    segment = [];
  };
  // Progress throttled by elapsed time, as in materializeWallet.
  let lastReportedAt = 0;
  for (let i = 0; i < events.length; i++) {
    const event = events[i];
    if (verifyCheckpoint(event)) {
      await flushSegment();
      state = applyCheckpointEvent(state, event);
    } else {
      segment.push(event);
    }
    const now = Date.now();
    if (onProgress && (i === 0 || now - lastReportedAt >= 150)) {
      onProgress(i + 1, events.length);
      lastReportedAt = now;
    }
  }
  await flushSegment();
  if (onProgress) onProgress(events.length, events.length);
  return state;
}

export function spendableClaims(state, domain) {
  return Object.values(state.conservation.claims).filter((c) => c.owner === domain && c.status === 'active');
}

export function totalBalance(rewardParams, state, domain) {
  const unclaimed = claimableNow(rewardParams, state.accrual, domain);
  const claimed = spendableClaims(state, domain).reduce((sum, c) => sum + c.amount, 0n);
  return unclaimed + claimed;
}
