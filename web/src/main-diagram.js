import mermaid from 'mermaid';
import { hostAvailable, hostCall } from './host.js';

// The diagram the super agent draws while it speaks: the app keeps its Mermaid text, this page asks for it and draws it again whenever it changes.
mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' });

const stage = document.getElementById('stage');
const note = document.getElementById('note');
let shown = -1;

async function draw({ id, code }) {
  try {
    const { svg } = await mermaid.render(`aiwa-diagram-${id}`, code);
    stage.innerHTML = svg;
    note.textContent = '';
  } catch {
    // a half-written diagram: the previous drawing stays, the next text will do better
    document.getElementById(`daiwa-diagram-${id}`)?.remove();
    note.textContent = 'Le schéma est en cours d’écriture…';
  }
}

async function tick() {
  if (!hostAvailable()) return;
  try {
    const current = await hostCall('diagram', {}, { timeoutMs: 5000 });
    if (current && current.code && current.id !== shown) { shown = current.id; await draw(current); }
  } catch { /* the app did not answer this time */ }
}

setInterval(tick, 800);
tick();
