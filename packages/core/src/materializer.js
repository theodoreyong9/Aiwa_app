// A materializer decides what events mean: a pure `apply(state, event) -> state`. The log never does.
// The default one folds key-value events; the modules of this package fold their own state machines.

export const defaultKvMaterializer = {
  initialState: () => ({}),
  apply(state, event) {
    if (event.type === 'kv.set') return { ...state, [event.payload.key]: event.payload.value };
    if (event.type === 'kv.delete') {
      const { [event.payload.key]: _removed, ...rest } = state;
      return rest;
    }
    return state;     // an event type it does not know is not an error: another materializer may care about it
  },
};
