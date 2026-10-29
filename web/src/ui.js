export const $ = (id) => document.getElementById(id);
export const short = (s) => (s && s.length > 18 ? `${s.slice(0, 8)}…${s.slice(-6)}` : (s ?? ''));

export function showError(el, message) { el.textContent = message ? String(message) : ''; }

export function flash(button, text) {
  const was = button.textContent;
  button.textContent = text;
  setTimeout(() => { button.textContent = was; }, 1200);
}

document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy]');
  if (!button) return;
  const el = $(button.dataset.copy);
  try { await navigator.clipboard.writeText(el.dataset.full ?? el.textContent); flash(button, 'Copié'); }
  catch { flash(button, 'Sélectionne'); }
});
