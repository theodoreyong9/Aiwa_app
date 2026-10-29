import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity, EventLog } from 'aiwa-core';
import { issueCapability, verifyCapability, CapabilitySet } from '../src/capability.js';
import { GuardedDataStore } from '../src/guarded-data-store.js';

async function grantedCapabilities(issuer, subject, resource, action) {
  const capability = await issueCapability(issuer, { resource, actions: [action], subject: subject.id });
  const check = await verifyCapability(capability, issuer);
  assert.equal(check.valid, true, 'test setup: the issued capability must itself verify');
  const set = new CapabilitySet();
  set.grant(capability);
  return set;
}

test('a write with a granted capability for the resource+action succeeds', async () => {
  const issuer = await generateIdentity();
  const writer = await generateIdentity();
  const capabilities = await grantedCapabilities(issuer, writer, 'sphere-1', 'write');

  const store = new GuardedDataStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities });
  await store.set('name', 'Alice');
  assert.equal(await store.get('name'), 'Alice');
});

test('SECURITY: a write with no capability at all is refused, the store left untouched', async () => {
  const writer = await generateIdentity();
  const store = new GuardedDataStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities: new CapabilitySet() });
  await assert.rejects(store.set('name', 'Alice'), /Write refused/);
  assert.equal(await store.get('name'), undefined);
});

test('SECURITY: a capability for a different resource does not authorize this store\'s writes', async () => {
  const issuer = await generateIdentity();
  const writer = await generateIdentity();
  const capabilities = await grantedCapabilities(issuer, writer, 'sphere-OTHER', 'write');

  const store = new GuardedDataStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities });
  await assert.rejects(store.set('name', 'Alice'), /Write refused/);
});

test('SECURITY: a capability for a different action (read, not write) does not authorize a write', async () => {
  const issuer = await generateIdentity();
  const writer = await generateIdentity();
  const capabilities = await grantedCapabilities(issuer, writer, 'sphere-1', 'read');

  const store = new GuardedDataStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities });
  await assert.rejects(store.set('name', 'Alice'), /Write refused/);
});

test('a custom resourceOf mapping is used instead of the default (store.domain)', async () => {
  const issuer = await generateIdentity();
  const writer = await generateIdentity();
  const capabilities = await grantedCapabilities(issuer, writer, 'profile:name', 'write');

  const store = new GuardedDataStore({
    identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities,
    resourceOf: (partial) => `profile:${partial.payload.key}`,
  });
  await store.set('name', 'Alice');
  assert.equal(await store.get('name'), 'Alice');

  await assert.rejects(store.set('email', 'a@example.com'), /Write refused/, 'a different key must resolve to a different, ungranted resource');
});

test('transact() is gated exactly like set()/delete() — it also routes through _commit', async () => {
  const writer = await generateIdentity();
  const store = new GuardedDataStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities: new CapabilitySet() });
  await assert.rejects(store.transact((tx) => tx.set('a', 1)), /Write refused/);
});

test('GuardedDataStore requires a capabilities set at construction — never silently ungated', () => {
  assert.throws(() => new GuardedDataStore({ identity: null, domain: 'd', log: new EventLog() }), /requires a real CapabilitySet/);
});
