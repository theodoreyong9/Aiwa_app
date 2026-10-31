import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const script = join(here, '..', 'src', 'hf-clip.py');
const python = spawnSync('python3', ['--version']).status === 0;
const need = { skip: python ? false : 'python3 is not installed here' };

/** A `gradio_client` of its own, made of a few lines: the Space answers with a file, or with a quota error. */
function fake(mode) {
  const dir = mkdtempSync(join(tmpdir(), 'hf-clip-'));
  mkdirSync(join(dir, 'gradio_client'));
  writeFileSync(join(dir, 'clip.mp4'), 'not really a video');
  writeFileSync(join(dir, 'gradio_client', '__init__.py'), `
import json, os
class Client:
    def __init__(self, space, hf_token=None):
        self.space, self.token = space, hf_token
    def predict(self, api_name=None, **kw):
        open(os.path.join(os.path.dirname(__file__), '..', 'seen.json'), 'w').write(json.dumps({'space': self.space, 'token': self.token, 'api': api_name, 'kw': kw}))
        if '${mode}' == 'quota':
            raise Exception('You have exceeded your free GPU quota (ZeroGPU)')
        return ({'video': os.path.join(os.path.dirname(__file__), '..', 'clip.mp4'), 'subtitles': None}, 42)
def handle_file(p): return p
`);
  return dir;
}
const run = (dir, args, env = {}) => spawnSync('python3', [script, ...args], { encoding: 'utf8', env: { ...process.env, PYTHONPATH: dir, ...env } });

test('hf-clip copies the video the Space returns and passes the prompt, the extra arguments and the token', need, () => {
  const d = fake('ok');
  const out = join(d, 'out', 'shot.mp4');
  const r = run(d, ['une rue au crépuscule', out, '--space', 'someone/wan-demo', '--api-name', '/generate', '--arg', 'duration=4', '--arg', 'fast=true'], { HF_TOKEN: 'hf_test' });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.ok(existsSync(out));
  const seen = JSON.parse(readFileSync(join(d, 'seen.json'), 'utf8'));
  assert.deepEqual(seen, { space: 'someone/wan-demo', token: 'hf_test', api: '/generate', kw: { prompt: 'une rue au crépuscule', duration: 4, fast: true } });
  assert.equal(JSON.parse(r.stdout).ok, true);
});

test('hf-clip says that the daily quota is reached, and that a free Hugging Face key gives more, when there is none', need, () => {
  const d = fake('quota');
  const r = run(d, ['x', join(d, 'o.mp4'), '--space', 'someone/ltx-demo'], { HF_TOKEN: '' });
  assert.equal(r.status, 3);
  const message = JSON.parse(r.stdout);
  assert.equal(message.quota, true);
  assert.match(message.message, /clé Hugging Face/);
});

test('hf-clip asks for a Space, and for the text and the file', need, () => {
  const d = fake('ok');
  assert.equal(run(d, []).status, 2);
  assert.equal(run(d, ['seul', '--space', 'a/b']).status, 2);
});
