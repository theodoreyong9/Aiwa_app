// The AIWA wallet: what a wallet UI or an app calls. It composes aiwa-core's reducers and aiwa-platform's transport into
// the handful of calls a wallet needs: connect, address, balance, claim, send, receive (including fully offline, by
// QR/NFC/Bluetooth), burn, backup. Every financial rule lives in aiwa-core, tested there; this only orchestrates.
//
//   ledger.js      the log and the state folded from it
//   mining.js      commitments, progression, claims
//   burns.js       burning on Solana, confirming burns
//   payments.js    send, offline bundles, vouchers          channel.js   "sign once, click many times"
//   observer.js    the Mirror, and where other domains stand
//   backup.js      checkpoints, backups, archive nodes      evidence.js  what an app verifies a wallet by
//
// One Ed25519 keypair is BOTH the Solana address and the AIWA identity. connect()/disconnect() unlock and clear that
// keypair in memory; joinNetwork()/leaveNetwork() are a separate thing, a live peer-to-peer session. The wallet's own
// synced data (address, balance, claimable) is readable offline, connected to the network or not.
//
// `rewardParams` are the deployment's own economic parameters: this library never invents a default for them.

import {
  fromUnits, spendableClaims, totalBalance, claimableNow, lightweightKeypairFromSecretKey, deriveKeypairFromPassphrase,
  deriveKeypairFromBip39Mnemonic, generateBip39Mnemonic, toIdentity, base58Encode,
} from 'aiwa-core';
import { Replicator } from 'aiwa-platform';
import { collectAncestors } from './ancestors.js';
import { Ledger } from './ledger.js';
import { Mining } from './mining.js';
import { Burns } from './burns.js';
import { Observer } from './observer.js';
import { Backup } from './backup.js';
import { exportMiningEvents, witnesses, submissionEvidence } from './evidence.js';
import { ownActor, pay, payOffline, issueVoucher, redeemVoucher } from './payments.js';
import { openChannel, requestChannel, acceptChannelRequest } from './channel.js';

export class AIWA {
  constructor({ rewardParams, logDomain = 'aiwa', dbName, backend, autoObserve = true, connection = null, miningArchive, keepMiningHistory = true } = {}) {
    if (!rewardParams) {
      throw new Error('AIWA: rewardParams ({alpha, beta, gamma, C, minQ}) is required — this library never invents a deployment\'s own economic parameters.');
    }
    this.rewardParams = rewardParams;
    this.logDomain = logDomain;
    this.ledger = new Ledger({ rewardParams, logDomain, dbName, backend, miningArchive, keepMiningHistory });
    this.keypair = null;
    this.identity = null;
    this.replicator = null;
    // Mirror: when events from another domain arrive, sign a reception commitment for them. On by default, because the
    // Mirror is meant to be continuous; turn it off to call observe() yourself. `onObserveError` hears what a
    // background observe() could not do.
    this.autoObserve = autoObserve;
    this.onObserveError = null;
    // A Solana Connection: lets the wallet confirm burns by itself when events arrive. Otherwise call confirmBurns(connection).
    this.connection = connection;
    this.miner = new Mining(this);
    this.burns = new Burns(this);
    this.observer = new Observer(this);
    this.backup = new Backup(this);
  }

  /** The wallet's event log. */
  get log() { return this.ledger.log; }

  /** Optional (current, total) => void, called while a potentially large backlog is folded: for a "catching up…" indicator. */
  get onMaterializeProgress() { return this.ledger.onProgress; }
  set onMaterializeProgress(fn) { this.ledger.onProgress = fn; }

  // --- Keys, fully offline ---

  /**
   * Derives or generates the keypair this wallet signs with: no network, no @solana/web3.js. With nothing given, a NEW
   * identity is made from a fresh 12-word recovery phrase, readable as `recoveryPhrase` while connected: write it down,
   * it is the only way to be this identity again (the same address a Solana wallet derives from those words). With a
   * passphrase there is no phrase to show; with a raw secret key, `recoveryKey` is that key in base58.
   */
  async connect({ mnemonic, passphrase, secretKeyBytes } = {}) {
    let keypair;
    let phrase = null;
    let key = null;
    if (secretKeyBytes) {
      keypair = await lightweightKeypairFromSecretKey(secretKeyBytes);
      key = base58Encode(keypair.secretKey);
    } else if (passphrase) {
      keypair = await deriveKeypairFromPassphrase(passphrase);
    } else {
      phrase = (mnemonic ? mnemonic : await generateBip39Mnemonic(12)).trim().replace(/\s+/g, ' ').toLowerCase();
      keypair = await deriveKeypairFromBip39Mnemonic(phrase);
    }
    this._recoveryPhrase = phrase;
    this._recoveryKey = key;
    this.keypair = keypair;
    this.identity = await toIdentity(keypair);
    this.ledger.domainId = this.identity.id;
    return { address: this.address, identityId: this.identity.id };
  }

  /** Clears the keypair from memory. The synced log stays, and stays readable. */
  async disconnect() {
    await this.leaveNetwork();
    this.miner.stopLoop();
    this.backup.stopAutoCheckpoint();
    this.backup.stopAutoArchive();
    this.keypair = null;
    this._recoveryPhrase = null;
    this._recoveryKey = null;
    this.identity = null;
  }

  /** The recovery phrase while connected (see connect()), or null when the wallet was not made from one. Secret: whoever has it controls the wallet. */
  get recoveryPhrase() { return this._recoveryPhrase ?? null; }

  /** For a wallet connected from a raw secret key: that key, base58, as Solana wallets export it. Null otherwise. Secret, like the phrase. */
  get recoveryKey() { return this._recoveryKey ?? null; }

  get connected() { return !!this.identity; }
  get address() { return this.keypair ? this.keypair.publicKey.toBase58() : null; }

  requireConnected() {
    if (!this.identity) throw new Error('AIWA: not connected — call connect() first.');
  }

  /** The wallet state folded from the log (accrual, claims, burns). */
  walletState() { return this.ledger.state(); }

  /** Publishes `ids` with their ancestors to every connected peer (a peer lacking the history could not append a bare event). */
  async publish(ids) {
    if (this.replicator) await this.replicator.publish(await collectAncestors(this.ledger.log, ids));
  }

  // --- Balances (decimal strings) ---

  /** The AIWA balance: what is claimable, plus the spendable claims already made. */
  async balance() {
    this.requireConnected();
    return fromUnits(totalBalance(this.rewardParams, await this.ledger.state(), this.identity.id));
  }

  /**
   * What can be sent right now: the active claims already made. balance() also counts claimable() — value accrued but
   * not yet moved into a claim, which cannot be sent until claim()ed.
   */
  async spendableBalance() {
    this.requireConnected();
    const claims = spendableClaims(await this.ledger.state(), this.identity.id);
    return fromUnits(claims.reduce((sum, c) => sum + c.amount, 0n));
  }

  /** What is claimable from the accrued position, not yet moved into a spendable claim. */
  async claimable() {
    this.requireConnected();
    return fromUnits(claimableNow(this.rewardParams, (await this.ledger.state()).accrual, this.identity.id));
  }

  // --- Mining ---

  recordCommitment(options) { return this.miner.recordCommitment(options); }
  advanceProgress(options) { return this.miner.advance(options); }
  startProgressLoop(options) { this.miner.startLoop(options); }
  stopProgressLoop() { this.miner.stopLoop(); }
  claim(amount) { return this.miner.claim(amount); }
  mining() { return this.miner.state(); }
  ranking() { return this.miner.ranking(); }

  // --- Burns (Solana) ---

  solanaKeypair() { return this.burns.solanaKeypair(); }
  solBalance(connection) { return this.burns.solBalance(connection); }
  burn(lamports, connection, options) { return this.burns.burn(lamports, connection, options); }
  burnQuote(lamports, T) { return this.burns.quote(lamports, T); }
  recordBurn(signature, connection) { return this.burns.record(signature, connection); }
  confirmBurns(connection) { return this.burns.confirm(connection); }

  // --- The Mirror ---

  observe() { return this.observer.observe(); }
  settled() { return this.observer.settled(); }
  position(domain, options) { return this.observer.position(domain, options); }
  standing(domain) { return this.observer.standing(domain); }
  standings() { return this.observer.standings(); }
  /** The other domains this wallet holds proof against: two signed histories of one domain (a fork). See Observer.accusations(). */
  accusations() { return this.observer.accusations(); }

  // --- Checkpoints, backups, archive nodes ---

  checkpoint() {
    this.requireConnected();
    return this.ledger.checkpoint(this.identity);
  }

  pruneToLastCheckpoint() { return this.ledger.pruneToCheckpoint(); }
  exportBackup() { return this.backup.export(); }
  importBackup(backup) { return this.backup.import(backup); }
  adoptState(serializedState) { return this.backup.adopt(serializedState); }
  archiveNow(nodes) { return this.backup.archiveNow(nodes); }
  restoreFromArchive(nodes) { return this.backup.restoreFromArchive(nodes); }
  startAutoArchive(options) { this.backup.startAutoArchive(options); }
  stopAutoArchive() { this.backup.stopAutoArchive(); }
  startAutoCheckpoint(options) { this.backup.startAutoCheckpoint(options); }
  stopAutoCheckpoint() { this.backup.stopAutoCheckpoint(); }

  // --- What an app verifies the wallet by ---

  exportMiningEvents(options) { return exportMiningEvents(this, options); }
  witnesses(options) { return witnesses(this, options); }
  submissionEvidence(options) { return submissionEvidence(this, options); }

  // --- Payments ---

  /** Sends `amount` of claimed AIWA to `toIdentityId`, signed; splits a claim first if none matches exactly. Published to connected peers. */
  async send(toIdentityId, amount) {
    this.requireConnected();
    return pay(this, ownActor(this), toIdentityId, amount);
  }

  /** send() plus every ancestor the transfer needs: a bundle a stranger can append with no prior sync. A claim with a long history makes a larger bundle, which matters for a QR code (NFC and Bluetooth have no such ceiling). */
  async sendOfflineBundle(toIdentityId, amount) {
    this.requireConnected();
    return payOffline(this, ownActor(this), toIdentityId, amount);
  }

  /**
   * Appends an offline bundle: the same verification as any append. Not gated by connect(): appending signs nothing with
   * this wallet's key (every event is already signed by its own sender), so receiving works with the key locked.
   */
  async receiveOfflineBundle(bundle) {
    await this.ledger.log.appendMany(bundle.events);
    this.observer.schedule();
  }

  /** A bearer voucher: `amount` hash-locked behind a fresh secret. Whoever redeems it first gets the value. */
  async issueVoucher(amount) {
    this.requireConnected();
    return issueVoucher(this, ownActor(this), amount);
  }

  redeemVoucher(voucher) { return redeemVoucher(this, voucher); }

  // --- Channels ("sign once, click many times") ---

  openChannel(peerId, options) { return openChannel(this, peerId, options); }
  requestChannel(peerId) { return requestChannel(this, peerId); }
  acceptChannelRequest(requestBlob) { return acceptChannelRequest(this, requestBlob); }

  // --- The live network ---

  /** Joins a peer-to-peer session over `transport` (e.g. a WebrtcTransport) for this wallet's log domain. */
  async joinNetwork(transport) {
    this.requireConnected();
    this.replicator = new Replicator({ transport, log: this.ledger.log, domain: this.logDomain });
    // Events that just arrived from a peer: commit to having received them.
    this._unsubObserve = this.replicator.onSync(({ receivedCount }) => { if (receivedCount > 0) this.observer.schedule(); });
    await this.replicator.start();
  }

  async leaveNetwork() {
    if (!this.replicator) return;
    this._unsubObserve?.();
    this._unsubObserve = null;
    await this.replicator.stop();
    this.replicator = null;
  }
}
