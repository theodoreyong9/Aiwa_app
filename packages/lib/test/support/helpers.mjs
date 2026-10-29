// A real wallet (aiwa-lib) and a Solana stand-in that really decodes the transaction the
// wallet built and keeps its own balances — the same shape as aiwa-lib's own tests use.
import * as solanaWeb3 from '@solana/web3.js';
import { ed25519 } from '@noble/curves/ed25519.js';
import { base58Encode } from 'aiwa-core';
import { AIWA } from 'aiwa-lib';

globalThis.window = { solanaWeb3 };

export const CREATOR = base58Encode(ed25519.getPublicKey(ed25519.utils.randomSecretKey()));

export const deployment = {
  rewardParams: { alpha: 1.1, beta: 2.2, gamma: 3, C: Math.pow(33, 3), minQ: 1, epochIterations: 150, creatorFee: { address: CREATOR, rateOfT: 0.001 } },
};

export function fakeSolana() {
  const transactions = {};
  let count = 0;
  return {
    transactions,
    getLatestBlockhash: async () => ({ blockhash: '11111111111111111111111111111111', lastValidBlockHeight: 1 }),
    sendRawTransaction: async (raw) => {
      const tx = solanaWeb3.Transaction.from(raw);
      const keys = [tx.feePayer.toBase58()];
      const transfers = tx.instructions.map((ix) => {
        const d = solanaWeb3.SystemInstruction.decodeTransfer(ix);
        return { from: d.fromPubkey.toBase58(), to: d.toPubkey.toBase58(), lamports: Number(d.lamports) };
      });
      for (const t of transfers) for (const k of [t.from, t.to]) if (!keys.includes(k)) keys.push(k);
      const pre = keys.map((_, i) => (i === 0 ? 50e9 : 0));
      const post = [...pre];
      for (const t of transfers) { post[keys.indexOf(t.from)] -= t.lamports; post[keys.indexOf(t.to)] += t.lamports; }
      post[0] -= 5000;
      const signature = `sig${++count}`;
      transactions[signature] = { rpc: { slot: 10, transaction: { message: { accountKeys: keys } }, meta: { err: null, fee: 5000, preBalances: pre, postBalances: post } } };
      return signature;
    },
    confirmTransaction: async () => ({}),
    getTransaction: async (signature) => transactions[signature]?.rpc ?? null,
  };
}

/** A connected wallet that burned `sol` at patience rate T and mined `epochs` epochs. */
export async function minedWallet(connection, { sol = 1, T = 0, epochs = 3 } = {}) {
  const aiwa = new AIWA({ rewardParams: deployment.rewardParams });
  await aiwa.connect();
  await aiwa.burn(Math.round(sol * 1e9), connection, { T });
  if (epochs > 0) await aiwa.advanceProgress({ epochs });
  return aiwa;
}

export const HTML = (title = 'hello') => `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title></head><body><h1>${title}</h1></body></html>`;
