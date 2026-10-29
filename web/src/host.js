// What the Android app offers the page: keeping a secret, GitHub's device login, saving a file, the dictation module's
// screen, and a back button that closes what is open before it leaves. In a browser none of it exists and the page does
// without.
//
// The channel is `window.AiwaHost`, added by the app to this page's own origin only: the sandboxed frame an app runs
// in has another origin and does not get it. The page sends JSON strings; the app answers on `onmessage`:
//   { id, result }           the one answer to the request `id`
//   { id, error }            it failed
//   { id, progress }         news while it is still going (the login's code to show)
export const hostAvailable = () => typeof window.AiwaHost?.postMessage === 'function';

const pending = new Map();
let counter = 0;

function listen() {
  if (!hostAvailable() || window.AiwaHost.onmessage) return;
  window.AiwaHost.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    const call = pending.get(message.id);
    if (!call) return;
    if ('progress' in message) { call.onProgress?.(message.progress); return; }
    pending.delete(message.id);
    clearTimeout(call.timer);
    if ('error' in message) call.reject(new Error(message.error)); else call.resolve(message.result);
  };
}

/** Fire and forget. */
export function hostPost(command) {
  window.AiwaHost.postMessage(JSON.stringify(command));
}

/** A request the app answers: resolves with its result, rejects with its error, or after `timeoutMs`. */
export function hostCall(cmd, args = {}, { onProgress, timeoutMs = 10 * 60_000 } = {}) {
  if (!hostAvailable()) return Promise.reject(new Error('This needs the Android app.'));
  listen();
  const id = ++counter;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`The app did not answer (${cmd}).`)); }, timeoutMs);
    pending.set(id, { resolve, reject, onProgress, timer });
    hostPost({ ...args, cmd, id });
  });
}

let backHandler = () => false;
export function setBackHandler(fn) { backHandler = fn; }
// Called by the app on the back button: true when the page used it (closed something), false to let the app leave.
window.aiwaHostBack = () => backHandler();
