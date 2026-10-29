# Recipe — professional quality film

The recipe fixes the PROCESS and the CHECKS. It never says which animation, object, transition or place to use: those are invented for each film, from the subject, and the folders of the earlier films (`docs/videos/*/concept.json`) are the record, and the novelty check forbids taking what they used.

## The stages, in order. A stage is not started before the one before it is written down and checked.
1. **Documents.** Read all of them. `notes.md`: the 5 to 8 ideas that matter, each with its passage, word for word. Nothing is invented later: every spoken line rests on a passage (`conductor/outline.mjs` checks it).
2. **Brief.** `brief.md`: who watches, ONE message, one call to action, the length. The budget (beats, words) comes from `outline.mjs`.
3. **Concept.** `concept.json`. The question to answer is: *what is the STRUCTURE of this subject, and what physical or visual thing has the same structure?* The pictures must be that structure made visible, not a theme laid over a picture. Then say what is new: language, objects, places, transitions, tracking style. `node video-kit/conductor/novelty.mjs concept.json` must say `new: ok`; it refuses a film that looks like one of the last three.
4. **Ingredients.** Real places (panoramas, footage) come from the indexes and are never one an earlier film used. Every clip or panorama is LOOKED AT on a sheet before it is used; one with text on it, a talking head or nothing to do with the line is refused. Each is fetched by the workflows (the session cannot reach the sources).
5. **Look-dev gate.** A still sheet: at least two images for every beat and one for every transition. Checked, in writing, against: each beat shows what its line says; no black or washed-out image; the captions can be read on the lightest image; nothing comes from an earlier film; the subject can be told from the pictures with the sound off. One failure: fix, redo the sheet. NO RENDER BEFORE THIS SHEET PASSES.
6. **Render.** Resumable (frames on disk are kept), disk checked first (`df`), the render restarts by itself when the browser dies.
7. **Sound.** A voice that says the lines, a bed for each place, accents on the beats, a music that is not one an earlier film used unless said. Listen to what the numbers say: no clipping, voice over music.
8. **Review.** A contact sheet, one image every 3 s, of the FINAL file; then `video-kit check`. A film that fails the sheet is redone, not published.
9. **Publish.** The file, `latest.json`, the changelog, and its `concept.json` stays in its folder: that is the record the next film is checked against.

What a film may NOT do: reuse a language, a place, an object, a transition or a tracking style of the last three films; invent a fact; hide a limit (say what is provisional); start a render before the gate.
