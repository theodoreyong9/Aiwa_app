import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// The runtime of the widget of the application is refreshed from the web by its first line (see RuntimeFile in the Android client): the line must be there, and `api` must be the one the application speaks.
const text = readFileSync(fileURLToPath(new URL('../home/aiwa-home.js', import.meta.url)), 'utf8');
const kotlin = readFileSync(fileURLToPath(new URL('../../android/app/src/main/java/com/aiwa/app/home/RemoteRuntime.kt', import.meta.url)), 'utf8');

test('the runtime starts with its header: the door it is made for and its revision', () => {
  const m = /^\/\* aiwa-home-runtime api=(\d{1,4}) rev=(\d{12}) \*\//.exec(text.split('\n')[0]);
  assert.ok(m, 'first line: /* aiwa-home-runtime api=N rev=YYYYMMDDHHMM */');
  assert.equal(Number(m[1]), Number(/const val API = (\d+)/.exec(kotlin)[1]), 'the api of the file is the one of the application');
  const rev = String(m[2]);
  assert.ok(rev.startsWith('20') && Number(rev.slice(4, 6)) <= 12, 'a date');
});

test('the runtime says it started, which is what the application checks before it keeps a file of the web', () => {
  assert.ok(text.includes('window.__aiwaHome'));
  assert.ok(text.includes('window.aiwa = {'));
});
