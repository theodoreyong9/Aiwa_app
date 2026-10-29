// The order in which a reader folds events into state, the same for every reader that holds the same events.
//
// A log is a graph: two events that do not know of each other (two branches) have no order of their own. That rarely
// matters; it does when they contradict each other (one claim spent twice, one voucher redeemed twice, one claim id
// taken by two domains): whichever is folded first wins. Folded in arrival order, two readers with the same events could
// pick different winners for good.
//
// canonicalOrder removes that. Among the events that can come next (every parent already placed) the smallest id goes
// first: a topological order, identical whatever order the events were handed in or arrived in.
//
// It is agreement, not fairness: the winner is the smaller id, which is arbitrary (nothing here has a clock), and a
// signer who writes two contradicting events can try variants until the one he wants has the smaller id. What stays is
// the proof that he wrote both: two valid signatures on contradicting events. Yellow paper §13.4.

/**
 * @param {Array<{ id: string, parents?: string[] }>} events duplicates (same id) are kept once
 * @param {{ placed?: Iterable<string> }} [options] `placed`: ids already folded before this batch. A parent that is in
 * neither `events` nor `placed` (pruned history, an ancestor this reader never had) counts as satisfied.
 * @returns {Array} the same events, in canonical order
 */
export function canonicalOrder(events, { placed } = {}) {
  const byId = new Map();
  for (const event of events) if (!byId.has(event.id)) byId.set(event.id, event);
  const done = new Set(placed ?? []);

  const unmet = new Map();     // id -> number of distinct parents still to be placed
  const children = new Map();  // parent id -> ids of its children in this batch
  for (const event of byId.values()) {
    let count = 0;
    for (const parent of new Set(event.parents ?? [])) {
      if (!byId.has(parent) || done.has(parent)) continue;
      count++;
      const list = children.get(parent);
      if (list) list.push(event.id); else children.set(parent, [event.id]);
    }
    unmet.set(event.id, count);
  }

  const ready = new MinHeap();
  for (const [id, count] of unmet) if (count === 0) ready.push(id);

  const ordered = [];
  while (ready.size > 0) {
    const id = ready.pop();
    ordered.push(byId.get(id));
    for (const child of children.get(id) ?? []) {
      const left = unmet.get(child) - 1;
      unmet.set(child, left);
      if (left === 0) ready.push(child);
    }
  }
  if (ordered.length !== byId.size) throw new Error('canonicalOrder: the events form a cycle, which content-addressed events cannot');
  return ordered;
}

// A binary min-heap of strings (event ids: lowercase hex, compared as plain strings).
class MinHeap {
  constructor() { this.items = []; }
  get size() { return this.items.length; }
  push(value) {
    const a = this.items;
    a.push(value);
    let i = a.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (a[parent] <= a[i]) break;
      [a[parent], a[i]] = [a[i], a[parent]];
      i = parent;
    }
  }
  pop() {
    const a = this.items;
    const top = a[0];
    const last = a.pop();
    if (a.length > 0) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const l = 2 * i + 1, r = l + 1;
        let smallest = i;
        if (l < a.length && a[l] < a[smallest]) smallest = l;
        if (r < a.length && a[r] < a[smallest]) smallest = r;
        if (smallest === i) break;
        [a[smallest], a[i]] = [a[i], a[smallest]];
        i = smallest;
      }
    }
    return top;
  }
}
