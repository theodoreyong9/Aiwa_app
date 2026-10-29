// The wallet page: the phrase, the rate, the burn, what can be claimed, the claim, the history. All on aiwa-lib; nothing here decides what is valid.
// The wallet starts by itself (boot.js): this page only shows it, and asks for something when there is nothing to start from.
import { fromUnits } from 'aiwa-lib';
import { config } from './config.js';
import { session, connected } from './session.js';
import { startWallet, solanaConnection } from './wallet-life.js';
import { bootWallet, runWallet, onWalletChange } from './boot.js';
import { secretsAreSafe, deleteSecret } from './keys.js';
import { $, short, showError } from './ui.js';
import { initCoffee } from './coffee.js';

const ACK = 'aiwa-phrase-written';
const DEVNET = /devnet/i.test(config.rpc ?? '');
let starting = true;
let timer = null;

function updateGates() {
  const on = connected();
  $('welcome').hidden = on || starting;
  $('wallet').hidden = !on;
}

async function refresh() {
  const aiwa = session.aiwa;
  if (!aiwa || !aiwa.identity) return;
  $('out-spendable').textContent = await aiwa.spendableBalance();
  $('out-claimable').textContent = await aiwa.claimable();
  $('out-balance').textContent = await aiwa.balance();
  const mining = await aiwa.mining();
  $('out-mining').textContent = mining
    ? `Capital ${mining.capital} SOL · taux T ${Math.round(mining.T * 100)} % · époque ${mining.epoch} (${mining.sinceLastAction} depuis ta dernière action)`
    : 'Pas encore de burn';
  if ($('history-section').open) renderHistory();
}

// ---------- history: read from the event log, never a separate ledger ----------

function row({ badge, label, detail, when }) {
  const el = document.createElement('div');
  el.className = 'history-item';
  const main = document.createElement('div');
  main.className = 'hist-main';
  const labelEl = document.createElement('div');
  labelEl.className = 'hist-label';
  const badgeEl = document.createElement('span');
  badgeEl.className = `hist-badge hist-${badge}`;
  badgeEl.textContent = { burn: 'burn', claim: 'claim', sent: 'envoyé', received: 'reçu' }[badge];
  labelEl.append(badgeEl, document.createTextNode(label));
  const detailEl = document.createElement('div');
  detailEl.className = 'hist-detail';
  detailEl.textContent = detail;
  main.append(labelEl, detailEl);
  const whenEl = document.createElement('div');
  whenEl.className = 'hist-when';
  whenEl.textContent = when ? new Date(when).toLocaleString('fr-FR') : '';
  el.append(main, whenEl);
  return el;
}

async function renderHistory() {
  const aiwa = session.aiwa;
  if (!aiwa || !aiwa.identity || !$('history-section').open) return;
  const myId = aiwa.identity.id;
  const events = [];
  for await (const event of aiwa.log.since([])) events.push(event);
  events.sort((a, b) => b.createdAt - a.createdAt);
  const state = await aiwa.walletState();
  const amountFor = (claimId) => fromUnits(state.conservation.claims[claimId]?.amount ?? 0n);
  const rows = [];
  for (const event of events) {
    const p = event.payload;
    if (!p) continue;
    if (event.type === 'accrual' && p.domain === myId) rows.push({ badge: 'burn', label: 'Engagé', detail: `+${p.b} SOL`, when: event.createdAt });
    else if (event.type === 'claim' && p.domain === myId) rows.push({ badge: 'claim', label: 'Réclamé', detail: `${p.amount} AIWA`, when: event.createdAt });
    else if (event.type === 'transfer' && (p.from === myId || p.to === myId)) {
      const out = p.from === myId;
      rows.push({ badge: out ? 'sent' : 'received', label: out ? 'Envoyé' : 'Reçu', detail: `${amountFor(p.claimId)} AIWA ${out ? 'à ' + short(p.to) : 'de ' + short(p.from)}`, when: event.createdAt });
    }
  }
  const list = $('history-list');
  list.replaceChildren();
  if (rows.length === 0) { const hint = document.createElement('p'); hint.className = 'hint'; hint.textContent = 'Rien pour l\'instant.'; list.append(hint); return; }
  for (const r of rows) list.append(row(r));
}

// ---------- the rate and the burn ----------

// T is chosen at the burn, for what follows. T % of the burn does not count as capital; a fixed part of it goes to the creator when the deployment has a creator address (yellow paper §11).
const terms = () => {
  const percent = $('burn-t').value.trim() === '' ? 0 : Number($('burn-t').value);
  return { sol: Number($('burn-amount').value), percent, T: percent / 100 };
};
const sol = (lamports) => `${lamports / 1e9} SOL`;

function previewBurn() {
  const { sol: amount, percent, T } = terms();
  const el = $('burn-preview');
  if (!(amount > 0 && percent >= 0 && percent <= 40) || !session.aiwa) { el.textContent = ''; return; }
  const quote = session.aiwa.burnQuote(Math.round(amount * 1e9), T);
  const creator = config.rewardParams.creatorFee;
  const parts = [`Compte pour ${sol(quote.capital)} de capital.`];
  if (percent > 0) {
    parts.push(creator
      ? `${sol(quote.toCreator)} du burn vont au créateur (${short(creator.address)}), le reste du burn est détruit.`
      : 'La part T du burn est détruite sans compter (ce déploiement n\'a pas de frais de créateur).');
  }
  parts.push('Cela remplace ta position actuelle et paie ce qu\'elle a accumulé.');
  el.textContent = parts.join(' ');
}

async function burn() {
  const { sol: amount, percent, T } = terms();
  if (!(amount > 0)) { $('burn-result').textContent = 'Un montant en SOL.'; return; }
  if (!(percent >= 0 && percent <= 40)) { $('burn-result').textContent = 'Le taux T est entre 0 et 40 %.'; return; }
  try {
    const signature = await session.aiwa.burn(Math.round(amount * 1e9), await solanaConnection(), { T });
    await refresh();
    $('burn-result').textContent = `Brûlé et engagé : ${signature}`;
  } catch (err) {
    $('burn-result').textContent = `Erreur : ${err.message}`;
  }
}

async function refreshSol() {
  try { $('out-sol-balance').textContent = `${(await session.aiwa.solBalance(await solanaConnection())) / 1e9} SOL`; }
  catch (err) { $('out-sol-balance').textContent = `Erreur : ${err.message}`; }
}

// ---------- the phrase ----------

const acknowledged = () => { try { return localStorage.getItem(ACK) === '1'; } catch { return true; } };

function showPhraseNotice() {
  $('phrase-notice').hidden = acknowledged();
  if (!$('phrase-notice').hidden) $('phrase-words').textContent = session.aiwa.recoveryPhrase;
}

async function stop() {
  clearInterval(timer);
  timer = null;
  const aiwa = session.aiwa;
  const { setSession } = await import('./session.js');
  setSession(null);
  await aiwa?.disconnect();
}

/** Makes (no phrase) or restores (a phrase) the wallet; shows the problem in `errorEl` if it cannot. */
async function switchWallet(mnemonic, errorEl) {
  showError(errorEl, '');
  try {
    const aiwa = await startWallet({ mnemonic });
    await stop();
    try { localStorage.removeItem(ACK); } catch { /* cosmetic */ }
    $('replace-phrase').value = '';
    $('replace-confirm').hidden = true;
    $('btn-replace').textContent = 'Utiliser cette phrase';
    await show(aiwa);
  } catch (err) {
    showError(errorEl, err.message);
  }
}

async function show(aiwa) {
  const restored = await runWallet(aiwa);
  starting = false;
  session.starting = false;
  updateGates();
  $('restore-note').hidden = !restored;
  if (restored) $('restore-note').textContent = `Ton historique est revenu de ${restored.source === 'archive' ? 'ton nœud d\'archive' : 'le registre'} : époque ${restored.epoch}.`;
  showPhraseNotice();
  await refresh();
  refreshSol();
  timer = setInterval(() => { if (session.aiwa) refresh(); }, 5000);
}

export async function initWalletPage(params) {
  $('btn-create').addEventListener('click', () => switchWallet(undefined, $('connect-error')));
  $('btn-restore').addEventListener('click', () => {
    const mnemonic = $('mnemonic').value.trim();
    if (!mnemonic) { showError($('connect-error'), 'Tes 12 mots.'); return; }
    switchWallet(mnemonic, $('connect-error'));
  });
  $('history-section').addEventListener('toggle', renderHistory);
  $('burn-amount').addEventListener('input', previewBurn);
  $('burn-t').addEventListener('input', previewBurn);
  $('btn-burn').addEventListener('click', burn);
  $('btn-refresh-sol').addEventListener('click', refreshSol);
  $('btn-claim').addEventListener('click', async () => {
    const claimable = await session.aiwa.claimable();
    if (Number(claimable) <= 0) return;
    await session.aiwa.claim(claimable);
    await refresh();
  });
  $('btn-faucet').hidden = !DEVNET;
  $('btn-faucet').addEventListener('click', async () => {
    const out = $('burn-result');
    if (!connected()) return;
    out.textContent = 'Je demande 1 SOL au robinet de test…';
    try {
      const connection = await solanaConnection();
      const { PublicKey } = window.solanaWeb3;
      const signature = await connection.requestAirdrop(new PublicKey(session.aiwa.address), 1_000_000_000);
      await connection.confirmTransaction(signature, 'confirmed');
      out.textContent = '1 SOL de test reçu.';
      refreshSol();
    } catch (err) { out.textContent = `Le robinet a refusé (${err.message}). Il limite la fréquence : réessaie plus tard.`; }
  });
  $('recovery-where').textContent = secretsAreSafe() ? 'Gardée dans le coffre du téléphone.' : 'Gardée dans le stockage de ce navigateur : celui qui peut lire ce profil peut la lire. L\'application Android la garde dans son coffre.';
  $('btn-show-phrase').addEventListener('click', () => {
    const out = $('out-phrase');
    out.hidden = !out.hidden;
    out.textContent = out.hidden ? '' : session.aiwa.recoveryPhrase;
    $('btn-show-phrase').textContent = out.hidden ? 'Voir mes 12 mots' : 'Cacher';
  });
  $('btn-phrase-done').addEventListener('click', () => {
    try { localStorage.setItem(ACK, '1'); } catch { /* shown again next time */ }
    $('phrase-notice').hidden = true;
  });
  $('btn-replace').addEventListener('click', async () => {
    const mnemonic = $('replace-phrase').value.trim();
    if (!mnemonic) return;
    if (!$('replace-confirm').hidden) { await switchWallet(mnemonic, $('replace-result')); return; }
    $('replace-confirm').hidden = false;
    $('btn-replace').textContent = 'Oui, la remplacer';
  });
  onWalletChange(() => { refresh().catch(() => {}); });
  window.addEventListener('aiwa:wallet-changed', () => { refresh().catch(() => {}); });
  if (params.get('coffee')) initCoffee(params);

  // The wallet starts by itself when this phone already has one; a phone that has none makes the person choose once.
  try {
    const aiwa = await bootWallet();
    if (aiwa) await show(aiwa);
  } catch (err) {
    showError($('connect-error'), err.message);
  }
  starting = false;
  session.starting = false;
  updateGates();
}

export { deleteSecret };
