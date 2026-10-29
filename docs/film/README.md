# Le film d'Aiwa (version 6)

78 secondes : une scène 3D (Blender), des écrans dessinés en HTML (le téléphone, la télévision), une voix de synthèse (Piper « siwis », en local), des bruitages synthétisés et une musique.

- **Texte dit** : `cues5.json`. **Écrans** : `screens.html`, `phone.html`, `contract.html`. **Étiquettes et titres** : `overlay.html`. **Bruitages** : `sound5.py`. **Remise en ordre des plans** : `retime.py`. **Scène 3D** : `scene3d.py`.
- Les deux scripts `make-*.sh` enchaînent les étapes (voix, écrans, rendu 3D de la pause, recomposition, son, montage). Ils supposent les outils de `skills/kit/video-kit` et un Blender (module `bpy`) installé à part : les chemins de `/tmp/os3` sont ceux de la machine où le film a été fait.
- Changements de cette version : plus de mention des agents externes ni de ChatGPT, plus de « et même depuis la télévision », la partie « personnalise ton application en temps réel » devient « découvre tes potentiels matchs, personnel et professionnel » (nouvelle scène à la télévision), une autre musique.

**Musique** : « Living Voyage », Kevin MacLeod (incompetech.com), licence Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/).
