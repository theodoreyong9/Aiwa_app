import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { generateIdentity, buildCheckpointEvent, initialWalletState, serializeWalletState, createEvent } from 'aiwa-core';
import { createArchiveServer, checkBackup } from '../src/archive-server.js';
import { pushBackup, fetchBackup, pushToNodes, fetchFromNodes, normalizeNodeUrl } from '../src/archive.js';

// An archive node: holds, per domain, the latest backup (a checkpoint signed by the wallet's own key), and hands it back.
// A HTTP server on a local port, signatures; nothing is stubbed.

async function backupOf(identity, { epoch = 0, createdAt, domain = identity.id } = {}) {
  const state = initialWalletState();
  if (epoch) state.accrual.progression.domains[identity.id] = { epoch, lastId: null, vdfOutput: 'ab' };
  const event = await buildCheckpointEvent(identity, { logDomain: 'aiwa', parents: [], coveredHeads: [], walletState: state });
  const made = createdAt === undefined ? event : await resign(identity, event, createdAt);
  return { version: 1, kind: 'aiwa-backup', domain, address: 'addr', createdAt: made.createdAt, epoch, events: [made] };
}
// a checkpoint with another time: built again (the id and the signature cover the time)
async function resign(identity, event, createdAt) {
  const realNow = Date.now;
  Date.now = () => createdAt;
  try { return await buildCheckpointEvent(identity, { logDomain: 'aiwa', parents: [], coveredHeads: [], walletState: await stateOf(event) }); } finally { Date.now = realNow; }
}
async function stateOf(event) {
  const { checkpointWalletState } = await import('aiwa-core');
  return checkpointWalletState(event);
}

async function node(options = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'aiwa-node-'));
  const server = createArchiveServer({ dir, ...options });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${server.address().port}`;
  return { dir, server, url, close: () => { server.closeAllConnections(); server.close(); rmSync(dir, { recursive: true, force: true }); } };
}

test('a wallet\'s backup goes in and comes back, and the node says what it holds', async () => {
  const n = await node();
  try {
    const who = await generateIdentity();
    const backup = await backupOf(who, { epoch: 7 });
    assert.equal(await fetchBackup(n.url, who.id), null, 'nothing yet');
    const put = await pushBackup(n.url, backup);
    assert.deepEqual([put.stored, put.epoch], [true, 7], 'the epoch is read from the checkpoint, not taken on the wallet\'s word');
    assert.deepEqual(await fetchBackup(n.url, who.id), backup);
    const status = await (await fetch(`${n.url}/v1/status`)).json();
    assert.deepEqual([status.ok, status.domains], [true, 1]);
  } finally { n.close(); }
});

test('only the owner of a key can write that key\'s backup: forged, altered or foreign ones are refused', async () => {
  const n = await node();
  try {
    const alice = await generateIdentity(); const mallory = await generateIdentity();
    const good = await backupOf(alice, { epoch: 3 });
    // mallory signs a checkpoint and says it is alice's
    const foreign = await backupOf(mallory, { epoch: 99, domain: alice.id });
    await assert.rejects(pushBackup(n.url, foreign), /made by the domain itself/);
    // alice's checkpoint with its state altered after signing
    const tampered = structuredClone(good);
    tampered.events[0].payload.walletState = tampered.events[0].payload.walletState.replace('"epoch":3', '"epoch":3000');
    await assert.rejects(pushBackup(n.url, tampered), /does not verify/);
    // not a backup, two events, not a checkpoint, not JSON
    await assert.rejects(pushBackup(n.url, { kind: 'nope' }), /not an Aiwa backup/);
    await assert.rejects(pushBackup(n.url, { ...good, events: [good.events[0], good.events[0]] }), /exactly one event/);
    const note = await createEvent(alice, { domain: 'aiwa', parents: [], type: 'note', payload: {} });
    await assert.rejects(pushBackup(n.url, { ...good, events: [note] }), /must be a checkpoint/);
    const raw = await fetch(`${n.url}/v1/backup`, { method: 'PUT', body: '{nope' });
    assert.equal(raw.status, 400);
    assert.equal(await fetchBackup(n.url, alice.id), null, 'nothing was kept');
    // and the one still goes in
    assert.equal((await pushBackup(n.url, good)).stored, true);
  } finally { n.close(); }
});

test('the most recent backup wins; an older one, replayed, changes nothing', async () => {
  const n = await node();
  try {
    const who = await generateIdentity();
    const t = Date.now();
    const older = await backupOf(who, { epoch: 2, createdAt: t - 60_000 });
    const newer = await backupOf(who, { epoch: 5, createdAt: t - 1_000 });
    assert.equal((await pushBackup(n.url, older)).stored, true);
    assert.equal((await pushBackup(n.url, newer)).stored, true);
    assert.equal((await pushBackup(n.url, older)).stored, false, 'replaying an old one does not roll the wallet back');
    assert.equal((await fetchBackup(n.url, who.id)).epoch, 5);
    const future = await backupOf(who, { epoch: 6, createdAt: t + 3_600_000 });
    await assert.rejects(pushBackup(n.url, future), /in the future/);
  } finally { n.close(); }
});

test('limits: a big body, too many writes, too many wallets', async () => {
  const n = await node({ limits: { maxBytes: 2000, maxDomains: 1, writesPerMinute: 3, futureSkewMs: 600000 } });
  try {
    const big = await fetch(`${n.url}/v1/backup`, { method: 'PUT', body: 'x'.repeat(5000) });
    assert.equal(big.status, 413);
    const a = await generateIdentity(); const b = await generateIdentity();
    await pushBackup(n.url, await backupOf(a));
    await assert.rejects(pushBackup(n.url, await backupOf(b)), /as many wallets as it takes/);
    const limited = await fetch(`${n.url}/v1/backup`, { method: 'PUT', body: '{}' });
    assert.equal(limited.status, 429, 'the fourth write in a minute');
  } finally { n.close(); }
});

test('browsers may call it (CORS), and what is kept survives a restart', async () => {
  const n = await node();
  try {
    const pre = await fetch(`${n.url}/v1/backup`, { method: 'OPTIONS' });
    assert.equal(pre.status, 204);
    assert.equal(pre.headers.get('access-control-allow-origin'), '*');
    assert.match(pre.headers.get('access-control-allow-methods'), /PUT/);
    const who = await generateIdentity();
    await pushBackup(n.url, await backupOf(who, { epoch: 4 }));
    // a second node on the same directory: what was written is there
    const again = createArchiveServer({ dir: n.dir });
    await new Promise((r) => again.listen(0, '127.0.0.1', r));
    try {
      const got = await fetchBackup(`http://127.0.0.1:${again.address().port}`, who.id);
      assert.equal(got.epoch, 4);
      assert.deepEqual(readdirSync(n.dir), [`${who.id}.json`], 'one file per wallet, no leftovers');
    } finally { again.closeAllConnections(); again.close(); }
  } finally { n.close(); }
});

test('several nodes: pushed to all, the most recent answer wins, a node that is down is skipped', async () => {
  const one = await node(); const two = await node();
  try {
    const who = await generateIdentity();
    const t = Date.now();
    await pushBackup(one.url, await backupOf(who, { epoch: 2, createdAt: t - 60_000 }));      // this node is behind
    const dead = 'http://127.0.0.1:1';
    const pushed = await pushToNodes([one.url, two.url, dead], await backupOf(who, { epoch: 6, createdAt: t - 1_000 }));
    assert.equal(pushed.ok.length, 2);
    assert.equal(pushed.failed.length, 1);
    assert.equal(pushed.failed[0].node, dead);
    await pushBackup(one.url, await backupOf(who, { epoch: 2, createdAt: t - 60_000 })).catch(() => {});
    const got = await fetchFromNodes([dead, one.url, two.url], who.id);
    assert.equal(got.backup.epoch, 6);
    assert.equal(await fetchFromNodes([dead], who.id), null, 'none holds one');
  } finally { one.close(); two.close(); }
});

test('an address typed by hand is checked: https, or http on a local network only', () => {
  assert.equal(normalizeNodeUrl('https://abc.trycloudflare.com/'), 'https://abc.trycloudflare.com');
  assert.equal(normalizeNodeUrl('http://192.168.1.20:8787/path'), 'http://192.168.1.20:8787');
  assert.equal(normalizeNodeUrl('http://localhost:8787'), 'http://localhost:8787');
  assert.throws(() => normalizeNodeUrl('http://example.com'), /https/);
  assert.throws(() => normalizeNodeUrl('ftp://example.com'), /https/);
  assert.throws(() => normalizeNodeUrl('not an address'), /not an address/);
});

test('checkBackup is pure: the same verdicts without a server', async () => {
  const who = await generateIdentity();
  const ok = await checkBackup(await backupOf(who, { epoch: 9 }));
  assert.equal(ok.epoch, 9);
  assert.match((await checkBackup(null)).error, /not an Aiwa backup/);
});
