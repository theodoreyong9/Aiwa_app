import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AIWA } from '../src/wallet.js';
import { collectAncestors } from '../src/ancestors.js';

// A domain that holds two signed histories (a fork) is something the wallets that received them can PROVE; accusations() says
// so, from proofs only. Two devices with the same 12 words, each with its own commitment, are two unrelated lineages.
const rewardParams = { alpha: 1.1, beta: 2.2, gamma: 3, C: Math.pow(33, 3), minQ: 1, commitmentBacking: 'none' };
const VDF_ITERATIONS = 20;

async function wallet(phrase) {
  const aiwa = new AIWA({ rewardParams });
  const { identityId } = await aiwa.connect(phrase ? { mnemonic: phrase } : {});
  return { aiwa, id: identityId };
}
const bundleOf = async (aiwa) => ({ events: await collectAncestors(aiwa.log, await aiwa.log.head()) });
async function advance(aiwa, times) { for (let i = 0; i < times; i++) await aiwa.advanceProgress({ vdfIterations: VDF_ITERATIONS }); }
async function receive(to, from) { await to.receiveOfflineBundle(await bundleOf(from)); await to.settled(); }

test('an honest domain is not accused, and neither is one that merely sent an older state', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(alice, 2);
  await receive(bob, alice);
  assert.deepEqual(await bob.accusations(), []);
  const old = await bundleOf(alice);                 // a payment made at epoch 2 ...
  await advance(alice, 3);
  await receive(bob, alice);                         // ... after bob has seen epoch 5
  await bob.receiveOfflineBundle(old);               // and only now delivered
  await bob.settled();
  assert.deepEqual(await bob.accusations(), [], 'a slow payment is not a rewind');
  assert.equal((await bob.position(aliceId)).position, 5);
});

test('two signed histories of one identity are an accusation, with the proof, once two wallets have received one each', async () => {
  const { aiwa: laptop, id: aliceId } = await wallet();
  const { aiwa: phone } = await wallet(laptop.recoveryPhrase);     // the same 12 words on another device
  await laptop.recordCommitment({ b: 1 });
  await advance(laptop, 3);
  await phone.recordCommitment({ b: 2 });
  await advance(phone, 2);
  const { aiwa: bob } = await wallet();
  const { aiwa: carol } = await wallet();
  await receive(bob, laptop);
  assert.deepEqual(await bob.accusations(), [], 'one history: nothing to say yet');
  await receive(carol, phone);
  await receive(bob, carol);                                       // bob now holds carol's reception of the other history

  const accused = await bob.accusations();
  assert.equal(accused.length, 1);
  assert.equal(accused[0].domain, aliceId);
  assert.equal(accused[0].reason, 'fork');
  assert.ok(accused[0].forks.length >= 1, 'the two events are the proof');
});

test('accusations() is read-only: it works with no key unlocked', async () => {
  const { aiwa: alice } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(alice, 2);
  await receive(bob, alice);
  await bob.disconnect();
  assert.deepEqual(await bob.accusations(), []);
});
