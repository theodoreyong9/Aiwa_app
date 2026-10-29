/** The two arguments every signed-event builder of aiwa-core takes after its fields: the 32-byte seed and the public key bytes. */
export const signerOf = (keypair) => [keypair.secretKey.slice(0, 32), keypair.publicKey.toBytes()];
