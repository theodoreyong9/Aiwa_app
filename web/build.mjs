// Builds the web app into dist/: one ES module per page (wallet.js, voir.js, chambre.js, with chunks shared between them, one of them lazily loaded for @solana/web3.js and the QR library), the pages, their style and their icons.
//   node build.mjs [--out dist] [--deployment ../deployment.json]
// `--deployment` lets a test build use other parameters; the deployment's file is what '@deployment' resolves to.
import { build } from 'esbuild';
import { cpSync, mkdirSync, rmSync, readdirSync, statSync, copyFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, a, i, all) => (a.startsWith('--') ? [...pairs, [a.slice(2), all[i + 1]]] : pairs), []));
const out = resolve(args.out ?? join(here, 'dist'));
const deployment = resolve(args.deployment ?? join(here, '../deployment.json'));

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

await build({
  entryPoints: { wallet: join(here, 'src/main-wallet.js'), voir: join(here, 'src/main-voir.js'), chambre: join(here, 'src/main-chambre.js') },
  outdir: out,
  bundle: true,
  splitting: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2022',
  minify: true,
  legalComments: 'none',
  logLevel: 'warning',
  alias: { '@deployment': deployment },
  define: { 'process.env.NODE_ENV': '"production"', global: 'globalThis' },
});

for (const page of ['wallet.html', 'voir.html', 'chambre.html', 'style.css']) copyFileSync(join(here, 'src', page), join(out, page));
cpSync(join(here, 'public'), out, { recursive: true });
// the home of the application: the runtime that puts the buttons of the application in a profile page, served as an asset
cpSync(join(here, 'home'), join(out, 'home'), { recursive: true });

let bytes = 0;
const walk = (dir) => { for (const f of readdirSync(dir)) { const p = join(dir, f); statSync(p).isDirectory() ? walk(p) : (bytes += statSync(p).size); } };
walk(out);
console.log(`${out}: ${Math.round(bytes / 1024)} KB`);
