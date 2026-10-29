// A wallet's burns: the irreversible spend on Solana that backs its commitments, and the confirmation of burns against
// Solana's own record of them (what a burn is worth is what Solana says, never what an event says).

import {
  loadSolanaWeb3, keypairFromSecretKey, broadcastBurnTransaction, fetchBurnRecord, verifyBurnRecordFor, creatorFeeLamports, burnQuote,
} from 'aiwa-core';
import { collectAncestors } from './ancestors.js';
import { checkPatienceRate } from './mining.js';

export class Burns {
  constructor(wallet) {
    this.wallet = wallet;
  }

  get _creatorAddress() {
    return this.wallet.rewardParams.creatorFee?.address;
  }

  /** The solanaWeb3.Keypair, for an on-chain call; @solana/web3.js is loaded only when needed. */
  async solanaKeypair() {
    this.wallet.requireConnected();
    return keypairFromSecretKey(await loadSolanaWeb3(), this.wallet.keypair.secretKey);
  }

  /** On-chain SOL balance in lamports. `connection` is a solanaWeb3.Connection the caller provides: this library never picks an RPC endpoint. */
  async solBalance(connection) {
    return connection.getBalance((await this.solanaKeypair()).publicKey);
  }

  /** What a burn of `lamports` at patience rate `T` would do: paid to the creator, burned, counted as capital. Show it before the user burns. */
  quote(lamports, T = 0) {
    checkPatienceRate(T);
    return burnQuote({ lamports, T, creatorFee: this.wallet.rewardParams.creatorFee });
  }

  /**
   * An irreversible burn to Solana's incinerator, committing the capital it covers in the same action: the key that
   * holds the SOL is the key AIWA accrues to, so there is no separate step to forget. This burn REPLACES the position
   * (the previous one is paid first, by the reducer); the capital that counts is what is left after T of it is
   * destroyed. A fixed part of the T share goes to the creator address, in the same transaction. Returns the signature.
   */
  async burn(lamports, connection, { T = 0 } = {}) {
    // Checked BEFORE anything is broadcast: a refusal after an irreversible burn is too late.
    checkPatienceRate(T);
    const creatorFee = this.wallet.rewardParams.creatorFee;
    const signature = await broadcastBurnTransaction(await loadSolanaWeb3(), connection, await this.solanaKeypair(), lamports, {
      creatorAddress: creatorFee?.address, creatorFeeLamports: creatorFeeLamports(lamports, T, creatorFee),
    });
    const { lamports: burned } = await this.record(signature, connection);
    await this.wallet.recordCommitment({ b: Math.floor(burned * (1 - T)) / 1e9, T });
    return signature;
  }

  /**
   * Asks Solana for the FINALIZED transaction `signature`, checks that it is a burn paid by this wallet's own key and,
   * only then, publishes it ('burn-record': the signature, nothing else) so that the capital it covers can be
   * committed. burn() does this; call it yourself to finish a burn that was broadcast but not yet finalized.
   */
  async record(signature, connection = this.wallet.connection) {
    const { wallet } = this;
    wallet.requireConnected();
    if (!connection) throw new Error('AIWA: recordBurn needs a Solana connection.');
    const record = await fetchBurnRecord(connection, signature, { creatorAddress: this._creatorAddress });
    if (!record) throw new Error(`AIWA: Solana does not report ${signature} as a finalized transaction (yet) — call recordBurn(signature, connection) again later.`);
    const check = await verifyBurnRecordFor(wallet.identity.id, record);
    if (!check.valid) throw new Error(`AIWA: ${signature} is not a burn by this wallet: ${check.reason}`);
    wallet.ledger.noteBurnRecords({ [signature]: record });
    const event = await wallet.ledger.append(wallet.identity, 'burn-record', { domain: wallet.identity.id, signature });
    await wallet.publish([event.id]);
    // `lamports`: what this burn covers in all (burned + paid to the creator); the capital it backs is computed from it.
    return { eventId: event.id, lamports: record.incineratorBalanceDeltaLamports + record.creatorBalanceDeltaLamports, toCreator: record.creatorBalanceDeltaLamports };
  }

  /**
   * Confirms against Solana the burns that events in the log point at ('burn-record' events, from any domain) and this
   * wallet has not confirmed yet. A burn Solana does not know (yet) stays pending, and the commitment it would cover
   * stays uncredited until a later call.
   * @returns {Promise<{ confirmed: string[], pending: string[] }>}
   */
  async confirm(connection = this.wallet.connection) {
    const { ledger } = this.wallet;
    if (!connection) throw new Error('AIWA: confirmBurns needs a Solana connection.');
    const wire = await collectAncestors(ledger.log, await ledger.log.head(), { tolerant: true });
    const wanted = [...new Set(wire.filter((e) => e.type === 'burn-record' && typeof e.payload?.signature === 'string').map((e) => e.payload.signature))];
    const confirmed = [];
    const pending = [];
    const found = {};
    for (const signature of wanted) {
      if (ledger.burnRecords[signature]) continue;
      let record = null;
      try { record = await fetchBurnRecord(connection, signature, { creatorAddress: this._creatorAddress }); } catch { /* unreachable: stays pending */ }
      if (record) { found[signature] = record; confirmed.push(signature); } else pending.push(signature);
    }
    if (confirmed.length > 0) ledger.noteBurnRecords(found);
    return { confirmed, pending };
  }
}
