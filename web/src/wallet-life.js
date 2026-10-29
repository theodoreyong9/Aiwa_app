// The wallet's life, apart from any page. It starts by itself: the key is made once and kept where the phone keeps
// secrets, the history it had is brought back when the phone lost it, and it works for as long as the app is open.
//
// The key IS the 12-word recovery phrase; everything else about a wallet is a history that is folded from its events.
// A new phone gets the key back from the phrase, and the history back, in this order, from: what the phone itself
// restored (Android's backup of the app), the archive nodes the deployment lists, and the registry's baseline (the last
// state it validated, if the wallet ever published).
import { AIWA } from 'aiwa-lib';
import { generateBip39Mnemonic, deriveKeypairFromBip39Mnemonic } from 'aiwa-core';
import { config } from './config.js';
import { loadSecret, saveSecret } from './keys.js';

const PHRASE = 'phrase';

// @solana/web3.js is part of this app (a separate chunk, loaded when a burn or a balance needs it): aiwa-core looks
// for it on window.solanaWeb3 before it would fetch it from a CDN.
let connectionPromise = null;
export function solanaConnection() {
  connectionPromise ??= (async () => {
    if (!window.solanaWeb3) window.solanaWeb3 = await import('@solana/web3.js');
    if (window.__aiwaTest?.connection) return window.__aiwaTest.connection;       // tests only: a stand-in for Solana
    return new window.solanaWeb3.Connection(config.rpc, 'confirmed');
  })();
  connectionPromise.catch(() => { connectionPromise = null; });
  return connectionPromise;
}

/** The phrase kept on this phone, or null: the wallet has never been made here. */
export const keptPhrase = () => loadSecret(PHRASE);

/** Connects a wallet from `mnemonic`, or from a new phrase; the phrase is kept before anything else can be done with the wallet. */
export async function startWallet({ mnemonic } = {}) {
  const phrase = (mnemonic ?? await generateBip39Mnemonic(12)).trim().replace(/\s+/g, ' ').toLowerCase();
  const keypair = await deriveKeypairFromBip39Mnemonic(phrase);        // refuses a phrase that is not one
  // One journal per identity: another phrase on the same phone never mixes histories.
  const aiwa = new AIWA({ rewardParams: config.rewardParams, dbName: `aiwa-wallet-${keypair.publicKey.toBase58().slice(0, 12)}` });
  await aiwa.connect({ mnemonic: phrase });
  await saveSecret(PHRASE, phrase);
  // Burns that arrive with other domains' events are confirmed against Solana by themselves once the wallet has a
  // connection. Never blocks: offline, it just stays unset.
  solanaConnection().then((connection) => { aiwa.connection = connection; }).catch(() => {});
  return aiwa;
}

/**
 * Brings back what a phone that lost it does not hold. Does nothing when the wallet already has a history here.
 * @returns {Promise<{ source: 'archive'|'registry', epoch: number }|null>}
 */
export async function restoreHistory(aiwa, { fetchFn = fetch } = {}) {
  if (await aiwa.mining()) return null;
  const nodes = config.archiveNodes ?? [];
  if (nodes.length > 0) {
    try {
      const got = await aiwa.restoreFromArchive(nodes);
      if (got.restored) return { source: 'archive', epoch: got.epoch };
    } catch { /* the nodes are unreachable: the next source */ }
  }
  try {
    const response = await fetchFn(`${config.registryUrl}/baselines/${aiwa.address}.json`, { cache: 'no-cache' });
    if (response.ok) {
      const baseline = await response.json();
      const got = await aiwa.adoptState(baseline.state);
      if (got.adopted) return { source: 'registry', epoch: got.epoch };
    }
  } catch { /* no baseline, or none that is this wallet's */ }
  return null;
}

/** What a wallet does while the app is open: work epochs without waiting (one signed event per `eventMs` of work), keep its own start fast, and send its backup to the archive nodes. */
export function keepRunning(aiwa) {
  // `progress.intervalMs` (tests, demos): one epoch per interval. Otherwise the wallet works without waiting.
  const { intervalMs, eventMs } = config.progress ?? {};
  const onError = (err) => console.error('progress:', err);
  aiwa.startProgressLoop(intervalMs ? { intervalMs, onError } : { eventMs: eventMs ?? 30_000, onError });
  aiwa.startAutoCheckpoint({ onError: (err) => console.error('checkpoint:', err) });
  if ((config.archiveNodes ?? []).length > 0) aiwa.startAutoArchive({ nodes: config.archiveNodes, onError: (err) => console.error('archive:', err) });
}
