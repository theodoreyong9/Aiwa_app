// The loader of a published contract: its code is run only after its hash has been checked against the hash the person accepted, and then inside a Worker (no page, no storage, no network, no key):
// it receives events and answers with a state. What it asks of the outside (checking a signature) goes through messages, so the code never holds anything that matters.
import { computeContractHash } from 'aiwa-core';

const PIN_KEY = 'aiwa-app:pinned-contracts';
const TIMEOUT_MS = 5000;

/** The hashes the person accepted (kept in this browser; an empty set when it cannot be read). */
export function pinnedHashes() {
  try { return new Set(JSON.parse(localStorage.getItem(PIN_KEY) ?? '[]')); } catch { return new Set(); }
}
export function pinHash(hash) {
  const set = pinnedHashes();
  set.add(hash);
  try { localStorage.setItem(PIN_KEY, JSON.stringify([...set])); } catch { /* not kept: asked again */ }
}

/** The source as the Worker can run it: the `aiwa-lib` import goes (its three names are given), `export` goes (the `definition` is what is returned). */
export function prepareSource(source) {
  return String(source)
    .replace(/^\s*import\s[^;]*?from\s*['"]aiwa-lib['"]\s*;?\s*$/gm, '')
    .replace(/^\s*export\s+(const|let|var|function|async function|class)\s/gm, '$1 ')
    .replace(/^\s*export\s*\{[^}]*\}\s*;?\s*$/gm, '');
}

// Runs inside the Worker. The network and the dynamic loading are removed before the contract's code exists.
export const WORKER_SOURCE = `
'use strict';
for (const name of ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'importScripts', 'indexedDB', 'caches', 'Worker', 'SharedWorker', 'BroadcastChannel', 'navigator']) {
  try { Object.defineProperty(self, name, { value: undefined, configurable: false, writable: false }); } catch (e) { try { self[name] = undefined; } catch (e2) {} }
}
const post = self.postMessage.bind(self);
const waiting = new Map();
let counter = 0;
const ask = (what, payload) => new Promise((resolve) => { const id = ++counter; waiting.set(id, resolve); post({ ask: id, what, payload }); });
const defineContract = ({ initialState, handlers }) => ({
  initialState,
  async apply(state, event) { const h = handlers[event.payload && event.payload.type]; return h ? await h(state, event) : state; },
  async materialize(events) { let state = initialState(); for (const e of events) state = await this.apply(state, e); return state; },
});
const verifySignedAction = (payload) => ask('verify', payload);
const signedAction = () => { throw new Error('signedAction se appelle hors du contrat : le contrat ne tient aucune clé'); };
let definition = null;
self.onmessage = async (message) => {
  const data = message.data || {};
  if ('answer' in data) { const resolve = waiting.get(data.answer); if (resolve) { waiting.delete(data.answer); resolve(data.value); } return; }
  try {
    if (data.cmd === 'load') {
      definition = new Function('defineContract', 'signedAction', 'verifySignedAction', data.code + '\\nreturn typeof definition !== "undefined" ? definition : null;')(defineContract, signedAction, verifySignedAction);
      if (!definition || typeof definition.materialize !== 'function') throw new Error('le fichier ne déclare pas de « definition »');
      post({ id: data.id, ok: true });
    } else if (data.cmd === 'state') {
      post({ id: data.id, ok: true, state: await definition.materialize(data.events) });
    }
  } catch (err) {
    post({ id: data.id, ok: false, error: String(err && err.message || err) });
  }
};
`;

/**
 * Loads a published contract. `spec` is { sourceCode, sourceHash }; `pinned` is the hash the person accepted. Refuses when the code does not hash to both.
 * @returns {Promise<{ state(events: object[]): Promise<any>, close(): void }>}
 */
export async function loadVerified(spec, pinned, { verifySignedAction, makeWorker = defaultWorker } = {}) {
  const real = await computeContractHash(spec.sourceCode);
  if (real !== spec.sourceHash) throw new Error('Le code ne correspond pas à l’empreinte annoncée par le contrat : je ne le charge pas.');
  if (real !== pinned) throw new Error('Cette empreinte n’est pas celle que tu as acceptée : je ne charge pas ce code.');
  const worker = makeWorker();
  const calls = new Map();
  let counter = 0;
  worker.onmessage = async (message) => {
    const data = message.data || {};
    if (data.ask) {
      let value = false;
      try { if (data.what === 'verify' && verifySignedAction) value = await verifySignedAction(data.payload); } catch { value = false; }
      worker.postMessage({ answer: data.ask, value });
      return;
    }
    const call = calls.get(data.id);
    if (!call) return;
    calls.delete(data.id);
    clearTimeout(call.timer);
    if (data.ok) call.resolve(data); else call.reject(new Error(data.error));
  };
  const send = (body) => new Promise((resolve, reject) => {
    const id = ++counter;
    const timer = setTimeout(() => { calls.delete(id); worker.terminate?.(); reject(new Error('Le contrat a mis trop de temps : je l’ai arrêté.')); }, TIMEOUT_MS);
    calls.set(id, { resolve, reject, timer });
    worker.postMessage({ id, ...body });
  });
  await send({ cmd: 'load', code: prepareSource(spec.sourceCode) });
  return { state: async (events) => (await send({ cmd: 'state', events })).state, close: () => worker.terminate?.() };
}

function defaultWorker() {
  const url = URL.createObjectURL(new Blob([WORKER_SOURCE], { type: 'text/javascript' }));
  const worker = new Worker(url);
  URL.revokeObjectURL(url);
  return worker;
}
