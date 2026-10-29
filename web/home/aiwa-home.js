/* Aiwa home runtime: fills the SLOTS of a page with the buttons of the application (the widget's buttons), whoever wrote the page.
 *  <div data-aiwa-slot="build"></div>            all the buttons of a group: build (Agent) | files | voir (Game) | chamber | bar      (several groups: "build voir"; "all": every group)
 *  <button data-aiwa-button="docs"></button>     one button (any id of the catalogue below); "widget" is ONE button that opens the widget (its three tabs) over the page
 *  <div data-aiwa-scenarios></div>               the scenarios of the page (scenarios.json next to it): cards with a Launch button; the application asks before it runs one of someone else's
 *  <section data-aiwa-favorites></section>      the favourites of the person (kept in Game, Favoris): one card each with the links of the repository; shown only on her own page
 *  data-aiwa-only="docs,media"  data-aiwa-skip="cast"  keep or drop buttons in a slot;  data-aiwa-look="icons|labels|both"  how a slot draws them.
 * The buttons ARE the application's, never the page's: they act on the account of whoever looks (the visitor on a profile that is not hers). The page styles them
 * with plain CSS (class .aiwa-btn, attributes data-tone, data-on, data-id; variables --aiwa-*); this file brings a base look that any rule of the page beats.
 * The native side listens on AiwaHomeHost (a press is a message {cmd:"press", id}) and calls aiwa.setState({id:{label,tone,on,found,icon}}) every few seconds to say what each
 * button shows now; without it (a preview in a browser) a press raises the event "aiwa-press" on the document. */
(function () {
  if (window.__aiwaHome) { if (window.aiwa) window.aiwa.render(); return; }
  window.__aiwaHome = true;
  var ICONS = {"widget": "<rect width=\"7\" height=\"7\" x=\"3\" y=\"3\" rx=\"1\" /> <rect width=\"7\" height=\"7\" x=\"14\" y=\"3\" rx=\"1\" /> <rect width=\"7\" height=\"7\" x=\"14\" y=\"14\" rx=\"1\" /> <rect width=\"7\" height=\"7\" x=\"3\" y=\"14\" rx=\"1\" />", "wallet": "<path d=\"M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1\" /> <path d=\"M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4\" />", "settings": "<path d=\"M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z\" /> <circle cx=\"12\" cy=\"12\" r=\"3\" />", "cast": "<path d=\"M2 8V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6\" /> <path d=\"M2 12a9 9 0 0 1 8 8\" /> <path d=\"M2 16a5 5 0 0 1 4 4\" /> <line x1=\"2\" x2=\"2.01\" y1=\"20\" y2=\"20\" />", "docs": "<path d=\"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z\" /> <path d=\"M14 2v4a2 2 0 0 0 2 2h4\" /> <path d=\"M10 9H8\" /> <path d=\"M16 13H8\" /> <path d=\"M16 17H8\" />", "app": "<rect width=\"14\" height=\"20\" x=\"5\" y=\"2\" rx=\"2\" ry=\"2\" /> <path d=\"M12 18h.01\" />", "page": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20\" /> <path d=\"M2 12h20\" />", "agent": "<path d=\"M12 8V4H8\" /> <rect width=\"16\" height=\"12\" x=\"4\" y=\"8\" rx=\"2\" /> <path d=\"M2 14h2\" /> <path d=\"M20 14h2\" /> <path d=\"M15 13v2\" /> <path d=\"M9 13v2\" />", "claude": "<path d=\"M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z\" /> <path d=\"M20 3v4\" /> <path d=\"M22 5h-4\" /> <path d=\"M4 17v2\" /> <path d=\"M5 18H3\" />", "listen": "<path d=\"M6 8.5a6.5 6.5 0 1 1 13 0c0 6-6 6-6 10a3.5 3.5 0 1 1-7 0\" /> <path d=\"M15 8.5a2.5 2.5 0 0 0-5 0v1a2 2 0 1 1 0 4\" />", "plus": "<path d=\"M5 12h14\" /> <path d=\"M12 5v14\" />", "scenario": "<rect width=\"8\" height=\"8\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M7 11v4a2 2 0 0 0 2 2h4\" /> <rect width=\"8\" height=\"8\" x=\"13\" y=\"13\" rx=\"2\" />", "nearby": "<path d=\"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0\" /> <circle cx=\"12\" cy=\"10\" r=\"3\" />", "link": "<path d=\"M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71\" /> <path d=\"M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71\" />", "qr": "<rect width=\"5\" height=\"5\" x=\"3\" y=\"3\" rx=\"1\" /> <rect width=\"5\" height=\"5\" x=\"16\" y=\"3\" rx=\"1\" /> <rect width=\"5\" height=\"5\" x=\"3\" y=\"16\" rx=\"1\" /> <path d=\"M21 16h-3a2 2 0 0 0-2 2v3\" /> <path d=\"M21 21v.01\" /> <path d=\"M12 7v3a2 2 0 0 1-2 2H7\" /> <path d=\"M3 12h.01\" /> <path d=\"M12 3h.01\" /> <path d=\"M12 16v.01\" /> <path d=\"M16 12h1\" /> <path d=\"M21 12v.01\" /> <path d=\"M12 21v-1\" />", "favorites": "<path d=\"M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z\" />", "room": "<path d=\"M2 20v-8a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v8\" /> <path d=\"M4 10V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4\" /> <path d=\"M12 4v6\" /> <path d=\"M2 18h20\" />", "roomtalk": "<path d=\"M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z\" />", "roomear": "<path d=\"M11 5 6 9H2v6h4l5 4z\" /> <path d=\"M15.54 8.46a5 5 0 0 1 0 7.07\" /> <path d=\"M19.07 4.93a10 10 0 0 1 0 14.14\" />", "roomnote": "<path d=\"M12 20h9\" /> <path d=\"M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z\" />", "roomcreate": "<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\" /> <path d=\"M12 9v4\" /> <path d=\"M12 17h.01\" />", "image": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <circle cx=\"9\" cy=\"9\" r=\"2\" /> <path d=\"m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21\" />", "video": "<path d=\"m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 11\" /> <rect width=\"14\" height=\"12\" x=\"2\" y=\"6\" rx=\"2\" />", "report": "<path d=\"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z\" /> <path d=\"M14 2v4a2 2 0 0 0 2 2h4\" /> <path d=\"M8 13h8\" /> <path d=\"M8 17h5\" />", "update": "<path d=\"M21 12a9 9 0 1 1-3-6.7L21 8\" /> <path d=\"M21 3v5h-5\" />", "question": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3\" /> <path d=\"M12 17h.01\" />"};
  var CATALOG = [
    ['build', [['agent', 'Super agent', 'orange'], ['listen', 'Écoute', 'grey'], ['plus', 'Ajouter', 'grey'], ['claude', 'Claude', 'grey'], ['scenario', 'Scénario', 'grey'], ['cast', 'Cast TV', 'grey'], ['question', 'Question', 'grey']]],
    ['files', [['docs', 'Docs', 'green'], ['image', 'Images', 'green'], ['video', 'Vidéos', 'green'], ['app', 'Apps', 'green'], ['page', 'Pages', 'yellow']]],
    ['voir', [['wallet', 'Wallet', 'grey'], ['nearby', 'Proximité', 'violet'], ['link', 'Lien', 'grey'], ['qr', 'QR code', 'grey'], ['favorites', 'Favoris', 'grey']]],
    ['chamber', [['room', 'Chambre', 'grey'], ['roomtalk', 'Converser', 'green'], ['roomear', 'Écouter', 'violet'], ['roomcreate', 'Create', 'red']]],
    ['bar', [['update', 'Mise à jour', 'grey'], ['settings', 'Réglages', 'grey']]]
  ];
  var BY = { widget: { id: 'widget', group: 'widget', label: 'Widget', tone: 'violet' } }, GROUPS = {};
  var TABS = [['build', 'Agent'], ['files', 'Files'], ['voir', 'Game']];
  CATALOG.forEach(function (g) { GROUPS[g[0]] = g[1].map(function (b) { return b[0]; }); g[1].forEach(function (b) { BY[b[0]] = { id: b[0], group: g[0], label: b[1], tone: b[2] }; }); });
  var STATE = {};
  var BASE = '.aiwa-btn{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:.55em;padding:.7em 1em;cursor:pointer;font:inherit;color:var(--aiwa-fg,#fff);' +
    'background:var(--aiwa-bg,rgba(255,255,255,.12));border:1px solid var(--aiwa-edge,rgba(255,255,255,.28));border-radius:var(--aiwa-radius,14px);-webkit-tap-highlight-color:transparent;transition:transform .15s,background .2s}' +
    '.aiwa-btn:active{transform:scale(.96)}.aiwa-btn svg{width:1.25em;height:1.25em;flex:none}.aiwa-btn[data-on="1"]{background:var(--aiwa-bg-on,rgba(120,255,190,.22))}' +
    '.aiwa-btn[data-tone="red"]{--aiwa-bg:rgba(255,90,90,.25)}.aiwa-btn[data-tone="green"][data-found="1"],.aiwa-btn[data-tone="green"]:not([data-found]){}' +
    '.aiwa-btn[data-found="0"]{opacity:.4}.aiwa-slot{display:flex;flex-wrap:wrap;gap:var(--aiwa-gap,8px)}.aiwa-btn[data-look="icons"] span{display:none}.aiwa-btn[data-look="labels"] svg{display:none}' +
    '.aiwa-sheet{position:fixed;inset:0;z-index:2147483001;font:15px system-ui,sans-serif;color:#fff}.aiwa-back{position:absolute;inset:0;background:rgba(0,0,0,.5)}' +
    '.aiwa-card{position:absolute;left:0;right:0;bottom:0;max-height:78vh;overflow:auto;padding:14px 14px 22px;border-radius:22px 22px 0 0;background:rgba(14,16,40,.95);backdrop-filter:blur(16px)}' +
    '.aiwa-tabs{display:flex;gap:8px;margin-bottom:12px}.aiwa-tab{all:unset;box-sizing:border-box;flex:1;text-align:center;padding:.6em .4em;border-radius:12px;cursor:pointer;background:rgba(255,255,255,.1)}.aiwa-tab[data-on="1"]{background:rgba(167,123,214,.55);font-weight:700}' +
    '.aiwa-card .aiwa-btn{flex:1 1 40%}.aiwa-scns{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.aiwa-scn{padding:12px 14px;border-radius:16px;background:var(--aiwa-bg,rgba(255,255,255,.1));border:1px solid var(--aiwa-edge,rgba(255,255,255,.25));color:var(--aiwa-fg,#fff);display:grid;gap:6px}' +
    '.aiwa-scn h3{margin:0;font-size:1.05em}.aiwa-scn p{margin:0;opacity:.8;font-size:.9em}.aiwa-launch{all:unset;cursor:pointer;justify-self:start;padding:.5em 1em;border-radius:999px;background:var(--aiwa-launch,rgba(120,255,190,.3));font-weight:700}' +
    '.aiwa-dock{position:fixed;right:14px;bottom:14px;z-index:2147483000;font:15px system-ui,sans-serif;color:#fff}.aiwa-dock>button{all:unset;cursor:pointer;width:52px;height:52px;border-radius:50%;display:grid;place-items:center;background:#3a2fa8;box-shadow:0 6px 24px #0008;font-weight:700}' +
    '.aiwa-dock>div{display:none;position:absolute;right:0;bottom:62px;width:min(86vw,340px);max-height:70vh;overflow:auto;padding:12px;border-radius:18px;background:rgba(14,16,40,.92);backdrop-filter:blur(14px);flex-direction:column;gap:10px}.aiwa-dock[data-open="1"]>div{display:flex}';
  function svg(id) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[id] || '') + '</svg>'; }
  function send(msg, evt) {
    if (window.AiwaHomeHost && window.AiwaHomeHost.postMessage) { try { window.AiwaHomeHost.postMessage(JSON.stringify(msg)); return; } catch (e) { } }
    document.dispatchEvent(new CustomEvent(evt, { detail: msg }));
  }
  function press(id) {
    if (id === 'widget') { togglePanel(); return; }
    send({ cmd: 'press', id: String(id) }, 'aiwa-press');
  }
  // the widget over the page: its three tabs, then the buttons of the tab (the same buttons as the slots')
  var sheet = null, tab = 'build';
  function closePanel() { if (sheet) { sheet.remove(); sheet = null; } }
  function drawPanel() {
    if (!sheet) return;
    var tabs = sheet.querySelector('.aiwa-tabs'), body = sheet.querySelector('.aiwa-body');
    tabs.textContent = ''; body.textContent = '';
    TABS.forEach(function (t) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 'aiwa-tab'; b.textContent = t[1]; b.setAttribute('data-on', t[0] === tab ? '1' : '0');
      b.addEventListener('click', function () { tab = t[0]; drawPanel(); }); tabs.appendChild(b);
    });
    (GROUPS[tab] || []).forEach(function (id) { var b = make(id, ''); b.addEventListener('click', closePanel); body.appendChild(b); });
  }
  function togglePanel() {
    if (sheet) { closePanel(); return; }
    sheet = document.createElement('div'); sheet.className = 'aiwa-sheet';
    sheet.innerHTML = '<div class="aiwa-back"></div><div class="aiwa-card"><div class="aiwa-tabs"></div><div class="aiwa-body aiwa-slot"></div></div>';
    sheet.firstChild.addEventListener('click', closePanel);
    document.body.appendChild(sheet); drawPanel();
  }
  // the scenarios of the page: scenarios.json next to it, one card each; Launch hands the scenario to the application (it runs it in the account of whoever looks)
  function drawScenarios(box) {
    if (box.__aiwaScn) return; box.__aiwaScn = true;
    var src = box.getAttribute('data-aiwa-scenarios') || 'scenarios.json';
    fetch(new URL(src, document.baseURI).href).then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; }).then(function (list) {
      if (!Array.isArray(list) || !list.length) { box.hidden = true; return; }
      box.textContent = ''; box.classList.add('aiwa-scns'); box.hidden = false;
      list.slice(0, 12).forEach(function (sc) {
        if (!sc || !sc.name) return;
        var card = document.createElement('article'); card.className = 'aiwa-scn';
        var h = document.createElement('h3'); h.textContent = String(sc.name).slice(0, 40);
        var p = document.createElement('p'); p.textContent = String(sc.desc || sc.prompt || '').slice(0, 150);
        var b = document.createElement('button'); b.type = 'button'; b.className = 'aiwa-launch'; b.textContent = 'Lancer chez moi';
        b.addEventListener('click', function () { send({ cmd: 'scenario', scenario: sc }, 'aiwa-scenario'); });
        card.appendChild(h); card.appendChild(p); card.appendChild(b); box.appendChild(card);
      });
    });
  }
  function ids(slot) {
    var spec = (slot.getAttribute('data-aiwa-slot') || '').split(/[\s,]+/).filter(Boolean), out = [];
    spec.forEach(function (g) { (g === 'all' ? Object.keys(BY).filter(function (k) { return k !== 'widget'; }) : (GROUPS[g] || [])).forEach(function (i) { if (out.indexOf(i) < 0) out.push(i); }); });
    var only = (slot.getAttribute('data-aiwa-only') || '').split(/[\s,]+/).filter(Boolean), skip = (slot.getAttribute('data-aiwa-skip') || '').split(/[\s,]+/).filter(Boolean);
    if (only.length) out = out.filter(function (i) { return only.indexOf(i) >= 0; });
    return out.filter(function (i) { return skip.indexOf(i) < 0; });
  }
  function make(id, look) {
    var def = BY[id], st = STATE[id] || {}, label = st.label || def.label;
    var b = document.createElement('button'); b.type = 'button'; b.className = 'aiwa-btn'; b.setAttribute('data-id', id); b.setAttribute('data-group', def.group);
    b.setAttribute('data-tone', st.tone || def.tone); if (st.on != null) b.setAttribute('data-on', st.on ? '1' : '0'); if (st.found != null) b.setAttribute('data-found', st.found ? '1' : '0');
    if (look) b.setAttribute('data-look', look); b.title = label; b.setAttribute('aria-label', label);
    b.innerHTML = svg(st.icon || id) + '<span>' + label.replace(/[<&]/g, '') + '</span>';
    b.addEventListener('click', function (ev) { ev.preventDefault(); press(id); });
    return b;
  }
  function fill(slot) {
    var look = slot.getAttribute('data-aiwa-look') || '';
    if (slot.hasAttribute('data-aiwa-button')) { var id = slot.getAttribute('data-aiwa-button'); if (!BY[id]) return; slot.textContent = ''; slot.appendChild(make(id, look)); return; }
    slot.classList.add('aiwa-slot'); slot.textContent = '';
    ids(slot).forEach(function (id) { slot.appendChild(make(id, look)); });
  }
  function slots() { return [].slice.call(document.querySelectorAll('[data-aiwa-slot],[data-aiwa-button]')).filter(function (n) { return n.tagName !== 'BUTTON' || n.hasAttribute('data-aiwa-slot'); }); }
  var dock = null;
  function render() {
    if (!document.getElementById('aiwa-home-base')) { var st = document.createElement('style'); st.id = 'aiwa-home-base'; st.textContent = BASE.replace(/(^|\})([^{}]+)\{/g, function (m, a, sel) { return a + sel.split(',').map(function (s) { return ':where(' + s.trim() + ')'; }).join(',') + '{'; }); (document.head || document.documentElement).appendChild(st); }
    var list = slots();
    list.forEach(fill);
    [].slice.call(document.querySelectorAll('[data-aiwa-scenarios]')).forEach(drawScenarios);
    [].slice.call(document.querySelectorAll('[data-aiwa-favorites]')).forEach(drawFavorites);
    // a page with no slot at all still gives access to everything: a round button opens the whole catalogue (a page may say it does not want it: <meta name="aiwa-home" content="none">)
    var none = document.querySelector('meta[name="aiwa-home"][content="none"]');
    if (!list.length && !none && !document.querySelector('[data-aiwa-scenarios],[data-aiwa-favorites]')) {
      if (!dock) { dock = document.createElement('div'); dock.className = 'aiwa-dock'; dock.innerHTML = '<button type="button" aria-label="Aiwa">A</button><div></div>'; dock.firstChild.addEventListener('click', function () { dock.setAttribute('data-open', dock.getAttribute('data-open') === '1' ? '0' : '1'); }); document.body.appendChild(dock); }
      var panel = dock.lastChild; panel.textContent = ''; CATALOG.forEach(function (g) { var row = document.createElement('div'); row.className = 'aiwa-slot'; g[1].forEach(function (b) { row.appendChild(make(b[0], '')); }); panel.appendChild(row); });
    } else if (dock) { dock.remove(); dock = null; }
    if (sheet) drawPanel();
  }
  // the favourites of the person: the application sends them to HER page only (a visitor never sees the visitor's own favourites in someone else's page)
  var FAVS = [];
  var KIND = { docs: 'Docs', image: 'Images', video: 'Vidéos', app: 'Apps', page: 'Pages' };
  function drawFavorites(box) {
    box.textContent = ''; box.classList.add('aiwa-scns'); box.hidden = !FAVS.length;
    FAVS.forEach(function (f) {
      var card = document.createElement('article'); card.className = 'aiwa-scn aiwa-fav';
      var h = document.createElement('h3'); h.textContent = f.repo || 'Lien'; card.appendChild(h);
      var p = document.createElement('p');
      (f.links || []).forEach(function (l, i) { if (!/^https:\/\//.test(l.url)) return; var a = document.createElement('a'); a.href = l.url; a.textContent = KIND[l.kind] || l.kind; a.style.cssText = 'color:inherit;margin-right:.9em'; p.appendChild(a); });
      card.appendChild(p); box.appendChild(card);
    });
  }
  function setFavorites(list) { if (!Array.isArray(list) || JSON.stringify(list) === JSON.stringify(FAVS)) return; FAVS = list; render(); }
  function setState(next) { if (!next || typeof next !== 'object') return; if (JSON.stringify(next) !== JSON.stringify(STATE)) { STATE = next; render(); } }
  window.aiwa = { press: press, panel: togglePanel, render: render, setState: setState, setFavorites: setFavorites, catalog: BY, groups: GROUPS };
  var queued = false;
  new MutationObserver(function (muts) {
    if (queued) return;
    // what the runtime itself draws inside a slot does not start another drawing
    if (muts.every(function (m) { return m.target.nodeType === 1 && m.target.closest && m.target.closest('[data-aiwa-slot],[data-aiwa-button],[data-aiwa-scenarios],[data-aiwa-favorites],.aiwa-dock,.aiwa-sheet'); })) return;
    queued = true; setTimeout(function () { queued = false; render(); }, 60);
  }).observe(document.documentElement, { childList: true, subtree: true });
  render();
})();
