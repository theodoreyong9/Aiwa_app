// The wallet's sections Publish, Contrats and Chercher: what is written to publish a contract and to use one, the contracts this phone holds, and the search among them.
import { publishContractSpec, toReducerEvents } from 'aiwa-core';
import { verifySignedAction } from 'aiwa-lib';
import { hostAvailable, hostPost } from './host.js';
import { session } from './session.js';
import { $, short, showError } from './ui.js';
import { specsOf, searchSpecs, checkForm, EXAMPLE } from './contracts-core.js';
import { loadVerified, pinnedHashes, pinHash } from './contract-loader.js';
import { profileFile, readProfileFile, repoOf } from './contracts-sync.js';

const USE = `import { Contract } from 'aiwa-lib';
import { definition } from './mon-contrat.js';     // le fichier publié (ou son code vérifié)

const contract = new Contract({ identity: aiwa.identity, log: aiwa.log, domain: 'mon-application', definition });

await contract.dispatch('vote', await signedAction(aiwa.identity, { from: aiwa.identity.id, choice: 'oui' }));
const state = await contract.state();      // { votes: { … } }, rejoué depuis les événements que tu détiens`;

let current = 'wallet';

function select(tab) {
  current = tab;
  for (const button of document.querySelectorAll('#tabs [data-tab]')) button.setAttribute('aria-selected', String(button.dataset.tab === tab));
  for (const name of ['wallet', 'publish', 'contracts', 'search']) $(`tab-${name}`).hidden = name !== tab;
  if (tab === 'contracts' || tab === 'search') render().catch(() => {});
}

async function heldEvents() {
  const aiwa = session.aiwa;
  if (!aiwa?.identity) return [];
  const events = [];
  for await (const event of aiwa.log.since([])) events.push(event);
  return events;
}

async function held() { return specsOf(await heldEvents()); }

/** Leaves her own contracts in her profile (the phone's brain writes the file, once for the same content), so that others can find them. */
export async function syncProfile() {
  const aiwa = session.aiwa;
  if (!hostAvailable() || !aiwa?.identity) return;
  const file = profileFile(await heldEvents(), aiwa.identity.id);
  if (file.events.length) hostPost({ cmd: 'contracts-profile', events: file.events });
}

const json = (value) => JSON.stringify(value, (_k, v) => (typeof v === 'bigint' ? v.toString() : v), 2);

/** The state of a contract: its code is loaded only once its hash is the one the person accepted, then it reads the events this phone holds. */
async function readState(spec, out) {
  out.textContent = 'Je charge le contrat…';
  let contract;
  try {
    contract = await loadVerified(spec, spec.sourceHash, { verifySignedAction });
    const events = toReducerEvents(await heldEvents());
    out.textContent = json(await contract.state(events));
  } catch (err) {
    out.textContent = `Impossible : ${err.message}`;
  } finally {
    contract?.close();
  }
}

function card(spec, mine, { onKeep } = {}) {
  const el = document.createElement('div');
  el.className = 'spec';
  const name = document.createElement('div');
  name.className = 'name';
  name.textContent = `${spec.name || '(sans nom)'} · v${spec.version}${mine ? ' · à toi' : ''}`;
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `contrat ${short(spec.id)} · créateur ${short(spec.creator)}`;
  const text = document.createElement('div');
  text.className = 'muted';
  text.textContent = spec.description;
  const copy = document.createElement('button');
  copy.type = 'button';
  copy.className = 'light';
  copy.textContent = 'Copier l’identifiant';
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(spec.id); copy.textContent = 'Copié'; } catch { copy.textContent = spec.id; }
  });
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Voir le code';
  const code = document.createElement('pre');
  code.className = 'code';
  code.textContent = spec.sourceCode;
  details.append(summary, code);
  el.append(name, meta, text, copy);
  if (onKeep) {
    const keep = document.createElement('button');
    keep.type = 'button';
    keep.className = 'light';
    keep.textContent = 'Garder';
    keep.addEventListener('click', async () => { keep.disabled = true; try { await onKeep(spec); keep.textContent = 'Gardé'; } catch (err) { keep.disabled = false; keep.textContent = `Refusé (${err.message})`; } });
    el.append(keep);
  } else {
    // running a contract: first the hash is accepted (once), then the code runs in a worker with no network and no key
    const state = document.createElement('pre');
    state.className = 'code';
    state.hidden = true;
    const run = document.createElement('button');
    run.type = 'button';
    run.className = 'light';
    const trusted = () => pinnedHashes().has(spec.sourceHash);
    const label = () => { run.textContent = trusted() ? 'Lire l\u2019état' : 'Faire confiance à cette empreinte'; };
    label();
    run.addEventListener('click', async () => {
      if (!trusted()) {
        // two touches: the first shows what is being accepted, the second accepts it (a script's confirm() may not exist in the app's view)
        if (!run.dataset.asked) {
          run.dataset.asked = '1';
          state.hidden = false;
          state.textContent = `Empreinte du code :\n${spec.sourceHash}\n\nIl ne sera chargé que s'il correspond exactement à cette empreinte, dans un espace isolé, sans réseau ni clé.`;
          run.textContent = 'Oui, accepter cette empreinte';
          return;
        }
        pinHash(spec.sourceHash);
        delete run.dataset.asked;
        state.hidden = true;
        label();
        return;
      }
      state.hidden = false;
      await readState(spec, state);
    });
    el.append(run, state);
  }
  el.append(details);
  return el;
}

function fill(list, specs, mineId, empty, options) {
  list.replaceChildren();
  if (specs.length === 0) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = empty; list.append(p); return; }
  for (const spec of specs) list.append(card(spec, spec.creator === mineId, options));
}

/** The contracts a person left in her profile (« owner/name »): read from GitHub's raw files, every event checked; « Garder » puts one in this phone's log, where the lists and the search find it. */
async function searchProfile() {
  const repo = repoOf($('search-query').value);
  const list = $('search-list');
  if (!repo) return;
  list.replaceChildren(Object.assign(document.createElement('p'), { className: 'hint', textContent: `Je lis le profil de ${repo}…` }));
  let data = null;
  try {
    const reply = await fetch(`https://raw.githubusercontent.com/${repo}/HEAD/Profile/aiwa-contracts.json`, { cache: 'no-cache' });
    if (reply.ok) data = await reply.json();
  } catch { /* unreachable: said below */ }
  const events = await readProfileFile(data);
  const byId = new Map(events.map((e) => [e.id, e]));
  fill(list, specsOf(events), session.aiwa?.identity?.id, `${repo} n\u2019a laissé aucun contrat dans son profil (ou le profil n\u2019est pas lisible).`, {
    onKeep: async (spec) => { await session.aiwa.log.append(byId.get(spec.id)); },
  });
}

async function render() {
  const mine = session.aiwa?.identity?.id;
  const specs = await held();
  if (current === 'contracts') fill($('contracts-list'), specs, mine, 'Aucun contrat pour l’instant. Publie le tien dans « Publish ».');
  if (current === 'search' && repoOf($('search-query').value)) { $('search-list').dataset.profile = '1'; return; }
  if (current === 'search') fill($('search-list'), searchSpecs(specs, $('search-query').value), mine, $('search-query').value.trim() ? 'Aucun contrat ne correspond, parmi ceux que ce téléphone a reçus.' : 'Aucun contrat reçu pour l’instant.');
}

async function publish() {
  const aiwa = session.aiwa;
  const out = $('pub-result');
  const form = { name: $('pub-name').value, version: $('pub-version').value, description: $('pub-description').value, sourceCode: $('pub-code').value };
  const problem = checkForm(form);
  if (problem) { showError(out, problem); return; }
  if (!aiwa?.identity) { showError(out, 'Ton wallet n’est pas prêt.'); return; }
  $('btn-publish').disabled = true;
  showError(out, 'Je publie…');
  try {
    const { specEventId } = await publishContractSpec(aiwa.identity, aiwa.log, aiwa.logDomain, { name: form.name.trim(), version: form.version.trim(), sourceCode: form.sourceCode, description: form.description.trim() });
    showError(out, `Publié. Identifiant du contrat : ${specEventId}`);
    syncProfile().catch(() => {});
  } catch (err) {
    showError(out, `Impossible de publier : ${err.message}`);
  } finally {
    $('btn-publish').disabled = false;
  }
}

/** Wires the sections; `wall` hides them (the wall of the donors is the wallet alone). */
export function initContracts({ wall = false } = {}) {
  $('tabs').hidden = wall;
  if (wall) return;
  $('example-code').textContent = EXAMPLE;
  $('use-code').textContent = USE;
  for (const button of document.querySelectorAll('#tabs [data-tab]')) button.addEventListener('click', () => select(button.dataset.tab));
  $('btn-pub-example').addEventListener('click', () => { $('pub-code').value = EXAMPLE; });
  $('btn-publish').addEventListener('click', publish);
  $('btn-contracts-refresh').addEventListener('click', () => render().catch(() => {}));
  $('search-query').addEventListener('input', () => { $('btn-search-profile').hidden = !repoOf($('search-query').value); render().catch(() => {}); });
  $('search-query').addEventListener('keydown', (e) => { if (e.key === 'Enter' && repoOf($('search-query').value)) searchProfile(); });
  $('btn-search-profile').addEventListener('click', searchProfile);
  syncProfile().catch(() => {});
}
