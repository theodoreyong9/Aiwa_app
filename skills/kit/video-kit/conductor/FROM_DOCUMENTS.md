# From documents to a film

The user gives documents and asks for a video: no script, no storyboard. You (the agent) are the LLM; no API key, no external service.

1. **Read** every document. Write `notes.md`: the 5 to 8 ideas that matter, each with the passage it comes from (word for word).
2. **Choose the angle**: who watches, ONE message, one call to action, one style (documentary, curiosity, storytelling, news, dramatic, motivational). Write it in `brief.md`.
3. **Budget**: `node video-kit/conductor/outline.mjs` prints it (about one beat every 4.5 s, 2.4 spoken words a second). A line that does not fit is cut, never rushed.
4. **Write `story.json`**: for each beat an `id`, one `idea`, a short spoken `say`, the `source` (`file` + `quote`, copied from the documents), a `mood` (energy, warmth, scale, tension, awe) and `place` (words to look for in the footage index: "city night", "ocean", "workshop"). The film rises and lands: the last beat is calm. A beat may have no `say` (a picture only).
5. **Run** `node video-kit/conductor/outline.mjs story.json --docs=<folder> --seconds=<n> --out=film.json`. It refuses a line without a source, a quote that is not in the documents, too many words, too many beats. Fix the story, never the check. It picks the places by mood in the footage and panorama indexes (never the same twice in a row), the transitions, the times, and writes `film.credits.json`.
6. **Make the film**: `sh video-kit/conductor/make-film.sh film.json <workdir> [music.wav]` (plan, stage, render, voice, sound, assemble, check). A clip that is not in `<workdir>/footage/` is reported with the exact items to give to the `Footage` workflow (mode fetch, `name=spec`), then it stops: nothing is replaced by something else. Put the clip and its `.json` (credit) in `<workdir>/footage/`, run again. An image of the user's creation can be shown on a beat (`image` in the story). Read the contact sheet before saying it is done: a clip can carry a title or text of its own; take another one.
7. **Every stage is a file** (`notes.md`, `brief.md`, `story.json`, `film.json`, plan, frames): a film can resume at any stage, and the critic (a fresh sub-agent) reads the files, not your memory.
8. **Nothing invented**: a figure, a name, a claim in the film is in the documents. If the documents do not say it, the film does not.
