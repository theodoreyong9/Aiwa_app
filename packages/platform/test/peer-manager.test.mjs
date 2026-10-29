import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PeerManager } from '../src/peer-manager.js';
import { CompositeTransport } from '../src/composite-transport.js';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function waitUntil(predicate, { timeoutMs = 2000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) { if (await predicate()) return; await sleep(5); }
  throw new Error('waitUntil: the condition never became true');
}

// A transport whose peers the test decides, and which says when they change.
function fakeTransport(peers = []) {
  const joins = new Set();
  const leaves = new Set();
  return {
    list: [...peers],
    peers() { return [...this.list]; },
    closed: [],
    closePeer(id) { this.closed.push(id); this.remove(id); },
    linked() { return [...this.list]; },
    onPeerJoin(h) { joins.add(h); return () => joins.delete(h); },
    onPeerLeave(h) { leaves.add(h); return () => leaves.delete(h); },
    add(id) { this.list.push(id); for (const h of joins) h(id); },
    remove(id) { this.list = this.list.filter((p) => p !== id); for (const h of leaves) h(id); },
  };
}

function fakeLobby({ enabled = true, connected = true, selfId = 'zzz' } = {}) {
  return { enabled, connected, selfId, calls: [], async connect() { this.connected = true; this.calls.push('connect'); }, async disconnect() { this.connected = false; this.calls.push('disconnect'); } };
}

function setup({ lobbyPeers = [], directPeers = [], introduce = async () => { throw new Error('nobody to offer'); }, ...options } = {}) {
  const lobbyT = fakeTransport(lobbyPeers);
  const direct = fakeTransport(directPeers);
  const lobby = Object.assign(fakeLobby(options.lobby), { peers: () => lobbyT.peers() });
  const all = { peers: () => [...new Set([...direct.peers(), ...lobbyT.peers()])], onPeerJoin: (h) => { const a = direct.onPeerJoin(h); const b = lobbyT.onPeerJoin(h); return () => { a(); b(); }; }, onPeerLeave: (h) => { const a = direct.onPeerLeave(h); const b = lobbyT.onPeerLeave(h); return () => { a(); b(); }; } };
  const asked = [];
  const introducer = { async requestIntroduction(mediator, opts) { asked.push({ mediator, exclude: opts.exclude }); return introduce(mediator, opts); } };
  const manager = new PeerManager({ transport: all, direct, lobby, introducer, target: 3, low: 2, roomMin: 1, leaveJitterMs: 0, retryMs: 50, answerMs: 200, ...options.manager });
  return { manager, lobby, lobbyT, direct, asked };
}

test('with enough direct peers the wallet leaves the room, and goes back when it falls too low', async () => {
  const { manager, lobby, direct } = setup({ lobbyPeers: ['l1'], directPeers: ['d1', 'd2'] });
  manager.start();
  await sleep(20);
  assert.deepEqual(lobby.calls, [], 'two direct peers are not enough (target 3)');
  direct.add('d3');
  await waitUntil(() => lobby.calls.includes('disconnect'));
  assert.equal(lobby.connected, false);
  direct.remove('d3'); direct.remove('d2');                  // one direct peer left: below 2
  await waitUntil(() => lobby.calls.includes('connect'));
  assert.equal(lobby.connected, true);
  manager.stop();
});

test('a machine that is always on stays in the room', async () => {
  const { manager, lobby } = setup({ directPeers: ['d1', 'd2', 'd3', 'd4'], manager: { stay: true } });
  manager.start();
  await sleep(30);
  assert.deepEqual(lobby.calls, []);
  manager.stop();
});

test('a person who turned the network off is not pulled back into the room, and nobody is asked for introductions', async () => {
  const { manager, lobby, asked } = setup({ lobby: { enabled: false, connected: false }, lobbyPeers: [], directPeers: ['d1'] });
  manager.enabled = false;
  manager.start();
  await sleep(30);
  assert.deepEqual(lobby.calls, []);
  assert.equal(asked.length, 0);
  manager.stop();
});

test('below the target it asks a peer to introduce it to its own, skips the one that has nobody, and keeps what it already has out of the offer', async () => {
  const { manager, direct, asked } = setup({
    lobbyPeers: ['l1', 'l2'], directPeers: [],
    introduce: async (mediator) => { if (mediator === 'l1') throw new Error('nobody to offer'); await sleep(10); },
  });
  manager.start();
  await waitUntil(() => asked.length >= 2);
  assert.deepEqual(asked.slice(0, 2).map((a) => a.mediator), ['l1', 'l2'], 'the first had nobody: the next is asked at once');
  assert.deepEqual(asked[0].exclude, [], 'nothing to skip yet');
  direct.add('l2');                                            // an introduction made a direct link
  await waitUntil(() => asked.some((a) => a.exclude.includes('l2')));
  manager.stop();
});

test('nobody to offer: it waits before asking again, by itself, and asks nobody when it has no peer', async () => {
  const none = setup({ lobbyPeers: [], directPeers: [] });
  none.manager.start();
  await sleep(30);
  assert.equal(none.asked.length, 0, 'no peer, nobody to ask');
  none.manager.stop();

  const { manager, asked } = setup({ lobbyPeers: ['l1'], directPeers: [] });   // the default introduce() refuses
  manager.start();
  await waitUntil(() => asked.length === 1);
  await sleep(20);
  assert.equal(asked.length, 1, 'it does not hammer the peer');
  await waitUntil(() => asked.length === 2, { timeoutMs: 1000 });             // retryMs 50: it comes back by itself
  manager.stop();
});

test('a retry whose timer fires before the clock says its time is set again, not forgotten', async () => {
  let t = 1000;                                                // a clock the test moves: the timer (50 ms) fires while it still stands at the same time
  const { manager, asked } = setup({ lobbyPeers: ['l1'], directPeers: [], manager: { now: () => t } });
  manager.start();
  await waitUntil(() => asked.length === 1);
  await sleep(120);                                            // the first timer fired meanwhile, too early
  assert.equal(asked.length, 1);
  t += 50;
  await waitUntil(() => asked.length === 2, { timeoutMs: 1000 });
  manager.stop();
});

test('an introduction that never answers is given up on', async () => {
  const { manager, asked } = setup({ lobbyPeers: ['l1'], introduce: () => new Promise(() => {}) });
  manager.start();
  await waitUntil(() => asked.length === 1);
  await waitUntil(() => asked.length === 2, { timeoutMs: 1500 });             // answerMs 200, then retryMs 50
  manager.stop();
});

test('the composite hands the signaling of a direct connection to the transport that makes them', async () => {
  const calls = [];
  const direct = { ...fakeTransport(), async createOfferFor(p) { calls.push(['offer', p]); return 'o'; }, async acceptOffer(b, o) { calls.push(['accept', b, o.peerId]); return 'a'; }, async completeConnection(p, b) { calls.push(['complete', p, b]); }, closePeer(p) { calls.push(['close', p]); } };
  const lobby = fakeTransport();
  const composite = new CompositeTransport([lobby, direct]);
  assert.equal(await composite.createOfferFor('x'), 'o');
  assert.equal(await composite.acceptOffer('blob', { peerId: 'y' }), 'a');
  await composite.completeConnection('x', 'ans');
  composite.closePeer('x');
  assert.deepEqual(calls, [['offer', 'x'], ['accept', 'blob', 'y'], ['complete', 'x', 'ans'], ['close', 'x']]);
  assert.throws(() => new CompositeTransport([lobby]).createOfferFor('x'), /direct connections/);
});

test('a thin room is not left: someone has to stay in it for a newcomer to find', async () => {
  const { manager, lobby, lobbyT } = setup({ lobbyPeers: ['l1', 'l2'], directPeers: ['d1', 'd2', 'd3'], manager: { roomMin: 3 } });
  manager.start();
  await sleep(40);
  assert.deepEqual(lobby.calls, [], 'two others in the room: it stays');
  lobbyT.add('l3');                                            // a third: the room can spare this wallet
  await waitUntil(() => lobby.calls.includes('disconnect'));
  manager.stop();
});

test('a network change drops every direct link and goes back to the room at once', async () => {
  const { manager, lobby, direct } = setup({ lobbyPeers: ['l1'], directPeers: ['d1', 'd2', 'd3'], lobby: { connected: false } });
  manager.start();
  await sleep(20);
  assert.deepEqual(lobby.calls, [], 'three direct links: no need for the room');
  await manager.networkChanged();
  assert.deepEqual(direct.closed.sort(), ['d1', 'd2', 'd3']);
  assert.equal(lobby.connected, true, 'it looks for the others again, from where it is now');
  manager.stop();
});

test('a network change in the room leaves it and joins it again', async () => {
  const { manager, lobby } = setup({ lobbyPeers: ['l1'], directPeers: [], lobby: { connected: true } });
  manager.start();
  await sleep(10);
  await manager.networkChanged();
  assert.deepEqual(lobby.calls, ['disconnect', 'connect']);
  manager.stop();
});

test('a person who turned the network off is left alone by a network change', async () => {
  const { manager, lobby, direct } = setup({ lobby: { enabled: false, connected: false }, directPeers: ['d1'] });
  manager.enabled = false;
  manager.start();
  await manager.networkChanged();
  assert.deepEqual(direct.closed, []);
  assert.deepEqual(lobby.calls, []);
  manager.stop();
});

test('the wallet with the lowest id among those in the room never leaves it, so the room is never emptied', async () => {
  const anchor = setup({ lobbyPeers: ['l1', 'l2'], directPeers: ['d1', 'd2', 'd3'], lobby: { selfId: 'a' } });
  anchor.manager.start();
  await sleep(40);
  assert.deepEqual(anchor.lobby.calls, [], 'the lowest id: it stays whatever it has');
  anchor.manager.stop();
  const other = setup({ lobbyPeers: ['l1', 'l2'], directPeers: ['d1', 'd2', 'd3'], lobby: { selfId: 'm' } });
  other.manager.start();
  await waitUntil(() => other.lobby.calls.includes('disconnect'));    // 'l1' is lower: this one can go
  other.manager.stop();
});
