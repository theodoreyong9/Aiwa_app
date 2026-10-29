// An Aiwa archive node: the always-on holder of wallets' backups that makes "my history is in the network" true.
//
// PUT /v1/backup a wallet's backup (aiwa-lib's exportBackup): a checkpoint signed by the key it belongs to
// GET /v1/backup/<domain> the latest backup held for that domain (404 if none)
// GET /v1/status { ok, domains, version }
//
// What it checks before keeping anything: the body is small; it is an Aiwa backup holding ONE event; that event is a
// checkpoint whose envelope verifies (id, signature) and whose author is the domain the backup names — so only the
// owner of a key can write that key's backup, and nothing can be forged. It keeps the most recent one per domain (by
// the checkpoint's own signed time) and refuses anything dated in the future.
//
// What it does not do: it never sees a secret (a backup holds none: balances and mining state, public in any case),
// and it does not authenticate readers — a backup is readable by anyone who knows the domain, like the events a peer
// that received them could show. It limits sizes, the number of domains and the rate of writes per address.
// Storage: one file per domain, written atomically. No dependency but aiwa-core and Node's own modules.

import http from 'node:http';
import { mkdirSync, readFileSync, writeFileSync, renameSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { verifyEvent, verifyCheckpoint, checkpointWalletState } from 'aiwa-core';

const HEX64 = /^[0-9a-f]{64}$/;

export const ARCHIVE_LIMITS = {
  maxBytes: 256 * 1024,        // one backup
  maxDomains: 100_000,         // what a node keeps (a new domain beyond this is refused)
  writesPerMinute: 30,         // per client address
  futureSkewMs: 10 * 60_000,   // a checkpoint dated further ahead than this is refused
};

/** Why `backup` cannot be kept, or null — and, if it can, what it is worth. Pure: no storage. */
export async function checkBackup(backup, { now = Date.now(), limits = ARCHIVE_LIMITS } = {}) {
  if (!backup || backup.kind !== 'aiwa-backup' || backup.version !== 1) return { error: 'not an Aiwa backup' };
  if (typeof backup.domain !== 'string' || !HEX64.test(backup.domain)) return { error: 'the domain is 64 hex characters' };
  if (!Array.isArray(backup.events) || backup.events.length !== 1) return { error: 'a backup holds exactly one event, a checkpoint' };
  const event = backup.events[0];
  if (!event || event.type !== 'checkpoint' || event.author !== backup.domain) return { error: 'the event must be a checkpoint made by the domain itself' };
  const verdict = await verifyEvent(event).catch(() => ({ valid: false, reason: 'malformed' }));
  if (!verdict.valid) return { error: `the checkpoint does not verify: ${verdict.reason ?? 'invalid'}` };
  if (!verifyCheckpoint(event)) return { error: 'not a self-authored checkpoint' };
  if (!Number.isFinite(event.createdAt) || event.createdAt > now + limits.futureSkewMs) return { error: 'the checkpoint is dated in the future' };
  let epoch = 0;
  try { epoch = checkpointWalletState(event)?.accrual?.progression?.domains?.[backup.domain]?.epoch ?? 0; } catch { return { error: 'the checkpoint holds no readable state' }; }
  return { epoch, createdAt: event.createdAt };
}

/**
 * @param {object} options
 * @param {string} options.dir where the backups are kept (created if missing)
 * @param {object} [options.limits] see ARCHIVE_LIMITS
 * @returns {http.Server} not listening yet: call .listen(port)
 */
export function createArchiveServer({ dir, limits = ARCHIVE_LIMITS, version = '0.1.0' } = {}) {
  if (!dir) throw new Error('createArchiveServer: a directory to keep the backups in');
  mkdirSync(dir, { recursive: true });
  const fileOf = (domain) => join(dir, `${domain}.json`);
  let domains = readdirSync(dir).filter((f) => HEX64.test(f.replace(/\.json$/, '')) && f.endsWith('.json')).length;
  const writes = new Map();   // client address -> timestamps of its writes in the last minute

  const rateLimited = (who, now) => {
    const recent = (writes.get(who) ?? []).filter((t) => now - t < 60_000);
    if (recent.length >= limits.writesPerMinute) { writes.set(who, recent); return true; }
    recent.push(now);
    writes.set(who, recent);
    return false;
  };

  const server = http.createServer(async (req, res) => {
    const cors = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET, PUT, OPTIONS', 'access-control-allow-headers': 'content-type', 'access-control-max-age': '86400' };
    const send = (status, body) => {
      res.writeHead(status, { ...cors, 'content-type': typeof body === 'string' ? 'text/plain; charset=utf-8' : 'application/json' });
      res.end(typeof body === 'string' ? body : JSON.stringify(body));
    };
    try {
      const url = new URL(req.url, 'http://x');
      if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
      if (req.method === 'GET' && url.pathname === '/') return send(200, 'Aiwa archive node. GET /v1/status, GET /v1/backup/<domain>, PUT /v1/backup.\n');
      if (req.method === 'GET' && url.pathname === '/v1/status') return send(200, { ok: true, domains, version });
      const match = /^\/v1\/backup\/([0-9a-f]{64})$/.exec(url.pathname);
      if (req.method === 'GET' && match) {
        const file = fileOf(match[1]);
        if (!existsSync(file)) return send(404, { error: 'no backup for this domain' });
        res.writeHead(200, { ...cors, 'content-type': 'application/json' });
        return res.end(readFileSync(file));
      }
      if (req.method === 'PUT' && url.pathname === '/v1/backup') {
        const now = Date.now();
        if (rateLimited(req.socket.remoteAddress ?? '?', now)) return send(429, { error: 'too many writes: slow down' });
        let size = 0;
        const chunks = [];
        for await (const chunk of req) {
          size += chunk.length;
          if (size > limits.maxBytes) return send(413, { error: `a backup is at most ${limits.maxBytes} bytes` });
          chunks.push(chunk);
        }
        let backup;
        try { backup = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { return send(400, { error: 'not JSON' }); }
        const checked = await checkBackup(backup, { now, limits });
        if (checked.error) return send(400, { error: checked.error });
        const file = fileOf(backup.domain);
        let known = null;
        if (existsSync(file)) { try { known = JSON.parse(readFileSync(file, 'utf8')); } catch { known = null; } }
        if (known && (known.events?.[0]?.createdAt ?? 0) >= checked.createdAt) return send(200, { stored: false, epoch: checked.epoch, createdAt: checked.createdAt });
        if (!known && domains >= limits.maxDomains) return send(507, { error: 'this node holds as many wallets as it takes' });
        const tmp = `${file}.${process.pid}.tmp`;
        writeFileSync(tmp, JSON.stringify(backup));
        renameSync(tmp, file);
        if (!known) domains++;
        return send(200, { stored: true, epoch: checked.epoch, createdAt: checked.createdAt });
      }
      return send(404, { error: 'unknown route' });
    } catch (err) {
      return send(500, { error: 'the node failed on this request' });
    }
  });
  return server;
}
