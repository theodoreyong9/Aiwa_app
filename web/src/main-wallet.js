import { initWalletPage } from './wallet-page.js';

window.addEventListener('unhandledrejection', (event) => {
  console.error('unhandled:', event.reason);
  const el = document.getElementById('connect-error');
  if (el) el.textContent = `Erreur inattendue : ${event.reason?.message ?? event.reason}`;
});
initWalletPage(new URLSearchParams(location.search));
