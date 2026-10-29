// Encodes/decodes the one message WebRTC's own standard signaling
// process needs before two peers can talk directly: an SDP offer or
// answer, tagged with who sent it. Pure, no WebRTC API involved — the
// opaque blob this produces travels over whatever real
// out-of-band channel the caller picks (pasted text, a QR code, a
// shared file); this module never transmits anything itself.

const FORMAT = 'aiwa-platform-signal-v1';

/**
 * @param {'offer'|'answer'} kind
 * @param {string} originId human-checkable label for who this signal is from — shown before the recipient accepts, never trusted as an identity proof on its own (the identity proof is whatever the application layer signs over the resulting data channel, not this blob).
 * @param {string} sdp the SDP string from RTCPeerConnection's own localDescription.
 */
export function encodeSignal(kind, originId, sdp) {
  if (kind !== 'offer' && kind !== 'answer') throw new Error(`encodeSignal: kind must be 'offer' or 'answer', got '${kind}'`);
  const payload = { format: FORMAT, kind, originId, sdp };
  return btoa(encodeURIComponent(JSON.stringify(payload)));
}

/** @returns {{ kind: 'offer'|'answer', originId: string, sdp: string }} */
export function decodeSignal(blob) {
  let payload;
  try {
    payload = JSON.parse(decodeURIComponent(atob(blob)));
  } catch {
    throw new Error('decodeSignal: not a real, valid signal blob (malformed base64/JSON).');
  }
  if (payload.format !== FORMAT) throw new Error(`decodeSignal: unrecognized format '${payload.format}', expected '${FORMAT}'.`);
  if (payload.kind !== 'offer' && payload.kind !== 'answer') throw new Error(`decodeSignal: invalid kind '${payload.kind}'.`);
  if (typeof payload.sdp !== 'string' || !payload.sdp) throw new Error('decodeSignal: missing or empty sdp.');
  return { kind: payload.kind, originId: payload.originId, sdp: payload.sdp };
}
