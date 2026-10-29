// The wallet of the person, started by itself on every page that needs it (the wallet page, « Voir », the coffee card): the key is the 12-word phrase the phone keeps; the history it had is brought back when the phone lost it;
// it works for as long as the page is open and meets the other wallets by itself. A page that finds no phrase decides what to do (the wallet page asks the person once).
import { setSession, session } from './session.js';
import { keptPhrase, startWallet, restoreHistory, keepRunning } from './wallet-life.js';
import { watchNetwork } from './network.js';

const listeners = new Set();
/** Tells `fn()` each time the wallet may have changed (an event came in from another wallet, a restore finished). */
export const onWalletChange = (fn) => { listeners.add(fn); };
const changed = () => { for (const fn of listeners) { try { fn(); } catch { /* a listener never stops the wallet */ } } };

/** Runs `aiwa` as the wallet of this page. Returns what the restore brought back (or null). */
export async function runWallet(aiwa) {
  setSession(aiwa);
  const restored = await restoreHistory(aiwa);
  keepRunning(aiwa);        // after the restore: working epochs on an empty log would fork the history that was about to come back
  watchNetwork(aiwa, async (state) => {
    if (session.aiwa !== aiwa || state.received <= 0) return;
    await aiwa.settled();   // what it signs for what just arrived is part of the evidence
    changed();
  }).catch(() => {});
  if (restored) changed();
  return restored;
}

/** Starts the wallet the phone already has; null when there is none (nothing is made without the person asking). */
export async function bootWallet() {
  const phrase = await keptPhrase();
  if (!phrase) return null;
  const aiwa = await startWallet({ mnemonic: phrase });
  await runWallet(aiwa);
  return aiwa;
}
