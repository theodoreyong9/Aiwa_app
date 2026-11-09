# Changelog

## Voix (version du cerveau 272)
- Moteur de la voix naturelle au choix dans Réglages > Voix : « Léger » (Piper, par défaut) ou « Plus naturel » (Kokoro, environ 350 Mo, téléchargé quand on le choisit ; Piper parle en attendant). Si Kokoro met plus de temps à fabriquer une phrase qu'à la dire, deux fois de suite, ou échoue trois fois, la voix revient à Piper toute seule et le dit.
- Skill video-kit : `voice.py --engine=kokoro|piper`, `--lang=en|fr`. En anglais Kokoro parle d'abord (meilleur que Piper), en français Piper (équivalent, plus léger) ; les voix s'installent toutes seules la première fois (`voice-setup.sh`, `--light` sans Kokoro, `--with-english` pour la voix anglaise légère).
- Catalogue de design : tout ce qui ressemble à un secret (jeton, clé) trouvé dans une page visitée est retiré avant d'être écrit, et une étape nettoie les fichiers avant le commit : GitHub refusait le push du 9 novembre à cause d'un faux jeton dans la page d'un site analysé.

## 0.1.0
- Repartie de zéro : cerveau découpé en modules, super agent omniscient, productions en releases, application par fonctions.
- Publication automatique : une branche claude/* qui passe le build est fusionnée dans main par le workflow Promote.
