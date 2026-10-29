# Aiwa

Un assistant qui vit sur le téléphone, parle à Claude, et fait des documents, des images, des vidéos, des apps et des pages, à la voix.

- **Le widget** : Super agent, Oreille, Ajouter, Claude, Rapport · Files (docs, images, vidéos, apps, pages, en release) · Scénario, Cast TV · Voir · Chambre.
- **L'accueil** : la page du profil de la personne, avec ses boutons ; chez quelqu'un d'autre, le dessin est le sien et les boutons sont ceux du visiteur (match, chambre, café, widget).
- **Le wallet** : passphrase, taux, burn, claimable, claim, historique.
- **Le super agent** : omniscient, il parle à voix haute, même dans la chambre.

L'architecture est dans [ARCHITECTURE.md](ARCHITECTURE.md). Les papers (yellow paper, valeur, film) sont dans `docs/`.

## Installer

Sur le téléphone : installe Termux (F-Droid), puis colle cette ligne dedans, une fois :

```
curl -fsSL https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/scripts/bootstrap.sh | bash
```

Elle installe le cerveau (Python, dans Termux), la ligne de commande de Claude, et télécharge l'APK dans le dossier Téléchargements : ouvre-le avec l'application Fichiers, puis ajoute le widget Aiwa sur l'écran d'accueil.

## Construire

```
npm install
npm test            # le protocole (packages/) et l'application web (web/)
npm run build:web   # web/dist
```
