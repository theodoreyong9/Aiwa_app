import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spendableClaims } from 'aiwa-core';
import { AIWA } from '../src/wallet.js';
import { createMemoryBackend } from 'aiwa-core';
import { fakeSolana, deployment } from './support/helpers.mjs';

// A log that answers after a moment, as a browser's database does: reads and appends then really interleave.
function slowBackend() {
  const inner = createMemoryBackend();
  const later = () => new Promise((r) => setTimeout(r, Math.random() * 3));
  return Object.fromEntries(Object.entries(inner).map(([name, fn]) => [name, async (...args) => { await later(); return fn(...args); }]));
}

// The wallet's state is folded once and kept, and only what is appended afterwards is folded onto it. Several things read it at
// the same time (the screen, the mining loop, an app that asks who the player is) while others append and while a burn is
// confirmed: a read that ends late must not leave the cache older than what happened since it began. Whatever the
// interleaving, the state of the wallet is the one a full fold of its log gives.

const summary = (wallet, state) => ({
  epoch: state.accrual.progression.domains[wallet.identity.id]?.epoch,
  position: !!state.accrual.positions[wallet.identity.id],
  spendable: spendableClaims(state, wallet.identity.id).reduce((sum, c) => sum + c.amount, 0n).toString(),
  rejections: state.accrual.rejections.map((r) => r.reason ?? r),
});

async function oneRound() {
  const wallet = new AIWA({ rewardParams: deployment.rewardParams, backend: slowBackend() });
  await wallet.connect();
  let stop = false;
  const hammer = (async () => { while (!stop) { await wallet.ledger.state(); await new Promise((r) => setTimeout(r, 0)); } })();
  wallet.startProgressLoop({ intervalMs: 5, onError: (e) => { throw e; } });
  await new Promise((r) => setTimeout(r, 60));

  await wallet.burn(1_000_000_000, fakeSolana(), { T: 0 });
  await new Promise((r) => setTimeout(r, 400));
  await wallet.claim(await wallet.claimable());
  await new Promise((r) => setTimeout(r, 200));
  wallet.stopProgressLoop();
  stop = true;
  await hammer;
  await new Promise((r) => setTimeout(r, 300));          // a tick that was already under way finishes: nothing is appended while we compare

  const incremental = summary(wallet, await wallet.ledger.state());
  wallet.ledger.reset();
  const full = summary(wallet, await wallet.ledger.state());
  assert.deepEqual(incremental, full);
  assert.equal(full.position, true);
  assert.deepEqual(full.rejections, []);
}

test('reading the state while mining and while a burn is confirmed gives the state of a full fold', async () => {
  for (let round = 0; round < 4; round++) await oneRound();     // an interleaving that goes wrong is rare: try several
});
