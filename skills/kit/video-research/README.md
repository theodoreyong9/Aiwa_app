# video-research

A catalogue of advertising campaigns for a Claude Code session to draw ideas from before it writes the script of a promotional video (stage 1 of `docs/PROMO-VIDEO.md`): for each campaign, the **idea** (a short excerpt of the description, with the link to the page), the **credits** (brand, agency, country, year), the **kind of work** (media, sector), and the **address of the film** (a YouTube or Vimeo link). **No film is downloaded or stored, and no picture of one.**

Source: Ads of the World. Its `robots.txt` forbids pagination (`?page=`) and some administrative paths, and nothing else for a generic bot: the reader fetches only the home page, the campaigns page and the campaign pages (`/campaigns/<name>`), one every 3 seconds at least, and never a path the `robots.txt` forbids (an unreadable `robots.txt` means nothing is fetched). The Vimeo and One Show sites were looked at and left out: Vimeo's terms forbid automated access outside its API, and The One Show's `robots.txt` disallows everything for a generic bot. YouTube and Vimeo refuse the servers of GitHub Actions, so a film cannot be fetched there anyway.

```
node video-research/src/cli.js sync [--max=40]                       # read the new campaigns (the weekly workflow does it)
node video-research/src/cli.js research "<the brief>" [--limit=8]    # the campaigns closest to a brief → .video-research/latest/campaigns.md
node video-research/src/cli.js stats
VR_CATALOG_URL=https://raw.githubusercontent.com/<owner>/Aiwa_app/main/skills/kit/video-research/catalog/campaigns.jsonl   # when the repository is not cloned
```

`research` is a keyword search (a few French words of a brief are carried over to English: wine, game, car…); it does not understand the brief, it brings back a few campaigns to read and cite. The catalogue grows by what the site shows on its first pages each week (about 60 recent campaigns), so it holds recent work, not the history of advertising.
