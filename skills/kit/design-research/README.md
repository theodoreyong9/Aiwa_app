# design-research

A script that visits reference interfaces in a real browser, **measures** what they do, keeps the measurements in the repository, and hands the ones that fit a brief to Claude Code as a research pack. It is not a list of links and it is not a skill that tells Claude to "make it look good": the pack holds numbers, evidence and pictures.

```
Awwwards + CSS Winner (Site of the Day)
  → one canonical entry per site (two registries = two sources, one entry)
  → Playwright drives Chromium: navigation, scroll, hover, screenshots on desktop and phone
  → Chrome DevTools Protocol watches what the browser itself knows: network, animations, performance, console, targets
  → detection (technologies, each with status OBSERVED / INFERRED / DECLARED, confidence and evidence)
  → measured traits (typography, composition, motion, interaction, rendering, palette) and design tokens
  → catalog/sites.jsonl, screenshots/, analysis/   (versioned in Git)
  → brief → plan (which dimensions matter) → filter by format → rank → research pack
```

## Use

```
node design-research/src/cli.js crawl https://example.com          # one site
node design-research/src/cli.js sync                                # both registries, then the visits that are needed
node design-research/src/cli.js bootstrap                           # a first, larger catalogue
node design-research/src/cli.js search "site cinématique sombre, scène 3D" --format=site
node design-research/src/cli.js research "pwa claire et épurée" --format=pwa   # writes .research/latest/
node design-research/src/cli.js classify <id>                       # re-run the rules on the stored observation
node design-research/src/cli.js doctor
```

`DR_CATALOG_URL` (and `DR_SHOTS_URL`) read the published catalogue instead of a local one: a phone or a session without the repository only needs the JSONL and the pictures it asks for. `DR_FULLPAGE=0` skips the full-page capture.

The workflow `.github/workflows/design-catalog-sync.yml` runs `sync` every week and commits what changed. The widget's backend (`android/backend/aiwa_server.py`, `_design_line`) gives every session that has an interface to make the instruction to clone the Store read-only and run `research` against the published catalogue (`DR_CATALOG_URL`); `INSTRUCTION.md` is the same line for a session set up by hand.

## What it decides and what it does not

- **Measured** (by rules written in `src/classify/traits.js`): oversized type, serif / sans / condensed, fullscreen sections, asymmetric grids, scroll-driven and smooth-scroll motion, reveal on scroll (counted by scrolling the page), page transitions, continuous animation, custom cursor, rich hover (hovering the page's own controls), 3D / WebGL / WebGPU / canvas (recorded when the page asks for the context), dark / light, monochrome / vivid.
- **Not guessed**: art direction, tone, industry, why a reference works. They are listed in each entry's `needs_interpretation`, for the reader that has the screenshots, which is Claude Code in front of the pack.
- **A library is never declared from its name in the HTML.** `window.gsap` is OBSERVED; a pattern that merely resembles it is INFERRED and says so.
- **Formats.** Every entry says, for `site`, `pwa`, `apk` and `contract_ui`, whether what it does can be used there: a 3D scene does not fit a single HTML file of 512 KB or less, type, colour and motion rhythm do. A contract has no screen of its own, so only the patterns of the screen that shows it carry over.
- **Patterns, not copies.** The pack's synthesis lists what several references share and the measured ranges. It never says "copy this site".

## Limits, stated

- The two registry parsers are written for the markup as known and were **not run against the live sites** (they were written where the network is closed). The first run of the workflow tells: `doctor` and the workflow fail when a registry gives nothing. The pipeline itself, the crawler, the detection and the search are tested against local pages.
- Respect for the sites: robots.txt is read before any request to a registry, a delay separates requests, one visit per site, an identifying user agent. The registries' terms of use on automated reading have not been checked: read them before the first scheduled run.
- Retrieval is a table (`src/retrieval/plan.js`) and a score, not embeddings. Extending the lexicon is the way to teach it a new word.
- Pictures make a catalogue heavy in Git (a few hundred KB per site). The workflow visits at most 20 sites a week; decide where the pictures live before the catalogue grows.
- Tracing, Web Worker internals and network throttling emulation of the specification are not in this first version. The CDP domains in use: Network, Animation, Performance, Log, Runtime (with the canvas, observer and `requestAnimationFrame` hooks set before the page's scripts run).
