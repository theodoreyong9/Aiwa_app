import test from 'node:test';
import assert from 'node:assert/strict';
import { deriveId, fromHex, generateIdentity } from 'aiwa-core';
import { coffeeTarget, coffeeAmount } from '../src/coffee-core.js';

test('the wallet of the person is the identity of the key her signed card carries', async () => {
  const me = await generateIdentity();
  assert.equal(await coffeeTarget(me.publicKey), await deriveId(fromHex(me.publicKey)));
  assert.equal(await coffeeTarget(me.publicKey), me.id, 'the same id the wallet of that key uses');
});

test('a key that is not a key gives nobody to pay', async () => {
  for (const bad of ['', null, 'abc', 'g'.repeat(64), 'A'.repeat(64), '../x', 'a'.repeat(63)]) assert.equal(await coffeeTarget(bad), null, String(bad));
});

test('the amount is a plain decimal above zero', () => {
  assert.equal(coffeeAmount('1'), '1');
  assert.equal(coffeeAmount(' 0,5 '), '0.5');
  for (const bad of ['', '0', '0.0', '-1', '1e3', '1.123456789', 'abc', '01', '1000000000']) assert.equal(coffeeAmount(bad), '', bad);
});
