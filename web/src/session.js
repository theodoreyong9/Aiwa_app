// What the wallet page shares: the one wallet it holds. `starting`: the page is still deciding whether a wallet exists (until it says so, nobody should be told there is none).
export const session = { aiwa: null, starting: true };
const sessionListeners = new Set();
export const onSession = (fn) => { sessionListeners.add(fn); };
export const setSession = (aiwa) => { session.aiwa = aiwa; for (const fn of sessionListeners) fn(aiwa); };
export const connected = () => !!(session.aiwa && session.aiwa.identity);
