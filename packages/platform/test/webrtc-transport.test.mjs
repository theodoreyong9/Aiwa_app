import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WebrtcTransport } from '../src/webrtc-transport.js';
import { decodeSignal, encodeSignal } from '../src/signaling-codec.js';

// A minimal, deliberately fake RTCPeerConnection/RTCDataChannel — real
// ICE negotiation and SDP semantics are NOT simulated (see
// webrtc-transport.js's own "HONEST LIMIT"). What this exercises is
// WebrtcTransport's own bookkeeping: which peers are pending vs.
// open, when join/leave/message handlers fire, and that malformed
// signaling is rejected — all logic this class owns, independent
// of whatever a browser's WebRTC stack does underneath it.

class FakeChannel {
  constructor(label) {
    this.label = label;
    this.readyState = 'connecting';
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.sent = [];
  }
  send(bytes) { this.sent.push(bytes); }
  close() {
    if (this.readyState === 'closed') return;
    this.readyState = 'closed';
    this.onclose?.();
  }
  open() {
    this.readyState = 'open';
    this.onopen?.();
  }
  receive(bytes) {
    this.onmessage?.({ data: bytes });
  }
}

class FakePeerConnection {
  constructor() {
    this.iceGatheringState = 'complete'; // skips ICE gathering entirely in tests
    this.localDescription = null;
    this.remoteDescription = null;
    this.ondatachannel = null;
    this.channel = null;
    this.closed = false;
  }
  createDataChannel(label) {
    this.channel = new FakeChannel(label);
    return this.channel;
  }
  async createOffer() { return { type: 'offer', sdp: 'fake-offer-sdp' }; }
  async createAnswer() { return { type: 'answer', sdp: 'fake-answer-sdp' }; }
  async setLocalDescription(desc) { this.localDescription = desc; }
  async setRemoteDescription(desc) { this.remoteDescription = desc; }
  addEventListener() {} // never invoked: iceGatheringState is already 'complete'
  removeEventListener() {}
  close() { this.closed = true; }
}

function makeTransport(selfId = 'self') {
  const pcs = [];
  const transport = new WebrtcTransport({
    selfId,
    createPeerConnection: () => { const pc = new FakePeerConnection(); pcs.push(pc); return pc; },
  });
  return { transport, pcs };
}

test('createOfferFor returns a decodable offer blob and registers the peer as pending (not yet open)', async () => {
  const { transport } = makeTransport();
  const blob = await transport.createOfferFor('bob');
  const decoded = decodeSignal(blob);
  assert.equal(decoded.kind, 'offer');
  assert.equal(decoded.originId, 'self');
  assert.deepEqual(transport.peers(), [], 'not open yet — the channel has not fired onopen');
});

test('createOfferFor rejects a duplicate peer already connected or connecting', async () => {
  const { transport } = makeTransport();
  await transport.createOfferFor('bob');
  await assert.rejects(transport.createOfferFor('bob'), /Already connected/);
});

test('the peer appears in peers() and fires onPeerJoin exactly when its channel opens', async () => {
  const { transport, pcs } = makeTransport();
  const joined = [];
  transport.onPeerJoin((id) => joined.push(id));
  await transport.createOfferFor('bob');
  assert.deepEqual(transport.peers(), []);
  pcs[0].channel.open();
  assert.deepEqual(transport.peers(), ['bob']);
  assert.deepEqual(joined, ['bob']);
});

test('send() is a silent no-op for a peer whose channel is not open yet — never throws', async () => {
  const { transport } = makeTransport();
  await transport.createOfferFor('bob');
  await assert.doesNotReject(transport.send('bob', new Uint8Array([1, 2, 3])));
});

test('send() delivers bytes once the channel is open', async () => {
  const { transport, pcs } = makeTransport();
  await transport.createOfferFor('bob');
  pcs[0].channel.open();
  const bytes = new Uint8Array([9, 8, 7]);
  await transport.send('bob', bytes);
  assert.deepEqual(pcs[0].channel.sent, [bytes]);
});

test('an incoming message on the channel fires onMessage with the correct peer id', async () => {
  const { transport, pcs } = makeTransport();
  const received = [];
  transport.onMessage((peerId, bytes) => received.push({ peerId, bytes }));
  await transport.createOfferFor('bob');
  pcs[0].channel.open();
  const payload = new Uint8Array([1, 2]);
  pcs[0].channel.receive(payload);
  assert.equal(received.length, 1);
  assert.equal(received[0].peerId, 'bob');
  assert.deepEqual(received[0].bytes, payload);
});

test('closing an OPEN channel removes the peer and fires onPeerLeave', async () => {
  const { transport, pcs } = makeTransport();
  const left = [];
  transport.onPeerLeave((id) => left.push(id));
  await transport.createOfferFor('bob');
  pcs[0].channel.open();
  pcs[0].channel.close();
  assert.deepEqual(transport.peers(), []);
  assert.deepEqual(left, ['bob']);
});

test('closing a PENDING (never-opened) channel never fires onPeerLeave — it was never really a peer', async () => {
  const { transport, pcs } = makeTransport();
  const left = [];
  transport.onPeerLeave((id) => left.push(id));
  await transport.createOfferFor('bob');
  pcs[0].channel.close();
  assert.deepEqual(left, []);
});

test('acceptOffer rejects a blob that is an answer, not an offer', async () => {
  const { transport } = makeTransport();
  const notAnOffer = encodeSignal('answer', 'bob', 'sdp');
  await assert.rejects(transport.acceptOffer(notAnOffer), /expected an offer/);
});

test('acceptOffer returns a decodable answer blob, registering the connection under the offer\'s own originId', async () => {
  const { transport } = makeTransport('bob');
  const offerBlob = encodeSignal('offer', 'alice', 'real-offer-sdp');
  const answerBlob = await transport.acceptOffer(offerBlob);
  const decoded = decodeSignal(answerBlob);
  assert.equal(decoded.kind, 'answer');
  assert.equal(decoded.originId, 'bob');
});

test('acceptOffer honors an explicit peerId override instead of the offer\'s own originId', async () => {
  const { transport, pcs } = makeTransport();
  const offerBlob = encodeSignal('offer', 'alice-real-id', 'sdp');
  await transport.acceptOffer(offerBlob, { peerId: 'alice-nickname' });
  pcs[0].ondatachannel({ channel: pcs[0].createDataChannel('x') });
  pcs[0].channel.open();
  assert.deepEqual(transport.peers(), ['alice-nickname']);
});

test('completeConnection throws when there is no pending connection for that peer', async () => {
  const { transport } = makeTransport();
  const answerBlob = encodeSignal('answer', 'bob', 'sdp');
  await assert.rejects(transport.completeConnection('never-offered', answerBlob), /No pending connection/);
});

test('completeConnection rejects a blob that is an offer, not an answer', async () => {
  const { transport } = makeTransport();
  await transport.createOfferFor('bob');
  const notAnAnswer = encodeSignal('offer', 'bob', 'sdp');
  await assert.rejects(transport.completeConnection('bob', notAnAnswer), /expected an answer/);
});

test('completeConnection applies the remote description on success', async () => {
  const { transport, pcs } = makeTransport();
  await transport.createOfferFor('bob');
  const answerBlob = encodeSignal('answer', 'bob', 'real-answer-sdp');
  await transport.completeConnection('bob', answerBlob);
  assert.deepEqual(pcs[0].remoteDescription, { type: 'answer', sdp: 'real-answer-sdp' });
});

test('broadcast reaches every open peer, never a peer still pending', async () => {
  const { transport, pcs } = makeTransport();
  await transport.createOfferFor('bob');
  await transport.createOfferFor('carol');
  pcs[0].channel.open(); // bob open, carol still pending
  await transport.broadcast(new Uint8Array([1]));
  assert.equal(pcs[0].channel.sent.length, 1);
  assert.equal(pcs[1].channel.sent.length, 0);
});

test('disconnect() closes every link, pending and open, and clears all state', async () => {
  const { transport, pcs } = makeTransport();
  await transport.createOfferFor('bob');
  await transport.createOfferFor('carol');
  pcs[0].channel.open();
  await transport.disconnect();
  assert.deepEqual(transport.peers(), []);
  assert.equal(pcs[0].closed, true);
  assert.equal(pcs[1].closed, true);
});

// Regression test for a bug found via two separate,
// live browser tabs (Playwright + Chromium): when STUN traffic is
// blocked (as it is in some sandboxed/firewalled networks),
// iceGatheringState never reaches 'complete' on its own, and an
// unbounded wait hangs forever. createOfferFor/acceptOffer must still
// resolve — with whatever candidates were gathered in time — rather
// than block indefinitely.
class StuckPeerConnection extends FakePeerConnection {
  constructor() {
    super();
    this.iceGatheringState = 'gathering'; // never reaches 'complete'
  }
  addEventListener() {} // no event will ever fire — only the timeout can resolve this
}

test('createOfferFor resolves via its timeout when ICE gathering never reaches complete', async () => {
  const transport = new WebrtcTransport({
    selfId: 'self',
    iceGatheringTimeoutMs: 20,
    createPeerConnection: () => new StuckPeerConnection(),
  });
  const start = Date.now();
  const blob = await transport.createOfferFor('bob');
  assert.ok(Date.now() - start < 2000, 'must resolve via the bounded timeout, not hang');
  assert.equal(decodeSignal(blob).kind, 'offer');
});

test('acceptOffer resolves via its timeout when ICE gathering never reaches complete', async () => {
  const { transport: offerer } = makeTransport('alice');
  const offerBlob = await offerer.createOfferFor('bob');
  const transport = new WebrtcTransport({
    selfId: 'bob',
    iceGatheringTimeoutMs: 20,
    createPeerConnection: () => new StuckPeerConnection(),
  });
  const start = Date.now();
  const answerBlob = await transport.acceptOffer(offerBlob);
  assert.ok(Date.now() - start < 2000, 'must resolve via the bounded timeout, not hang');
  assert.equal(decodeSignal(answerBlob).kind, 'answer');
});

test('a channel that reaches the answering side already open counts as a link at once (its open event is not coming)', async () => {
  const { transport, pcs } = makeTransport('answerer');
  const joined = [];
  transport.onPeerJoin((peer) => joined.push(peer));
  await transport.acceptOffer(encodeSignal('offer', 'asker', 'fake-offer-sdp'));
  const channel = new FakeChannel('aiwa-platform');
  channel.readyState = 'open';
  pcs[0].ondatachannel({ channel });
  await Promise.resolve();
  assert.deepEqual(transport.peers(), ['asker']);
  assert.deepEqual(joined, ['asker']);
  channel.open();                         // and an open event that does come after is not a second join
  assert.deepEqual(joined, ['asker']);
});
