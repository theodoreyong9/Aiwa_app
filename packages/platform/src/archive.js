// The client of an Aiwa archive node: keep a wallet's backup somewhere that is always there, and get it back.
//
// An archive node (archive-server.js, run with node/aiwa-node.js) holds, per domain, the latest BACKUP of a wallet — a
// checkpoint, the wallet's state signed by its own key (aiwa-lib: exportBackup / importBackup). The wallet pushes one
// whenever it has a new one; a wallet that lost its device logs in with its recovery phrase and asks the nodes for it.
// Anyone can run a node, and a wallet can use several: it pushes to all and takes the most recent answer.
//
// Nothing here needs trusting: a backup is signed by the key it belongs to, so a node can neither forge one nor hand a
// wallet someone else's (importBackup refuses another identity), and a node that lies by giving an older one is
// outvoted by a node that did not. What a node can do is withhold or forget — hence several.
//
// Uses the platform's `fetch` (browsers, Node 18+). No dependency.

const HEX64 = /^[0-9a-f]{64}$/;

/**
 * A node's address, normalised: https (or http on this machine / a local network, for a node you run yourself), no
 * trailing slash, no path. Throws on anything else: an address typed by hand is checked before it is used.
 */
export function normalizeNodeUrl(raw) {
  let url;
  try { url = new URL(String(raw).trim()); } catch { throw new Error(`not an address: ${raw}`); }
  const local = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[::1\])/.test(url.hostname) || url.hostname.endsWith('.local');
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) throw new Error(`a node is reached over https (http only on a local network): ${raw}`);
  return url.origin;
}

async function request(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try { return await fetch(url, { ...options, signal: controller.signal }); } finally { clearTimeout(timer); }
}

// When a backup was made, from the checkpoint inside it — signed by the wallet's key — not from the wrapper around it.
const backupTime = (backup) => backup?.events?.[0]?.createdAt ?? 0;

/** Pushes `backup` (aiwa-lib's exportBackup) to one node. @returns {Promise<{ stored: boolean, epoch: number, createdAt: number }>} `stored` is false when the node already had a newer one. */
export async function pushBackup(nodeUrl, backup, { timeoutMs = 15000 } = {}) {
  const base = normalizeNodeUrl(nodeUrl);
  const reply = await request(`${base}/v1/backup`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(backup) }, timeoutMs);
  const body = await reply.json().catch(() => ({}));
  if (!reply.ok) throw new Error(`${base} refused the backup (${reply.status}): ${body.error ?? 'no reason given'}`);
  return body;
}

/** The backup a node holds for `domain`, or null if it holds none. */
export async function fetchBackup(nodeUrl, domain, { timeoutMs = 15000 } = {}) {
  if (!HEX64.test(domain)) throw new Error('fetchBackup: a domain is 64 hex characters');
  const base = normalizeNodeUrl(nodeUrl);
  const reply = await request(`${base}/v1/backup/${domain}`, { method: 'GET' }, timeoutMs);
  if (reply.status === 404) return null;
  if (!reply.ok) throw new Error(`${base} answered ${reply.status}`);
  return reply.json();
}

/** Pushes to every node; never throws for one that is down. @returns {Promise<{ ok: Array<{ node: string, stored: boolean, epoch: number }>, failed: Array<{ node: string, error: string }> }>} */
export async function pushToNodes(nodes, backup, options) {
  const settled = await Promise.allSettled(nodes.map((node) => pushBackup(node, backup, options)));
  const result = { ok: [], failed: [] };
  settled.forEach((s, i) => {
    if (s.status === 'fulfilled') result.ok.push({ node: nodes[i], ...s.value });
    else result.failed.push({ node: nodes[i], error: s.reason?.message ?? String(s.reason) });
  });
  return result;
}

/**
 * Asks every node for `domain`'s backup and returns the most recent one (by when it was made), with the node that had
 * it — or null when none holds one. A node that is down is skipped.
 * @returns {Promise<{ backup: object, node: string } | null>}
 */
export async function fetchFromNodes(nodes, domain, options) {
  const settled = await Promise.allSettled(nodes.map(async (node) => ({ node, backup: await fetchBackup(node, domain, options) })));
  let best = null;
  for (const s of settled) {
    if (s.status !== 'fulfilled' || !s.value.backup) continue;
    if (!best || backupTime(s.value.backup) > backupTime(best.backup)) best = s.value;
  }
  return best;
}
