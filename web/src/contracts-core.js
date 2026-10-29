// Contracts as the wallet shows them: the `contract-spec` events its log holds (its own and those that reached it), listed and searched.
// There is no central registry (yellow paper §16.4): what is found here is what this phone has received.

export const LIMITS = { name: 60, version: 20, description: 500, source: 50_000 };

/** The contracts found in wire events ({ id, author, type, payload, createdAt }), the newest first. */
export function specsOf(events) {
  return events
    .filter((e) => e && e.type === 'contract-spec' && e.payload && typeof e.payload.sourceCode === 'string')
    .map((e) => ({
      id: e.id, creator: e.author, createdAt: e.createdAt ?? 0,
      name: String(e.payload.name ?? ''), version: String(e.payload.version ?? ''), description: String(e.payload.description ?? ''),
      sourceHash: String(e.payload.sourceHash ?? ''), sourceCode: e.payload.sourceCode,
    }))
    .sort((a, b) => b.createdAt - a.createdAt);
}

/** By contract id, by creator id (a beginning is enough), or by a word of the name; nothing asked: all of them. */
export function searchSpecs(specs, query) {
  const q = String(query ?? '').trim().toLowerCase();
  if (!q) return specs;
  return specs.filter((s) => s.id.toLowerCase().startsWith(q) || String(s.creator).toLowerCase().startsWith(q) || s.name.toLowerCase().includes(q));
}

/** What the form is missing or exceeds, or null when it can be published. */
export function checkForm({ name, version, description, sourceCode }) {
  if (!String(name ?? '').trim()) return 'Donne un nom au contrat.';
  if (String(name).length > LIMITS.name) return `Le nom : ${LIMITS.name} caractères au plus.`;
  if (!String(version ?? '').trim()) return 'Donne une version (par exemple 1).';
  if (String(version).length > LIMITS.version) return `La version : ${LIMITS.version} caractères au plus.`;
  if (String(description ?? '').length > LIMITS.description) return `La description : ${LIMITS.description} caractères au plus.`;
  if (!String(sourceCode ?? '').trim()) return 'Colle le code du contrat.';
  if (String(sourceCode).length > LIMITS.source) return `Le code : ${LIMITS.source} caractères au plus.`;
  return null;
}

/** The skeleton offered in the form. */
export const EXAMPLE = `import { defineContract, signedAction, verifySignedAction } from 'aiwa-lib';

// Un vote : chaque personne a une voix, la dernière compte.
export const definition = defineContract({
  initialState: () => ({ votes: {} }),
  handlers: {
    async vote(state, { payload }) {
      if (!(await verifySignedAction(payload))) return state;   // la signature est DANS l'action : jamais payload.from seul
      return { votes: { ...state.votes, [payload.from]: payload.choice } };
    },
  },
});

// Pour voter : contract.dispatch('vote', await signedAction(identity, { from: identity.id, choice: 'oui' }))`;
