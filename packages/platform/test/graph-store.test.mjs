import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity, EventLog } from 'aiwa-core';
import { issueCapability, verifyCapability, CapabilitySet } from '../src/capability.js';
import { GraphStore } from '../src/graph-store.js';
import { ref, isRef } from '../src/graph-materializer.js';

test('put/get round-trips a field on a node', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('alice', 'name', 'Alice');
  assert.equal(await store.get('alice', 'name'), 'Alice');
});

test('a node accumulates multiple fields across separate puts', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('alice', 'name', 'Alice');
  await store.put('alice', 'age', 30);
  assert.deepEqual(store.node('alice'), { name: 'Alice', age: 30 });
});

test('unset removes exactly the one field, others untouched', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('alice', 'name', 'Alice');
  await store.put('alice', 'age', 30);
  await store.unset('alice', 'age');
  assert.deepEqual(store.node('alice'), { name: 'Alice' });
});

test('has() reflects the current presence of a field', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  assert.equal(await store.has('alice', 'name'), false);
  await store.put('alice', 'name', 'Alice');
  assert.equal(await store.has('alice', 'name'), true);
  await store.unset('alice', 'name');
  assert.equal(await store.has('alice', 'name'), false);
});

test('a node with no fields yet is an empty object, never undefined', () => {
  const store = new GraphStore({ identity: null, domain: 'sphere-1', log: new EventLog() });
  assert.deepEqual(store.node('ghost'), {});
});

test('THE GRAPH PROPERTY: a field holding a reference resolves to the referenced node\'s own full field map', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('bob', 'name', 'Bob');
  await store.put('bob', 'company', 'Acme');
  await store.put('alice', 'employer', ref('bob'));

  const resolved = await store.get('alice', 'employer');
  assert.deepEqual(resolved, { name: 'Bob', company: 'Acme' });
});

test('isRef distinguishes a reference from an ordinary value', () => {
  assert.equal(isRef(ref('bob')), true);
  assert.equal(isRef('bob'), false);
  assert.equal(isRef({ name: 'bob' }), false);
  assert.equal(isRef(null), false);
});

test('nodeIds lists every node with at least one field', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('alice', 'name', 'Alice');
  await store.put('bob', 'name', 'Bob');
  assert.deepEqual((await store.nodeIds()).sort(), ['alice', 'bob']);
});

test('rebuild() reconstructs the identical graph state from the EventLog alone', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();
  const store = new GraphStore({ identity, domain: 'sphere-1', log });
  await store.put('alice', 'name', 'Alice');
  await store.put('bob', 'name', 'Bob');
  await store.put('alice', 'friend', ref('bob'));

  const rebuilt = new GraphStore({ identity, domain: 'sphere-1', log });
  await rebuilt.rebuild();
  assert.deepEqual(rebuilt.node('alice'), store.node('alice'));
  assert.deepEqual(rebuilt.node('bob'), store.node('bob'));
});

test('subscribe() fires with the current state on every write', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  const seen = [];
  store.subscribe(({ event, state }) => seen.push({ type: event.type, nodes: Object.keys(state.nodes) }));
  await store.put('alice', 'name', 'Alice');
  await store.put('bob', 'name', 'Bob');
  assert.equal(seen.length, 2);
  assert.deepEqual(seen[1].nodes.sort(), ['alice', 'bob']);
});

test('transact() is refused outright — never a silent kv-shaped no-op against the graph materializer', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await assert.rejects(store.transact((tx) => tx.set('a', 1)), /does not support transact/);
});

test('SECURITY: an ungated GraphStore (no capabilities passed) allows any write — matches plain DataStore\'s own default, documented behavior', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog() });
  await store.put('alice', 'name', 'Alice'); // must not throw
  assert.equal(await store.get('alice', 'name'), 'Alice');
});

test('a capability-gated GraphStore refuses a write with no grant', async () => {
  const identity = await generateIdentity();
  const store = new GraphStore({ identity, domain: 'sphere-1', log: new EventLog(), capabilities: new CapabilitySet() });
  await assert.rejects(store.put('alice', 'name', 'Alice'), /Write refused/);
});

test('a capability-gated GraphStore accepts a write covered by a verified grant', async () => {
  const issuer = await generateIdentity();
  const writer = await generateIdentity();
  const capability = await issueCapability(issuer, { resource: 'sphere-1:alice.name', actions: ['write'], subject: writer.id });
  assert.equal((await verifyCapability(capability, issuer)).valid, true);
  const capabilities = new CapabilitySet();
  capabilities.grant(capability);

  const store = new GraphStore({ identity: writer, domain: 'sphere-1', log: new EventLog(), capabilities });
  await store.put('alice', 'name', 'Alice');
  assert.equal(await store.get('alice', 'name'), 'Alice');

  // A DIFFERENT field on the same node was never granted — still refused.
  await assert.rejects(store.put('alice', 'age', 30), /Write refused/);
});
