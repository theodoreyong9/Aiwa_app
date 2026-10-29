import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AIWA } from '../src/wallet.js';
import { collectAncestors } from '../src/ancestors.js';

// What a wallet can say of another domain, in words a person reads (yellow paper §19): where it stands, what is proven, whether it
// signed two histories, and how fast it progresses compared with this wallet. Reported, never applied.
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

test('standing(): where a domain is, what is proven of it, and nothing about pace from one observation', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(alice, 3);
  await receive(bob, alice);
  const s = await bob.standing(aliceId);
  assert.equal(s.domain, aliceId);
  assert.equal(s.epoch, 3);
  assert.equal(s.provenAtLeast, 3);
  assert.equal(s.forked, false);
  assert.equal(s.verification, 'chain');
  assert.equal(s.pace, null, 'one observation: nothing to compare yet');
});

test('pace is how many epochs the other gained for each one this wallet gained between two observations, with no clock', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(bob, 1);                 // bob is at epoch 1
  await advance(alice, 2);
  await receive(bob, alice);             // bob (epoch 1) sees alice at 2
  await advance(bob, 3);                 // bob is at epoch 4
  await advance(alice, 6);
  await receive(bob, alice);             // bob (epoch 4) sees alice at 8
  const { pace } = await bob.standing(aliceId);
  assert.deepEqual(pace.mine, [1, 4]);
  assert.deepEqual(pace.theirs, [2, 8]);
  assert.equal(pace.ratio, 2, 'alice gained 6 epochs while bob gained 3');
});

test('no pace when this wallet did not progress between its two observations (nothing to divide by)', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(alice, 2);
  await receive(bob, alice);
  await advance(alice, 3);
  await receive(bob, alice);
  assert.equal((await bob.standing(aliceId)).pace, null);
});

test('standings() lists every other domain, the furthest first, and works with no key unlocked', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: carol, id: carolId } = await wallet();
  const { aiwa: bob } = await wallet();
  await advance(alice, 2);
  await advance(carol, 5);
  await receive(bob, alice);
  await receive(bob, carol);
  await bob.disconnect();
  const all = await bob.standings();
  assert.deepEqual(all.map((s) => [s.domain, s.epoch]), [[carolId, 5], [aliceId, 2]]);
  assert.ok(all.every((s) => s.pace === null), 'with no identity there is no "compared with me"');
});

test('a domain that signed two histories shows as forked, with what it is', async () => {
  const { aiwa: laptop, id: aliceId } = await wallet();
  const { aiwa: phone } = await wallet(laptop.recoveryPhrase);
  await laptop.recordCommitment({ b: 1 });
  await advance(laptop, 3);
  await phone.recordCommitment({ b: 2 });
  await advance(phone, 2);
  const { aiwa: bob } = await wallet();
  const { aiwa: carol } = await wallet();
  await receive(bob, laptop);
  assert.equal((await bob.standing(aliceId)).forked, false);
  await receive(carol, phone);
  await receive(bob, carol);
  assert.equal((await bob.standing(aliceId)).forked, true);
});

test('the median is a vote weighted by what each observer committed, and the position is never below what is proven', async () => {
  const { aiwa: alice, id: aliceId } = await wallet();
  const { aiwa: carol } = await wallet();
  const { aiwa: dave } = await wallet();
  await carol.recordCommitment({ b: 3 });      // carol weighs 3
  await dave.recordCommitment({ b: 1 });       // dave weighs 1
  await advance(alice, 2);
  await receive(carol, alice);                 // carol saw alice at 2
  await advance(alice, 3);
  await receive(dave, alice);                  // dave saw alice at 5
  const { aiwa: bob } = await wallet();
  await receive(bob, carol);
  await receive(bob, dave);
  const s = await bob.standing(aliceId);
  assert.equal(s.median, 2, 'the heavier observer saw less: the vote says 2');
  assert.equal(s.provenAtLeast, 5, 'but dave provably received epoch 5, and only alice can sign that');
  assert.equal(s.epoch, 5, 'the position never goes below what is proven');
  assert.ok(s.witnesses >= 2);
});
