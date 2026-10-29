// « Un café »: a direct send of AIWA to the person whose profile one looks at. The profile says nothing: the person's wallet is known from the signed card she gave out in « Voir » (her key, bound to her repository).
// The card asks twice: once to see it, once to confirm.
import { session, connected } from './session.js';
import { coffeeTarget, coffeeAmount } from './coffee-core.js';
import { $, short } from './ui.js';

export async function initCoffee(params) {
  const target = await coffeeTarget(params.get('coffee'));
  if (!target) return;
  const repo = (params.get('repo') || '').slice(0, 100);
  const card = document.createElement('section');
  card.className = 'card'; card.id = 'coffee';
  card.innerHTML = '<h2>☕ Offrir un café</h2><p class="muted" id="coffee-who"></p><div class="line"><input id="coffee-amount" type="text" inputmode="decimal" value="1" aria-label="Montant en AIWA"> <span>AIWA</span><button type="button" id="coffee-go" class="primary">Envoyer</button></div><div class="muted" id="coffee-result"></div>';
  document.querySelector('main').prepend(card);
  $('coffee-who').textContent = `Pour ${repo || 'cette personne'} · wallet ${short(target)}`;
  let armed = false;
  $('coffee-go').addEventListener('click', async () => {
    const amount = coffeeAmount($('coffee-amount').value);
    if (!amount) { $('coffee-result').textContent = 'Un montant, par exemple 1 ou 0.5.'; return; }
    if (!connected()) { $('coffee-result').textContent = 'Connecte ton wallet d’abord.'; return; }
    if (!armed) { armed = true; $('coffee-go').textContent = `Confirmer : ${amount} AIWA`; $('coffee-result').textContent = 'Un second appui envoie. C’est définitif.'; return; }
    armed = false; $('coffee-go').textContent = 'Envoyer';
    try { await session.aiwa.send(target, amount); $('coffee-result').textContent = `Envoyé : ${amount} AIWA. Merci pour le café.`; window.dispatchEvent(new Event('aiwa:wallet-changed')); }
    catch (err) { $('coffee-result').textContent = `Non envoyé : ${err.message}`; }
  });
}
