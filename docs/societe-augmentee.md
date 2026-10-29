# VISION PAPER
# SOCIÉTÉ AUGMENTÉE
### Une infrastructure sociale de proximité pour le monde physique

**Document de vision produit, technologique et stratégique — Version 1.0 — Octobre 2026**

**Statut :** vision fondatrice et proposition d’architecture à valider par des prototypes.

> Aiwa (le portefeuille, le Store, le widget vocal) est le socle logiciel de cette vision. Aucune des fonctions décrites ci-dessous (détection optique, localisation, affichage dans des lunettes) n’est démontrée à ce jour : c’est un cap et un plan de preuves. Les seuils chiffrés du §13 sont des objectifs à tester, pas des résultats.

---

## 1. Résumé exécutif

Nous sommes à l’aube d’une nouvelle génération d’interfaces numériques.

Depuis vingt ans, les réseaux sociaux ont déplacé une part croissante de nos relations dans des applications, des fils d’actualité et des espaces numériques séparés de notre environnement physique. La réalité augmentée a ensuite proposé de superposer des informations et des objets virtuels au monde réel.

Mais ces deux approches partagent une limite : elles considèrent encore principalement le monde physique comme un environnement dans lequel on consulte des informations numériques.

**Notre ambition est différente : faire du monde physique lui-même un espace social programmable.**

Nous proposons de développer une infrastructure de proximité destinée aux lunettes intelligentes, dans laquelle les personnes participantes peuvent être détectées, localisées et associées à leur identité numérique, puis devenir le point de départ d’interactions sociales et d’expériences partagées.

Lorsqu’un utilisateur regarde une autre personne participante, son profil peut apparaître à la position correspondante dans son champ de vision. Il peut découvrir ses centres d’intérêt, consulter ses créations, engager une interaction ou lui proposer instantanément un jeu.

Cette expérience repose sur une séparation claire des responsabilités :

- **Le dispositif optique** assure l’identification et contribue à la localisation relative des lunettes à proximité.
- **Les lunettes** assurent la perception de l’environnement, le suivi spatial et l’affichage.
- **Le téléphone** fournit la connectivité, les services et les capacités de calcul nécessaires.
- **Le réseau social** gère les identités, les relations, les autorisations et les interactions.
- **La plateforme de développement** permet à des tiers de créer, publier et déployer des expériences utilisables dans le monde physique.

Le système ne nécessite pas de construire un monde virtuel autonome. Il enrichit les interactions qui existent déjà autour de nous.

Notre thèse est que les lunettes ne doivent pas être conçues comme un simple accessoire technologique. Elles constituent un nouveau point d’accès à une infrastructure sociale distribuée.

**Nous ne voulons pas augmenter le monde. Nous voulons augmenter les possibilités de la société humaine.**

---

## 2. La vision fondatrice

### 2.1. Les lunettes sont une interface sociale

Une paire de lunettes possède une propriété particulière : elle accompagne naturellement le regard de son porteur. Contrairement au téléphone, elle ne nécessite pas de détourner constamment son attention de son environnement.

Cette position en fait une interface potentielle entre trois dimensions :

1. Ce que l’utilisateur voit.
2. Les personnes présentes autour de lui.
3. Les possibilités numériques qu’il peut activer dans ce contexte.

Une lunette intelligente ne devrait donc pas être définie uniquement par son écran, sa caméra ou ses capacités d’assistance.

Elle peut devenir un moyen de rendre les identités, les relations et les expériences numériques accessibles au moment où les personnes se rencontrent réellement.

### 2.2. Le monde physique devient un espace d’interaction

Imaginons une rencontre ordinaire.

Une personne entre dans un café. Une autre personne, assise à proximité, participe au réseau. Les lunettes détectent sa présence et peuvent déterminer sa position relative.

Si les deux personnes ont choisi de rendre leur présence visible, un indicateur discret apparaît à côté de la personne concernée. L’utilisateur peut alors ouvrir son profil.

Il découvre qu’ils partagent un intérêt pour les échecs. Il lui propose une partie rapide. L’autre personne accepte. Une expérience commune se lance, sans qu’ils aient besoin d’entrer dans un monde virtuel distinct.

La technologie s’efface derrière la rencontre.

Le même principe peut s’appliquer à un événement, une université, un espace de travail, une exposition, une communauté locale ou une activité collective.

### 2.3. Une société augmentée, pas un métavers

Le métavers cherche souvent à créer des espaces numériques dans lesquels les utilisateurs se rencontrent.

Notre approche commence par l’existence des personnes dans le monde physique.

Nous ne cherchons pas à remplacer les lieux réels par des environnements virtuels. Nous voulons permettre à ces lieux de devenir des espaces dans lesquels les identités numériques et les expériences interactives peuvent être activées, avec le consentement des participants.

Le monde réel reste le contexte principal. Le numérique devient une couche d’interaction.

---

## 3. Le problème à résoudre

Les technologies actuelles sont encore organisées autour de plusieurs systèmes distincts.

### Les réseaux sociaux

Ils permettent de découvrir des personnes, mais reposent principalement sur des recherches, des contacts préexistants, des contenus publiés et des interactions à distance.

### Les applications mobiles

Elles donnent accès à une grande variété de services, mais imposent généralement de sortir son téléphone, d’ouvrir une application et de passer par une interface spécifique.

### Les lunettes intelligentes

Elles peuvent apporter des informations dans le champ de vision, mais leur potentiel social dépend encore largement des applications, des plateformes et des mécanismes de découverte disponibles.

### Les environnements de réalité augmentée

Ils permettent de positionner des contenus numériques dans l’espace, mais ne fournissent pas automatiquement une infrastructure universelle d’identification sociale et d’interaction entre personnes.

Le problème n’est donc pas l’absence d’écrans, de capteurs ou d’applications.

**Le problème est l’absence d’une couche de proximité qui relie de manière cohérente la présence physique, l’identité numérique, la position spatiale et les expériences interactives.**

C’est cette couche que nous voulons construire.

---

## 4. Le produit : une infrastructure sociale de proximité

Le projet se compose de cinq éléments complémentaires.

### 4.1. La couche physique : détecter et localiser

Chaque paire de lunettes participante possède une identité technique et un moyen de signalisation compatible avec le système de proximité.

Une approche à base de communication optique, notamment de technologies apparentées au Li-Fi ou à la communication par lumière visible, constitue une piste privilégiée pour étudier cette couche.

L’objectif est de fournir suffisamment d’informations pour que le système puisse :

- détecter la présence d’une paire de lunettes participante ;
- identifier son signal sans exposer inutilement une identité permanente ;
- déterminer sa direction et, si l’architecture le permet, sa position relative ;
- distinguer plusieurs participants présents simultanément ;
- maintenir une association stable entre le signal détecté et la personne visible.

Le module optique doit rester aussi petit, léger et économe en énergie que possible.

Il ne doit pas devenir un ordinateur autonome. Son rôle est celui d’un composant d’infrastructure.

### 4.2. La couche spatiale : placer l’information au bon endroit

Détecter une paire de lunettes ne signifie pas nécessairement savoir où se trouve son porteur dans l’image.

Le système doit résoudre deux problèmes distincts :

1. **Identification radio ou optique :** quel appareil participant est à proximité ?
2. **Association spatiale :** quelle personne visible porte cet appareil, et où se trouve-t-elle dans le champ de vision ?

Le second problème est essentiel.

La position doit rester associée à la personne correspondante lorsque l’utilisateur bouge la tête, lorsque les personnes se déplacent ou lorsque plusieurs participants sont proches.

Le système pourra s’appuyer sur les capacités spatiales des lunettes, leurs caméras et leurs algorithmes de suivi, selon le matériel retenu.

La vision par ordinateur ne doit pas être utilisée pour identifier automatiquement des inconnus à partir de leur visage. L’association peut reposer sur le signal technique, le suivi de position et, lors des premiers prototypes, un marqueur visuel volontaire.

### 4.3. La couche mobile : le téléphone comme relais et moteur de services

Le téléphone reste un élément central de l’architecture.

Il fournit notamment :

- la connexion Internet ;
- l’accès au réseau social ;
- la résolution des identifiants techniques vers les profils autorisés ;
- les échanges de données ;
- les notifications et invitations ;
- la coordination des expériences multijoueurs ;
- les mises à jour et la gestion des paramètres de confidentialité.

Cette architecture évite de chercher à intégrer immédiatement toutes les fonctions dans les lunettes.

Elle permet de commencer avec du matériel existant, de réduire les contraintes de calcul et d’itérer rapidement sur le produit.

À terme, certaines fonctions pourront être déplacées vers les lunettes ou vers des modules dédiés si cela améliore la latence, la consommation ou la fiabilité.

### 4.4. La couche sociale : le réseau devient présent dans l’environnement

Le réseau social ne se limite plus à un fil d’actualité.

Il organise les relations entre les personnes, leurs identités numériques, leurs préférences de partage et les interactions qu’elles acceptent.

Les profils peuvent comprendre :

- une identité et une présentation personnelle ;
- des centres d’intérêt ;
- des créations et des expériences publiées ;
- des communautés et des relations ;
- des préférences de visibilité ;
- des invitations et des interactions autorisées.

La proximité physique devient un contexte possible de découverte, mais elle ne donne pas automatiquement accès aux informations personnelles.

La visibilité doit être contrôlée par chaque utilisateur.

### 4.5. La couche de création : un réseau social programmable

Le système ne doit pas être fermé à une liste prédéfinie d’applications.

Il doit permettre à des développeurs de créer de nouvelles interactions adaptées au contexte physique.

Un développeur pourrait créer :

- un jeu de proximité ;
- un quiz entre deux personnes ;
- une activité collaborative ;
- une expérience artistique ;
- un parcours interactif ;
- une présentation de produit ;
- une expérience de rencontre fondée sur des intérêts communs.

La plateforme doit fournir des outils de création, de test, de publication, de distribution et de mise à jour.

**L’objectif est que les développeurs puissent créer des expériences sociales activables dans le monde réel, sans avoir à construire leur propre infrastructure de proximité, d’identité et de synchronisation.**

---

## 5. L’expérience utilisateur cible

### 5.1. Voir

L’utilisateur porte ses lunettes normalement.

Lorsqu’une personne participante se trouve dans son environnement et que les conditions de visibilité le permettent, le système peut signaler sa présence.

L’information doit être discrète et ne pas encombrer le champ de vision.

### 5.2. Découvrir

L’utilisateur choisit d’ouvrir le profil disponible.

Il découvre uniquement les informations que cette personne a autorisé à partager dans ce contexte.

La découverte doit être rapide, compréhensible et réversible.

### 5.3. Interagir

Le profil peut proposer des actions contextuelles : engager une conversation, consulter une création, envoyer une invitation ou proposer une activité.

Ces actions sont des possibilités, pas des automatismes imposés.

### 5.4. Créer

L’utilisateur peut lancer une expérience ou en proposer une nouvelle.

À terme, la création peut être assistée par des outils visuels ou par l’intelligence artificielle. Une expérience pourrait être décrite en langage naturel, générée, testée et déployée dans le cadre des capacités autorisées de la plateforme.

### 5.5. Partager

Une expérience acceptée peut être synchronisée entre plusieurs participants.

Les utilisateurs voient alors les éléments utiles à l’interaction commune, dans leur environnement respectif, en fonction des capacités de leurs appareils.

---

## 6. Architecture technologique de référence

L’architecture proposée doit être modulaire. Chaque fonction doit pouvoir évoluer sans obliger à reconstruire le reste du système.

### 6.1. Vue d’ensemble

**Lunettes et capteur optique → téléphone → services réseau → téléphone → lunettes**

La chaîne physique fournit un signal de proximité et des informations de mesure. Les lunettes exploitent leurs capacités spatiales pour associer ce signal à une position dans le champ de vision.

Le téléphone transmet les données utiles aux services sociaux et récupère les informations nécessaires à l’affichage.

Cette représentation est logique plutôt qu’obligatoirement séquentielle : les mesures spatiales peuvent être traitées localement, tandis que les profils et les expériences sont chargés en parallèle.

### 6.2. Matériel optique

La première phase consiste à évaluer des composants disponibles.

Les pistes comprennent :

- LED modulées et photodétecteurs ;
- communication optique visible ;
- infrarouge, si cette option offre de meilleures performances et respecte les exigences de sécurité ;
- réseaux de photodétecteurs ou capteurs optiques directionnels ;
- caméras et suivi spatial des lunettes ;
- synchronisation et estimation de distance ou de direction.

Le choix ne doit pas être arrêté sur la seule base du débit de transmission.

Le critère principal est la capacité à identifier et à localiser correctement les appareils portés, avec une consommation et un encombrement compatibles avec une monture.

### 6.3. Application mobile

Une application mobile sert de relais entre les lunettes et le réseau.

Elle gère l’association de l’appareil, la session de l’utilisateur, les autorisations, les échanges de données et les expériences.

La conception doit prévoir des interfaces modulaires pour connecter différentes marques de lunettes et différents systèmes de proximité lorsque leurs SDK le permettent.

### 6.4. Backend social

Le backend gère les comptes, les profils, les relations, les invitations, les autorisations, les sessions et les données nécessaires aux expériences.

Une première implémentation peut utiliser :

- une API avec FastAPI ;
- PostgreSQL pour les données structurées ;
- WebSockets pour les interactions en temps réel ;
- un système de gestion des identifiants éphémères ;
- une architecture de services déployable sur une infrastructure standard.

Ces choix sont des propositions initiales, et non des dépendances irréversibles.

### 6.5. SDK et environnement de création

Le SDK doit abstraire les différences matérielles dans la mesure du possible.

Il doit exposer des fonctions cohérentes, par exemple :

- détecter un participant autorisé ;
- obtenir une mesure de position et son niveau de confiance ;
- accéder aux informations de profil autorisées ;
- afficher un élément spatial ;
- proposer et accepter une interaction ;
- démarrer une session partagée ;
- publier une expérience.

Les capacités non disponibles sur un appareil doivent être clairement signalées. Le SDK ne doit jamais simuler une précision spatiale que le matériel ne peut pas fournir.

---

## 7. Le problème scientifique et technique central

La faisabilité globale dépend d’un problème précis : **associer de façon fiable un signal émis par une paire de lunettes à la position de son porteur dans le champ de vision d’une autre paire de lunettes.**

Ce problème doit être étudié avant tout investissement important dans une monture personnalisée.

### 7.1. Identité et localisation sont deux fonctions différentes

Un identifiant optique peut indiquer quel émetteur est détecté.

Il ne fournit pas nécessairement une position tridimensionnelle précise.

Une mesure de puissance lumineuse ne suffit généralement pas à déterminer une position exacte. Une solution robuste peut nécessiter plusieurs capteurs, des mesures directionnelles, une estimation de distance ou l’association avec le suivi visuel.

### 7.2. Contraintes à tester

Le système doit être évalué dans des conditions représentatives :

- lumière du jour et éclairage intérieur ;
- différentes orientations de tête ;
- mouvements de marche ;
- personnes qui se croisent ;
- plusieurs appareils à proximité ;
- occultations partielles ;
- différentes distances ;
- surfaces réfléchissantes ;
- pertes temporaires du signal.

Le résultat attendu n’est pas seulement une démonstration réussie dans une salle de laboratoire. Il doit s’agir d’un mécanisme stable dans des situations de vie courante.

### 7.3. Ne pas confondre Li-Fi et positionnement

Le Li-Fi est principalement associé à la communication optique sans fil. Il constitue une famille de technologies pertinente pour transmettre des données, mais le positionnement est une fonction supplémentaire qui doit être conçue et validée.

Le projet ne doit donc pas imposer une solution Li-Fi complète si un protocole optique plus simple permet de remplir le besoin.

L’infrarouge, la lumière visible et une combinaison de capteurs restent des options à comparer.

Le principe fondateur est la fonction à obtenir, pas le nom d’une technologie.

---

## 8. Confidentialité, sécurité et confiance

Une infrastructure qui relie les personnes physiques à leurs identités numériques doit être conçue autour du consentement.

La proximité ne constitue pas une autorisation générale.

### 8.1. Visibilité choisie

Chaque utilisateur doit pouvoir définir s’il est visible, dans quels contextes, pour quelles catégories de personnes et avec quelles informations.

Des modes distincts peuvent être prévus : invisible, visible aux contacts, visible aux participants autorisés ou découverte publique volontaire.

### 8.2. Identifiants techniques protégés

Le signal émis par le dispositif ne devrait pas exposer directement un identifiant permanent et réutilisable.

Des identifiants temporaires, renouvelables et vérifiables côté serveur peuvent limiter le suivi non désiré.

### 8.3. Contrôle des interactions

Une invitation à jouer, à discuter ou à partager un contenu doit pouvoir être refusée simplement.

Les utilisateurs doivent pouvoir bloquer un compte, désactiver la découverte et mettre fin à une session.

### 8.4. Protection contre le harcèlement et le suivi abusif

Le système doit limiter les sollicitations répétées, la collecte d’historique de présence et l’utilisation des signaux pour suivre quelqu’un à son insu.

Les données de localisation doivent être minimisées, avec des durées de conservation définies et des accès contrôlés.

### 8.5. Sécurité des expériences tierces

Les expériences créées par des développeurs doivent fonctionner dans un environnement à permissions limitées.

Elles ne doivent pas obtenir librement l’identité, la position ou les informations sociales des personnes présentes.

Une publication doit passer par des contrôles de sécurité, de compatibilité et de conformité aux règles de la plateforme.

---

## 9. La plateforme de développement

L’ouverture aux créateurs est essentielle pour que le projet dépasse une simple fonctionnalité de lunettes.

### 9.1. Les primitives du SDK

Le SDK doit proposer un ensemble restreint de fonctions de base :

- découverte de proximité autorisée ;
- identité et profil avec permissions ;
- localisation relative avec indication de confiance ;
- éléments d’interface spatiaux ;
- invitations et acceptations ;
- sessions multijoueurs ;
- synchronisation d’état ;
- publication et gestion des versions.

Ces primitives doivent être suffisamment générales pour permettre des expériences différentes, sans transformer la plateforme en système d’exploitation universel.

### 9.2. Création et déploiement

Les développeurs doivent pouvoir créer une expérience, la tester avec des appareils compatibles, la publier et gérer ses versions.

Le processus comprend :

1. Création du projet.
2. Utilisation des API de proximité et d’interaction.
3. Test sur appareils physiques.
4. Vérification des permissions et de la sécurité.
5. Publication.
6. Découverte et lancement par les utilisateurs.
7. Mise à jour ou retrait de l’expérience.

### 9.3. Assistance par intelligence artificielle

À terme, un utilisateur ou un développeur pourrait décrire une expérience en langage naturel.

Exemple : « Crée un jeu de trois questions entre deux personnes qui aiment le cinéma. »

Un assistant pourrait générer une première version, préparer les éléments visuels et configurer la session multijoueur.

La génération ne doit cependant pas contourner les permissions ou créer automatiquement une interaction non acceptée. Toute expérience doit respecter les capacités du SDK et les règles de la plateforme.

---

## 10. Marché et positionnement

Le projet se situe à l’intersection de plusieurs catégories : lunettes intelligentes, réseaux sociaux, communications de proximité, expériences spatiales et plateformes de développement.

Son positionnement distinctif repose sur leur combinaison.

### 10.1. Ce que nous ne sommes pas

Nous ne sommes pas simplement :

- une marque de lunettes ;
- un fabricant d’écrans transparents ;
- un réseau social traditionnel avec une interface en réalité augmentée ;
- une plateforme de métavers ;
- un système de géolocalisation généraliste ;
- un magasin d’applications sans infrastructure de proximité.

### 10.2. Ce que nous voulons devenir

Nous voulons devenir une infrastructure permettant aux identités et aux expériences numériques de se manifester, de manière contrôlée, dans les rencontres physiques.

La valeur du système dépendra de trois éléments :

1. La qualité de la détection et du positionnement.
2. La facilité avec laquelle les personnes peuvent découvrir et accepter des interactions.
3. La capacité des développeurs à créer des expériences utiles et attractives.

### 10.3. Effet de réseau

Plus le nombre de participants augmente, plus la découverte et les interactions deviennent intéressantes.

Mais l’adoption dépend également de la compatibilité matérielle, de la confidentialité et de l’existence d’expériences utiles même lorsque peu de personnes sont présentes.

Le lancement doit donc commencer par des communautés ou des contextes où les interactions ont une valeur immédiate : campus, événements, communautés créatives ou espaces professionnels.

---

## 11. Modèle économique potentiel

Le modèle économique doit être étudié après validation de l’usage et de la technologie.

Plusieurs sources de revenus sont envisageables.

### Plateforme et services développeurs

Des outils avancés, des services de publication ou des fonctions de gestion de sessions peuvent être proposés aux développeurs professionnels.

### Expériences premium

Des créateurs peuvent commercialiser des expériences, des contenus ou des fonctionnalités supplémentaires, avec une répartition transparente des revenus.

### Solutions professionnelles

Des organisations peuvent financer des expériences pour leurs événements, espaces, communautés ou activités collaboratives.

### Infrastructure et partenariats

À plus long terme, la technologie de proximité et le SDK peuvent faire l’objet de partenariats avec des fabricants de lunettes et des intégrateurs.

Le modèle doit éviter de faire de la surveillance ou de la vente des données de présence le moteur économique du projet.

La confiance est une condition de l’adoption, pas une variable d’ajustement.

---

## 12. Stratégie de développement

Le projet doit progresser par preuves successives, sans chercher à développer simultanément un matériel propriétaire, un réseau social complet et un SDK universel.

### Phase 1 — Validation de la fonction de proximité

Objectif : démontrer qu’un dispositif peut émettre un identifiant optique, qu’un autre dispositif peut le recevoir et que le système peut mesurer une position relative exploitable.

Livrables :

- comparaison des solutions optiques existantes ;
- banc de test avec composants disponibles ;
- mesure de portée et de latence ;
- étude de l’association signal-personne ;
- premier rapport de faisabilité.

### Phase 2 — Prototype social avec téléphone

Objectif : valider la valeur de l’expérience avant de miniaturiser le matériel.

Deux participants utilisent des téléphones, des dispositifs optiques ou des marqueurs de test. Ils peuvent détecter une présence autorisée, ouvrir un profil et démarrer une interaction.

Livrables :

- application mobile ;
- profils et autorisations ;
- service de proximité ;
- interaction en temps réel ;
- mini-expérience partagée.

### Phase 3 — Intégration avec des lunettes existantes

Objectif : démontrer l’affichage spatial sur un appareil disponible et accessible aux développeurs.

Livrables :

- prototype sur une plateforme compatible ;
- suivi spatial ;
- association avec le participant détecté ;
- affichage contextuel ;
- test de mouvement et de stabilité.

### Phase 4 — SDK expérimental

Objectif : séparer les fonctions de la plateforme des détails matériels.

Livrables :

- API de proximité ;
- API d’identité et de permissions ;
- API d’expériences partagées ;
- documentation ;
- exemple de jeu ;
- outils de test.

### Phase 5 — Module matériel optimisé

Objectif : déterminer si un dispositif optique dédié apporte une amélioration suffisante pour justifier son industrialisation.

Livrables :

- conception électronique ;
- étude de consommation ;
- prototype de taille réduite ;
- essais d’intégration dans une monture ;
- étude de fabrication et de coût.

### Phase 6 — Écosystème et déploiement

Objectif : permettre à des créateurs et à des communautés pilotes de publier des expériences.

Livrables :

- environnement de développement ;
- mécanisme de publication ;
- contrôles de sécurité ;
- documentation développeur ;
- premières communautés pilotes.

---

## 13. Critères de réussite du premier prototype

Le premier prototype ne doit pas chercher à démontrer toute la vision. Il doit prouver le mécanisme fondamental.

Les seuils ci-dessous sont des **objectifs initiaux à tester**, et non des performances déjà démontrées.

| Critère | Objectif expérimental initial |
|---|---|
| Identification | Distinguer deux appareils participants ou davantage |
| Portée | Tester plusieurs distances, avec une cible initiale de 1 à 3 mètres |
| Direction | Associer le signal à la bonne personne visible |
| Positionnement | Viser une erreur angulaire inférieure à 5° dans les conditions de test définies |
| Latence | Viser une mise à jour exploitable en moins de 100 ms |
| Stabilité | Maintenir l’association pendant les mouvements ordinaires |
| Confidentialité | Aucun profil personnel révélé sans permission |
| Interaction | Permettre une invitation et une acceptation en temps réel |
| Intégration | Faire fonctionner l’ensemble avec du matériel de développement disponible |

Ces critères devront être adaptés après les premières mesures. Une erreur angulaire de 5°, par exemple, peut être suffisante pour un indicateur discret mais insuffisante pour certaines interactions spatiales.

La réussite ne se limite pas aux performances instrumentales. L’expérience doit aussi être confortable, non intrusive et utile.

---

## 14. Risques et décisions à prendre

### Risque 1 : la communication optique ne suffit pas à localiser

Réponse : comparer plusieurs architectures et combiner les mesures optiques avec le suivi spatial lorsque nécessaire.

### Risque 2 : les lunettes ne permettent pas l’accès aux capteurs nécessaires

Réponse : sélectionner dès le début une plateforme offrant un SDK adapté, ou utiliser un prototype optique externe pendant la phase de validation.

### Risque 3 : l’expérience est trop intrusive

Réponse : privilégier une présence discrète, des profils volontairement visibles et des interactions explicitement acceptées.

### Risque 4 : la compatibilité entre appareils devient un obstacle

Réponse : définir une couche d’abstraction matérielle et commencer avec un nombre limité de dispositifs certifiés.

### Risque 5 : le réseau ne présente pas assez de valeur au démarrage

Réponse : choisir un contexte pilote où la proximité a déjà une valeur claire et où les participants sont motivés à rejoindre le système.

### Risque 6 : l’ambition matérielle retarde le produit social

Réponse : valider d’abord l’expérience avec des composants existants et un prototype contrôlé, puis décider si le module dédié est indispensable.

---

## 15. Partenaires recherchés

Le projet nécessite plusieurs expertises complémentaires.

### Photonique et capteurs

Pour concevoir et évaluer l’émetteur, le récepteur, la mesure de direction et les contraintes de miniaturisation.

### Systèmes embarqués

Pour la consommation énergétique, l’intégration électronique et la conception d’un module adapté à une monture.

### Réalité augmentée et suivi spatial

Pour associer la détection d’un appareil à la position de la personne visible et stabiliser l’affichage.

### Logiciel et réseau

Pour l’application mobile, le backend social, les sessions en temps réel et le SDK.

### Design produit et expérience utilisateur

Pour garantir que l’information reste discrète, compréhensible et compatible avec une interaction humaine naturelle.

### Terrains pilotes

Pour tester les usages dans des contextes réels : campus, événements, espaces créatifs ou communautés locales.

---

## 16. Plan d’action immédiat

Les premières semaines doivent être consacrées à réduire les inconnues les plus importantes.

**Étape 1 — Cartographier les solutions existantes**

Comparer les composants optiques, les kits de communication visible et infrarouge, les capteurs de positionnement et les SDK de lunettes disponibles.

**Étape 2 — Obtenir une revue de faisabilité**

Contacter des spécialistes de la photonique et de l’optique portable, notamment dans l’écosystème de Lausanne et de l’EPFL, pour valider les options d’identification et de localisation.

**Étape 3 — Écrire les spécifications de test**

Définir les distances, la précision, la latence, les conditions d’éclairage, les orientations et le nombre de participants visés.

**Étape 4 — Construire un banc de test**

Utiliser des composants existants avant de développer une électronique propriétaire.

**Étape 5 — Développer en parallèle le prototype social**

Créer les profils, les autorisations, les invitations et une première expérience partagée, indépendamment de la miniaturisation optique.

**Étape 6 — Intégrer les deux démonstrateurs**

Relier la détection physique à l’expérience sociale et mesurer la qualité réelle de l’ensemble.

La première preuve doit être simple : une personne regarde une autre personne participante, le système l’associe au bon signal, affiche son profil au bon endroit et permet de lui proposer une interaction.

---

## 17. La thèse stratégique à long terme

L’importance du projet ne réside pas dans l’affichage de profils au-dessus des personnes.

Cette fonction n’est que la première manifestation visible d’une infrastructure plus profonde.

Si le système fonctionne, il devient possible de rendre les interactions numériques contextuelles à la présence physique, sans exiger que chaque expérience possède son propre mécanisme de découverte, d’identité et de synchronisation.

La même infrastructure peut servir à des interactions sociales, ludiques, créatives, éducatives ou professionnelles.

Les lunettes deviennent un point d’accès à cette infrastructure. Le téléphone fournit les services. Le réseau organise les identités et les interactions. Le SDK permet aux créateurs d’inventer de nouveaux usages.

La technologie ne doit pas imposer une nouvelle réalité séparée. Elle doit rendre possibles de nouvelles formes de relation dans la réalité que nous partageons déjà.

---

## Conclusion

Nous voulons construire une couche sociale du monde physique.

Une couche dans laquelle la présence peut devenir une découverte, la découverte une interaction, et l’interaction une expérience partagée.

Le projet commence par un problème matériel précis : identifier et localiser des lunettes participantes avec un système compact, fiable et économe en énergie.

Mais sa finalité dépasse largement ce composant.

La véritable ambition est de développer une infrastructure sociale programmable qui permette aux personnes et aux créateurs d’enrichir leurs interactions dans le monde réel.

**Nous ne vendons pas seulement une interface portée sur le visage. Nous construisons les fondations d’une société augmentée.**

### Les trois décisions fondatrices à prendre maintenant

Le vision paper fixe le cap, mais trois décisions doivent être validées avant d’engager le développement matériel.

1. **Le principe de localisation.** Le Li-Fi est-il une exigence absolue, ou le moyen privilégié à ce stade pour atteindre l’identification et la position relative ?

2. **Le premier produit.** Le prototype doit-il fonctionner avec une seule plateforme de lunettes existante, ou commencer par deux dispositifs optiques et deux téléphones pour valider la technologie indépendamment des fabricants ?

3. **Le modèle de plateforme.** La couche sociale et le SDK seront-ils ouverts aux développeurs dès le départ, ou le premier pilote sera-t-il une expérience fermée permettant de valider l’usage et la confidentialité ?

Conseil : ne pas figer le Li-Fi comme choix technologique irréversible. Figer le résultat à obtenir. La valeur du projet est l’identification et la localisation de proximité reliées à une infrastructure sociale programmable. Si une architecture optique différente remplit mieux ces exigences, elle doit rester admissible.

---

*Nous cherchons des partenaires pour aller plus loin : photonique et capteurs, systèmes embarqués, réalité augmentée et suivi spatial, logiciel et réseau, design produit, terrains pilotes.*
