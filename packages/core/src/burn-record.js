// A burn, as a reader can check it: the record of a FINALIZED Solana transaction that sent lamports to the
// incinerator, paid for by the domain's own key.
//
// identity-cost.js verifies such a record; it never touches the network. This file is the missing half:
// turning what Solana says about a transaction into that record (`normalizeBurnTransaction`), fetching it
// (`fetchBurnRecord`, the connection is injected), and checking that it is THIS domain's burn
// (`verifyBurnRecordFor`) — without that last check anyone could register a burn someone else made, by
// quoting its signature.
//
// The binding: a domain id is SHA-256 of an Ed25519 public key, and that same key is the domain's Solana
// address. So a burn is the domain's own when the fee payer (first account of the transaction) derives to the
// domain, and that payer's balance really went down by at least what reached the incinerator.

import { deriveId } from './identity.js';
import { SOLANA_INCINERATOR_ADDRESS, verifyBurnProof } from './identity-cost.js';
import { toHex } from './bytes.js';
import { base58Decode } from './base58.js';

const keyText = (key) => (typeof key === 'string' ? key : key.toBase58());

/**
 * The record of a burn from what Solana's `getTransaction` returned (web3.js's TransactionResponse, or the same
 * shape with string keys). `null` in, `null` out: an unknown or not-yet-finalized transaction proves nothing.
 * `options.creatorAddress` (the deployment's creator fee address, if any): what reached it in this transaction is recorded as
 * `creatorBalanceDeltaLamports` (0 if the address is not in the transaction, or lost money).
 * @returns {{ signature: string, err: object | null, incineratorBalanceDeltaLamports: number, creatorBalanceDeltaLamports: number, commitment: 'finalized', slot: number | null, payerPubkey: string, payerSpentLamports: number } | null}
 */
export function normalizeBurnTransaction(rpcTransaction, signature, { creatorAddress } = {}) {
  if (!rpcTransaction) return null;
  const message = rpcTransaction.transaction?.message ?? {};
  const meta = rpcTransaction.meta ?? {};
  const loaded = meta.loadedAddresses ?? {};
  const keys = [...(message.accountKeys ?? message.staticAccountKeys ?? []), ...(loaded.writable ?? []), ...(loaded.readonly ?? [])].map(keyText);
  const pre = meta.preBalances ?? [];
  const post = meta.postBalances ?? [];
  const incinerator = keys.indexOf(SOLANA_INCINERATOR_ADDRESS);
  const delta = incinerator >= 0 ? post[incinerator] - pre[incinerator] : 0;
  const creator = creatorAddress ? keys.indexOf(creatorAddress) : -1;
  const creatorDelta = creator >= 0 ? post[creator] - pre[creator] : 0;
  return {
    signature,
    err: meta.err ?? null,
    incineratorBalanceDeltaLamports: Number.isFinite(delta) ? delta : 0,
    creatorBalanceDeltaLamports: Number.isFinite(creatorDelta) && creatorDelta > 0 ? creatorDelta : 0,
    commitment: 'finalized', // the only commitment fetchBurnRecord asks for
    slot: rpcTransaction.slot ?? null,
    payerPubkey: keys.length > 0 ? toHex(base58Decode(keys[0])) : '',
    payerSpentLamports: keys.length > 0 && Number.isFinite(pre[0] - post[0]) ? pre[0] - post[0] : 0,
  };
}

/**
 * Asks Solana (through `connection`, a web3.js Connection or anything with the same getTransaction) for the
 * FINALIZED transaction `signature`, and returns its burn record — or null if Solana does not know it (yet).
 */
export async function fetchBurnRecord(connection, signature, options = {}) {
  const rpcTransaction = await connection.getTransaction(signature, { commitment: 'finalized', maxSupportedTransactionVersion: 0 });
  return normalizeBurnTransaction(rpcTransaction, signature, options);
}

/**
 * Is `record` a burn, made by `domain`'s own key? (verifyBurnProof: finalized, no error, positive amount;
 * plus the binding described at the top.)
 * @returns {Promise<{ valid: boolean, reason?: string }>}
 */
export async function verifyBurnRecordFor(domain, record, { minLamports = 0 } = {}) {
  if (!record) return { valid: false, reason: 'no transaction record' };
  const check = verifyBurnProof(record, { minLamports });
  if (!check.valid) return check;
  if (typeof record.payerPubkey !== 'string' || !/^[0-9a-f]{64}$/.test(record.payerPubkey)) return { valid: false, reason: 'the record does not name who paid' };
  const bytes = Uint8Array.from(record.payerPubkey.match(/../g).map((h) => parseInt(h, 16)));
  if ((await deriveId(bytes)) !== domain) return { valid: false, reason: "the burn was not paid by this domain's own key" };
  if (!(record.payerSpentLamports >= record.incineratorBalanceDeltaLamports + (record.creatorBalanceDeltaLamports ?? 0))) return { valid: false, reason: "the payer's balance did not go down by what was burned and paid to the creator" };
  return { valid: true };
}
