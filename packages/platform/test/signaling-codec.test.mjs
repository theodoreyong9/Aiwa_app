import { test } from 'node:test';
import assert from 'node:assert/strict';
import { encodeSignal, decodeSignal } from '../src/signaling-codec.js';

test('encode/decode round-trips an offer', () => {
  const blob = encodeSignal('offer', 'alice', 'v=0\r\no=- 123 2 IN IP4 127.0.0.1\r\n');
  const decoded = decodeSignal(blob);
  assert.equal(decoded.kind, 'offer');
  assert.equal(decoded.originId, 'alice');
  assert.equal(decoded.sdp, 'v=0\r\no=- 123 2 IN IP4 127.0.0.1\r\n');
});

test('encode/decode round-trips an answer', () => {
  const blob = encodeSignal('answer', 'bob', 'real-sdp-content');
  const decoded = decodeSignal(blob);
  assert.equal(decoded.kind, 'answer');
  assert.equal(decoded.originId, 'bob');
});

test('encodeSignal rejects a kind that is neither offer nor answer', () => {
  assert.throws(() => encodeSignal('hello', 'alice', 'sdp'), /must be 'offer' or 'answer'/);
});

test('decodeSignal rejects malformed input rather than crashing unpredictably', () => {
  assert.throws(() => decodeSignal('not-real-base64-!!!'), /not a real, valid signal blob/);
  assert.throws(() => decodeSignal(btoa(JSON.stringify({ not: 'the right shape' }))), /unrecognized format/);
});

test('decodeSignal rejects a blob from a different, unrecognized format tag', () => {
  const blob = btoa(encodeURIComponent(JSON.stringify({ format: 'some-other-format-v1', kind: 'offer', originId: 'x', sdp: 'y' })));
  assert.throws(() => decodeSignal(blob), /unrecognized format/);
});

test('decodeSignal rejects a missing or empty sdp', () => {
  const blob = btoa(encodeURIComponent(JSON.stringify({ format: 'aiwa-platform-signal-v1', kind: 'offer', originId: 'x', sdp: '' })));
  assert.throws(() => decodeSignal(blob), /missing or empty sdp/);
});

test('the encoded blob carries no plaintext SDP visible without decoding — if minimal, obfuscation against a careless glance', () => {
  const blob = encodeSignal('offer', 'alice', 'SECRET-LOOKING-SDP-MARKER');
  assert.ok(!blob.includes('SECRET-LOOKING-SDP-MARKER'));
});
