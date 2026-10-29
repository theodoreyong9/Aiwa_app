# Plan

## What version 1 is

One repository, one promise: **an app store with a wallet, usable on a phone within minutes, on a protocol with no shared ledger.**

| Part | What it does |
|---|---|
| `packages/core` | The protocol, pure and without I/O: identity, signed events, the log, progression (verifiable work), accrual, conservation, canonical fold order, verification of a submission. |
| `packages/platform` | Distribution: transport, replication, storage, publication of apps, the archive node. |
| `packages/lib` | The wallet API (12-word recovery, backup, restore, burn, payments), the contract SDK. |
| `apps/web` | The store and the wallet as one web app: list, rank, open apps in a sandbox; the wallet starts and restores by itself; one sheet publishes. |
| `registry` | The open listing: validation and merge of submissions of the three kinds (code, Aiwa contract, comment for the critic), ranking by the existing `score / laps`. |
| `android` | One APK: the web app in a WebView, plus the dictation widget for Claude Code as an optional module. |
| `docs` | The yellow paper, the explanation, the business model. |

## What version 1 leaves out

Peer-to-peer discovery between strangers, a graph data layer, hardware attestation as a requirement, any payment other than the creator fee, a price or purchase flow for apps.

## The creator fee

A fixed share of the burn is sent to a creator address that is a constant of the protocol, not a choice of the application or of the user. The verifier counts it; a burn that omits it counts for less. The first value is 0.1 % of the T share, changeable later through a versioned rule. See the yellow paper.

## Where each step stands

| Step | State |
|---|---|
| Protocol, distribution and wallet packages in one workspace, one lock file | done — core 421 tests, platform 107, lib 114. The protocol was rewritten for clarity without changing a byte it signs (one signing module; the wallet class split into focused modules); the signed messages' bytes are pinned by a test |
| The creator fee in the burn: rule, verification, wallet transaction | done, with tests (core 8 + lib 5); the creator address is set in `deployment.json` |
| The yellow paper, standalone, with the fee (§11) and the order of conflicting branches (§13.4) | done |
| The documents: the README, the plain-words explanation (EN and FR) and the yellow paper (seven parts and four appendices, in the order the system works: foundations, the three pillars, creating value, agreement without a clock, applications, observation, assessment), each with diagrams of how it **functions**; `scripts/check-diagrams.mjs` renders every diagram and checks every `§` reference in CI | done |
| The registry: signed packages of three kinds (code, a pointer to a bundle published through Aiwa, or a comment for the critic), validation with the protocol's own checks, ranking `score / laps`, public baselines, workflow | done, 19 tests against a stand-in Solana; the workflow itself has not run on GitHub |
| The web app: store, wallet that starts and restores by itself, one publish sheet with the author's GitHub login, an SDK module for contract apps | done, unit tests (61, 30 of them in Chromium) (ranking, sandbox, tampering host, offline, the wallet starting by itself and its history coming back, the burn with the fee, publishing of both kinds through stand-ins of the Android host and of GitHub whose pull request is given to the real registry code, an app that uses the SDK) |
| The Android app: the web app in a WebView, keystore and GitHub device login for the page, the widget (Light and Glasses shapes), the voice (eleven personal words), the super agent, loops and links between critics, videos, cast and campaigns, in the brain (Termux, 208 Python tests) and a Kotlin bridge tested on a JVM | written; compiled in CI; **never run on a phone**; the voice, the real Claude Code sessions, the glasses and the TV never tried |
| The Android app follows the site: its page is downloaded from Pages, each file checked against the SHA-256 of `release.json` and served from app storage at the next start; a copy stays in the APK for the first run and offline | written; the checks are unit-tested on a JVM (14 tests, against a release written by the Node side, which 5 tests cover); **never run on a phone** |
| Apps that use the wallet: a declared `<meta name="aiwa-wallet">`, a banner, a door (who I am, pay, receive, show or scan a code); the **click duel** between two phones (WebRTC linked by two codes, a price per click, 20 s, the one who clicked less pays, no signature per click) | done and tested between two pages of one Chromium, against a stand-in Solana. **Not** between real phones. Left for later, on purpose: nobody is stopped from lying about their count, no escrow, no cap, no search for players nearby |
| Meeting the other wallets and seeing them: the wallet's *Network* (a Trystero room, then the replicator) and, by hand, *Link with another phone* (two codes), and *Who this phone has seen* (position, proof, vote, fork, pace: yellow paper §19, reported and never applied) | done: 6 lib tests, 3 platform tests, 1 test in Chromium between two pages. **Not** between real phones. Not wired, on purpose: hardware roots (§19.2), since nothing in this repository issues any |
| The business model, with its real numbers | [docs/BUSINESS.md](docs/BUSINESS.md) |

## Not verified

- A real burn on Solana (devnet or mainnet), end to end. `scripts/devnet-check.mjs` does it (burn at T = 0.4 with a creator address made for the run, the creator account read on chain, the registry's own verification, the fail-closed check) and passes against a stand-in; run for real from GitHub (the *Devnet check* workflow) the RPC answered (solana-core 4.3.0) but the faucet refused the shared runner twice (429, daily limit per IP). It needs a devnet wallet funded once — faucet.solana.com — whose phrase goes in the repository secret `DEVNET_PHRASE`, or `node scripts/devnet-check.mjs --phrase "…"` from your own machine or phone.
- The Android app on a real device: the WebView host, the keystore, **GitHub's device login against the real GitHub** (it needs an OAuth App with Device Flow enabled, whose Client ID goes in `deployment.json`), Android's automatic backup carrying the wallet's history to a new phone, the Termux backend, the widget. Google Play policy.
- The page updating itself on a real phone: the download, the swap at the next start and the serving from app storage (`/site/`), and that the WebView gives scripts served from app storage a JavaScript type. It needs GitHub Pages on (the workflow is red without it).
- A pull request opened by the Store's sheet on GitHub, end to end (the sheet's calls are tested against a stand-in of GitHub's API).
- The registry workflow on GitHub, with a real pull request. GitHub Pages must be enabled for the site to be served (Settings → Pages → Source: GitHub Actions).
- The legal status of the creator fee and of the store, and the economic parameters in the field.

## Definition of done for a step

Tests pass in CI; documentation says exactly what was and was not verified; no claim without a check.

## Known risks

- **Receiving AIWA needs Solana once.** The receiving wallet confirms the burn the coin was created from (otherwise anyone could invent AIWA). With no connection a payment is received but counts only once the phone has been online: two phones in a room with no network cannot see the payment in the balance yet. A mode where a wallet accepts a payment from the person in front of it, flagged as unchecked, is not built.

- **The camera in the Android app has never run.** The page reads QR codes with `getUserMedia` and decodes them in JavaScript (jsQR, tested in Chromium against a fake camera that films a code); `StoreActivity` grants the camera to the page's own origin, for video only, after Android's permission (written, compiled in CI). Whether a phone's WebView then delivers frames is not known. Pasting a code always works.
- **Receiving a payment checks the sender's whole history, and that takes time.** A payment carries the events behind its coins. In the click-duel test the winner's phone spends about 35 s on a 570 KB payment (25 s of it checking the events) from a wallet that has mined every 150 ms, a pace the real 30 s tick does not reach; checkpoints are meant to bound it, but nobody has measured a real wallet's payment on a real phone.
- **Observation is mostly unused.** Of the observation layer (§19) the wallet uses the forks only (a warning when it receives from an identity that signed two histories); the weighted median, hardware roots and relative rate are tested library code that no wallet, registry or screen calls. The registry protects itself differently, with the witnesses it requires in each submission.
- **The site decides what every phone runs.** The Android app takes its page from the site without a signature: whoever can publish on it (the repository's GitHub account) can change the Store's page on every phone that follows it, including the code that holds the wallet. That is the account that already owns the repository and the APK's release, so no second key is asked for now. If the account becomes a risk (real value, more than one maintainer), add a signature kept off GitHub, checked by the APK, in front of the same download; the APKs already installed would not check it until they are updated.
- **An app that declares the wallet pays only once the player allows it** (a sheet of the Store: that payment, or a budget until the app is closed; a refusal silences the app for 30 s). What the player allows is spent as the app wishes, and the app is not reviewed: the name in the sheet is the author's. Not tried on a real phone.

- Everything involving real Solana has only been played against a stand-in. The first real run is a prerequisite for any claim.
- A permissionless store attracts abuse: sandbox by design, plus listing rules and reporting.
- The creator fee and a store that lists paid-for things need legal advice before launch.
- The Android build can only be compiled in CI; the dictation module needs Termux and is optional for that reason.
