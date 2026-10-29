# video-kit

The tools of `docs/PROMO-VIDEO.md`: render a timeline page frame by frame in Chromium (`src/render.js`), assemble the frames and a soundtrack into an MP4 with ffmpeg (`src/assemble.js`), check the result (`src/qc.js`), a template page that adapts to 9:16, 16:9, 1:1 and 4:5 (`template/timeline.html`), and a placeholder audio bed (`src/audio-bed.py`). `node src/cli.js` runs the three steps. The tests render the template in the four formats, assemble it and check it, and check that the check finds a silent file, black screens, a wrong size, a missing track and an unreadable file (they are skipped, saying so, where ffmpeg is not installed).

## The cinematic engine (and why a slideshow is not enough)

`template/timeline.html` shows one title and one picture per scene: that is a slideshow. For a video worth watching there is `template/cinematic.js` on top of `template/motion.js`: kinetic text, images and real pages (`capture`) in browser or phone frames with camera moves, shapes, counters, drawing paths, animated backgrounds, eight transitions, grain and vignette, all pure functions of time. `src/beat.py` makes a pulse with an accent on every cut (`frames/cuts.json`), `src/voice.py` a local voice-over (the music ducks under it, `assemble --voice`), and `check` warns of a `slideshow` when too many half-seconds barely move (an old title-over-screenshot video had 51% of them still; a cinematic cut has none). The production in stages, with its critique, is in `docs/PROMO-VIDEO.md` (section 6).

## Real shots (3D, real footage, generated)

`shots/README.md` says which tool makes which shot: Blender for a product in real 3D (`shots/blender/glasses.py`), a real footage with elements that follow someone (`src/track.py`, `render --transparent`), clips from the user's own video generator (`video-kit shotlist` writes the prompts), laid over the frames with `assemble --clips`. `sh src/shots-setup.sh` installs bpy and OpenCV once. The mirror of a free footage is the workflow `footage-mirror.yml`.
