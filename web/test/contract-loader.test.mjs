import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { generateIdentity, EventLog, publishContractSpec, computeContractHash } from 'aiwa-core';
import { prepareSource, WORKER_SOURCE, loadVerified } from '../src/contract-loader.js';
import { profileFile, readProfileFile, repoOf } from '../src/contracts-sync.js';

const SOURCE = `import { defineContract, signedAction, verifySignedAction } from 'aiwa-lib';
export const definition = defineContract({
  initialState: () => ({ votes: {} }),
  handlers: { async vote(state, { payload }) { if (!(await verifySignedAction(payload))) return state; return { votes: { ...state.votes, [payload.from]: payload.choice } }; } },
});`;

// a Worker stand-in: the real worker source runs in a vm with a fake `self`
function fakeWorker(verifyAnswer = true) {
  const w = { onmessage: null, terminated: false };
  const self = { onmessage: null, postMessage: (data) => queueMicrotask(() => w.onmessage?.({ data })) };
  self.self = self;
  vm.runInNewContext(WORKER_SOURCE, vm.createContext(self));
  w.postMessage = (data) => queueMicrotask(() => self.onmessage?.({ data }));
  w.terminate = () => { w.terminated = true; };
  return w;
}

test('the source loses its import and its export, nothing else', () => {
  const out = prepareSource(SOURCE);
  assert.ok(!/aiwa-lib/.test(out) && !/^\s*export\b/m.test(out));
  assert.ok(out.includes('const definition = defineContract('));
});

test('a verified contract is loaded in the worker and gives its state; signatures are checked outside', async () => {
  const hash = await computeContractHash(SOURCE);
  const asked = [];
  const contract = await loadVerified({ sourceCode: SOURCE, sourceHash: hash }, hash, { makeWorker: () => fakeWorker(), verifySignedAction: async (p) => { asked.push(p); return p.from !== 'forger'; } });
  const state = await contract.state([
    { id: '1', parents: [], payload: { type: 'vote', from: 'a', choice: 'oui' } },
    { id: '2', parents: [], payload: { type: 'vote', from: 'forger', choice: 'non' } },
    { id: '3', parents: [], payload: { type: 'other' } },
  ]);
  assert.deepEqual(JSON.parse(JSON.stringify(state)), { votes: { a: 'oui' } });
  assert.equal(asked.length, 2);
});

test('SECURITY: a hash that is not the announced one, or not the accepted one, loads nothing', async () => {
  const hash = await computeContractHash(SOURCE);
  await assert.rejects(loadVerified({ sourceCode: SOURCE + '//', sourceHash: hash }, hash, { makeWorker: () => assert.fail('no worker') }), /empreinte annoncée/);
  await assert.rejects(loadVerified({ sourceCode: SOURCE, sourceHash: hash }, 'other', { makeWorker: () => assert.fail('no worker') }), /acceptée/);
});

test('the worker has no network and a file without definition is refused', async () => {
  const bad = 'const nothing = 1;';
  const hash = await computeContractHash(bad);
  await assert.rejects(loadVerified({ sourceCode: bad, sourceHash: hash }, hash, { makeWorker: () => fakeWorker() }), /definition/);
  const spy = `export const definition = defineContract({ initialState: () => ({ net: typeof fetch + typeof XMLHttpRequest }), handlers: {} });`;
  const h2 = await computeContractHash(spy);
  const c = await loadVerified({ sourceCode: spy, sourceHash: h2 }, h2, { makeWorker: () => fakeWorker() });
  assert.deepEqual(JSON.parse(JSON.stringify(await c.state([]))), { net: 'undefinedundefined' });
});

test('a profile file: its own contracts go out, forged or foreign ones do not come back', async () => {
  const me = await generateIdentity();
  const other = await generateIdentity();
  const log = new EventLog();
  const a = await publishContractSpec(me, log, 'd', { name: 'Vote', version: '1', sourceCode: 'x', description: '' });
  const b = await publishContractSpec(other, log, 'd', { name: 'Autre', version: '1', sourceCode: 'y', description: '' });
  const events = [await log.get(a.specEventId), await log.get(b.specEventId)];
  const file = profileFile(events, me.id);
  assert.deepEqual(file.events.map((e) => e.id), [a.specEventId]);
  assert.equal((await readProfileFile(file)).length, 1);
  const forged = { ...file, events: [{ ...file.events[0], payload: { ...file.events[0].payload, sourceCode: 'evil' } }] };
  assert.equal((await readProfileFile(forged)).length, 0);
  const foreign = { ...file, creator: other.id };
  assert.equal((await readProfileFile(foreign)).length, 0);
});

test('a repository from what was typed', () => {
  assert.equal(repoOf('https://github.com/me/Aiwa_app'), 'me/Aiwa_app');
  assert.equal(repoOf('me/app'), 'me/app');
  assert.equal(repoOf('aa11bb'), null);
});
