# Pages

Une page web d'un seul fichier HTML.

- Un seul `.html` autonome : CSS et JS dedans, aucune dépendance locale ; bibliothèques seulement depuis un CDN avec version exacte.
- Adapté au téléphone : `viewport`, texte lisible, boutons de 44 px, pas de défilement horizontal.
- Ouvre-la dans un navigateur sans interface et regarde une capture avant de publier.
- Publie selon `skills/release/SKILL.md` avec le tag `page-…` : l'application l'ouvre dans sa propre fenêtre.

## Direction créative


*Dans ce texte, `<propriétaire>/<dépôt>` est le dépôt de ta session.*

Direction créative : une page n'est pas un modèle à remplir. Avant de coder, écris en UNE phrase le concept (une idée, pas un style : « une page qui se comporte comme… »), choisis UN élément signature qu'on retient (un geste visuel, une interaction, une mise en scène du texte) et une typographie marquée (pas la police système par défaut), et écris du contenu précis et vivant : jamais de formules génériques (« simple, sobre, rapide », « moderne et accessible ») qui conviendraient à n'importe quelle page. Quand ma demande est vague (pas de sujet, pas d'ambiance), n'en conclus pas qu'il faut rester sobre : « simple » décrit l'usage, pas l'ambition visuelle ; fais une proposition audacieuse, dis-moi en une phrase l'hypothèse que tu as prise, et je corrigerai. Fabrique toi-même les visuels par le code (SVG, canvas, WebGL, dégradés, formes animées) plutôt que de laisser des vides ou de n'utiliser que du texte et des cartes, et mets du mouvement qui a un sens (entrée en scène, réaction au défilement et au survol, transitions), en respectant `prefers-reduced-motion`. Le catalogue de références montre ce qui se fait à ce niveau (WebGL, GSAP, défilement piloté, transitions de vue) : prends ce que le format porte. Avant de me rendre la page, demande-toi : serait-elle interchangeable avec un modèle de page trouvé en ligne ? Si oui, recommence avec une idée plus forte.


## Design : des références mesurées


*Dans ce texte, `<propriétaire>/<dépôt>` est le dépôt de ta session.*

Design : avant de dessiner une interface (site, PWA, APK, écran d'un contrat), prends des références MESURÉES au lieu de t'en remettre à ta mémoire. Clone le Store en lecture seule (`git clone --depth 1 https://github.com/theodoreyong9/Aiwa_app /tmp/aiwa-ref`), puis, depuis ton répertoire de travail : `DR_CATALOG_URL=https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/design-research/catalog DR_SHOTS_URL=https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/design-research/screenshots node /tmp/aiwa-ref/skills/kit/design-research/src/cli.js research "<ma demande en une phrase>" --format=<site|pwa|apk|contract_ui>`. Lis ensuite `.research/latest/synthesis.md`, `references.json` et les captures. Les traits sont des mesures ; l'ambiance, le ton et pourquoi une référence marche, c'est à toi de les juger en regardant les captures. Retiens ce que PLUSIEURS références partagent pour les fondamentaux (lisibilité, structure, performance) et prends le risque ailleurs ; respecte ce que le format peut porter (`transposable_to_format`), et ne recopie ni l'identité, ni la mise en page, ni le contenu, ni les assets, ni l'implémentation distinctive d'un site. Une fois l'interface construite, ouvre-la dans Chromium avec Playwright (`npx playwright install chromium` si besoin) en 390 px et en 1440 px, regarde les captures, et corrige les débordements, les contrastes faibles, les textes coupés, les images cassées et les erreurs de console avant de me dire que c'est fini. Traçabilité : écris `aiwa-design/references.md` dans le dépôt (commite-le avec le reste) avec 2 ou 3 références RETENUES, et pour chacune : son nom et son adresse, son `id` dans le catalogue (la ligne de https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/design-research/catalog/sites.jsonl), les captures que tu as regardées (adresses `https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/design-research/screenshots/<id>/<fichier>`), les mesures du catalogue que tu en as tirées (typographie, couleurs, mouvement, composition, bibliothèques), ce que tu as vu sur les captures et que les mesures ne disent pas, et ce que tu en as pris, avec où cela se voit dans ma création. Ne cite pas une référence que tu n'as pas vraiment regardée. Résume-moi cela en trois lignes dans ta réponse. Si le clone ou le catalogue est inaccessible ou vide, dis-le-moi en une phrase et conçois sans (sans références.md). N'ajoute pas `.research/` au dépôt.
