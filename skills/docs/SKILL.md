# Documents

Lettre, CV, rapport, contrat, présentation, tableur.

- Formats : texte → `.docx` ou `.pdf` ; présentation → `.pptx` ; tableau → `.xlsx`. Si la personne n'en nomme pas, `.pdf` pour lire, `.docx` pour modifier.
- Écris dans la langue de la demande. Structure claire : titre, sections courtes, pas de remplissage.
- Les faits (noms, dates, montants) viennent de la demande ou du dépôt ; ce qui manque, tu le suppose raisonnablement et tu le dis en une phrase.
- Vérifie le rendu (ouvre le fichier produit, convertis en image si besoin) avant de publier.
- Publie selon `skills/release/SKILL.md` avec le tag `docs-…`.

## Partir d'un fichier de la personne


*Dans ce texte, `<propriétaire>/<dépôt>` est le dépôt de ta session.*

Fichier : si je te donne un document (CV, lettre, argumentaire commercial, brochure, présentation, notes…), lis-le en entier, dis-moi en une phrase de quel type il est, puis adapte la vidéo à ce type : un CV donne un parcours (qui je suis, ce que je sais faire, la preuve, comment me joindre) ; un argumentaire commercial donne une vente (le problème, la solution, la preuve, le prix, l'appel à l'action) ; pour tout autre type, choisis la forme qui sert le propos, et si tu hésites vraiment pose-moi UNE question par le widget. N'utilise que ce que le fichier dit : n'invente aucun poste, chiffre, client ni prix, et dans `facts.md` sépare ce qui vient du fichier de ce que tu ajoutes. Mes réalisations GitHub ne sont utilisées QUE si ma demande dit que je l'ai coché : alors prends parmi mes dépôts PUBLICS ceux qui servent le propos, montre-les au bon moment de la vidéo (vraies captures ou pages), liste ceux que tu retiens dans `brief.md`, jamais un dépôt privé que je n'ai pas nommé. Sans cette mention, le fichier seul compte. Mets la vidéo dans une release du dépôt en cours (tag `video-<nom>-<AAAAMMJJ>`, voir `skills/release/SKILL.md`) : l'appli montre la liste de toutes les vidéos. Mes fichiers sources sont dans le dossier `aiwa-campagne/` du dépôt en cours : quand ma demande en nomme, lis-les là (tu y as accès), un par un ; un CSV, un JSON ou un texte tels quels, un tableur .xlsx avec Python (openpyxl ou pandas), un PDF avec `pdftotext`, une image ou une vidéo en les citant ou en les intégrant telles quelles sans rien dire de leur contenu que tu n'as pas pu lire. Quand ma demande contient un document collé et te dit de le ranger, écris-en une copie dans `aiwa-campagne/` (même nom) et pousse-la avec la consigne Push.
