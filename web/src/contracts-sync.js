// What a person leaves in her profile (`Profile/aiwa-contracts.json`) so that others can find her contracts, and the reading of such a file: every event is a signed `contract-spec` event, checked one by one.
import { verifyEvent } from 'aiwa-core';

export const FILE = 'aiwa-contracts.json';
export const MAX_CHARS = 300_000;

/** The file to leave: her own contract-spec events, the newest first, as many as fit. */
export function profileFile(events, creatorId) {
  const mine = events.filter((e) => e && e.type === 'contract-spec' && e.author === creatorId).sort((a, b) => b.createdAt - a.createdAt);
  const kept = [];
  let size = 0;
  for (const event of mine) {
    size += JSON.stringify(event).length;
    if (size > MAX_CHARS) break;
    kept.push(event);
  }
  return { v: 1, creator: creatorId, events: kept };
}

/** The verified contract-spec events of a file read from a profile: forged, altered or foreign events are dropped. */
export async function readProfileFile(data) {
  if (!data || data.v !== 1 || typeof data.creator !== 'string' || !Array.isArray(data.events)) return [];
  const out = [];
  for (const event of data.events.slice(0, 200)) {
    if (!event || event.type !== 'contract-spec' || event.author !== data.creator || typeof event.payload?.sourceCode !== 'string') continue;
    try { if ((await verifyEvent(event)).valid) out.push(event); } catch { /* malformed: dropped */ }
  }
  return out;
}

/** « owner/name » from what was typed (a GitHub link is accepted), or null. */
export function repoOf(text) {
  const t = String(text ?? '').trim();
  const link = /github\.com[/:]([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/?#\s]|$)/.exec(t);
  if (link) return `${link[1]}/${link[2]}`;
  return /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(t) ? t : null;
}
