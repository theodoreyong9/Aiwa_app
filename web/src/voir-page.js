// « Voir »: what the people near publish, and what comes by a link, by a QR code or from the favourites. NOT a transfer of anything: a person publishes the web links of the Files of her current repository.
// The page of « Voir ». Four ways in (?page=voir&m=lien|proche|qr|favoris): by link (a pasted link or card), near (about 50 m: a Trystero room per map cell of 38 x 19 m, her own and the neighbours toward the nearest edges; the relay sees only that
// someone looks in a cell), by QR code (mine to show, another's to scan), the favourites (kept on this phone). The people near are ranked by the Aiwa score they sign.
//   &pub=1 publish my links to the people near   &repo=owner/name   &links=[{"kind","url"}]
import { joinRoom } from '@trystero-p2p/nostr';
import { config } from './config.js';
import { session, connected, onSession } from './session.js';
import { $ } from './ui.js';
import { hostAvailable, hostPost } from './host.js';
import { drawQr, scanQr } from './qr.js';
import { cleanSeen, levelOfDistance, distanceTo, SEEN_MAX, cellsAround, cleanLinks, checkEntry, messageOf, parseCard, cardText, parseRepo, repoLinks, linksFromReleases, LEVELS, roomName, filterRows, scoreRange, readBlocked, writeBlocked, utf8, PERIOD_MS } from './voir-core.js';

const kindName = { docs: 'Docs', image: 'Images', video: 'Vidéos', app: 'Apps', page: 'Pages' };
const FAVS = 'aiwa-voir-favs';
const readFavs = () => { try { const v = JSON.parse(localStorage.getItem(FAVS) ?? '[]'); return Array.isArray(v) ? v.slice(0, 200) : []; } catch { return []; } };
const writeFavs = (list) => {
  try { localStorage.setItem(FAVS, JSON.stringify(list)); } catch { /* it lasts until the page closes */ }
  // the app keeps a copy: the person's own profile shows her favourites
  if (hostAvailable()) { try { hostPost({ cmd: 'favorites', list: list.slice(0, 50).map((f) => ({ repo: f.repo, links: f.links })) }); } catch { /* the page works without */ } }
};
// what this phone saw in the last week (repository names only): it is what it tells to the people it meets (gossip), and what the app keeps for « Swipe »
const SEEN = 'aiwa-seen', WEEK = 7 * 24 * 3600 * 1000;
const readSeen = () => { try { const v = JSON.parse(localStorage.getItem(SEEN) ?? '{}'); const now = Date.now(); return Object.fromEntries(Object.entries(v).filter(([r, t]) => typeof t === 'number' && now - t < WEEK)); } catch { return {}; } };
const noteSeen = (repo) => { if (!repo) return; const v = readSeen(); v[repo] = Date.now(); try { localStorage.setItem(SEEN, JSON.stringify(v)); } catch { /* it lasts until the page closes */ } };
const mySeen = () => cleanSeen(Object.entries(readSeen()).sort((a, b) => b[1] - a[1]).map(([r]) => r));
const hostOf = (url) => { try { return new URL(url).host; } catch { return url; } };

/** One card (a person, a pasted link, a favourite): her name, her links (they open in the browser), and the buttons given. */
function cardItem({ repo, pub, score, laps, links }, buttons) {
  const li = document.createElement('li');
  const who = document.createElement('div'); who.className = 'who';
  const name = document.createElement('span'); name.textContent = repo || (pub ? `${pub.slice(0, 8)}…` : hostOf(links[0]?.url ?? ''));
  who.append(name);
  if (Number.isFinite(score)) { const s = document.createElement('span'); s.className = 'score'; s.textContent = `score ${score.toPrecision(3)} · tours ${laps ?? 0}`; who.append(s); }
  li.append(who);
  for (const link of links) {
    const a = document.createElement('a');
    a.href = link.url; a.rel = 'noopener noreferrer'; a.target = '_blank'; a.textContent = `${kindName[link.kind] ?? 'Lien'} · ${hostOf(link.url)}`;
    li.append(a);
  }
  for (const [label, fn] of buttons) { const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', fn); li.append(b); }
  return li;
}

/** Opens the profiles of a list full screen on the phone (the app reads each `Profile/index.html` from its repository and swipes from one to the next); in a browser, the folder of the one chosen opens on GitHub. */
function openProfiles(repos, index, pubs = {}) {
  if (hostAvailable()) hostPost({ cmd: 'profile', repos, index, pubs: repos.map((r) => (/^[0-9a-f]{64}$/.test(pubs[r] || '') ? pubs[r] : '')) });
  else window.open(`https://github.com/${repos[index]}/tree/HEAD/Profile`, '_blank', 'noopener');
}
const profileButton = (repos, repo, pubs = {}) => (repo && repos.includes(repo) ? [['Profil', () => openProfiles(repos, repos.indexOf(repo), pubs)]] : []);

function addFavourite(card) {
  const list = readFavs();
  const key = card.links.map((l) => l.url).join('|');
  if (!list.some((f) => f.links.map((l) => l.url).join('|') === key)) { list.unshift({ repo: card.repo ?? '', links: card.links, pub: card.pub ?? '', at: Date.now() }); writeFavs(list); }
}

function showResult(card, message = 'Ce n\'est ni un lien https ni la carte d\'une personne.') {
  $('voir-result').hidden = false;
  const ul = $('voir-result-list'); ul.textContent = '';
  if (!card) { const li = document.createElement('li'); li.textContent = message; ul.append(li); return; }
  ul.append(cardItem(card, [...profileButton(card.repo ? [card.repo] : [], card.repo), ['Garder en favori', () => { addFavourite(card); showResult(card); }]]));
}

function renderFavourites() {
  $('voir-list-card').hidden = false; $('voir-list-title').textContent = 'Mes favoris';
  const ul = $('voir-list'); ul.textContent = ''; const list = readFavs();
  $('voir-empty').hidden = list.length > 0; $('voir-empty').textContent = 'Aucun favori : garde un lien, une carte scannée ou une personne proche.';
  const favRepos = list.map((f) => f.repo).filter(Boolean);
  const favPubs = Object.fromEntries(list.filter((f) => f.repo && f.pub).map((f) => [f.repo, f.pub]));
  for (const fav of list) ul.append(cardItem(fav, [...profileButton(favRepos, fav.repo, favPubs), ['Retirer', () => { writeFavs(readFavs().filter((f) => f.at !== fav.at)); renderFavourites(); }]]));
}

/** The people detected, as a horizontal slider of profiles (the best score first), kept by ONE geographic slider: the reach, from 50 m to the world. `view` holds `here` and `level`. */
function renderNear(entries, blocked, mode, view) {
  const strip = $('voir-list'); strip.textContent = '';
  const detected = [...entries.values()].filter((e) => !blocked.has(e.pub));
  const rows = filterRows(detected, { here: view.here, maxMeters: LEVELS[view.level].meters }).sort((a, b) => (b.score / Math.max(1, b.laps)) - (a.score / Math.max(1, a.laps)));
  $('voir-empty').hidden = rows.length > 0;
  $('voir-empty').textContent = detected.length === 0 ? 'Personne pour l\'instant : la liste se remplit quand d\'autres personnes ouvrent « Voir » (plus la portée est large, plus il faut qu\'ils aient regardé aussi loin).' : 'Personne dans cette portée : élargis-la.';
  const repos = rows.map((e) => e.repo).filter(Boolean);
  const pubs = Object.fromEntries(rows.filter((e) => e.repo && e.pub).map((e) => [e.repo, e.pub]));
  for (const e of rows) strip.append(cardItem(e, [...profileButton(repos, e.repo, pubs), ['Garder en favori', () => addFavourite({ repo: e.repo, links: e.links, pub: e.pub })], ['Bloquer', () => { const set = readBlocked(); set.add(e.pub); writeBlocked(set); renderNear(entries, set, mode, view); }]]));
}

export function initVoirPage(params) {
  // the favourites put in the app from a profile are merged with the ones kept here
  try {
    const fromApp = JSON.parse(params.get('nfavs') ?? '[]');
    if (Array.isArray(fromApp)) {
      const list = readFavs();
      for (const repo of fromApp.filter((r) => typeof r === 'string' && /^[\w.-]{1,60}\/[\w.-]{1,100}$/.test(r))) if (!list.some((f) => f.repo === repo)) list.unshift({ repo, links: repoLinks(repo), pub: '', at: Date.now() });
      writeFavs(list);
    }
  } catch { /* nothing to merge */ }
  writeFavs(readFavs());      // the app learns the favourites kept before it listened
  const mode = ['lien', 'proche', 'qr', 'favoris'].includes(params.get('m')) ? params.get('m') : 'proche';
  const publish = params.get('pub') === '1';
  const repo = params.get('repo') ?? '';
  let mine = [];
  try { mine = cleanLinks(JSON.parse(params.get('links') ?? '[]')); } catch { mine = []; }
  const status = (text) => { $('voir-status').textContent = text; };
  $('voir-title').textContent = { lien: 'Voir un dépôt', proche: 'Voir la zone', qr: 'Voir par QR code', favoris: 'Mes favoris' }[mode];
  $('voir-mine').textContent = mine.length ? `Tes liens (${repo || 'ton dépôt'}) : ${mine.map((l) => kindName[l.kind]).join(', ')}.` : 'Ton dépôt n\'a encore rien à montrer (ou il est privé).';

  if (mode === 'favoris') { status('Gardés sur ce téléphone.'); renderFavourites(); return; }

  if (mode === 'lien') {
    $('voir-lien').hidden = false; status('Le nom GitHub et le dépôt.');
    const go = async () => {
      const repoName = parseRepo($('voir-owner').value, $('voir-repo').value);
      if (!repoName) { showResult(null, 'Il faut le nom GitHub et le dépôt (ou « nom/dépôt »).'); return; }
      status(`Je regarde ${repoName}…`);
      // what exists, read without any key (GitHub's public API): only the kinds the releases hold are shown; if GitHub cannot be reached, the five lists are shown, unchecked
      let links = repoLinks(repoName);
      try {
        const base = `https://api.github.com/repos/${repoName}`;
        const head = { headers: { Accept: 'application/vnd.github+json' } };
        if (!(await fetch(base, head)).ok) { showResult(null, `${repoName} : introuvable, ou privé (Aiwa ne lit que les dépôts publics).`); status(''); return; }
        const res = await fetch(`${base}/releases?per_page=100`, head);
        if (res.ok) links = linksFromReleases(repoName, await res.json());
      } catch { /* the five links are shown, unchecked */ }
      status(''); showResult({ repo: repoName, links });
    };
    $('voir-go').addEventListener('click', go);
    for (const id of ['voir-owner', 'voir-repo']) $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
    navigator.clipboard?.readText?.().then((text) => { const r = parseRepo(text); if (r && !$('voir-owner').value) { $('voir-owner').value = r; go(); } }).catch(() => {});
    return;
  }

  if (mode === 'qr') {
    $('voir-qr').hidden = false; status('Un code à montrer, un code à scanner.');
    if (mine.length) drawQr($('voir-qr-draw'), cardText(repo, mine), 280).catch(() => {}); else $('voir-qr-note').textContent = 'Ton dépôt n\'a rien à montrer : pas de code à afficher. Tu peux quand même scanner celui d\'une autre personne.';
    $('voir-scan-btn').addEventListener('click', async () => {
      const video = $('voir-scan'); video.hidden = false; status('Vise le code…');
      const text = await scanQr(video); video.hidden = true;
      status(text ? 'Code lu.' : 'Aucun code lu (caméra refusée ou fermée).'); if (text) showResult(parseCard(text));
    });
    return;
  }

  // near or far: the same rooms, a wider cell for a wider reach (a room per level: 50 m, 150 m, 1 km, 5 km, 40 km, 150 km, 1 250 km, the world)
  $('voir-list-card').hidden = false; $('voir-list-title').textContent = 'Les profils détectés';
  $('voir-filters').hidden = false; $('voir-empty').textContent = '';
  const meet = (here) => {
    const cells = cellsAround(here.lat, here.lon), own = cells[0];
    const entries = new Map(), blocked = readBlocked(), decoder = new TextDecoder();
    const view = { here, level: 0, minScore: null };
    const iceServers = config.nearby?.iceServers ?? [{ urls: 'stun:stun.l.google.com:19302' }];
    const rooms = new Map();          // level -> { room, action }
    const status2 = () => status(publish ? `Tu es visible (zone ${own}), portée ${LEVELS[view.level].label}.` : 'Tu regardes sans te montrer. Active « Visible » dans le widget pour publier tes liens.');
    const mineEntry = async () => {
      if (!publish || !connected() || mine.length === 0) return null;
      let figure = { score: 0, laps: 0 };
      try { figure = (await session.aiwa.ranking()) ?? figure; } catch { /* no burn yet: zero */ }
      const e = { v: 1, cell: own, repo, links: mine, score: Number(figure.score) || 0, laps: Number(figure.laps) || 0, ts: Date.now(), pub: session.aiwa.identity.publicKey, seen: mySeen() };
      e.sig = await session.aiwa.identity.sign(messageOf(e));
      return e;
    };
    const announce = async (action, peerId) => { const e = await mineEntry(); if (e) await action.send(utf8.encode(JSON.stringify(e)), peerId ? { target: peerId } : {}); };
    const join = (level) => {
      if (rooms.has(level)) return;
      // the nearest level is the cell of the person and its neighbours; a wider level is ONE room named by a shorter prefix (or the whole world)
      const names = level === 0 ? cells.map((c) => `voir:${c}`) : [roomName(own, level)];
      const prefixes = level === 0 ? cells : [LEVELS[level].len === 0 ? '' : own.slice(0, LEVELS[level].len)];
      const made = names.map((name) => {
        const room = joinRoom({ appId: 'aiwa-voir-v1', rtcConfig: { iceServers } }, name);
        const action = room.makeAction('entry');
        action.onMessage = (data) => {
          let entry; try { entry = JSON.parse(decoder.decode(data instanceof Uint8Array ? data : new Uint8Array(data))); } catch { return; }
          const ok = checkEntry(entry, prefixes);
          if (ok && ok.pub !== session.aiwa?.identity?.publicKey) {
            entries.set(ok.pub, ok); renderNear(entries, blocked, mode, view);
            // the app keeps who was seen, at which reach, and the list that person saw (the list of the one whose place the visitor takes in « Swipe »)
            if (ok.repo) { noteSeen(ok.repo); if (hostAvailable()) { try { hostPost({ cmd: 'seen', repo: ok.repo, level: levelOfDistance(distanceTo(here.lat, here.lon, ok.cell)), seen: ok.seen, pub: ok.pub }); } catch { /* the page works without */ } } }
          }
        };
        room.onPeerJoin = (peerId) => { announce(action, peerId).catch(() => {}); };
        return { room, action };
      });
      rooms.set(level, made);
    };
    const all = () => Promise.all([...rooms.values()].flat().map(({ action }) => announce(action).catch(() => {})));
    join(0); status2();
    $('voir-dist').addEventListener('input', () => {
      view.level = Number($('voir-dist').value);
      for (let l = 1; l <= view.level; l++) join(l);       // the rooms of every wider level up to the one chosen: seen, and seen by those who look as wide
      $('voir-dist-label').textContent = LEVELS[view.level].label; status2(); all();
      renderNear(entries, blocked, mode, view);
    });
    setInterval(all, PERIOD_MS); onSession(() => { all(); }); all();
    renderNear(entries, blocked, mode, view);
  };
  if (!navigator.geolocation) { status('Ce téléphone ne donne pas la position : « Voir » ne peut pas trouver les personnes proches.'); return; }
  status('Recherche de ta zone…');
  navigator.geolocation.getCurrentPosition((pos) => meet({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
    (err) => status(err.code === 1 ? 'Sans l\'autorisation de position, « Voir » ne peut pas trouver les personnes proches.' : `Position indisponible (${err.message}).`), { enableHighAccuracy: true, maximumAge: 60_000, timeout: 20_000 });
}
