// A small, careful reader of robots.txt: may this path be fetched by a generic bot (User-agent: *)? Longest matching rule wins, Allow beats Disallow on a tie,
// `*` and `$` are understood. If the file cannot be read, nothing is fetched: the answer is no.
export function parseRobots(text) {
  const groups = []; let cur = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim(); if (!line) continue;
    const i = line.indexOf(':'); if (i < 0) continue;
    const k = line.slice(0, i).trim().toLowerCase(), v = line.slice(i + 1).trim();
    if (k === 'user-agent') { if (!cur || cur.rules.length) { cur = { agents: [], rules: [], delay: null }; groups.push(cur); } cur.agents.push(v.toLowerCase()); }
    else if (cur && (k === 'allow' || k === 'disallow')) cur.rules.push([k, v]);
    else if (cur && k === 'crawl-delay') cur.delay = Number(v);
  }
  return groups;
}
const toRe = (p) => new RegExp('^' + p.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\\\$$/, '$'));
export function allowed(groups, path) {
  const g = groups.find((x) => x.agents.includes('*'));
  if (!g) return true;
  let best = null;
  for (const [k, v] of g.rules) { if (!v) continue; if (toRe(v).test(path) && (!best || v.length > best.len || (v.length === best.len && k === 'allow'))) best = { k, len: v.length }; }
  return !best || best.k === 'allow';
}
export const crawlDelay = (groups) => (groups.find((x) => x.agents.includes('*')) || {}).delay ?? null;
