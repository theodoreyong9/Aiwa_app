import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ed25519 } from '@noble/curves/ed25519.js';
import * as solanaWeb3 from '@solana/web3.js';
import { deriveId } from '../src/identity.js';
import { initialWalletState, applyWalletEvent } from '../src/wallet.js';
import { withConfirmedBurns, buildSignedAccrualEvent, creatorFeeLamports, burnQuote, commitmentPriceLamports } from '../src/accrual.js';
import { SOLANA_INCINERATOR_ADDRESS } from '../src/identity-cost.js';
import { normalizeBurnTransaction, verifyBurnRecordFor } from '../src/burn-record.js';
import { base58Encode } from '../src/base58.js';
import { buildBurnTransaction } from '../src/solana-wallet.js';

// The creator fee (yellow paper §11): a small fixed part of the T share of a burn goes to ONE address that is a
// constant of the deployment; the rest is destroyed. The reader counts it: a commitment at T > 0 whose burn did not
// pay the creator is refused.
const CREATOR = base58Encode(ed25519.getPublicKey(ed25519.utils.randomSecretKey()));
const fee = { address: CREATOR, rateOfT: 0.001 };
const base = { alpha: 1.1, beta: 2.2, gamma: 3, C: Math.pow(33, 3), minQ: 1, creatorFee: fee };

async function person() {
  const seed = ed25519.utils.randomSecretKey();
  const pubkey = ed25519.getPublicKey(seed);
  return { seed, pubkey, domain: await deriveId(pubkey), address: base58Encode(pubkey) };
}
// what Solana says about a burn paid by `who`: `toIncinerator` and `toCreator` lamports, the payer paying both (+ network fee)
const solanaSays = (who, { toIncinerator, toCreator = 0 }, { spent = toIncinerator + toCreator + 5000 } = {}) => ({
  slot: 100,
  transaction: { message: { accountKeys: [who.address, SOLANA_INCINERATOR_ADDRESS, CREATOR, '11111111111111111111111111111111'] } },
  meta: { err: null, fee: 5000, preBalances: [10_000_000_000, 0, 7, 1], postBalances: [10_000_000_000 - spent, toIncinerator, 7 + toCreator, 1] },
});
const recordOf = (who, amounts, signature, options, normalizeOptions = { creatorAddress: CREATOR }) => normalizeBurnTransaction(solanaSays(who, amounts, options), signature, normalizeOptions);

let n = 0;
const event = (payload) => ({ id: `ev${++n}`, parents: [], payload });
const commit = async (who, b, T) => event({ type: 'accrual', ...(await buildSignedAccrualEvent({ domain: who.domain, b, T }, who.seed, who.pubkey)) });
const burnEvent = (who, signature) => event({ type: 'burn-record', domain: who.domain, signature });
async function fold(params, records, events) {
  let state = withConfirmedBurns(initialWalletState(), records);
  for (const e of events) state = await applyWalletEvent(params, state, e);
  return state;
}
const reasons = (state) => state.accrual.rejections.map((r) => r.reason);

test('the fee is floor(burned x T x rateOfT), in integers, and nothing without T, without a deployment fee, or without a rate', () => {
  assert.equal(creatorFeeLamports(1_000_000_000, 0.4, fee), 400_000);          // 1 SOL at T 40 %: T share 0.4 SOL, 0.1 % of it
  assert.equal(creatorFeeLamports(1_000_000_000, 0.2, fee), 200_000);
  assert.equal(creatorFeeLamports(999_999_999, 0.4, fee), 399_999);            // rounds down
  assert.equal(creatorFeeLamports(1_000_000_000, 0, fee), 0);                  // T = 0: nothing to share
  assert.equal(creatorFeeLamports(1_000_000_000, 0.4, undefined), 0);          // a deployment without a creator fee
  assert.equal(creatorFeeLamports(1_000_000_000, 0.4, { address: CREATOR, rateOfT: 0 }), 0);
  assert.equal(creatorFeeLamports(1, 0.4, fee), 0);
});

test('a quote adds up: what the wallet pays is what goes to the incinerator and to the creator', () => {
  const q = burnQuote({ lamports: 1_000_000_000, T: 0.4, creatorFee: fee });
  assert.deepEqual(q, { lamports: 1e9, T: 0.4, toCreator: 400_000, toIncinerator: 1e9 - 400_000, capital: 600_000_000, destroyedWithoutCounting: 1e9 - 600_000_000 - 400_000 });
  assert.equal(q.toCreator + q.toIncinerator, q.lamports);
  assert.equal(burnQuote({ lamports: 1e9, T: 0.4 }).toCreator, 0, 'no fee configured: everything is burned, as before');
});

test('the transaction pays the creator and the incinerator in one transaction; without a fee it is the single transfer it always was', () => {
  const payer = solanaWeb3.Keypair.generate();
  const common = { fromPubkey: payer.publicKey, lamports: 1_000_000_000, recentBlockhash: '11111111111111111111111111111111' };
  const none = buildBurnTransaction(solanaWeb3, common);
  assert.equal(none.instructions.length, 1);
  const withFee = buildBurnTransaction(solanaWeb3, { ...common, creatorAddress: CREATOR, creatorFeeLamports: 400_000 });
  const transfers = withFee.instructions.map((ix) => solanaWeb3.SystemInstruction.decodeTransfer(ix));
  assert.deepEqual(transfers.map((t) => [t.toPubkey.toBase58(), Number(t.lamports)]), [[SOLANA_INCINERATOR_ADDRESS, 1_000_000_000 - 400_000], [CREATOR, 400_000]]);
  assert.throws(() => buildBurnTransaction(solanaWeb3, { ...common, creatorFeeLamports: 5 }), /creator address/);
  assert.throws(() => buildBurnTransaction(solanaWeb3, { ...common, creatorAddress: CREATOR, creatorFeeLamports: 1_000_000_000 }), RangeError);
});

test('the record shows what reached the creator, only when the reader asked for that address, and the payer must have paid for both', async () => {
  const alice = await person();
  const amounts = { toIncinerator: 999_600_000, toCreator: 400_000 };
  const record = recordOf(alice, amounts, 'sig');
  assert.equal(record.incineratorBalanceDeltaLamports, 999_600_000);
  assert.equal(record.creatorBalanceDeltaLamports, 400_000);
  assert.equal((await verifyBurnRecordFor(alice.domain, record)).valid, true);
  // a reader that does not ask for the creator address sees no creator payment (fails closed, see below)
  assert.equal(recordOf(alice, amounts, 'sig', {}, {}).creatorBalanceDeltaLamports, 0);
  // the payer's balance must have gone down by both: money from someone else does not count
  const shortPaid = recordOf(alice, amounts, 'sig', { spent: 999_600_000 });
  assert.equal((await verifyBurnRecordFor(alice.domain, shortPaid)).valid, false);
});

test('a commitment at T > 0 is covered only if the burn paid the creator what the T share owes', async () => {
  const alice = await person();
  // 1 SOL at T 40 %: 400 000 lamports to the creator, 999 600 000 to the incinerator, capital 0.6
  const paid = recordOf(alice, { toIncinerator: 999_600_000, toCreator: 400_000 }, 'paid');
  const ok = await fold(base, { paid }, [burnEvent(alice, 'paid'), await commit(alice, 0.6, 0.4)]);
  assert.equal(ok.accrual.positions[alice.domain].b, 0.6);
  assert.equal(ok.accrual.burns.feeCovered[alice.domain], 400_000);
  assert.equal(ok.accrual.burns.feeConsumed[alice.domain], 400_000);
  assert.equal(ok.accrual.burns.covered[alice.domain], 1_000_000_000);
  assert.equal(commitmentPriceLamports(0.6, 0.4), 1_000_000_000);

  // one lamport short: refused, with the reason, and nothing is created
  const short = recordOf(alice, { toIncinerator: 999_600_001, toCreator: 399_999 }, 'short');
  const refused = await fold(base, { short }, [burnEvent(alice, 'short'), await commit(alice, 0.6, 0.4)]);
  assert.equal(refused.accrual.positions[alice.domain], undefined);
  assert.match(reasons(refused)[0], /owes the creator 400000 lamports/);

  // everything incinerated, nothing to the creator: refused
  const skipped = recordOf(alice, { toIncinerator: 1_000_000_000 }, 'skipped');
  const noFee = await fold(base, { skipped }, [burnEvent(alice, 'skipped'), await commit(alice, 0.6, 0.4)]);
  assert.equal(noFee.accrual.positions[alice.domain], undefined);
  assert.match(reasons(noFee)[0], /owes the creator/);
});

test('at T = 0 nothing is owed; a burn that paid more than owed is fine; the fee is used once, like the burn', async () => {
  const alice = await person();
  const plain = recordOf(alice, { toIncinerator: 2_000_000_000 }, 'plain');
  const zero = await fold(base, { plain }, [burnEvent(alice, 'plain'), await commit(alice, 2, 0)]);
  assert.equal(zero.accrual.positions[alice.domain].b, 2, 'T = 0: no fee, as before');

  // a burn of 2 SOL that paid the creator 800 000 (the fee for 2 SOL at T 40 %) backs one such commitment, not two
  const twice = recordOf(alice, { toIncinerator: 2_000_000_000 - 800_000, toCreator: 800_000 }, 'twice');
  const one = await fold(base, { twice }, [burnEvent(alice, 'twice'), await commit(alice, 0.6, 0.4), await commit(alice, 0.6, 0.4)]);
  assert.equal(one.accrual.burns.feeConsumed[alice.domain], 800_000, 'two commitments of 1 SOL each use the 800 000 paid');
  const three = await fold(base, { twice }, [burnEvent(alice, 'twice'), await commit(alice, 0.6, 0.4), await commit(alice, 0.6, 0.4), await commit(alice, 0.6, 0.4)]);
  assert.match(reasons(three).at(-1), /not covered|owes the creator/, 'a third has neither burn nor fee left');
});

test('a reader that did not ask for the creator address credits no fee: a commitment at T > 0 fails closed', async () => {
  const alice = await person();
  const asked = recordOf(alice, { toIncinerator: 999_600_000, toCreator: 400_000 }, 'sig');
  const notAsked = recordOf(alice, { toIncinerator: 999_600_000, toCreator: 400_000 }, 'sig', {}, {});
  const withIt = await fold(base, { sig: asked }, [burnEvent(alice, 'sig'), await commit(alice, 0.6, 0.4)]);
  assert.ok(withIt.accrual.positions[alice.domain]);
  const without = await fold(base, { sig: notAsked }, [burnEvent(alice, 'sig'), await commit(alice, 0.6, 0.4)]);
  assert.equal(without.accrual.positions[alice.domain], undefined);
});

test("a deployment with no creator fee behaves exactly as before: T costs a share of the burn, all of it incinerated", async () => {
  const alice = await person();
  const { creatorFee: _unused, ...noFeeParams } = base;
  const record = normalizeBurnTransaction(solanaSays(alice, { toIncinerator: 1_000_000_000 }), 'sig');
  const state = await fold(noFeeParams, { sig: record }, [burnEvent(alice, 'sig'), await commit(alice, 0.6, 0.4)]);
  assert.equal(state.accrual.positions[alice.domain].b, 0.6);
});
