// The chamber without a page: the rules and the manners (see chambre.js for what it is). All that it touches is given to it, so that two phones can be tried in a test with a stand-in room.
export const REPO = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/;
const TEXT_MAX = 700;
/** What comes with a proposal, as plain bounded text (the brain checks it again before anything is kept): a kind, a short title, a https address. */
export const attachOf = (a) => ({ kind: clip(a?.kind, 10), title: clip(a?.title, 60), url: clip(a?.url, 300) });
export const clip = (text, max = TEXT_MAX) => String(text ?? '').replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ' ').split(/\s+/).filter(Boolean).join(' ').slice(0, max);
/** The name of the room two people meet in: a fingerprint of the two repositories in a fixed order. Only the two of them can work it out, so nobody else can guess it or come in; the relay only sees a name. */
export async function pairKey(a, b) {
  const [x, y] = [String(a).toLowerCase(), String(b).toLowerCase()].sort();
  const bytes = new TextEncoder().encode(`aiwa-chambre|${x}|${y}`);
  const digest = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
  return [...digest].slice(0, 20).map((n) => n.toString(16).padStart(2, '0')).join('');
}
export const nameOf = (repo) => String(repo || '').split('/')[0] || 'quelqu\'un';

/**
 * `join(roomName)` returns { send(message, peerId?), onMessage(fn(message, peerId)), onPeerJoin(fn), onPeerLeave(fn), leave() }, `call(cmd, args)` asks the phone (promise), `post(cmd)` tells it.
 * `me` is { repo, name }. Nothing here touches a page: it is all tested with stand-ins.
 */
export function createChamber({ join, call, post, me }) {
  let room = null;
  let mode = 'closed';                 // 'call' (I called the person and wait for her call) | 'closed'
  let roomRepo = null;                 // the person I called
  let partner = null;                  // { id, repo, name } the one other we talk to
  let conversing = false;
  let dangerMe = false, dangerThem = false;
  let ear = false;
  let speak = false;                   // what the person says by voice goes into this chamber, as from her human (the phone decides which chamber, only one at a time)
  let myNote = '';                     // what the person wrote for the agent of the other (never shown to the other person; it goes to the other's brain only)
  let refused = null;                  // why a conversation did not start ("busy": the other is already in one)
  let turning = false, waiting = null; // one turn at a time; the latest words that came meanwhile wait
  let starting = null;                 // the entry into the conversation being made when the other starts it (its first words may arrive before we are in)
  let last = '';

  const status = () => ({
    mode, room: roomRepo, partner: partner ? { repo: partner.repo, name: partner.name } : null, conversing, dangerMe, dangerThem, ear, speak, refused,
    connected: mode !== 'closed', waiting: mode !== 'closed' && !partner,
  });
  const emit = () => { const s = status(); const key = JSON.stringify(s); if (key !== last) { last = key; post({ cmd: 'chamber-status', status: s }); } };
  const send = (message, id) => { try { room?.send(message, id ?? partner?.id); } catch { /* the link went away: the leave handler ends it */ } };

  const stop = async (tell) => {
    const was = conversing;
    conversing = false; turning = false; waiting = null;
    if (was) { if (tell) send({ t: 'end' }); try { await call('chamber-active', { on: false, peer: partner?.repo }); } catch { /* the phone is gone */ } }
  };

  // `incoming` is { text, human } (human: the words are those of the person in front, not of her agent) or null for the opening
  const takeTurn = async (incoming) => {
    if (!conversing || !partner) return;
    if (turning) { waiting = waiting && incoming ? { text: `${waiting.text} ${incoming.text}`, human: waiting.human || incoming.human } : (incoming || waiting); return; }
    turning = true;
    try {
      do {
        const heard = incoming;
        waiting = null;
        const answer = await call('chamber-turn', { peer: partner.repo, name: partner.name, me: me.name, incoming: heard ? { kind: 'say', text: heard.text, ...(heard.human ? { human: true } : {}) } : null, danger: dangerMe && dangerThem, peer_note: partner.note || '' });
        if (answer?.ok === false) throw new Error(answer.error || 'refusé');
        if (!conversing) break;
        if (answer?.say) send({ t: 'say', text: clip(answer.say) });
        if (dangerMe && dangerThem) {
          if (answer?.message) send({ t: 'dm', kind: 'message', text: clip(answer.message) });
          if (answer?.proposal) send({ t: 'dm', kind: 'proposal', text: clip(answer.proposal), ...(answer.attach ? { attach: attachOf(answer.attach) } : {}) });
        }
        incoming = waiting;
      } while (incoming && conversing);
    } catch (err) {
      refused = String(err?.message || err).slice(0, 160);
      await stop(true);
    } finally { turning = false; emit(); }
  };

  // the note is read from the brain when the room opens and again when a conversation begins (she may have changed it); the other is told when it arrives
  const loadNote = async () => {
    try { const r = await call('chamber-note', {}); const text = clip(r?.text, 400); if (text !== myNote) { myNote = text; if (partner) send({ t: 'note', text: myNote }); } } catch { /* no note */ }
  };

  const hello = (id) => (partner && partner.id !== id ? send({ t: 'busy' }, id) : send({ t: 'hello', repo: me.repo, name: me.name, danger: dangerMe, note: myNote }, id));

  const onMessage = async (message, id) => {
    if (!message || typeof message !== 'object') return;
    switch (message.t) {
      case 'hello': {
        const repo = clip(message.repo, 201);
        if (!REPO.test(repo)) return;
        // the room is the pair's: the one who says hello must be the person I called
        if (repo !== roomRepo) return;
        if (partner && partner.id !== id) { send({ t: 'busy' }, id); return; }
        partner = { id, repo, name: clip(message.name, 60) || nameOf(repo), note: clip(message.note, 400) };
        dangerThem = message.danger === true;
        emit();
        // the two have called each other: that is the match. The conversation starts by itself, opened by the one whose repository comes first (no request, no acceptance)
        if (me.repo.toLowerCase() < repo.toLowerCase()) cmd({ cmd: 'begin' });
        return;
      }
      case 'note': if (partner && partner.id === id) partner.note = clip(message.text, 400); return;
      case 'busy': {
        // the other is in a chamber already (or its super agent is): nothing starts, and a conversation we had begun stops
        if (partner && partner.id === id) { await stop(false); partner = null; dangerThem = false; }
        else if (!partner) { /* a stranger said it, before any hello */ }
        refused = 'busy'; emit();
        return;
      }
      case 'begin': {
        if (!partner || partner.id !== id || conversing) return;
        if (typeof message.note === 'string') partner.note = clip(message.note, 400);
        starting = (async () => {
          try { const out = await call('chamber-active', { on: true, peer: partner.repo, name: partner.name }); if (out?.busy || out?.ok === false) throw new Error(out?.busy ? 'busy' : (out.error || 'refusé')); }
          catch (err) { send({ t: 'busy' }, id); refused = 'busy'; emit(); return false; }
          conversing = true; refused = null; emit();
          return true;
        })();
        await starting; starting = null;
        return;
      }
      case 'say': {
        if (starting) await starting;
        if (!partner || partner.id !== id || !conversing) return;
        const text = clip(message.text);
        if (text) takeTurn({ text });
        return;
      }
      case 'human': {
        if (starting) await starting;
        if (!partner || partner.id !== id || !conversing) return;
        const text = clip(message.text);
        if (text) takeTurn({ text, human: true });
        return;
      }
      case 'dm': {
        if (!partner || partner.id !== id || !conversing || !(dangerMe && dangerThem)) return;
        const kind = message.kind === 'proposal' ? 'proposal' : 'message';
        const text = clip(message.text);
        if (text) call('chamber-deliver', { peer: partner.repo, kind, text, danger: true, ...(kind === 'proposal' && message.attach ? { attach: attachOf(message.attach) } : {}) }).catch(() => {});
        return;
      }
      case 'danger': if (partner && partner.id === id) { dangerThem = message.on === true; emit(); } return;
      case 'end': {
        if (starting) await starting;
        if (partner && partner.id === id && conversing) { stop(false); emit(); }

        return;
      }
      default:
    }
  };

  const enter = async (repo) => {
    if (room) return;
    mode = 'call'; roomRepo = repo; partner = null; refused = null;
    loadNote();
    room = join(`chambre:${await pairKey(me.repo, repo)}`);
    room.onMessage(onMessage);
    room.onPeerJoin((id) => hello(id));
    room.onPeerLeave((id) => { if (partner?.id === id) { stop(false).then(() => { partner = null; dangerThem = false; emit(); }); } });
    emit();
  };

  const leave = async () => {
    await stop(true);
    try { room?.leave(); } catch { /* already out */ }
    room = null; mode = 'closed'; roomRepo = null; partner = null; dangerThem = false; refused = null; ear = false; speak = false;
    emit();
  };

  let queue = Promise.resolve();
  const cmd = (c) => { queue = queue.then(() => run(c), () => run(c)); return queue; };
  const run = async (c) => {
    switch (c?.cmd) {
      case 'call': if (REPO.test(c.repo || '') && c.repo.toLowerCase() !== String(me.repo).toLowerCase()) await enter(c.repo); break;      // I call the person: her call is awaited in the room of the two of us
      case 'close': await leave(); break;
      case 'begin': {
        if (!partner || conversing) break;
        await loadNote();
        try { const out = await call('chamber-active', { on: true, peer: partner.repo, name: partner.name }); if (out?.busy || out?.ok === false) throw new Error(out?.busy ? 'busy' : (out.error || 'refusé')); }
        catch (err) { refused = String(err?.message || 'busy').slice(0, 160); send({ t: 'busy' }); emit(); break; }
        conversing = true; refused = null; send({ t: 'begin', note: myNote }); emit();
        takeTurn(null);                                                                                       // the one who starts opens the conversation
        break;
      }
      case 'end': await stop(true); emit(); break;
      case 'danger': dangerMe = c.on === true || (c.on === undefined && !dangerMe); send({ t: 'danger', on: dangerMe }); emit(); break;
      case 'ear': ear = c.on === true || (c.on === undefined && !ear); emit(); break;
      case 'speak': speak = c.on === true || (c.on === undefined && !speak); emit(); break;
      case 'modes': if (typeof c.ear === 'boolean') ear = c.ear; if (typeof c.speak === 'boolean') speak = c.speak; emit(); break;   // set both at once (all off when the person leaves the profile)
      case 'human': {
        // what the person says in this chamber: kept by the brain as hers, and given to the other side as from her human
        const text = clip(c.text);
        if (!text || !partner || !conversing) { return { ...status(), humanRefused: true }; }
        try { await call('chamber-human', { peer: partner.repo, me: me.name, text }); } catch { /* the line is not kept, the other still hears it */ }
        send({ t: 'human', text });
        break;
      }
      default:
    }
    return status();
  };

  return { cmd, status, onMessage, enter, leave, _internals: () => ({ mode, partner, conversing }) };
}


/**
 * Several chambers at once: one `createChamber` per room (my own room when I wait for visitors, the room of each person I visit). The phone is told the list of all of them at each change.
 * Commands name the room (`room`: the room's repository or the partner's); only one chamber at a time has the voice of the person (`speak`).
 */
export function createChambers({ join, call, post, me }) {
  const rooms = new Map();             // room repo -> chamber
  let last = '';
  const list = () => [...rooms.values()].map((c) => c.status()).filter((s) => s.mode !== 'closed');
  const emit = () => {
    for (const [key, c] of rooms) if (c.status().mode === 'closed') rooms.delete(key);
    const all = list(); const key = JSON.stringify(all);
    if (key !== last) { last = key; post({ cmd: 'chamber-status', rooms: all, status: all[0] || { mode: 'closed' } }); }
  };
  const open = (repo, mode) => {
    if (!rooms.has(repo)) rooms.set(repo, createChamber({ join, call, me, post: (c) => { if (c.cmd === 'chamber-status') emit(); else post(c); } }));
    return rooms.get(repo);
  };
  const find = (key) => rooms.get(key) || [...rooms.values()].find((c) => c.status().partner?.repo === key);
  let queue = Promise.resolve();
  const cmd = (c) => { queue = queue.then(() => run(c), () => run(c)); return queue; };
  const run = async (c) => {
    switch (c?.cmd) {
      case 'call': if (REPO.test(c.repo || '')) { const ch = open(c.repo); await ch.cmd(c); } break;
      case 'close': {
        const targets = c.room ? [find(c.room)].filter(Boolean) : [...rooms.values()];
        for (const ch of targets) await ch.cmd({ cmd: 'close' });
        break;
      }
      case 'speak': case 'modes': {
        const ch = find(c.room);
        if (!ch) break;
        if (c.speak === true || (c.cmd === 'speak' && c.on !== false)) for (const other of rooms.values()) if (other !== ch) await other.cmd({ cmd: 'modes', speak: false });   // one voice at a time
        await ch.cmd(c);
        break;
      }
      case 'quiet': for (const ch of rooms.values()) await ch.cmd({ cmd: 'modes', ear: false, speak: false }); break;                                       // the person left: nobody listens or speaks, the chambers go on
      case 'human': {
        // the voice goes to the chamber that has it (or the one named)
        const ch = c.room ? find(c.room) : [...rooms.values()].find((x) => x.status().speak);
        if (!ch) return { ok: false };
        await ch.cmd(c);
        break;
      }
      case 'ear': {
        // one ear at a time: listening to a chamber switches off the one listened to before
        const ch = find(c.room);
        if (!ch) break;
        const turningOn = c.on === true || (c.on === undefined && !ch.status().ear);
        if (turningOn) for (const other of rooms.values()) if (other !== ch) await other.cmd({ cmd: 'modes', ear: false });
        await ch.cmd(c);
        break;
      }
      default: { const ch = find(c?.room); if (ch) await ch.cmd(c); }
    }
    emit();
    return { rooms: list() };
  };
  return { cmd, status: () => list(), speaking: () => list().find((s) => s.speak)?.room || null, _rooms: rooms };
}
