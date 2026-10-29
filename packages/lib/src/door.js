// The door, seen from inside an app's frame. An app runs in a sandbox with an opaque origin: no storage of its own. The Store that
// opened it keeps what the app asks it to keep (apps/web/src/app-door.js: one reserve per app, with a size limit), and answers these
// requests {aiwa: 1, id, cmd, args} with {aiwa: 1, id, result | error}. Outside the Store (no parent page, or one that does not
// answer) everything here falls back to memory: the app still runs, it just forgets when it is closed.
import { generateIdentity, identityFromSecretKey } from 'aiwa-core';

let nextId = 1;
let listening = false;
let dead = false;                        // the Store did not answer once: do not wait for it again
const waiting = new Map();

const inFrame = () => typeof window !== 'undefined' && window.parent && window.parent !== window;

/** Is there a page around the app that may answer? */
export const doorAvailable = () => inFrame() && !dead;

function listen() {
  if (listening) return;
  listening = true;
  window.addEventListener('message', (event) => {
    const m = event.data;
    if (event.source !== window.parent || !m || m.aiwa !== 1) return;
    const w = waiting.get(m.id);
    if (!w) return;
    waiting.delete(m.id);
    clearTimeout(w.timer);
    if (m.error !== undefined) w.reject(new Error(m.error)); else w.resolve(m.result);
  });
}

/** One request to the Store. Rejects at once outside it, and after a few seconds when it does not answer. */
export function callDoor(cmd, args = {}, timeoutMs = 4000) {
  if (!doorAvailable()) return Promise.reject(new Error('this app is not opened in the Store'));
  listen();
  return new Promise((resolve, reject) => {
    const id = nextId++;
    const timer = setTimeout(() => { if (waiting.delete(id)) { dead = true; reject(new Error('the Store did not answer')); } }, timeoutMs);
    waiting.set(id, { resolve, reject, timer });
    window.parent.postMessage({ aiwa: 1, id, cmd, args }, '*');   // an opaque origin takes no other target
  });
}

/** The app's own reserve in the Store: strings under short keys (a key: up to 100 of letters, digits and . : @ / _ -). */
export const doorStorage = {
  get: async (key) => (await callDoor('storage.get', { key })).value ?? null,
  set: (key, value) => callDoor('storage.set', { key, value: String(value) }).then(() => undefined),
  remove: (key) => callDoor('storage.remove', { key }).then(() => undefined),
  keys: async () => (await callDoor('storage.keys')).keys,
};

/** An event-log backend that outlives the frame: the events are kept in the Store's reserve of this app (and in memory, read once). */
export function createDoorBackend() {
  let cache = null;
  const load = () => (cache ??= (async () => {
    const map = new Map();
    if (!doorAvailable()) return map;
    try {
      for (const key of (await doorStorage.keys()).filter((k) => k.startsWith('ev:'))) {
        const raw = await doorStorage.get(key);
        if (raw) map.set(key.slice(3), JSON.parse(raw));
      }
    } catch { /* the Store does not answer: memory only */ }
    return map;
  })());
  return {
    async putEvent(event) { (await load()).set(event.id, event); await doorStorage.set(`ev:${event.id}`, JSON.stringify(event)).catch(() => {}); },
    async getEvent(id) { return (await load()).get(id) ?? null; },
    async hasEvent(id) { return (await load()).has(id); },
    async allIds() { return [...(await load()).keys()]; },
    async deleteEvent(id) { (await load()).delete(id); await doorStorage.remove(`ev:${id}`).catch(() => {}); },
  };
}

/** The player's identity in this app, the same at each opening: read from the Store's reserve, or made and kept there. */
export async function loadOrCreateIdentity() {
  try {
    const secret = await doorStorage.get('identity');
    if (secret) return await identityFromSecretKey(secret);
  } catch { /* nothing kept, or no Store */ }
  const identity = await generateIdentity();
  await doorStorage.set('identity', identity.exportSecretKey()).catch(() => {});
  return identity;
}
