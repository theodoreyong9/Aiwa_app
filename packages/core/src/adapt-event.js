// The one seam between the wire event ({ id, domain, author, authorPublicKey, parents, type, payload, createdAt, signature })
// and the reducers' convention ({ id, parents, payload }, with `type` folded into `payload`). Reducers never see the author:
// whatever they attribute to a signer is a signature embedded in the payload itself.

export const toReducerEvent = (event) => ({ id: event.id, parents: event.parents, payload: { type: event.type, ...event.payload } });

export const toReducerEvents = (events) => events.map(toReducerEvent);
