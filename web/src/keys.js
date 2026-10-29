// Where the wallet's secrets live. In the Android app, in the phone's keystore, which the page cannot read back out of
// the app's private storage; in a browser, in that browser's own storage (readable by anyone with the browser profile:
// the page says so where it matters).
import { hostAvailable, hostCall } from './host.js';

const browserKey = (name) => `aiwa-app:${name}`;

export const secretsAreSafe = () => hostAvailable();

export async function loadSecret(name) {
  if (hostAvailable()) return (await hostCall('secret-get', { key: name })).value ?? null;
  try { return localStorage.getItem(browserKey(name)); } catch { return null; }
}

export async function saveSecret(name, value) {
  if (hostAvailable()) { await hostCall('secret-set', { key: name, value }); return; }
  try { localStorage.setItem(browserKey(name), value); } catch { throw new Error('This browser refuses to keep the wallet. Allow site storage, or use the Android app.'); }
}

export async function deleteSecret(name) {
  if (hostAvailable()) { await hostCall('secret-delete', { key: name }); return; }
  try { localStorage.removeItem(browserKey(name)); } catch { /* nothing to remove */ }
}
