// The wallet's network: ONE transport made of the two ways it meets other wallets, which feed the same log.
//   by itself: the wallets that are open join a room (Trystero, through a public relay that sees only that someone looks for
//              peers) and a direct connection opens to each of them: nobody swaps a code, there is no server of ours;
//   by hand:   a direct transport that two phones can open with two codes (kept for when no relay can be reached; the app has no screen for it).
// Once it has some peers a wallet no longer needs the room: it asks them to introduce it to theirs (Introducer), which opens direct
// connections of its own, and with enough of those it leaves the room (PeerManager). A machine that is always on stays in the room, so
// that a newcomer always finds someone.
// Persistence is another matter (a wallet that nobody holds is gone with its phone): it is for machines that stay connected.
import { WebrtcTransport, TrysteroTransport, CompositeTransport, Introducer, PeerManager } from 'aiwa-lib';
import { joinRoom, selfId } from '@trystero-p2p/nostr';
import { config } from './config.js';

const PREFERENCE = 'aiwa-network';      // 'off' once the person turned it off
const RELAYS = 'aiwa-relays';
const PEERS = 'aiwa-peers';             // '{"target":6,"low":3}': how many direct connections are enough, and how few send the wallet back to the room
const LOBBY = 'aiwa-lobby';             // 'stay': this machine stays in the room whatever it has (an always-on terminal)           // a JSON list of relay addresses, instead of the built-in public ones (a relay of one's own, a test)

const read = (key) => { try { return localStorage.getItem(key); } catch { return null; } };

export const wantsNetwork = () => read(PREFERENCE) !== 'off';

function relays() {
  try {
    const list = JSON.parse(read(RELAYS));
    return Array.isArray(list) && list.length > 0 && list.every((u) => /^wss?:\/\//.test(u)) ? list : null;
  } catch { return null; }
}

function peerLimits() {
  try {
    const { target, low, roomMin, leaveJitterMs } = JSON.parse(read(PEERS));
    if (!(Number.isInteger(target) && Number.isInteger(low) && target >= 1 && low >= 1 && low <= target)) return {};
    return { target, low, ...(Number.isInteger(roomMin) && roomMin >= 0 ? { roomMin } : {}), ...(Number.isInteger(leaveJitterMs) && leaveJitterMs >= 0 ? { leaveJitterMs } : {}) };
  } catch { return {}; }
}

// What the browser says about the network it is on ('wifi', 'cellular'…), where it says it.
const connectionKind = () => navigator.connection?.type ?? null;

/**
 * A wallet that changes network (Wi-Fi to the phone's data) or wakes up after a long sleep has links that are tied to an address it no
 * longer has. The browser says so in a few ways; any of them has the manager drop the links and look for the others again at once, instead
 * of finding out half a minute later when the connections time out.
 */
function watchNetworkChanges(manager) {
  let kind = connectionKind();
  let hiddenAt = null;
  let timer = null;
  const changed = (why) => {
    clearTimeout(timer);
    timer = setTimeout(() => { console.debug('network changed:', why); manager.networkChanged().catch((err) => console.debug('network change:', err.message)); }, 1500);
  };
  window.addEventListener('online', () => changed('online'));
  navigator.connection?.addEventListener?.('change', () => {
    const now = connectionKind();
    if (now !== kind) { kind = now; changed('connection'); }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { hiddenAt = Date.now(); return; }
    const slept = hiddenAt !== null && Date.now() - hiddenAt > 60_000;
    hiddenAt = null;
    if (slept) changed('resumed');
  });
}

const networks = new WeakMap();      // wallet -> { manual, lobby, all, manager }

/** The wallet's transports, made and joined to its replicator the first time. */
export async function networkOf(aiwa) {
  let net = networks.get(aiwa);
  if (!net) {
    const iceServers = config.nearby?.iceServers ?? [{ urls: 'stun:stun.l.google.com:19302' }];
    const manual = new WebrtcTransport({ iceServers });
    const lobby = new TrysteroTransport({
      joinRoom, selfId, appId: 'aiwa-store-v1', roomId: `lobby:${config.cluster ?? 'devnet'}`,
      relayUrls: relays(), rtcConfig: { iceServers }, enabled: wantsNetwork(),
    });
    const all = new CompositeTransport([manual, lobby]);
    net = { manual, lobby, all };
    networks.set(aiwa, net);
    await aiwa.joinNetwork(all);
    const introducer = new Introducer({ transport: all });
    introducer.start();
    net.manager = new PeerManager({ transport: all, direct: manual, lobby, introducer, stay: read(LOBBY) === 'stay', ...peerLimits() });
    net.manager.enabled = wantsNetwork();
    net.manager.start();
    watchNetworkChanges(net.manager);
  }
  return net;
}

/** Turns the lobby on or off, and remembers it. */
export async function setNetwork(aiwa, on) {
  try { if (on) localStorage.removeItem(PREFERENCE); else localStorage.setItem(PREFERENCE, 'off'); } catch { /* it lasts until the page closes */ }
  const { lobby, manager } = await networkOf(aiwa);
  lobby.enabled = on;
  manager.enabled = on;
  if (on) { await lobby.connect(); manager.evaluate().catch(() => {}); } else await lobby.disconnect();
}

/**
 * Tells `onChange({ peers, direct, room, received })` when a wallet joins or leaves, and when events arrive from one. `peers` is how
 * many are connected now (whichever way), `direct` how many of them by a connection that does not depend on the room, `room` whether
 * the wallet is in the room, `received` how many events came in over those links so far.
 */
export async function watchNetwork(aiwa, onChange) {
  const { all, manual, lobby } = await networkOf(aiwa);
  let received = 0;
  const tell = () => onChange({ peers: all.peers().length, direct: manual.peers().length, room: lobby.connected, received, wanted: wantsNetwork() });
  all.onPeerJoin(tell);
  all.onPeerLeave(tell);
  aiwa.replicator.onSync(({ receivedCount }) => { if (receivedCount > 0) { received += receivedCount; tell(); } });
  tell();
  return tell;
}
