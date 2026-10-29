import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as solanaWeb3 from '@solana/web3.js';
import { ed25519 } from '@noble/curves/ed25519.js';
import { base58Encode, SOLANA_INCINERATOR_ADDRESS, assessSubmission } from 'aiwa-core';
import { AIWA } from '../src/wallet.js';

// The creator fee through the wallet: burn(lamports, connection, { T }) pays a fixed part of the T share to the creator
// address in the same transaction, the wallet confirms the burn against Solana, and the capital it commits is what counts.
// Solana is a stand-in that really decodes the transaction the wallet built and keeps its own balances.
globalThis.window = { solanaWeb3 };
const CREATOR = base58Encode(ed25519.getPublicKey(ed25519.utils.randomSecretKey()));
const rewardParams = { alpha: 1.1, beta: 2.2, gamma: 3, C: Math.pow(33, 3), minQ: 1, creatorFee: { address: CREATOR, rateOfT: 0.001 } };

function fakeSolana() {
  const transactions = {};
  let count = 0;
  return {
    transactions,
    getLatestBlockhash: async () => ({ blockhash: '11111111111111111111111111111111', lastValidBlockHeight: 1 }),
    sendRawTransaction: async (raw) => {
      const tx = solanaWeb3.Transaction.from(raw);
      const keys = [tx.feePayer.toBase58()];
      const transfers = tx.instructions.map((ix) => {
        const d = solanaWeb3.SystemInstruction.decodeTransfer(ix);
        return { from: d.fromPubkey.toBase58(), to: d.toPubkey.toBase58(), lamports: Number(d.lamports) };
      });
      for (const t of transfers) for (const k of [t.from, t.to]) if (!keys.includes(k)) keys.push(k);
      const pre = keys.map((_, i) => (i === 0 ? 50e9 : 0));
      const post = [...pre];
      for (const t of transfers) { post[keys.indexOf(t.from)] -= t.lamports; post[keys.indexOf(t.to)] += t.lamports; }
      post[0] -= 5000;
      const signature = `sig${++count}`;
      transactions[signature] = { transfers, rpc: { slot: 10, transaction: { message: { accountKeys: keys } }, meta: { err: null, fee: 5000, preBalances: pre, postBalances: post } } };
      return signature;
    },
    confirmTransaction: async () => ({}),
    getTransaction: async (signature) => transactions[signature]?.rpc ?? null,
  };
}
async function wallet(params = rewardParams) {
  const aiwa = new AIWA({ rewardParams: params });
  await aiwa.connect();
  return aiwa;
}

test('a burn at T = 40 % pays the creator in the same transaction, and the committed capital is what counts', async () => {
  const aiwa = await wallet();
  const connection = fakeSolana();
  const signature = await aiwa.burn(1_000_000_000, connection, { T: 0.4 });
  const { transfers } = connection.transactions[signature];
  assert.deepEqual(transfers.map((t) => [t.to, t.lamports]), [[SOLANA_INCINERATOR_ADDRESS, 1_000_000_000 - 400_000], [CREATOR, 400_000]]);
  const mining = await aiwa.mining();
  assert.equal(mining.capital, 0.6);
});

test('at T = 0 the burn is the single transfer to the incinerator it always was, and nothing goes to the creator', async () => {
  const aiwa = await wallet();
  const connection = fakeSolana();
  const signature = await aiwa.burn(1_000_000_000, connection, { T: 0 });
  assert.deepEqual(connection.transactions[signature].transfers.map((t) => [t.to, t.lamports]), [[SOLANA_INCINERATOR_ADDRESS, 1_000_000_000]]);
});

test('the quote says what the burn will do before it is made', async () => {
  const aiwa = await wallet();
  assert.deepEqual(aiwa.burnQuote(1_000_000_000, 0.4), { lamports: 1e9, T: 0.4, toCreator: 400_000, toIncinerator: 999_600_000, capital: 600_000_000, destroyedWithoutCounting: 399_600_000 - 0 });
  assert.throws(() => aiwa.burnQuote(1e9, 0.5), /between 0 and 0.4/);
});

test('a burn that did not pay the creator cannot back a commitment at T > 0 (the wallet says why before appending anything), but still backs T = 0', async () => {
  // the same key, in a wallet that knows no creator fee: it burns everything to the incinerator
  const plain = await wallet({ ...rewardParams, creatorFee: undefined });
  const connection = fakeSolana();
  const signature = await plain.burn(1_000_000_000, connection, { T: 0 });
  assert.equal(connection.transactions[signature].transfers.length, 1);

  const aiwa = new AIWA({ rewardParams });
  await aiwa.connect({ secretKeyBytes: plain.keypair.secretKey });
  await aiwa.recordBurn(signature, connection);
  await assert.rejects(aiwa.recordCommitment({ b: 0.6, T: 0.4 }), /owes the creator 400000 lamports/);
  assert.equal((await aiwa.walletState()).accrual.rejections.length, 0, 'refused before anything was appended');
  await aiwa.recordCommitment({ b: 1, T: 0 });                       // T = 0 owes nothing
  assert.equal((await aiwa.mining()).capital, 1);
});

test('a verifier that knows the creator address accepts the evidence of a wallet that paid it; one that does not know it counts no position (fails closed)', async () => {
  const params = { ...rewardParams, epochIterations: 150 };
  const aiwa = await wallet(params);
  const connection = fakeSolana();
  await aiwa.burn(1_000_000_000, connection, { T: 0.4 });
  await aiwa.advanceProgress({ epochs: 1 });
  const evidence = await aiwa.submissionEvidence();

  const knows = await assessSubmission({ rewardParams: params, evidence, domain: aiwa.identity.id, connection });
  assert.equal(knows.ok, true);
  assert.equal(knows.mining.capital, 0.6);
  assert.equal(knows.mining.epoch, 1);

  const { creatorFee: _unused, ...withoutFee } = params;
  const ignorant = await assessSubmission({ rewardParams: withoutFee, evidence, domain: aiwa.identity.id, connection });
  assert.equal(ignorant.mining, null, 'a reader that does not look at the creator address sees only 999 600 000 burned: the commitment is not covered');
});
