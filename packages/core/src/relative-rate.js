// A domain's VDF-verified progression epoch (progression.js) already marks how much sequential work it has done.
// This file uses that marker for a signed statement: "at MY OWN epoch X, I observed target domain Y at their epoch Z".
// Never a clock reading or a duration in any unit: two successive statements from the same observer about the same
// target give a purely structural ratio, with no clock consulted by any party.
//
// Kept separate from mirror.js's reception commitments, and purely informational: it never gates, corrects or
// bounds what a domain can claim (as in causal-tick.js).

import { weightedMedian } from './weighted-median.js';
import { toHex, fromHex } from './bytes.js';
import { signHex, verifyHex } from './signing.js';

function canonicalWitnessMessage({ observer, observerEpoch, target, targetEpoch, sourceEventId }) {
  return JSON.stringify({ observer, observerEpoch, target, targetEpoch, sourceEventId });
}

/**
 * A signed statement: "at my own VDF-verified progression
 * epoch `observerEpoch`, I observed target domain `target` at
 * their own epoch `targetEpoch`, via event `sourceEventId`."
 * Both epochs are already-verified quantities (progression.js);
 * nothing here is a clock reading of any kind.
 */
export async function buildRateWitness(keypair, observer, observerEpoch, target, targetEpoch, sourceEventId) {
  const fields = { observer, observerEpoch, target, targetEpoch, sourceEventId };
  const signature = signHex(new TextEncoder().encode(canonicalWitnessMessage(fields)), keypair.secretKey.slice(0, 32));
  return { ...fields, signature, signerPubkey: toHex(keypair.publicKey.toBytes()) };
}

/**
 * @returns {boolean} true only if the signature verifies over
 * the exact fields claimed — never trusted from the witness's
 * own claims about itself.
 */
export function verifyRateWitness(witness) {
  try {
    const { observer, observerEpoch, target, targetEpoch, sourceEventId, signature, signerPubkey } = witness;
    return verifyHex(new TextEncoder().encode(canonicalWitnessMessage({ observer, observerEpoch, target, targetEpoch, sourceEventId })), signature, signerPubkey);
  } catch {
    return false;
  }
}

/**
 * From two successive, valid witnesses by the SAME real
 * observer about the SAME target — the ratio of how much the
 * target's own epoch advanced versus how much the observer's
 * own epoch advanced, between these two observations.
 * Purely structural: no clock, no timestamp, no declared duration of
 * any kind enters this computation anywhere.
 *
 * @returns {number|null} null if the pair is invalid (wrong order,
 * zero observer delta, mismatched observer/target, bad signature) —
 * a honest refusal to compute, never a fabricated ratio.
 */
export function computeRelativeRate(witnessEarlier, witnessLater) {
  if (!verifyRateWitness(witnessEarlier) || !verifyRateWitness(witnessLater)) return null;
  if (witnessEarlier.observer !== witnessLater.observer) return null;
  if (witnessEarlier.target !== witnessLater.target) return null;
  if (witnessEarlier.signerPubkey !== witnessLater.signerPubkey) return null;
  const observerDelta = witnessLater.observerEpoch - witnessEarlier.observerEpoch;
  if (!(observerDelta > 0)) return null; // must be later, forward progress — never zero or negative
  const targetDelta = witnessLater.targetEpoch - witnessEarlier.targetEpoch;
  if (targetDelta < 0) return null; // Mirror's own reception monotonicity — a regression is never trusted
  return targetDelta / observerDelta;
}

/**
 * Aggregates many (observer, target) relative-rate pairs into a
 * single, robust, informational estimate — weighted by each real
 * observer's own already-verified committed capital (identity-cost.js),
 * the identical security shape causal-tick.js already relies on:
 * robust while adversarial weight stays below half of the total real
 * weight contributing an estimate. Purely informational — this NEVER
 * feeds back into what any domain can claim or how fast it may
 * progress; see causal-tick.js's own header for why that direction is
 * refused.
 *
 * @param {Array<{ratio: number, observerDomain: string}>} estimates
 * @param {ReturnType<typeof import('./identity-cost.js').initialIdentityCostState>} identityCostState
 * @returns {{ emergentRate: number, observationCount: number, totalWeight: number } | null}
 */
export function computeEmergentRate(estimates, identityCostState) {
  const weighted = [];
  let totalWeight = 0;
  for (const { ratio, observerDomain } of estimates) {
    const weight = identityCostState.registered[observerDomain]?.burnedLamports ?? 0;
    if (!(weight > 0)) continue; // no committed capital — no weight, exactly like causal-tick.js
    if (!(ratio > 0) || !Number.isFinite(ratio)) continue;
    weighted.push({ value: ratio, weight });
    totalWeight += weight;
  }
  if (weighted.length === 0) return null; // bottom: insufficiently determined, a honest absence
  return { emergentRate: weightedMedian(weighted), observationCount: weighted.length, totalWeight };
}

// Composing ρ_AB · ρ_BC = ρ_AC is mathematically valid, but and
// dangerous if built without a bound: A→B was measured at some real
// point, B→C at some possibly much later point, and if B's own
// relative rate drifted between the two (genuinely — new
// hardware, thermal throttling, different load — never requiring any
// forged signature), the composed result can be badly wrong. This
// bounds that risk using B's own already-verified progression epoch
// as the freshness measure — never a clock, never a timestamp — but
// it is a mitigation, not a closure: even within the bound, the
// intermediate domain still freely chooses when it observes the next
// link, and drift can in principle occur within any bound.
// Callers should treat a wide bound as reduced confidence, not
// as equivalent to a short, direct measurement.
export function composeRelativeRates(pairAB, pairBC, { maxFreshnessGap } = {}) {
  if (!(maxFreshnessGap > 0)) throw new Error('maxFreshnessGap must be a positive real epoch count — required, never defaulted silently, since the right bound is deployment-specific.');

  const rhoAB = computeRelativeRate(pairAB.earlier, pairAB.later);
  const rhoBC = computeRelativeRate(pairBC.earlier, pairBC.later);
  if (rhoAB === null || rhoBC === null) return null;

  // The chain must connect: A's own later witness about B
  // must reference the identical domain B is observing itself as
  // in the B→C pair — never trusted from a caller's own claim that
  // they connect.
  if (pairAB.later.target !== pairBC.earlier.observer) return null;

  // B's own epoch when it started observing C, minus B's own
  // epoch as last referenced by A — both refer to the identical
  // verified quantity (B's own progression), never a clock.
  const freshnessGap = pairBC.earlier.observerEpoch - pairAB.later.targetEpoch;
  if (freshnessGap < 0) return null; // chronologically impossible for B's own progression — refused, never silently reordered
  if (freshnessGap > maxFreshnessGap) return null; // too stale to trust composing through — a honest refusal, not a degraded guess

  return { composedRate: rhoAB * rhoBC, freshnessGap, rhoAB, rhoBC };
}
