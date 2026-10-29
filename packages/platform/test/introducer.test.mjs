import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Introducer } from '../src/introducer.js';

// A minimal, deliberately fake WebrtcTransport-shaped object — real
// signaling semantics (createOfferFor/acceptOffer/completeConnection)
// are already covered by webrtc-transport.test.mjs against a fake
// RTCPeerConnection; this exercises Introducer's OWN logic (who
// gets asked, who relays what to whom, in what order) using a shared,
// in-memory registry so send() actually reaches the addressed fake
// transport's own registered handlers — exactly the property real
// message relaying depends on.
function createFakeTransport(selfId, registry, { peers = [] } = {}) {
  const handlers = new Set();
  const calls = { offers: [], accepts: [], completes: [] };
  const transport = {
    selfId,
    peers: () => peers,
    async send(to, bytes) {
      const target = registry.get(to);
      if (target) for (const h of [...target._handlers]) h(selfId, bytes);
    },
    onMessage(h) { handlers.add(h); return () => handlers.delete(h); },
    async createOfferFor(peerId) { calls.offers.push(peerId); return `offer:${selfId}->${peerId}`; },
    async acceptOffer(blob, { peerId }) { calls.accepts.push({ blob, peerId }); return `answer:${selfId}->${peerId}`; },
    async completeConnection(peerId, blob) { calls.completes.push({ peerId, blob }); },
    _handlers: handlers,
    calls,
  };
  registry.set(selfId, transport);
  return transport;
}

function makeThreeParty({ aPeers = ['M'], mPeers = ['A', 'P'], pPeers = ['M'] } = {}) {
  const registry = new Map();
  const a = createFakeTransport('A', registry, { peers: aPeers });
  const m = createFakeTransport('M', registry, { peers: mPeers });
  const p = createFakeTransport('P', registry, { peers: pPeers });
  const introA = new Introducer({ transport: a }); introA.start();
  const introM = new Introducer({ transport: m }); introM.start();
  const introP = new Introducer({ transport: p }); introP.start();
  return { a, m, p, introA, introM, introP };
}

test('requestIntroduction: A gets connected to mediator M\'s other peer P, purely via relay', async () => {
  const { a, m, p, introA } = makeThreeParty();

  const newPeerId = await introA.requestIntroduction('M');
  assert.equal(newPeerId, 'P');

  // A generated an offer FOR P, and completed with P's answer.
  assert.deepEqual(a.calls.offers, ['P']);
  assert.deepEqual(a.calls.completes, [{ peerId: 'P', blob: 'answer:P->A' }]);
  // P accepted A's offer, addressed to A.
  assert.deepEqual(p.calls.accepts, [{ blob: 'offer:A->P', peerId: 'A' }]);
  // The mediator M never generates or accepts any signal itself — pure relay.
  assert.deepEqual(m.calls.offers, []);
  assert.deepEqual(m.calls.accepts, []);
  assert.deepEqual(m.calls.completes, []);
});

test('requestIntroduction rejects when the mediator has no other peer to offer', async () => {
  const { introA } = makeThreeParty({ mPeers: ['A'] }); // M knows only A
  await assert.rejects(introA.requestIntroduction('M'), /no other real peer/);
});

test('requestIntroduction never proposes a peer explicitly excluded by the caller', async () => {
  const registry = new Map();
  const a = createFakeTransport('A', registry, { peers: ['M'] });
  const m = createFakeTransport('M', registry, { peers: ['A', 'P', 'Q'] });
  const p = createFakeTransport('P', registry, { peers: ['M'] });
  const q = createFakeTransport('Q', registry, { peers: ['M'] });
  const introA = new Introducer({ transport: a }); introA.start();
  new Introducer({ transport: m }).start();
  new Introducer({ transport: p }).start();
  new Introducer({ transport: q }).start();

  const newPeerId = await introA.requestIntroduction('M', { exclude: ['P'] });
  assert.equal(newPeerId, 'Q');
});

test('requestIntroduction rejects if the introduced connection attempt itself fails (e.g. already connected)', async () => {
  const registry = new Map();
  const a = createFakeTransport('A', registry, { peers: ['M', 'P'] }); // An is ALREADY connected to P
  a.createOfferFor = async () => { throw new Error('Already connected (or connecting) to \'P\'.'); };
  const m = createFakeTransport('M', registry, { peers: ['A', 'P'] });
  const p = createFakeTransport('P', registry, { peers: ['M'] });
  const introA = new Introducer({ transport: a }); introA.start();
  new Introducer({ transport: m }).start();
  new Introducer({ transport: p }).start();

  await assert.rejects(introA.requestIntroduction('M'), /Already connected/);
});

test('two independent introductions (different sessions) do not interfere with each other', async () => {
  const registry = new Map();
  const a = createFakeTransport('A', registry, { peers: ['M'] });
  const m = createFakeTransport('M', registry, { peers: ['A', 'B', 'P', 'Q'] });
  const b = createFakeTransport('B', registry, { peers: ['M'] });
  const p = createFakeTransport('P', registry, { peers: ['M'] });
  const q = createFakeTransport('Q', registry, { peers: ['M'] });
  const introA = new Introducer({ transport: a }); introA.start();
  const introB = new Introducer({ transport: b }); introB.start();
  new Introducer({ transport: m }).start();
  new Introducer({ transport: p }).start();
  new Introducer({ transport: q }).start();

  const [aResult, bResult] = await Promise.all([
    introA.requestIntroduction('M', { exclude: ['B', 'Q'] }),
    introB.requestIntroduction('M', { exclude: ['A', 'P'] }),
  ]);
  assert.equal(aResult, 'P');
  assert.equal(bResult, 'Q');
});
