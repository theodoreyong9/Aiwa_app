import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity, createEvent, EventLog } from 'aiwa-core';
import { TrysteroTransport } from '../src/trystero-transport.js';
import { CompositeTransport } from '../src/composite-transport.js';
import { LoopbackTransport } from '../src/transport.js';
import { Replicator } from '../src/replicator.js';

// A stand-in for Trystero: rooms of one hub, found by (appId, roomId), with the same surface the transport uses (joinRoom, makeAction,
// onPeerJoin / onPeerLeave as properties, action.send with a target, action.onMessage with the sender's id, leave).
function fakeHub() {
  const rooms = new Map();
  let count = 0;
  const joinRoom = (config, roomId) => {
    const key = `${config.appId}/${roomId}`;
    const members = rooms.get(key) ?? new Map();
    rooms.set(key, members);
    const id = `peer${++count}`;
    const actions = new Map();
    const room = {
      id,
      onPeerJoin: null,
      onPeerLeave: null,
      makeAction(name) {
        const action = {
          onMessage: null,
          async send(data, { target = null } = {}) {
            const targets = target === null ? [...members.keys()].filter((p) => p !== id) : [target].flat();
            for (const t of targets) {
              const other = members.get(t);
              const received = other?.actions.get(name);
              if (received?.onMessage) setTimeout(() => received.onMessage(data instanceof Uint8Array ? data.slice() : data, { peerId: id }), 0);
            }
          },
        };
        actions.set(name, action);
        return action;
      },
      async leave() {
        members.delete(id);
        for (const other of members.values()) other.room.onPeerLeave?.(id);
      },
    };
    // Found a moment later, as through a relay: the caller has set its handlers by then.
    setTimeout(() => {
      for (const [otherId, other] of members) {
        other.room.onPeerJoin?.(id);
        room.onPeerJoin?.(otherId);
      }
      members.set(id, { room, actions });
    }, 0);
    return room;
  };
  return joinRoom;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function waitUntil(predicate, { timeoutMs = 2000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) { if (await predicate()) return; await sleep(5); }
  throw new Error('waitUntil: the condition never became true');
}

const pair = (joinRoom, roomB = 'lobby') => ({
  a: new TrysteroTransport({ joinRoom, appId: 'aiwa-test', roomId: 'lobby' }),
  b: new TrysteroTransport({ joinRoom, appId: 'aiwa-test', roomId: roomB }),
});

test('two wallets in the same room find each other by themselves; another room is not theirs', async () => {
  const joinRoom = fakeHub();
  const { a, b } = pair(joinRoom);
  const stranger = pair(joinRoom, 'elsewhere').b;
  const joined = [];
  a.onPeerJoin((peer) => joined.push(peer));
  await a.connect(); await b.connect(); await stranger.connect();
  await waitUntil(() => a.peers().length === 1 && b.peers().length === 1);
  assert.deepEqual(joined, a.peers());
  assert.equal(stranger.peers().length, 0);
  await Promise.all([a.disconnect(), b.disconnect(), stranger.disconnect()]);
});

test('bytes go to one peer or to all', async () => {
  const joinRoom = fakeHub();
  const a = new TrysteroTransport({ joinRoom, appId: 'x', roomId: 'r' });
  const b = new TrysteroTransport({ joinRoom, appId: 'x', roomId: 'r' });
  const c = new TrysteroTransport({ joinRoom, appId: 'x', roomId: 'r' });
  const seen = { b: [], c: [] };
  b.onMessage((peer, bytes) => seen.b.push([peer, [...bytes]]));
  c.onMessage((peer, bytes) => seen.c.push([peer, [...bytes]]));
  await Promise.all([a.connect(), b.connect(), c.connect()]);
  await waitUntil(() => a.peers().length === 2);
  await a.send(a.peers()[0], new Uint8Array([1, 2, 3]));
  await a.broadcast(new Uint8Array([9]));
  await waitUntil(() => seen.b.length + seen.c.length === 3);
  const all = [...seen.b, ...seen.c];
  assert.equal(all.filter(([, bytes]) => bytes.length === 1 && bytes[0] === 9).length, 2, 'the broadcast reached both');
  assert.equal(all.filter(([, bytes]) => bytes.length === 3).length, 1, 'the send reached one');
  await Promise.all([a.disconnect(), b.disconnect(), c.disconnect()]);
});

test('leaving tells the others, and tells the handlers of the one who left', async () => {
  const joinRoom = fakeHub();
  const { a, b } = pair(joinRoom);
  const left = { a: [], b: [] };
  a.onPeerLeave((peer) => left.a.push(peer));
  b.onPeerLeave((peer) => left.b.push(peer));
  await a.connect(); await b.connect();
  await waitUntil(() => a.peers().length === 1);
  await b.disconnect();
  await waitUntil(() => left.a.length === 1);
  assert.equal(left.b.length, 1);
  assert.deepEqual(a.peers(), []);
  assert.equal(b.connected, false);
  await b.connect();                                         // it can come back
  await waitUntil(() => a.peers().length === 1);
  await Promise.all([a.disconnect(), b.disconnect()]);
});

test('a message that is not bytes is ignored, not thrown on', async () => {
  const joinRoom = fakeHub();
  const { a, b } = pair(joinRoom);
  let got = 0;
  b.onMessage(() => { got++; });
  await a.connect(); await b.connect();
  await waitUntil(() => a.peers().length === 1);
  b._action.onMessage({ not: 'bytes' }, { peerId: 'x' });
  assert.equal(got, 0);
  await Promise.all([a.disconnect(), b.disconnect()]);
});

test('two logs replicate through the room: the Replicator never knew which transport it had', async () => {
  const joinRoom = fakeHub();
  const author = await generateIdentity();
  const events = [];
  let parents = [];
  for (let i = 0; i < 5; i++) {
    const event = await createEvent(author, { domain: 'aiwa', parents, type: 'note', payload: { i } });
    events.push(event);
    parents = [event.id];
  }
  const logA = new EventLog();
  await logA.appendMany(events);
  const logB = new EventLog();
  const a = new Replicator({ transport: new TrysteroTransport({ joinRoom, appId: 'aiwa-test', roomId: 'lobby' }), log: logA, domain: 'aiwa' });
  const b = new Replicator({ transport: new TrysteroTransport({ joinRoom, appId: 'aiwa-test', roomId: 'lobby' }), log: logB, domain: 'aiwa' });
  await a.start(); await b.start();
  await waitUntil(async () => { for (const e of events) if (!(await logB.has(e.id))) return false; return true; }, { timeoutMs: 5000 });
  await a.stop(); await b.stop();
});

test('a composite is one transport: peers are all of theirs, a message leaves by the transport its peer belongs to', async () => {
  const joinRoom = fakeHub();
  const lobby = new TrysteroTransport({ joinRoom, appId: 'x', roomId: 'r' });
  const other = new TrysteroTransport({ joinRoom, appId: 'x', roomId: 'r' });
  const loop = new LoopbackTransport('loop-a');
  const loopPeer = new LoopbackTransport('loop-b');
  const composite = new CompositeTransport([lobby, loop]);
  const messages = [];
  const joined = [];
  composite.onMessage((peer, bytes) => messages.push([peer, bytes.length]));
  composite.onPeerJoin((peer) => joined.push(peer));
  await composite.connect(); await other.connect(); await loopPeer.connect();
  await waitUntil(() => composite.peers().length === 2);
  assert.deepEqual([...composite.peers()].sort(), [...lobby.peers(), 'loop-b'].sort());
  assert.equal(joined.length, 2);
  const received = [];
  other.onMessage((peer, bytes) => received.push(bytes.length));
  loopPeer.onMessage((peer, bytes) => received.push(bytes.length * 10));
  await composite.send(lobby.peers()[0], new Uint8Array(2));
  await composite.send('loop-b', new Uint8Array(3));
  await composite.send('nobody', new Uint8Array(1));          // no owner: nothing, no throw
  await waitUntil(() => received.length === 2);
  assert.deepEqual(received.sort((x, y) => x - y), [2, 30]);
  await loopPeer.send('loop-a', new Uint8Array(4));
  await waitUntil(() => messages.length === 1);
  await composite.disconnect(); await other.disconnect(); await loopPeer.disconnect();
});
