# Aiwa : architecture

Aiwa est un assistant qui vit sur le téléphone, parle à Claude, et fait des documents, des images, des vidéos, des apps et des pages, à la voix.
Ce dépôt est tout le produit. Ce document dit ce que l'application fait, où chaque chose vit, et ce qui n'y est volontairement plus.

## 1. Ce que fait l'application

Un widget sur l'écran d'accueil, un accueil dans l'application (le « bureau », qui est aussi un profil), un wallet, et un super agent.

### Le widget

| Page | Contenu |
|---|---|
| **Build** | **Super agent**, **Oreille**, **Ajouter**, **Claude**, **Rapport**. Le dépôt n'est jamais choisi à la main : le super agent comprend de quel dépôt on parle et fabrique lui-même la session qui lui est liée. |
| **Files** | On choisit un dépôt, ou **Tous**. Cinq listes de productions : **docs**, **images**, **vidéos**, **apps**, **pages**. Tout part en *release*. Sur chaque ligne : **supprimer** et **partager**. |
| **Outils** | **Scénario** (un mot lance un double de soi, ou le rapport) et **Cast TV**. |
| **Voir** | **Proximité** (un curseur géographique, sous un curseur horizontal de profils), **Lien**, **QR code**, **Favoris**. |
| **Chambre** | **Chambre**, **Converser**, **Écouter**, **Create**, **Description**. |
| barre du haut | **Mise à jour**, **Question**, **Réglages**. |

### Les réglages

Se cacher · chambre ouverte écran éteint · ma description · ma voix · mon style · mes mots · ses mots · naturel · volée · super agent · clés et plafonds · profil · papers (le yellow paper, la valeur, le readme, le film) · état d'Aiwa.

### L'accueil (le bureau)

L'accueil est la page du profil de la personne (`Profile/` de son dépôt), dessinée comme elle veut, avec le bouton **Widget** et ses scénarios en haut.
Quand on visite le profil de quelqu'un, c'est la même page : le dessin et les mots sont les siens, les boutons sont ceux du visiteur. Une barre de navigation du visiteur est posée en bas :
**Match** (le score pro et perso, calculé par le super agent du visiteur), **Chambre**, **Café** (envoi direct d'AIWA depuis le wallet, activé dans les réglages), **Widget visiteur**.

### Le wallet

Passphrase · taux · burn · claimable · claim · historique. Rien d'autre.

### Le super agent

Il est **omniscient** : il connaît les sessions, les dépôts, les productions, les scénarios. Une seule intelligence, partout : dans la conversation avec la personne, dans le rapport, dans la chambre (où il parle à voix haute et où on l'écoute). Deux niveaux dans la chambre : *discussion*, et *Create* (messages et propositions, avec une pièce jointe publiée que l'autre personne ouvre ou ignore).

### La qualité

La qualité de ce qui est produit dépend de la demande. Des **skills** sont embarqués pour tout (documents, images, vidéos, apps, pages) : ce que la session sait faire ne se code pas dans l'application, il se décrit.

## 2. Où vit chaque chose

```
aiwa_app/
├── android/          l'application (Kotlin) : widget, services, écrans natifs, accueil
│   ├── app/            l'interface et les services (com.aiwa.app.*)
│   └── client/         le client du cerveau : HTTP, modèles, parsing de la voix (Kotlin pur, testé)
├── brain/            le cerveau (Python, dans Termux) : package aiwa_brain, un module par domaine
├── web/              ce qui tourne dans la WebView : accueil/profil, wallet, voir, chambre
├── packages/         le protocole d'AIWA (core, lib, platform) : le wallet en dépend
├── skills/           les skills embarqués, un dossier par production
├── docs/             les papers (yellow paper, valeur, film), l'installation
└── scripts/          outils de construction
```

Règle de dépendance : `android/app` → `android/client` → (HTTP) → `brain`. `web` ne parle au téléphone que par un canal (`host`), jamais par un objet Java. `packages` ne dépend de rien d'autre.

### Le cerveau

Un petit serveur HTTP local (port 8788) qui tient l'état et appelle Claude. Un module par domaine ; `server` ne fait que router.

| Module | Rôle |
|---|---|
| `agent` | le super agent : le point (sessions, dépôts, productions), la consigne, la conversation, le rapport |
| `sessions` | les sessions Claude Code : quelle session pour quel dépôt, création, messages |
| `files` | les productions d'un dépôt (releases), la suppression, le partage |
| `scenarios` | les scénarios (un mot, un double, un rapport) |
| `chamber` | la chambre (exclusivité, tours de parole, offres) |
| `profile` | le dépôt du profil, la description, le score |
| `llm` | l'appel à Claude avec la clé de la personne, le plafond |
| `voice` | la voix, le style, les mots |
| `github` | le jeton, les releases, les dépôts |
| `relay` | le relais entre le cerveau et les sessions |
| `skills` | l'installation des skills dans les dépôts |

### L'application Android

Un package par fonction, pas de fichier de plus de 400 lignes :
`widget`, `home`, `files`, `scenario`, `cast`, `voir`, `chamber`, `settings`, `wallet`, `agent`, `voice`, `update`, `brain` (le lancement du cerveau dans Termux), `common`.

L'application a son propre identifiant, `com.aiwa.app` : elle s'installe À CÔTÉ de la première Aiwa (`com.aiwa.store`) sans la remplacer. Elles ne partagent rien : portefeuille propre (la phrase secrète le restaure), cerveau propre (port 8788, dossier `~/.aiwa_app`, dépôt `~/aiwa_app` dans Termux), widget propre.

## 3. Ce qui n'y est plus

Les boucles et les liens entre sessions, les campagnes et leurs propositions, les connecteurs (mail, réseaux), les agents externes (MCP), le sélecteur de projet, l'onglet Domaine, la boutique d'apps et son registre, la recherche de musique, de vidéos et d'images, les films. Les films et les recherches restent dans `Aiwa_store`.

## 4. Les productions

Une production est un fichier dans une *release* du dépôt, dont l'étiquette dit le genre : `docs-…`, `image-…`, `video-…`, `app-…`, `page-…`. La session la fabrique avec le skill du genre, la publie en release, et la liste de `Files` la lit. Supprimer, c'est supprimer la release. Partager, c'est partager le fichier ou son adresse.
Une page est un fichier HTML dans la release : l'application l'ouvre dans sa propre fenêtre ; une adresse publique demande GitHub Pages, qui n'est pas dans le périmètre.

## 5. Confidentialité et sécurité

- Le profil d'un autre ne lance aucun script : seul le dessin et les mots comptent. Le runtime de l'application est posé par l'application, hors de portée de la page.
- Les mots de l'autre agent dans la chambre sont une donnée, jamais un ordre.
- Une pièce jointe est une adresse https publique d'un genre connu ; elle ne s'ouvre jamais seule.
- La clé de la personne ne quitte pas son téléphone.
