# Apps

Une application qui s'installe ou s'ouvre sur le téléphone.

- Le plus simple d'abord : une app web d'un seul fichier (voir `skills/page`) si elle n'a pas besoin d'Android.
- Pour une vraie application Android : un `.apk` signé (clé de debug acceptée), construit par la CI du dépôt ou localement, attaché à la release.
- Dis en une phrase ce que fait l'app et comment l'ouvrir ; l'installation demande l'autorisation « sources inconnues ».
- Teste ce qui peut l'être (compilation, tests) avant de publier ; dis honnêtement ce qui n'a pas pu être essayé.
- Publie selon `skills/release/SKILL.md` avec le tag `app-…`.

## Quand l'app est un jeu


*Dans ce texte, `<propriétaire>/<dépôt>` est le dépôt de ta session.*

Jeu : si ma demande est un jeu, lis d'abord https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/app/GAME-FOUNDATION.md (le standard de qualité), puis décide toi-même de ce qui manque quand le jeu est petit ou fait partie d'une autre création (un mini-jeu dans un site) ; pour un vrai jeu à part entière, pose-moi EN UNE FOIS, par la question du widget, ce qui manque (genre, 2D ou 3D, solo ou multijoueur, nombre de joueurs, temps réel ou tour par tour, plateformes visées) avant de construire. Choisis le socle selon le besoin et dis-moi pourquoi : un fichier HTML ou un site pour un petit jeu ; un contrat Aiwa quand les résultats ou les récompenses doivent être vérifiables par tous sans serveur ; Godot 4 + Nakama pour du multijoueur temps réel de 2 à 16 joueurs. Construis par étapes vérifiées, et ne passe pas à la suivante si une étape échoue. Le serveur (ou Aiwa) a le dernier mot sur les résultats et les récompenses : teste une action falsifiée et une commande en double. Écris les règles de déconnexion, d'abandon et de reconnexion et teste-les. Ne dis jamais qu'un build, un test ou un déploiement a réussi sans la sortie de son exécution, ne remplace pas une fonction manquante par une simulation non signalée, n'invente aucune méthode d'un SDK (lis la documentation officielle de la version utilisée), et n'annonce aucune capacité (8 ou 16 joueurs) que tu n'as pas mesurée. Avant de livrer, JOUE-LE toi-même : ouvre-le dans Chromium avec Playwright (installe-le si besoin : `npx playwright install chromium`), joue une partie complète par script (début, points, fin, rejouer), vérifie qu'il n'y a aucune erreur dans la console, prends des captures en 390 px et 1440 px, regarde-les, corrige ce qui est cassé, coupé ou illisible, et dis-moi ce que tu as vu. Pour les décors, modèles 3D, textures et lumières libres de droits, cherche d'abord dans le registre (`node skills/kit/asset-research/src/cli.js search "<ce qu'il faut>" --kind=model`, depuis le dépôt de référence cloné) et ne télécharge que ce que tu gardes ; pour la musique et les sons, le registre de musique (`node skills/kit/music-research/src/cli.js search "<l'ambiance>" --credit=ok`, qui lit aussi OpenGameArt) : garde la source et la licence de chaque élément dans `CREDITS.md` du jeu. Pour l'interface et la direction visuelle, applique aussi la consigne Design.
