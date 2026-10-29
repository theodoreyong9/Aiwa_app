#!/usr/bin/env node
// Runs an Aiwa archive node. Usage:
// node node/aiwa-node.js [--port 8787] [--data ~/aiwa-node-data] [--tunnel]
// --tunnel starts a Cloudflare quick tunnel (cloudflared, if installed) and prints the public https address to give to
// wallets: a phone or a home connection has no address of its own, and wallets (pages served over https) need https.
import { spawn } from 'node:child_process';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { createArchiveServer } from '../src/archive-server.js';

const args = process.argv.slice(2);
const option = (name, fallback) => { const i = args.indexOf(`--${name}`); return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : fallback; };
const port = Number(option('port', process.env.PORT ?? 8787));
const dir = option('data', process.env.AIWA_NODE_DATA ?? join(homedir(), 'aiwa-node-data'));

const server = createArchiveServer({ dir });
server.listen(port, '0.0.0.0', () => {
  console.log(`Aiwa archive node: listening on port ${port}, backups kept in ${dir}`);
  console.log(`  on this machine: http://127.0.0.1:${port}/v1/status`);
  if (!args.includes('--tunnel')) { console.log('  to be reached from elsewhere over https, run again with --tunnel (needs cloudflared), or put it behind your own https address.'); return; }
  const tunnel = spawn('cloudflared', ['tunnel', '--no-autoupdate', '--url', `http://127.0.0.1:${port}`], { stdio: ['ignore', 'pipe', 'pipe'] });
  tunnel.on('error', () => console.log('  --tunnel needs cloudflared (Termux: pkg install cloudflared).'));
  let announced = false;
  const watch = (chunk) => {
    const found = !announced && /https:\/\/[a-z0-9-]+\.trycloudflare\.com/.exec(String(chunk));
    if (found) {
      announced = true;
      console.log(`\n  Archive node address: ${found[0]}`);
      console.log('  Paste it in the wallet: Recovery → Archive nodes → Add. It changes each time the tunnel restarts.');
    }
  };
  tunnel.stdout.on('data', watch);
  tunnel.stderr.on('data', watch);
  process.on('exit', () => tunnel.kill());
});
process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));
