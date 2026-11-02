# Profil

La page de la personne est le dossier `Profile/` de son dépôt de profil : `Profile/index.html` (une page autonome, dessinée comme elle le veut), et `Profile/profile.json` (nom, description courte, liens). Elle s'ouvre comme accueil du téléphone et se met à jour dès un nouveau commit sur la branche par défaut ; garde-la rapide et sobre. Pousse sur la branche indiquée dans les consignes.

Quand la personne te demande de modifier son profil, sa barre ou son widget, c'est du travail ordinaire sur deux fichiers de ce dépôt : `Profile/index.html` (la page et les emplacements de boutons) et `Profile/aiwa-ui.json` (la barre du bas). Tu n'as rien d'autre à demander à l'application.

## Les boutons d'Aiwa dans la page (le widget de l'application)

Les boutons ne s'écrivent pas : tu poses des EMPLACEMENTS et l'application y met les vrais boutons, qui agissent au nom de celui qui regarde.

- `<div data-aiwa-slot="build"></div>` : tous les boutons d'un groupe. Groupes : `build` (Super agent, Ajouter, Claude, Scénario, Cast TV, Question), `files` (Docs, Images, Vidéos, Apps, Pages), `voir` (Wallet, Zone, Chambres, Lien, QR code, Favoris), `bar` (Mise à jour, Réglages). Plusieurs groupes : `data-aiwa-slot="build voir"` ; tous : `data-aiwa-slot="all"`.
- `<button data-aiwa-button="docs"></button>` : un seul bouton. Identifiants : agent, plus, claude, scenario, cast, question, docs, image, video, app, page, wallet, nearby, link, qr, favorites, room (la liste des chambres), update, settings, report ; `widget` est UN bouton qui ouvre tout le widget (ses onglets) sur la page.
- Dans un emplacement : `data-aiwa-only="docs,image"` garde seulement ceux-là, `data-aiwa-skip="cast"` retire ceux-là, `data-aiwa-look="icons"`, `"labels"` ou `"both"` règle l'aspect.
- `<div data-aiwa-scenarios></div>` : les scénarios de la page (`Profile/scenarios.json` à côté) ; `<section data-aiwa-favorites></section>` : les favoris de la personne, sur sa propre page seulement.
- Le style est de la CSS ordinaire sur la classe `.aiwa-btn`, les attributs `data-tone`, `data-on`, `data-id`, et les variables `--aiwa-fg`, `--aiwa-bg`, `--aiwa-edge`, `--aiwa-radius`, `--aiwa-gap`.
- Une page sans aucun emplacement garde un bouton rond (en bas à droite) qui ouvre le catalogue complet ; `<meta name="aiwa-home" content="none">` le retire.


## La barre du bas de l'application (`Profile/aiwa-ui.json`)

`{"v":1,"bar":[{"action":"zone","icon":"📍","label":"Autour","tone":"violet"},{"action":"url:https://…","icon":"🎬","label":"Film"}]}`

- Autant de touches que la personne veut, dans l'ordre voulu. `label` : le nom ; `icon` : un emoji ; `tone` : violet, blue, gold, green, white ou #RRGGBB.
- `action` : une touche de l'application (favoris, swipe, precedent, give, reseau, match, chambre, cafe, zone, mur, widget, rang), un écran (files_docs, files_image, files_video, files_app, files_page, files, build, scenario, cast, voir, voir_near, voir_link, voir_qr, voir_fav, chambre, chambres, repo, session, set_accounts, set_words, set_persona, set_me, set_voice, set_papers, set_model, set_health, set_ear, set_ready, set_push, set_bg, settings, update, question, claude, add, listen, wallet, report, home, github, health, claude_login, keys, style, wall), ou `url:https://…`. Une action que l'application ne connaît pas ne fait rien.
- Sans fichier, la barre est celle de l'application : sur sa propre page, favoris, reseau, mur, widget ; sur le profil de quelqu'un d'autre, favoris, swipe, reseau, give, match, widget (et rang quand il y a plusieurs profils). Une touche absente du fichier disparaît.
- Retour au départ : supprimer le fichier, ou en pousser un invalide ou vide ; la barre redevient celle de l'application.
- Le widget du bureau d'Android n'est jamais touché par ce fichier ni par la page : il est dans l'application.

Pousse sur la branche par défaut : le changement apparaît dans les secondes qui suivent ton commit.

## Tout remettre par défaut

Quand la personne demande de rétablir le défaut, de tout remettre à zéro ou de recommencer son profil : supprime `Profile/index.html` et `Profile/aiwa-ui.json` dans son dépôt de profil (sur la branche par défaut). L'application affiche alors l'accueil d'origine d'Aiwa, exactement celui d'une application neuve (tous les boutons, avec un mot qui explique comment faire sa propre page), avec le moteur et le design d'aujourd'hui : ils ne sont pas dans son dépôt et ne se rétablissent pas, ils ne changent pas. Ses médias, ses scénarios (`Profile/scenarios/`) et sa fiche `Profile/profile.json` restent, sauf si elle demande aussi de les effacer. Dis-lui ensuite qu'elle peut recommencer sa page en te la demandant.
