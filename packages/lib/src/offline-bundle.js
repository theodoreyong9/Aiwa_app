// A compact, transportable text encoding of a bundle or a handshake message, for a QR code, NFC, Bluetooth or a paste.

export const encodeOfflineBundle = (bundle) => btoa(encodeURIComponent(JSON.stringify(bundle)));

export const decodeOfflineBundle = (blob) => JSON.parse(decodeURIComponent(atob(blob)));
