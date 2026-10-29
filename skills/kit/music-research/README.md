# music-research

A register of music a promotional video can use **without asking anyone**: CC0, public domain, CC BY. One line per track in `catalog/tracks.jsonl`: title, author, source, licence, **tempo** (BPM), **tags** (the feel), instruments, length, an **energy** from 1 to 5, the address of the file and the credit line to show. The agent searches the register, listens to two or three candidates, downloads **only the one it keeps**, and writes its source and licence in the brief of the film.

## Use

```
node music-research/src/cli.js search "énergique, tendu, punchy" --bpm=100-130 --energy=4 --credit=ok
node music-research/src/cli.js search "épique" --credit=none          # only tracks that ask for no credit (CC0, public domain)
node music-research/src/cli.js fetch inc-hit-the-gas musique.mp3     # downloads that one track, prints its credit and source
node music-research/src/cli.js credit <id>
node music-research/src/cli.js stats
```
Without the repository cloned: `MR_CATALOG_URL=https://raw.githubusercontent.com/theodoreyong9/Aiwa_app/main/skills/kit/music-research/catalog/tracks.jsonl`. The brief may be in French (the common mood words are carried over to the English tags).

Then `node video-kit/src/cli.js assemble frames film.mp4 --audio=musique.mp3 --voice=vo.wav --duck=light`: the track is looped if shorter than the film, faded in and out, cut at the end; `--duck=light` keeps the music forward under a few punchy lines (`strong`, the default, lets the voice lead).

## Where the tracks come from, and what each licence asks

| Source | Licence | Credit | How it is read |
|---|---|---|---|
| Incompetech (Kevin MacLeod), about 1400 pieces | CC BY 4.0 (stated on its FAQ) | **asked**: « Musique : « titre », Kevin MacLeod (incompetech.com), CC BY 4.0 », small, in the film or its description | its one list file `pieces.json` (its robots.txt allows `/music`), once a week |
| OpenGameArt | CC0 (no credit) or CC BY 3.0 / 4.0 (credit) | per page | listing pages then each page, **10 s apart** as its robots.txt asks |

Left out on purpose: anything NC (non-commercial), ND (no derivatives), SA (share-alike, which could reach the film), GPL, and anything whose licence is not read. Pixabay, Freesound, ccMixter and Musopen are not read by a program: their robots.txt or terms forbid it or refuse bots. A track from them can be added by hand, with its licence page address.

## What is measured and what is not

The tempo of an Incompetech track is **declared by its author**, not measured here (`bpm_basis: "declared"`). OpenGameArt pages give no tempo: `bpm` is empty there until a measurement is added. The energy is a rough reading of the tags and the tempo (`energy_basis`), good enough to rank, not an ear. No audio is stored in this repository: the register keeps the address of each file, and `fetch` downloads one track from its source. `fetch` tries the source, then the copy in the release `music` of this repository (made on request by the workflow *Music mirror*, only for tracks of the register). If neither can be reached from the session, say so and use the generated bed (`video-kit/src/beat.py`).

Weekly sync: `.github/workflows/music-catalog-sync.yml`. Tests: `npm test` in this folder.
