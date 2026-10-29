// The wallet's sections Publish, Contrats and Chercher: what is written to publish a contract and to use one, the contracts this phone holds, and the search among them.
import { publishContractSpec } from 'aiwa-core';
import { session } from './session.js';
import { $, short, showError } from './ui.js';
import { specsOf, searchSpecs, checkForm, EXAMPLE } from './contracts-core.js';

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

async function held() {
  const aiwa = session.aiwa;
  if (!aiwa?.identity) return [];
  const events = [];
  for await (const event of aiwa.log.since([])) events.push(event);
  return specsOf(events);
}

function card(spec, mine) {
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
  el.append(name, meta, text, copy, details);
  return el;
}

function fill(list, specs, mineId, empty) {
  list.replaceChildren();
  if (specs.length === 0) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = empty; list.append(p); return; }
  for (const spec of specs) list.append(card(spec, spec.creator === mineId));
}

async function render() {
  const mine = session.aiwa?.identity?.id;
  const specs = await held();
  if (current === 'contracts') fill($('contracts-list'), specs, mine, 'Aucun contrat pour l’instant. Publie le tien dans « Publish ».');
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
  $('search-query').addEventListener('input', () => render().catch(() => {}));
}
