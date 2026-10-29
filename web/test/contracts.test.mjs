import test from 'node:test';
import assert from 'node:assert/strict';
import { specsOf, searchSpecs, checkForm, EXAMPLE } from '../src/contracts-core.js';

const spec = (id, author, name, createdAt) => ({ id, author, type: 'contract-spec', createdAt, payload: { name, version: '1', description: '', sourceHash: 'h', sourceCode: 'x' } });
const events = [spec('aa11', 'c1', 'Vote', 1), { id: 'zz', author: 'c1', type: 'burn', payload: {} }, spec('bb22', 'c2', 'Jeton', 3), { id: 'no', author: 'c2', type: 'contract-spec', payload: { name: 'sans code' } }];

test('only the contracts that carry their code, the newest first', () => {
  assert.deepEqual(specsOf(events).map((s) => s.id), ['bb22', 'aa11']);
});

test('search by contract id, by creator id, by name', () => {
  const specs = specsOf(events);
  assert.deepEqual(searchSpecs(specs, 'aa1').map((s) => s.id), ['aa11']);
  assert.deepEqual(searchSpecs(specs, 'C2').map((s) => s.id), ['bb22']);
  assert.deepEqual(searchSpecs(specs, 'vot').map((s) => s.id), ['aa11']);
  assert.equal(searchSpecs(specs, '  ').length, 2);
  assert.equal(searchSpecs(specs, 'nothing').length, 0);
});

test('the form is checked before anything is published', () => {
  const ok = { name: 'Vote', version: '1', description: '', sourceCode: EXAMPLE };
  assert.equal(checkForm(ok), null);
  assert.match(checkForm({ ...ok, name: ' ' }), /nom/);
  assert.match(checkForm({ ...ok, sourceCode: '' }), /code/);
  assert.match(checkForm({ ...ok, sourceCode: 'x'.repeat(50_001) }), /code/);
});
