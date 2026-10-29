import { test } from 'node:test';
import assert from 'node:assert/strict';

// The app side of the door (src/door.js) against a Store that keeps strings: what an app in its frame sees.
const listeners = [];
const reserve = new Map();
const parent = {
  postMessage(m) {
    const { id, cmd, args } = m;
    queueMicrotask(() => {
      let result;
      if (cmd === 'storage.get') result = { value: reserve.get(args.key) ?? null };
      else if (cmd === 'storage.set') { reserve.set(args.key, args.value); result = {}; }
      else if (cmd === 'storage.remove') { reserve.delete(args.key); result = {}; }
      else if (cmd === 'storage.keys') result = { keys: [...reserve.keys()] };
      for (const f of listeners) f({ source: parent, data: { aiwa: 1, id, result } });
    });
  },
};
globalThis.window = { parent, addEventListener: (type, f) => { if (type === 'message') listeners.push(f); } };

const { createDoorBackend, loadOrCreateIdentity, doorStorage, doorAvailable } = await import('../src/door.js');
const { EventLog, createEvent } = await import('aiwa-core');

test('an app in the Store keeps its identity between two openings', async () => {
  assert.equal(doorAvailable(), true);
  const first = await loadOrCreateIdentity();
  const second = await loadOrCreateIdentity();
  assert.equal(second.id, first.id, 'the same player the second time');
  assert.match(reserve.get('identity'), /^[0-9a-f]{64}$/);
});

test('a log on the door backend survives the frame: a new backend reads the events back', async () => {
  const me = await loadOrCreateIdentity();
  const log = new EventLog(createDoorBackend());
  const event = await createEvent(me, { domain: 'door-test', type: 'note', payload: { n: 1 }, parents: [] });
  await log.append(event);
  assert.ok([...reserve.keys()].some((k) => k === `ev:${event.id}`), 'the event is in the Store\'s reserve');
  const reopened = new EventLog(createDoorBackend());                  // a new opening: nothing in memory, only the reserve
  assert.equal(await reopened.backend.hasEvent(event.id), true);
  assert.equal((await reopened.backend.getEvent(event.id)).id, event.id);
  assert.deepEqual(await reopened.backend.allIds(), [event.id]);
});

test('the reserve is plain strings under short keys', async () => {
  await doorStorage.set('score', 12);
  assert.equal(await doorStorage.get('score'), '12');
  await doorStorage.remove('score');
  assert.equal(await doorStorage.get('score'), null);
});
