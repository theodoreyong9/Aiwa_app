# Promotional videos: the standard

What a Claude Code session reads when asked for a promotional video of a creation (the widget's "Vidéo" instruction points here). The tools are in `video-kit/`. A video is a deliverable like the creation itself: made by a script, checked by a script, and stored in the creation's own GitHub repository.

## 1. What the user gets

A video without any video-editing skill needed. The steps: **brief** (a description, an address, a logo, photos, screenshots, a product sheet, or just the creation itself) → **analysis and concept** (target, promise, hook, script, storyboard) → **production** (media, scenes, animation, voice if available, music, editing) → **check** (technical, visual, sound, advertising) → **delivery** (the final video, the other formats, variants).

Two modes: automatic, and intermediate validation (the storyboard is shown before the render, through a *demande* of the widget). The user is never forced to validate every scene.

## 2. Rules that do not bend

- **Nothing is invented.** Every statement of the video is traceable to what the user gave or to what the creation shows. No statistic, result, testimonial, guarantee or "before / after" that is not authentic and authorised. Assumptions are said in one sentence.
- **A brief may be incomplete.** Fill in only what can be deduced from the available sources, and say which hypotheses matter.
- **Media have a source.** Priority: what the user provided; captures and resources of the real product (Chromium screenshots of the creation); free libraries whose terms were checked; graphics made locally. Each medium is recorded with its source, its type, its size, the rights known and the scene that uses it. A missing medium is replaced by an authorised one or reported, never filled in silently with an incoherent scene.
- **One art direction** for the whole video: colours, typefaces, contrast, rhythm, transitions, the way the logo is used. No change of style from scene to scene without a reason.
- **Free and local first.** ffmpeg, Chromium, local graphics. An external service only when its value justifies its cost, and the cost is said before it is spent. Free software, a downloadable model, a free hosted service and a free API are four different things: say which one is used.

## 3. Script and storyboard

Scenes, in order. Each has an identifier, a planned duration, a narrative goal, the narration or dialogue, the text shown, the main medium, the movement or framing, the transitions, the sound, and the call to action if any. The storyboard is a versioned JSON/JS object (`STORYBOARD` in `video-kit/template/timeline.html`), independent of any AI provider, so that one scene can be changed without redoing the others.

Several concepts only when that brings a real value (problem then solution, product demonstration, a benefit, an application walk-through, a cinematic presentation, an offer and a call to action); say which one is chosen and why.

## 3b. Motion and ambition: a video is not a slideshow

The rules above keep a video honest; this section keeps it worth watching. A screenshot laid in the middle of a dark frame with a title above it is a slide, not a video, and a page that has little content does not excuse it.

- **Every scene moves.** Text is animated (word by word, by mask, in motion); captures are cropped in close, zoomed or panned slowly; a real page scrolls (record it in motion with Playwright instead of photographing it); elements enter and leave on the beat.
- **Pace.** A cut or a visible change every 1.5 to 3 seconds. A hook in the first 2 seconds that holds the attention. One art direction (the rule above) is not a reason for one static composition.
- **Little material.** When the creation is nearly empty, make material out of what it does: animate it, zoom on a detail, turn it into a graphic. Do not stretch emptiness.
- **Sound is designed.** A rhythm with accents on the cuts (the bed of `audio-bed.py` is a placeholder), not a continuous pad; a licensed track when there is one.
- **The honest look.** Before delivering, extract at least 8 frames at regular intervals (`ffmpeg -i video.mp4 -vf fps=1/3 f%02d.png`), look at them, and say plainly whether it looks like a slideshow. If it does, redo it. The automatic check cannot tell: it reads the file, not the idea.

## 4. Formats

| Format | Size | For |
|---|---|---|
| 9:16 | 1080 × 1920 | TikTok, Reels, Shorts |
| 16:9 | 1920 × 1080 | YouTube, websites, presentations |
| 1:1 | 1080 × 1080 | square posts |
| 4:5 | 1080 × 1350 | vertical social ads |

Durations: 15, 30, 45, 60 s (a first one of 20 to 30 s). MP4, H.264, AAC. The layout is recomposed for each format (the template does it): the text is repositioned and kept out of the zones the platforms cover (the top tenth and the bottom sixth of a vertical format).

## 5. The check, mandatory, separate from the making

`video-kit check` reads the finished file and reports three levels: **blocking** (do not deliver: unreadable file, wrong size or duration, no audio track, silent audio, black screen), **warning** (codec, frame rate, size, clipping, a frozen picture), **suggestion** (a quiet level). Creative suggestions are never presented as certain technical errors. After the script check, look at frames of the video yourself (a contact sheet) for what a script cannot see: text cut off, a deformed logo, a medium unrelated to the product, a wrong transition. A blocking error stops the delivery until it is fixed or the user accepts it explicitly.

## 6. Making it: the production, in stages

A good video is not one long generation, it is a chain of short decisions, each written down and each checked. The model matters less than the order: **do the stages in order, write each result to a file under `docs/`, and re-read the previous file before starting the next** (that is what keeps a long job coherent).

| # | Stage | The file | What it settles |
|---|---|---|---|
| 0 | **Facts** | `facts.md` | What is TRUE and usable: what the user gave, what the creation shows (read its code, open it, list what it does), real names, figures that are on the page. Capture the real material: `video-kit capture` for a tall picture of a page, Playwright screenshots, recorded interactions. |
| 1 | **Brief** | `brief.md` | The audience, the ONE message, the tone, the art direction taken from the creation (palette, type, how it moves), the length and formats, the call to action. Read `docs/DIRECTOR-PLAYBOOK.md`, and look for ideas in real campaigns: `node video-research/src/cli.js research "<the brief>"` brings back the closest campaigns of the catalogue (idea, credits, sector, link): keep 2 or 3 and cite them in `brief.md` (title, link, what you keep from each), without copying anything. `video-kit/src/analyze.py` reads a film you are allowed to read and reports its shots, rhythm, movement and sound. |
| 2 | **Script** | `script.md` | The logline, then five beats: hook (0 to 3 s: a promise or a question, never a logo), tension (what is wrong or missing), reveal (the creation, in use), proof (a real detail), call to action. The voice-over text with its seconds, and each on-screen text (7 words at most). |
| 3 | **Shot list** | `video.html` (`SHOTS`) | One shot per beat or part of a beat: its purpose, its movement (camera, text, the real page scrolling), its transition, its sound cue. Start from `video-kit/template/cinematic.html`; the layers are in `cinematic.js`. When a shot must look real (a product, a person, a place), choose its tool in `video-kit/shots/README.md`: a 3D shot made with Blender, a real footage with our elements over it (tracked), a clip from a video generator of the user's, or the engine; `video-kit shotlist` writes the list of what to produce and `assemble --clips` lays the clips. Say in the report which shots are real, 3D, generated or drawn. |
| 4 | **Sound** | `bed.wav`, `vo.wav` | `beat.py` for a pulse with an accent on every cut (`--cuts-file=frames/cuts.json`), a tempo that fits the tone; `voice.py` for a voice-over (the music ducks under it): run `sh video-kit/src/voice-setup.sh` once for a natural neural voice (the Piper voice "siwis medium" through sherpa-onnx, French, runs on the CPU, about 80 MB); without it the engine falls back on espeak-ng, which is robotic. Say which engine spoke. For a film that hits, look for a real track in the register (`node music-research/src/cli.js search "<mood>" --bpm=100-130 --energy=4`, see `music-research/README.md`), download only the one you keep, put the cuts and the few punchy lines of the voice on its strong beats, and assemble with `--duck=light` so the music stays forward. Write its title, author, licence and source in the brief; if it asks for a credit, show it small in the film or give it for the description. |
| 5 | **Preview** | `preview/` | Render small and fast (`--width=480 --height=270 --fps=10`), assemble, and extract a contact sheet (`ffmpeg -i out.mp4 -vf "fps=1/2,scale=320:-1,tile=5x3" sheet.png`). Never render at full size before the preview has passed stage 6. |
| 6 | **Critique** | `critique.md` | A separate pass, as a demanding creative director who has NOT seen the code, looking only at the contact sheet and the brief. Score 1 to 5: hook, clarity of the message, pace and variety, movement in every shot, legibility, art direction, sound and sync, honesty (nothing invented), call to action. Anything under 4 is fixed, then stages 5 and 6 are repeated, at most three rounds. If a sub-agent tool is available, give the critique to a fresh agent with the frames and the brief only. Report the final scores as they are. |
| 7 | **Final** | `<name>-16x9.mp4` … | Full-size render, `video-kit check` (a `slideshow` warning means redo), then the release and a short summary: what was verified, what is a placeholder, what could not be done. |

The commands:

```
node video-kit/src/cli.js capture page.html page-full.png --width=1440 --height=810       # a page as one tall picture (for a "page" layer)
node video-kit/src/cli.js render video.html frames/ --seconds=<total> --width=1920 --height=1080   # frames/cuts.json: where the shots change
python3 video-kit/src/beat.py bed.wav <total> --bpm=108 --cuts-file=frames/cuts.json
python3 video-kit/src/voice.py cues.json vo.wav <total> --lang=fr                           # optional: [{"at": 3.2, "text": "…"}, …]
node video-kit/src/cli.js assemble frames/ out-16x9.mp4 --audio=bed.wav --voice=vo.wav
node video-kit/src/cli.js check out-16x9.mp4 --seconds=<total> --width=1920 --height=1080
```

The page defines `window.render(t)`, a pure function of t, so a frame can be redone alone. The cinematic engine (`template/cinematic.js`, on top of `template/motion.js`) gives: kinetic text (words, letters, lines; mask, rise, blur, scale, drop, typewriter), images and real pages in browser or phone frames with camera moves, shapes, counters, paths that draw themselves, animated backgrounds, eight transitions, grain and vignette. `template/timeline.html` (a title and a picture per scene) remains for the simplest cases, and is a slideshow engine: use it only when a slideshow is what is wanted.

## 7. Revisions in natural language

"Make the start punchier", "keep the editing but change the music", "replace only scene three", "cut it to fifteen seconds", "a more premium version", "adapt it vertically": translate the request into precise changes of the storyboard, keep what is not concerned, redo only the frames of the scenes that changed, and check again. Each version is kept with the storyboard it came from.

## 8. Where it goes

In the creation's repository: the video as a file directly in `docs/` (one file per video, named `name-9x16.mp4`, `name-16x9.mp4`, …), and under `docs/video-<name>/` its storyboard, the media list with their sources and rights, and the check report. The widget's "Vidéos" button lists the video files of `docs/` (a public repository: Aiwa never asks for a GitHub token) and asks the session for a new one.

## 9. Limits to state

A first version does not do AI video generation for each scene, a good synthetic voice, or professional music: the bed is a placeholder, and a voice needs a tool that was checked for licence and quality. Rendering and the cost in time and space are measured, not promised: say what the render took. Rights to the media remain the user's: say which ones were assumed.
