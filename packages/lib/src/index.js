// aiwa-lib: the public, developer-facing facade over aiwa-core
// (validation, event/identity substrate) and aiwa-platform
// (distributed infra) — a wallet API and a smart-contract/token
// authoring SDK, composed from what those two packages already prove
// out, never a reimplementation of either.

export { fromUnits, toUnits, SOLANA_INCINERATOR_ADDRESS } from 'aiwa-core';
export { WebrtcTransport, TrysteroTransport, CompositeTransport, Introducer, PeerManager } from 'aiwa-platform';
export { AIWA } from './wallet.js';
export { Channel } from './channel.js';
export { encodeOfflineBundle, decodeOfflineBundle } from './offline-bundle.js';
export { collectAncestors } from './ancestors.js';
export { defineContract, Contract, signedAction, verifySignedAction } from './contract.js';
export { callDoor, doorAvailable, doorStorage, createDoorBackend, loadOrCreateIdentity } from './door.js';
