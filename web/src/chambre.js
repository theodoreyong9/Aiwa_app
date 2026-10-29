// The chamber (the transport and the manners of the room where two super agents meet; the brain has the rules of what they say, aiwa_chamber.py).
//
// A chamber is a direct connection between two phones (Trystero over WebRTC, the same way « Voir » finds people: a public relay only sees that someone looks for a room of this name; what the two say goes
// straight from one phone to the other). The room is named for the person who is VISITED: she opens it on her own page (mode "host"), the visitor joins it from her profile (mode "visit"); they find each other
// when both have pressed their button. Then ONE of the two starts the conversation, which has no limit until one of them stops it.
//
// This page has no screen: it lives under the home of the application and talks to the phone through the host channel (host.js):
//   chamber-active   the brain says whether this super agent may enter a chamber (it takes part in only one at a time)
//   chamber-turn     the brain makes the next words of OUR agent from what the other said
//   chamber-deliver  with the danger of both sides: a message or a proposal of the other, given to our super agent
//   chamber-line     a line to show and, if the person listens, to say aloud
//   chamber-status   what is going on (for the buttons of the home)
// and it is driven by the phone: window.aiwaChamber.cmd({ cmd: 'open' | 'visit' | 'close' | 'begin' | 'end' | 'danger' | 'ear', ... }).
//
// What comes from the other is bounded text; plain words are the conversation, a "dm" (message or proposal) is given on only if BOTH pressed the danger button.
import { joinRoom as trysteroJoin } from '@trystero-p2p/nostr';
import { hostAvailable, hostCall } from './host.js';
import { createChamber, nameOf } from './chambre-core.js';

const APP_ID = 'aiwa-chambre-v1';

/** The page: joins rooms with Trystero, talks to the phone, and gives it `window.aiwaChamber`. */
export function startChambre(params) {
  const repo = params.get('me') || '';
  const name = params.get('name') || nameOf(repo);
  const utf8 = new TextEncoder(), decoder = new TextDecoder();
  const join = (roomName) => {
    const room = trysteroJoin({ appId: APP_ID }, roomName);
    const action = room.makeAction('chm');
    const handlers = { message: () => {}, join: () => {}, leave: () => {} };
    action.onMessage = (data, peerId) => { let m; try { m = JSON.parse(decoder.decode(data instanceof Uint8Array ? data : new Uint8Array(data))); } catch { return; } handlers.message(m, peerId); };
    room.onPeerJoin = (id) => handlers.join(id);
    room.onPeerLeave = (id) => handlers.leave(id);
    return {
      send: (m, id) => action.send(utf8.encode(JSON.stringify(m)), id ? { target: id } : {}),
      onMessage: (fn) => { handlers.message = fn; }, onPeerJoin: (fn) => { handlers.join = fn; }, onPeerLeave: (fn) => { handlers.leave = fn; },
      leave: () => room.leave(),
    };
  };
  const chamber = createChamber({ join, me: { repo, name }, call: (cmd, args) => hostCall(cmd, args, { timeoutMs: 120_000 }), post: (c) => { if (hostAvailable()) window.AiwaHost.postMessage(JSON.stringify(c)); } });
  window.aiwaChamber = { cmd: (c) => chamber.cmd(c), status: () => chamber.status() };
  return chamber;
}
