# Images

Affiche, illustration, visuel, logo.

- Format : `.png` (ou `.svg` pour un logo / un dessin vectoriel). Taille adaptée à l'usage (affiche A4 ≈ 2480×3508, visuel réseau ≈ 1080×1080).
- Sans outil de génération d'image, dessine en SVG ou HTML puis exporte en PNG (navigateur sans interface).
- Texte lisible, contrastes forts, marges ; une idée par image.
- Regarde le résultat avant de publier.
- Publie selon `skills/release/SKILL.md` avec le tag `image-…`.

## Direction créative


*Dans ce texte, `<propriétaire>/<dépôt>` est le dépôt de ta session.*

Direction créative : une page n'est pas un modèle à remplir. Avant de coder, écris en UNE phrase le concept (une idée, pas un style : « une page qui se comporte comme… »), choisis UN élément signature qu'on retient (un geste visuel, une interaction, une mise en scène du texte) et une typographie marquée (pas la police système par défaut), et écris du contenu précis et vivant : jamais de formules génériques (« simple, sobre, rapide », « moderne et accessible ») qui conviendraient à n'importe quelle page. Quand ma demande est vague (pas de sujet, pas d'ambiance), n'en conclus pas qu'il faut rester sobre : « simple » décrit l'usage, pas l'ambition visuelle ; fais une proposition audacieuse, dis-moi en une phrase l'hypothèse que tu as prise, et je corrigerai. Fabrique toi-même les visuels par le code (SVG, canvas, WebGL, dégradés, formes animées) plutôt que de laisser des vides ou de n'utiliser que du texte et des cartes, et mets du mouvement qui a un sens (entrée en scène, réaction au défilement et au survol, transitions), en respectant `prefers-reduced-motion`. Le catalogue de références montre ce qui se fait à ce niveau (WebGL, GSAP, défilement piloté, transitions de vue) : prends ce que le format porte. Avant de me rendre la page, demande-toi : serait-elle interchangeable avec un modèle de page trouvé en ligne ? Si oui, recommence avec une idée plus forte.
