# Modèle économique

*À présenter tel quel, avec ses limites. Tout ce qui est chiffré ici vient du code de ce dépôt (formules, tests) ou d'un calcul que
chacun peut refaire ; ce qui est une hypothèse est écrit comme telle. Ce n'est pas un avis juridique.*

## En une phrase

Le Store n'a ni publicité, ni commission sur les apps, ni frais sur les transferts. Il y a **un seul flux d'argent** : quand quelqu'un
mine, il brûle du SOL et choisit une part **T** de ce brûlage (0 à 40 %) qui ne compte pas comme capital ; **0,1 % de cette part T va à
une adresse fixe, celle du créateur**, dans la même transaction que le brûlage. Le reste du brûlage est détruit, comme avant.

> Miner en payant un petit impôt à un tiers, qui n'est pas choisi par l'utilisateur.

## Qui paie qui

```
utilisateur ── brûle 1 SOL, T = 40 % ──►  incinérateur Solana   0,9996 SOL   (détruit)
                                      └►  adresse du créateur   0,0004 SOL   (0,1 % de la part T = 0,4 SOL)
                capital qui mine = 1 × (1 − 0,4) = 0,6 SOL
```

- Le montant est calculé en entiers (`creatorFeeLamports`), le portefeuille l'affiche **avant** de signer, et chaque lecteur
  vérifie sur Solana que le créateur a bien reçu sa part : un engagement à T > 0 dont la part n'a pas été payée est refusé.
- À T = 0 (le défaut), le créateur ne reçoit rien.
- Le taux et l'adresse sont des paramètres du protocole (`deployment.json`, yellow paper §11) : ils changent par une nouvelle version
  des règles, jamais par un réglage de l'app ni du portefeuille. L'utilisateur ne choisit pas qui est payé.

## Pourquoi quelqu'un choisirait T > 0

Parce que, pour qui mine longtemps, un T plus haut rapporte **plus** par SOL brûlé. Calcul avec `reward()` (les paramètres de
`deployment.json`, une identité neuve, capital brûlé de 1 SOL) : ce que 1 SOL brûlé permet de réclamer après *q* époques minées.

| époques minées | T = 0 | T = 20 % | T = 40 % | T = 40 % / T = 0 |
|---:|---:|---:|---:|---:|
| 10 | 0,0109 | 0,0087 | 0,0065 | 0,60 |
| 100 | 0,118 | 0,107 | 0,082 | 0,69 |
| 1 000 | 0,568 | 0,851 | 0,973 | 1,72 |
| 10 000 | 3,02 | 4,72 | 8,04 | 2,66 |
| 100 000 | 19,5 | 30,4 | 54,0 | 2,77 |

Au début T > 0 coûte (la part T ne compte pas), puis la courbe plus généreuse l'emporte : le point de passage est entre 100 et 1 000
époques, et à terme T = 40 % rapporte environ **2,8 fois** plus par SOL brûlé que T = 0. Un mineur patient a donc intérêt
à choisir T = 40 %, ce qui est l'hypothèse de calcul du revenu ci-dessous. (T est un taux de patience : on paie maintenant pour que
la courbe soit plus généreuse plus tard.) Cela dépend des paramètres actuels, pas encore éprouvés sur le terrain.

## Le revenu, et ce qu'il faut pour qu'il compte

Revenu du créateur = SOL brûlés × T × 0,1 %. À T = 40 % : **0,0004 SOL par SOL brûlé**, soit 2 500 SOL brûlés pour 1 SOL gagné.

| SOL brûlés par mois (T = 40 %) | revenu du créateur, en SOL | en USD si 1 SOL = 100 USD *(hypothèse, pas une prévision)* |
|---:|---:|---:|
| 100 | 0,04 | 4 |
| 1 000 | 0,4 | 40 |
| 10 000 | 4 | 400 |
| 100 000 | 40 | 4 000 |
| 1 000 000 | 400 | 40 000 |

**Conclusion honnête : à petite échelle, ce n'est pas un salaire.** Pour 5 000 USD par mois (50 SOL à 100 USD), il faut environ
125 000 SOL brûlés par mois. Le taux de 0,1 % est celui du départ ; le changer est possible (par une nouvelle version des règles,
visible dans le portefeuille avant chaque brûlage), et à 1 % le même revenu demanderait dix fois moins de brûlage. Ce n'est pas
décidé ici : un taux plus haut est un coût plus visible pour l'utilisateur.

## Ce qui crée la demande de brûlage

Il faut le dire clairement : **aujourd'hui, AIWA n'a ni prix, ni marché, et le Store ne l'accepte pas en paiement.** Personne n'a de
raison de brûler du vrai SOL pour en obtenir. Les seules raisons que ce dépôt construit :

1. **Publier une app exige d'avoir miné** : le registre refuse une première app si l'auteur n'a rien à réclamer (donc rien brûlé), et
   le classement des apps est `score / laps` — ce qu'un auteur a miné. Plus l'auteur a brûlé et miné, plus son app monte. Brûler est
   donc, de fait, la manière de se rendre visible. C'est un classement « au capital et au temps », pas à la qualité : à dire en
   toutes lettres, avec ses risques (juridiques et de réputation).
2. L'attrait propre de miner de l'AIWA, qui n'existe que si l'AIWA finit par servir à quelque chose. Ce n'est pas construit.

Ce qui reste à démontrer, et que cette version ne démontre pas : qu'il y a des auteurs d'apps et des utilisateurs qui veulent être là.
Les premières mesures à prendre sont simples : nombre d'apps soumises et acceptées, nombre de portefeuilles qui brûlent, SOL brûlés
par mois, part brûlée à T > 0.

## Coûts

- **Infrastructure : zéro.** Le registre est un dépôt GitHub (un workflow vérifie et écrit les fichiers), le site est servi par
  GitHub Pages, le protocole n'a pas de serveur, l'APK est construit par GitHub Actions. Rien à héberger tant qu'il n'y a pas
  d'échelle ; les limites sont celles de GitHub.
- **Le module de dictée** (facultatif) utilise l'abonnement Claude de l'utilisateur ; rien n'est facturé par le Store.
- **Le temps**, et pas encore de poste de dépense identifié pour le droit, les comptes, une éventuelle société.

## Risques

- **Juridique : non vérifié.** Un magasin sans permission, un classement qu'on obtient en brûlant, une redevance perçue sur des
  brûlages de cryptomonnaie : le statut de chacun de ces éléments (en Suisse comme ailleurs : intermédiation financière, valeurs
  mobilières, protection des consommateurs, fiscalité du revenu perçu) n'a pas été examiné. Une consultation juridique est une étape
  avant tout lancement public avec de l'argent réel.
- **Distribution Android.** L'APK s'installe à la main (hors Google Play). Le Play Store a des règles sur les applications liées aux
  cryptomonnaies et sur le contenu généré par l'utilisateur : ce n'est pas examiné ici.
- **Contenu des apps.** Elles ne sont pas relues ; elles tournent dans un cadre isolé qui ne voit pas le portefeuille, mais elles
  peuvent utiliser le réseau. Il n'y a pas de modération dans le code ; c'est un choix qui a un coût.
- **Fourche.** La licence est MIT : n'importe qui peut reprendre le code et changer l'adresse du créateur. Ce sera un autre déploiement,
  avec son propre registre et sa propre économie ; il ne prend rien à celui-ci, mais il peut aussi lui concurrencer l'attention.
- **Prix du SOL, paramètres économiques non éprouvés, un seul vérificateur de brûlage (le RPC Solana).** Rien n'a été exécuté contre le
  vrai réseau Solana (devnet compris) ni sur de vrais téléphones.

## Ce qu'on peut montrer aujourd'hui

- Un dépôt unique, 722 tests JavaScript (protocole, registre, application web dans un vrai navigateur) et 208 tests Python (le cerveau, backend Termux) qui passent, CI verte sur le JavaScript.
- Le portefeuille qui affiche, avant de signer, ce que fait un brûlage et ce que reçoit le créateur ; la redevance appliquée par le
  protocole lui-même, pas par une convention.
- Un Store où chaque app est signée par son auteur, vérifiée avant ouverture, isolée du portefeuille ; un classement `score / laps` repris
  tel qu'il existait.
- Ce qu'on **ne peut pas** montrer : un brûlage réel, un utilisateur, une app publiée par un tiers.

## Étapes, avec de quoi vérifier chacune

1. **Un brûlage réel sur le devnet de Solana**, de bout en bout (portefeuille → transaction → registre qui le confirme) :
   `node scripts/devnet-check.mjs` (ou le workflow *Devnet check*) le fait, avec un portefeuille devnet financé une fois. Fait quand :
   le script passe contre le vrai devnet. Il passe contre un faux Solana ; le faucet a refusé les machines GitHub.
2. **L'adresse du créateur** : renseignée dans `deployment.json` (`GABatPZG…NqvWEp`). Tant que le réseau configuré est le devnet, elle reçoit du SOL de devnet, sans valeur.
3. **Pages activé et le registre en ligne** ; un premier auteur tiers publie une app par pull request.
4. **Un avis juridique** sur les trois points ci-dessus, avant tout brûlage en argent réel proposé au public.
5. **Mesures** (voir plus haut) sur 3 mois, puis décision sur le taux et la suite.
