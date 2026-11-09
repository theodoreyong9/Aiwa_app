# Changelog

## Voix (version du cerveau 272)
- Moteur de la voix naturelle au choix dans Réglages > Voix : « Léger » (Piper, par défaut) ou « Plus naturel » (Kokoro, environ 350 Mo, téléchargé quand on le choisit ; Piper parle en attendant). Si Kokoro met plus de temps à fabriquer une phrase qu'à la dire, deux fois de suite, ou échoue trois fois, la voix revient à Piper toute seule et le dit.
- Skill video-kit : `voice.py --engine=kokoro`, `--lang=en` (voix Piper anglaise), `voice-setup.sh --with-kokoro --with-english`.

## 0.1.0
- Repartie de zéro : cerveau découpé en modules, super agent omniscient, productions en releases, application par fonctions.
- Publication automatique : une branche claude/* qui passe le build est fusionnée dans main par le workflow Promote.
