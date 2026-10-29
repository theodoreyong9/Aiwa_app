import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity, EventLog, createMemoryBackend } from 'aiwa-core';
import { defineContract, Contract, signedAction, verifySignedAction, collectAncestors, encodeOfflineBundle, decodeOfflineBundle } from '../src/index.js';

// What docs/CONTRACTS.md says, as code that runs: the vote of docs/aiwa-app-example.html, on two devices that exchange their events.
const definition = defineContract({
  initialState: () => ({ votes: {} }),
  handlers: {
    vote: async (state, event) => {
      const action = event.payload;
      if (!(await verifySignedAction(action))) return state;
      if (action.choice !== 'yes' && action.choice !== 'no') return state;
      if (action.from in state.votes) return state;
      return { votes: { ...state.votes, [action.from]: action.choice } };
    },
  },
});

const replica = async (identity) => new Contract({ identity, log: new EventLog(createMemoryBackend()), domain: 'show-of-hands', definition });
const vote = async (contract, choice) => contract.dispatch('vote', await signedAction(contract.identity, { from: contract.identity.id, choice }));
const tally = async (contract) => Object.values((await contract.state()).votes).sort().join(',');

// the events a device holds, as the text that goes in a QR code, a paste, or a data channel; and the other end taking them in
const share = async (from) => encodeOfflineBundle({ events: await collectAncestors(from.log, await from.log.head()) });
const take = async (into, text) => into.log.appendMany(decodeOfflineBundle(text).events);

test('two devices that exchange their events fold to the same state', async () => {
  const [a, b] = [await replica(await generateIdentity()), await replica(await generateIdentity())];
  await vote(a, 'yes');
  await vote(b, 'no');
  assert.equal(await tally(a), 'yes', 'before the exchange, each device only knows its own vote');
  assert.equal(await tally(b), 'no');
  await take(b, await share(a));
  await take(a, await share(b));
  assert.equal(await tally(a), 'no,yes');
  assert.equal(await tally(b), 'no,yes');
});

test('one identity voting twice, on two devices, counts once, and the same vote wins on both', async () => {
  const me = await generateIdentity();
  const [a, b] = [await replica(me), await replica(me)];
  await vote(a, 'yes');
  await vote(b, 'no');
  await take(b, await share(a));
  await take(a, await share(b));
  const [onA, onB] = [await tally(a), await tally(b)];
  assert.equal(onA, onB, 'the same winner for every reader');
  assert.ok(onA === 'yes' || onA === 'no', 'one vote, not two');
});

test('an action that claims to be someone else is ignored', async () => {
  const [honest, thief] = [await generateIdentity(), await generateIdentity()];
  const a = await replica(honest);
  const forged = await signedAction(thief, { from: honest.id, choice: 'no' });         // signed by the thief, claiming to be `honest`
  assert.equal(await verifySignedAction(forged), false);
  await a.dispatch('vote', forged);
  assert.equal(await tally(a), '', 'the event is in the log (its envelope is fine) but the rules do not count it');
  await vote(a, 'yes');
  assert.equal(await tally(a), 'yes');
});

test('identities are free in a contract: many identities, many votes', async () => {
  const a = await replica(await generateIdentity());
  for (let i = 0; i < 3; i++) await vote(new Contract({ identity: await generateIdentity(), log: a.log, domain: 'show-of-hands', definition }), 'yes');
  assert.equal(await tally(a), 'yes,yes,yes');
});
