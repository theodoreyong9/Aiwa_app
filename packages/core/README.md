# aiwa-core

The protocol, pure and without I/O: no transport, no storage backend of its own choosing, no application code. Everything above it (distribution, wallet, apps) composes it and never changes what counts as a valid state transition.

Where it sits in the repository (highlighted):

<!-- diagram: pkg-core-01-79f0d2e7.png -->
![Diagram: aiwa-core](../../docs/img/diagrams/pkg-core-01-79f0d2e7.png)

<details>
<summary>The source of this diagram (Mermaid)</summary>

```mermaid
flowchart BT
  core["<b>packages/core</b><br/>the protocol: identity, signed events,<br/>verifiable work, conservation"]
  platform["<b>packages/platform</b><br/>transport, replication, storage, bundles"]
  lib["<b>packages/lib</b><br/>the wallet API and the contract SDK"]
  registry["<b>registry</b><br/>validates submissions, ranks the apps"]
  web["<b>apps/web</b><br/>the Store and the wallet, one web app"]
  android["<b>android</b><br/>the APK: the web app in a WebView,<br/>and the optional widget"]
  platform --> core
  lib --> platform
  lib --> core
  registry --> lib
  web --> lib
  web --> registry
  android -. "carries the build of" .-> web
  style core fill:#fde68a,stroke:#b45309,stroke-width:2px
```

</details>
<!-- /diagram -->

```
npm test        # 421 tests, including a cross-check against an independent Rust implementation when cargo is available
```

## What is in it

| Area | Modules |
|---|---|
| Identity and events | `identity.js`, `event.js`, `event-log.js`, `adapt-event.js`, `canonical-order.js` |
| Time as work | `vdf.js`, `wesolowski-vdf.js`, `succinct-vdf.js`, `progression.js` |
| Creating value | `reward.js`, `fixed-point-math.js`, `accrual.js`, `burn-record.js`, `identity-cost.js` |
| Reading the result | `mining-state.js` (mining state and ranking figure), `submission.js` (verify a wallet's evidence) |
| Owning value | `conservation.js`, `units.js` |
| Wallet state | `wallet.js`, `materializer.js`, `checkpoint.js`, `solana-wallet.js` |
| Between domains | `mirror.js`, `causal-tick.js`, `weighted-median.js`, `triangulation.js`, `position.js`, `relative-rate.js` (the last four are experimental) |
| Applications | `contract-registry.js`, delegation and bearer vouchers (in `wallet.js`) |

## Things worth knowing

- **Every event is signed and content-addressed.** A reader never trusts the author field of an event: authority lives in signatures embedded in the payload.
- **A conflict has the same winner for every reader.** `canonicalOrder(events)` gives one order for the same events whatever order they arrived in (parents first, then the smaller id). It is agreement, not fairness; see the yellow paper §13.4.
- **A third party can verify a wallet's mining without trusting it.** `assessSubmission({ rewardParams, evidence, domain, baseline, witnessed, connection })` checks the envelopes, the work proofs and the burn on Solana, and returns the ranking figure.
- **The creator fee.** A deployment may set `rewardParams.creatorFee = { address, rateOfT }`: a fixed part of the T share of every burn then goes to that one address, in the same transaction, and the reader counts it (`creatorFeeLamports`, `burnQuote`, `fetchBurnRecord(connection, signature, { creatorAddress })`). A commitment at T > 0 whose burn did not pay it is refused; a reader that does not look at the address sees no payment and refuses too. Yellow paper §11.
- **Formats are frozen (version 1)**: the payloads of progression, accrual and claim events, the starting point of an epoch's work, the checkpoint and the backup.

## Honest limits

Everything involving real Solana has been played against a stand-in only. See [docs/YELLOWPAPER.md](../../docs/YELLOWPAPER.md) §21 for what is not claimed.
