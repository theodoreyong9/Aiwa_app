// The chamber without a page: the rules and the manners (see chambre.js for what it is). All that it touches is given to it, so that two phones can be tried in a test with a stand-in room.
export const REPO = /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/;
const TEXT_MAX = 700;
/** What comes with a proposal, as plain bounded text (the brain checks it again before anything is kept): a kind, a short title, a https address. */
export const attachOf = (a) => ({ kind: clip(a?.kind, 10), title: clip(a?.title, 60), url: clip(a?.url, 300) });
export const clip = (text, max = TEXT_MAX) => String(text ?? '').replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ' ').split(/\s+/).filter(Boolean).join(' ').slice(0, max);
export const nameOf = (repo) => String(repo || '').split('/')[0] || 'quelqu\'un';

/**
 * `join(roomName)` returns { send(message, peerId?), onMessage(fn(message, peerId)), onPeerJoin(fn), onPeerLeave(fn), leave() }, `call(cmd, args)` asks the phone (promise), `post(cmd)` tells it.
 * `me` is { repo, name }. Nothing here touches a page: it is all tested with stand-ins.
 */
export function createChamber({ join, call, post, me }) {
  let room = null;
  let mode = 'closed';                 // 'host' (my own room) | 'visit' (the room of the person I visit) | 'closed'
  let roomRepo = null;                 // the person the room is named for
  let partner = null;                  // { id, repo, name } the one other we talk to
  let conversing = false;
  let dangerMe = false, dangerThem = false;
  let ear = false;
  let myNote = '';                     // what the person wrote for the agent of the other (never shown to the other person; it goes to the other's brain only)
  let refused = null;                  // why a conversation did not start ("busy": the other is already in one)
  let turning = false, waiting = null; // one turn at a time; the latest words that came meanwhile wait
  let starting = null;                 // the entry into the conversation being made when the other starts it (its first words may arrive before we are in)
  let last = '';

  const status = () => ({
    mode, room: roomRepo, partner: partner ? { repo: partner.repo, name: partner.name } : null, conversing, dangerMe, dangerThem, ear, refused,
    connected: mode !== 'closed', waiting: mode !== 'closed' && !partner,
  });
  const emit = () => { const s = status(); const key = JSON.stringify(s); if (key !== last) { last = key; post({ cmd: 'chamber-status', status: s }); } };
  const send = (message, id) => { try { room?.send(message, id ?? partner?.id); } catch { /* the link went away: the leave handler ends it */ } };

  const stop = async (tell) => {
    const was = conversing;
    conversing = false; turning = false; waiting = null;
    if (was) { if (tell) send({ t: 'end' }); try { await call('chamber-active', { on: false, peer: partner?.repo }); } catch { /* the phone is gone */ } }
  };

  const takeTurn = async (incoming) => {
    if (!conversing || !partner) return;
    if (turning) { waiting = incoming; return; }
    turning = true;
    try {
      do {
        const text = incoming;
        waiting = null;
        const answer = await call('chamber-turn', { peer: partner.repo, name: partner.name, me: me.name, incoming: text ? { kind: 'say', text } : null, danger: dangerMe && dangerThem, peer_note: partner.note || '' });
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
        // the visitor joins the room of the person he visits: the host must really claim that room; the host takes one visitor only
        if (mode === 'visit' && repo !== roomRepo) return;
        if (partner && partner.id !== id) { send({ t: 'busy' }, id); return; }
        partner = { id, repo, name: clip(message.name, 60) || nameOf(repo), note: clip(message.note, 400) };
        dangerThem = message.danger === true;
        emit();
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
        if (text) takeTurn(text);
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

  const enter = (repo, asMode) => {
    if (room) return;
    mode = asMode; roomRepo = repo; partner = null; refused = null;
    loadNote();
    room = join(`chambre:${repo}`);
    room.onMessage(onMessage);
    room.onPeerJoin((id) => hello(id));
    room.onPeerLeave((id) => { if (partner?.id === id) { stop(false).then(() => { partner = null; dangerThem = false; emit(); }); } });
    emit();
  };

  const leave = async () => {
    await stop(true);
    try { room?.leave(); } catch { /* already out */ }
    room = null; mode = 'closed'; roomRepo = null; partner = null; dangerThem = false; refused = null;
    emit();
  };

  let queue = Promise.resolve();
  const cmd = (c) => { queue = queue.then(() => run(c), () => run(c)); return queue; };
  const run = async (c) => {
    switch (c?.cmd) {
      case 'open': if (REPO.test(me.repo || '')) enter(me.repo, 'host'); break;                                  // on my own page: my room opens, I wait for a visitor
      case 'visit': if (REPO.test(c.repo || '')) enter(c.repo, 'visit'); break;                                  // on the profile of someone: I go to her room
      case 'close': await leave(); break;
      case 'begin': {
        if (!partner || conversing) break;
        await loadNote();
        try { const out = await call('chamber-active', { on: true, peer: partner.repo, name: partner.name }); if (out?.busy || out?.ok === false) throw new Error(out?.busy ? 'busy' : (out.error || 'refusé')); }
        catch (err) { refused = String(err?.message || 'busy').slice(0, 160); emit(); break; }
        conversing = true; refused = null; send({ t: 'begin', note: myNote }); emit();
        takeTurn(null);                                                                                       // the one who starts opens the conversation
        break;
      }
      case 'end': await stop(true); emit(); break;
      case 'danger': dangerMe = c.on === true || (c.on === undefined && !dangerMe); send({ t: 'danger', on: dangerMe }); emit(); break;
      case 'ear': ear = c.on === true || (c.on === undefined && !ear); emit(); break;
      default:
    }
    return status();
  };

  return { cmd, status, onMessage, enter, leave, _internals: () => ({ mode, partner, conversing }) };
}

