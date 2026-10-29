// A nested/graph-shaped Materializer for aiwa-core's own
// Materializer contract ({initialState, apply}) — the flat-KV
// defaultKvMaterializer covers one field per key; this covers many
// fields per node, where a field's own value can be a real
// reference to another node's id, resolved by the reader, never
// eagerly denormalized. The same principle GUN's own "soul"
// references use — built on aiwa-core's own event/materializer
// contract, not a bespoke one.

export function ref(nodeId) {
  return { $ref: nodeId };
}
export function isRef(value) {
  return value !== null && typeof value === 'object' && typeof value.$ref === 'string';
}

export const graphMaterializer = {
  initialState: () => ({ nodes: {} }),
  apply(state, event) {
    if (event.type === 'graph.put') {
      const { node, field, value } = event.payload;
      const existing = state.nodes[node] ?? {};
      return { nodes: { ...state.nodes, [node]: { ...existing, [field]: value } } };
    }
    if (event.type === 'graph.unset') {
      const { node, field } = event.payload;
      const existing = state.nodes[node];
      if (!existing || !(field in existing)) return state;
      const { [field]: _removed, ...rest } = existing;
      return { nodes: { ...state.nodes, [node]: rest } };
    }
    return state; // a unrecognized event type is a no-op here, never an error
  },
};
