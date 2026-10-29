import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity } from '../src/identity.js';
import { fromHex } from '../src/bytes.js';
import {
  ACTIONS, canonicalMessage, signAction, verifyAction, issueDelegation, verifyDelegation, signDelegatedAction, verifyDelegatedAction,
} from '../src/signing.js';

const text = (bytes) => new TextDecoder().decode(bytes);
const seedOf = (identity) => fromHex(identity._secretKey);
const pubOf = (identity) => fromHex(identity.publicKey);

// The bytes each action signs are part of the protocol: any change here breaks every signature already made.
test('the canonical messages are frozen', () => {
  assert.equal(text(canonicalMessage(ACTIONS.transfer, { claimId: 'c', from: 'a', to: 'b', nonce: 'n', timestamp: 1, extra: 'ignored' })),
    '{"claimId":"c","from":"a","to":"b","nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.transfer, { claimId: 'c', from: 'a', to: 'b', delegate: 'd', nonce: 'n', timestamp: 1 }, true)),
    '{"claimId":"c","from":"a","to":"b","delegate":"d","nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.split, { claimId: 'c', owner: 'o', firstAmount: 5, firstId: 'x', secondId: 'y', nonce: 'n', timestamp: 1 })),
    '{"claimId":"c","owner":"o","firstAmount":5,"firstId":"x","secondId":"y","nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.voucherRedeem, { claimId: 'c', secret: 's', to: 'b', nonce: 'n', timestamp: 1 })),
    '{"claimId":"c","secret":"s","to":"b","nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.accrual, { domain: 'd', b: 2, nonce: 'n', timestamp: 1 })), '{"domain":"d","b":2,"T":null,"nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.accrual, { domain: 'd', b: 2, T: 0.4, nonce: 'n', timestamp: 1, previous: 'p' })),
    '{"domain":"d","b":2,"T":0.4,"nonce":"n","timestamp":1,"previous":"p"}');
  assert.equal(text(canonicalMessage(ACTIONS.claim, { domain: 'd', amount: 3, nonce: 'n', timestamp: 1, previous: null })),
    '{"domain":"d","amount":3,"claimId":null,"nonce":"n","timestamp":1,"previous":null}');
  assert.equal(text(canonicalMessage(ACTIONS.claim, { domain: 'd', amount: 3, claimId: 'c', delegate: 'x', nonce: 'n', timestamp: 1 }, true)),
    '{"domain":"d","amount":3,"claimId":"c","delegate":"x","nonce":"n","timestamp":1}');
  assert.equal(text(canonicalMessage(ACTIONS.progression, { domain: 'd', epoch: 1, vdfIterations: 9, vdfOutput: 'o', nonce: 'n', timestamp: 1, previous: null })),
    '{"domain":"d","epoch":1,"vdfIterations":9,"vdfOutput":"o","nonce":"n","timestamp":1,"previous":null}');
});

test('an action is valid only if signed by the key that owns it, and only as signed', async () => {
  const owner = await generateIdentity();
  const other = await generateIdentity();
  const fields = { claimId: 'c1', from: owner.id, to: other.id };
  const event = await signAction(ACTIONS.transfer, fields, seedOf(owner), pubOf(owner), { now: 5, nonce: 'n1' });
  assert.equal(event.timestamp, 5);
  assert.equal(await verifyAction(ACTIONS.transfer, event), true);
  assert.equal(await verifyAction(ACTIONS.transfer, { ...event, to: owner.id }), false, 'a changed field breaks the signature');
  assert.equal(await verifyAction(ACTIONS.transfer, { ...event, from: other.id }), false, 'the signer is not the claimed owner');
  const forged = await signAction(ACTIONS.transfer, fields, seedOf(other), pubOf(other));
  assert.equal(await verifyAction(ACTIONS.transfer, forged), false, 'signed by a key that does not own `from`');
  assert.equal(await verifyAction(ACTIONS.transfer, { ...event, signature: undefined }), false);
});

test('a delegated action proves both the delegation and the delegate\'s own signature', async () => {
  const owner = await generateIdentity();
  const delegate = await generateIdentity();
  const stranger = await generateIdentity();
  const delegation = await issueDelegation(seedOf(owner), pubOf(owner), pubOf(delegate));
  assert.equal(await verifyDelegation(delegation), true);
  assert.equal(await verifyDelegation({ ...delegation, delegate: stranger.publicKey }), false);
  assert.equal(await verifyDelegation(null), false);

  const event = await signDelegatedAction(ACTIONS.transfer, delegation, { claimId: 'c1', to: 'dest', ignored: 1 }, seedOf(delegate), pubOf(delegate), { now: 7, nonce: 'n2' });
  assert.equal(event.from, owner.id);
  assert.equal(event.ignored, undefined);
  assert.equal(await verifyDelegatedAction(ACTIONS.transfer, event), true);
  assert.equal(await verifyDelegatedAction(ACTIONS.transfer, { ...event, to: 'elsewhere' }), false);
  assert.equal(await verifyDelegatedAction(ACTIONS.transfer, { ...event, from: stranger.id }), false);

  // a delegate the owner never authorised
  const notAuthorised = await signDelegatedAction(ACTIONS.transfer, { ...delegation, delegate: stranger.publicKey }, { claimId: 'c1', to: 'dest' }, seedOf(stranger), pubOf(stranger));
  assert.equal(await verifyDelegatedAction(ACTIONS.transfer, notAuthorised), false);
});
