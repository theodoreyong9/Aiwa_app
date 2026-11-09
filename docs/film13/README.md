# Aiwa film (version 13, English)

43 s, 1920×1080. `docs/film.mp4` is this film, in English.

- **Text spoken**: `cues13_en.json` (the French text is `cues13.json`). **Screens**: `ui13.html` (French) and `ui13_en.html` (written from it by `translate13.py`), drawn frame by frame by `render_ui13.cjs` (Playwright; the real `Profile/index.html` runs inside, with a clock of its own so that its liquid moves the same way at every run). **Timeline**: `build13.py` (from the length of each voice). **Sound**: `sound13.py` with `sfxlib.py` (the effects are synthesised), the voice by `voice13.py` (Piper, local). **Assembly**: `make-2-assemble.sh` (`SUF=_en` for the English one).
- The interfaces are the real profile page and rebuilt windows (they follow the application's own colours and texts); the target cards, the map and the scores are drawn in its style. The names of the targets are invented.

**Music**: « Hiding Your Reality », Kevin MacLeod (incompetech.com), licence Creative Commons Attribution 4.0 (https://creativecommons.org/licenses/by/4.0/).
**Voice**: Piper `en_US-ryan-high` (English), `fr_FR-siwis-medium` (French).
