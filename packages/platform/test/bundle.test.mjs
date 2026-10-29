import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateIdentity, EventLog, createMemoryBackend } from 'aiwa-core';
import { publishBundle, readBundle, latestBundle, listBundlesByAuthor } from '../src/bundle.js';

test('publish/read round-trips a multi-file bundle', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();
  const { manifestEventId } = await publishBundle(identity, log, 'sample-app', {
    name: 'sample-app', version: '1.0.0',
    files: [
      { path: 'index.html', content: '<!doctype html><html></html>' },
      { path: 'css/style.css', content: 'body { margin: 0; }' },
      { path: 'js/app.js', content: 'console.log("hello");' },
    ],
  });

  const bundle = await readBundle(log, manifestEventId);
  assert.equal(bundle.name, 'sample-app');
  assert.equal(bundle.version, '1.0.0');
  assert.equal(bundle.files['index.html'], '<!doctype html><html></html>');
  assert.equal(bundle.files['css/style.css'], 'body { margin: 0; }');
  assert.equal(bundle.files['js/app.js'], 'console.log("hello");');
});

test('THE DEDUP PROPERTY: an unchanged file across two versions is published exactly once, never retransmitted or duplicated', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();

  const v1 = await publishBundle(identity, log, 'sample-app', {
    name: 'sample-app', version: '1.0.0',
    files: [
      { path: 'index.html', content: '<html>v1</html>' },
      { path: 'css/style.css', content: 'body { margin: 0; }' }, // unchanged in v2
    ],
  });

  const v2 = await publishBundle(identity, log, 'sample-app', {
    name: 'sample-app', version: '2.0.0',
    files: [
      { path: 'index.html', content: '<html>v2</html>' }, // changed content
      { path: 'css/style.css', content: 'body { margin: 0; }' }, // byte-identical to v1
    ],
  });

  assert.equal(v1.fileEventIds['css/style.css'], v2.fileEventIds['css/style.css'], 'the identical file content must reuse the identical event id, never a new one');
  assert.notEqual(v1.fileEventIds['index.html'], v2.fileEventIds['index.html'], 'genuinely changed content must be a genuinely new event');

  // The unchanged file's own event was appended exactly once — appending
  // it "again" during v2's publish is EventLog.append's own no-op.
  const allIds = await log.backend.allIds();
  const cssEventCount = allIds.filter((id) => id === v1.fileEventIds['css/style.css']).length;
  assert.equal(cssEventCount, 1);
});

test('latestBundle resolves to the most recently published version', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();
  await publishBundle(identity, log, 'sample-app', { name: 'sample-app', version: '1.0.0', files: [{ path: 'a.js', content: 'v1' }] });
  await publishBundle(identity, log, 'sample-app', { name: 'sample-app', version: '2.0.0', files: [{ path: 'a.js', content: 'v2' }] });

  const latest = await latestBundle(log, 'sample-app');
  assert.equal(latest.version, '2.0.0');
  assert.equal(latest.files['a.js'], 'v2');
});

test('latestBundle returns null when nothing has been published yet for that domain', async () => {
  const log = new EventLog();
  assert.equal(await latestBundle(log, 'ghost-domain'), null);
});

test('latestBundle scopes strictly by domain — another domain\'s published bundle is invisible', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();
  await publishBundle(identity, log, 'sample-app', { name: 'sample-app', version: '1.0.0', files: [{ path: 'a.js', content: 'x' }] });
  assert.equal(await latestBundle(log, 'other-app'), null);
});

test('SECURITY: two concurrent, competing manifests (a fork) are surfaced, never silently resolved for the caller', async () => {
  const identityA = await generateIdentity();
  const identityB = await generateIdentity();

  // Two independent peers — neither has ever seen the other's
  // history, so neither manifest chains from the other.
  const logA = new EventLog();
  await publishBundle(identityA, logA, 'sample-app', { name: 'sample-app', version: '2.0.0-a', files: [{ path: 'a.js', content: 'variant-a' }] });

  const logB = new EventLog();
  await publishBundle(identityB, logB, 'sample-app', { name: 'sample-app', version: '2.0.0-b', files: [{ path: 'a.js', content: 'variant-b' }] });

  // A merge — the exact shape a Replicator sync between them produces.
  const mergedLog = new EventLog();
  const allA = await Promise.all((await logA.backend.allIds()).map((id) => logA.get(id)));
  const allB = await Promise.all((await logB.backend.allIds()).map((id) => logB.get(id)));
  await mergedLog.appendMany([...allA, ...allB]);

  await assert.rejects(latestBundle(mergedLog, 'sample-app'), /Multiple, unresolved manifest heads/);
});

test('readBundle returns null (an honest "not fully synced"), never a corrupted partial result, for a manifest whose files haven\'t all arrived', async () => {
  const identity = await generateIdentity();
  const sourceLog = new EventLog();
  const { manifestEventId } = await publishBundle(identity, sourceLog, 'sample-app', {
    name: 'sample-app', version: '1.0.0',
    files: [{ path: 'a.js', content: 'x' }, { path: 'b.js', content: 'y' }],
  });

  // A partial peer: has the manifest, but only one of the two files.
  const partialLog = new EventLog();
  const manifestEvent = await sourceLog.get(manifestEventId);
  const aEvent = await sourceLog.get(manifestEvent.payload.files['a.js']);
  await partialLog.append(aEvent);
  // manifestEvent itself can't even be appended yet (missing parent b.js) — appendMany would throw; readBundle must be given the id regardless and handle it gracefully.
  assert.equal(await readBundle(partialLog, manifestEventId), null);
});

// Regression test for an EventLog.head() bug (fixed in aiwa-core):
// a fresh EventLog constructed over an already-populated backend
// — exactly what a service worker restart or a page reload does
// against IndexedDB — used to report every past manifest as a
// "head" too, not just the latest one, so latestBundle() threw a false
// "fork" error after any restart of a domain with more than one
// linearly-published version. Two versions, then a brand
// new EventLog over the same backend, must still resolve cleanly.
test('latestBundle resolves the latest version from a FRESH EventLog instance after a restart, even with prior versions in history', async () => {
  const identity = await generateIdentity();
  const backend = createMemoryBackend(); // stands in for a persisted backend surviving a restart
  const sessionOne = new EventLog(backend);
  await publishBundle(identity, sessionOne, 'sample-app', { name: 'sample-app', version: '1.0.0', files: [{ path: 'a.js', content: 'v1' }] });
  await publishBundle(identity, sessionOne, 'sample-app', { name: 'sample-app', version: '2.0.0', files: [{ path: 'a.js', content: 'v2' }] });

  const sessionTwo = new EventLog(backend); // a brand-new instance, same backend — this is the "restart"
  const bundle = await latestBundle(sessionTwo, 'sample-app');
  assert.equal(bundle.version, '2.0.0');
  assert.equal(bundle.files['a.js'], 'v2');
});

test('a bundle with no files still produces a valid, readable manifest', async () => {
  const identity = await generateIdentity();
  const log = new EventLog();
  const { manifestEventId } = await publishBundle(identity, log, 'sample-app', { name: 'sample-app', version: '0.0.1', files: [] });
  const bundle = await readBundle(log, manifestEventId);
  assert.deepEqual(bundle.files, {});
});

test('listBundlesByAuthor finds every version this author published, across different domains, needing no new protocol beyond the already-verified author field', async () => {
  const author = await generateIdentity();
  const someoneElse = await generateIdentity();
  const log = new EventLog();

  await publishBundle(author, log, 'my-token', { name: 'my-token', version: '1.0.0', files: [{ path: 'index.html', content: 'v1' }] });
  await publishBundle(author, log, 'my-token', { name: 'my-token', version: '2.0.0', files: [{ path: 'index.html', content: 'v2' }] });
  await publishBundle(author, log, 'another-contract', { name: 'another-contract', version: '1.0.0', files: [{ path: 'index.html', content: 'x' }] });
  await publishBundle(someoneElse, log, 'not-mine', { name: 'not-mine', version: '1.0.0', files: [{ path: 'index.html', content: 'y' }] });

  const mine = await listBundlesByAuthor(log, author.id);
  assert.equal(mine.length, 3, 'both real versions of my-token, plus another-contract — never someone else\'s publish');
  assert.ok(mine.every((b) => b.domain !== 'not-mine'));
  const myToken = mine.filter((b) => b.domain === 'my-token');
  assert.deepEqual(myToken.map((b) => b.version).sort(), ['1.0.0', '2.0.0']);
});

test('listBundlesByAuthor returns an empty list for an author who never published anything', async () => {
  const author = await generateIdentity();
  const log = new EventLog();
  assert.deepEqual(await listBundlesByAuthor(log, author.id), []);
});

test('SECURITY: listBundlesByAuthor never credits a publish to an author who did not really sign it', async () => {
  const realAuthor = await generateIdentity();
  const impostor = await generateIdentity();
  const log = new EventLog();
  await publishBundle(realAuthor, log, 'sample-app', { name: 'sample-app', version: '1.0.0', files: [{ path: 'a.js', content: 'x' }] });

  const asImpostor = await listBundlesByAuthor(log, impostor.id);
  assert.deepEqual(asImpostor, [], 'the impostor never signed anything — nothing is attributed to them, no matter what domain they ask about');
});
