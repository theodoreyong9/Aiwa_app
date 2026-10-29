// The Capability — an application never receives "access to
// everything." A capability is a signed, scoped grant:
// this resource, these actions, issued by this real
// identity, for this subject.

function coreBytes({ resource, actions, issuer, subject, expiresAt }) {
  const core = { resource, actions: [...actions].sort(), issuer, subject, expiresAt: expiresAt ?? null };
  return new TextEncoder().encode(JSON.stringify(core));
}

/** `issuerIdentity` must be a secret-key-bearing Identity (aiwa-core's own identity.js) — the subject can never issue its own capability over someone else's resource. */
export async function issueCapability(issuerIdentity, { resource, actions, subject, expiresAt }) {
  const bytes = coreBytes({ resource, actions, issuer: issuerIdentity.id, subject, expiresAt });
  const signature = await issuerIdentity.sign(bytes);
  return { resource, actions, issuer: issuerIdentity.id, subject, expiresAt: expiresAt ?? null, signature };
}

/**
 * pure verification: the signature must verify
 * against the claimed issuer, and — if `expiresAt` is set — the
 * capability must not have expired as of `now`.
 */
export async function verifyCapability(capability, issuerIdentity, now = Date.now()) {
  if (capability.issuer !== issuerIdentity.id) return { valid: false, reason: 'issuer mismatch' };
  if (capability.expiresAt !== null && now > capability.expiresAt) return { valid: false, reason: 'real capability has genuinely expired' };
  const bytes = coreBytes(capability);
  const sigValid = await issuerIdentity.verify(bytes, capability.signature);
  if (!sigValid) return { valid: false, reason: 'real signature does not verify' };
  return { valid: true };
}

/** pure: does this already-verified capability actually cover the requested action on the requested resource? */
export function capabilityAllows(capability, { resource, action }) {
  return capability.resource === resource && capability.actions.includes(action);
}

/**
 * A minimal, per-subject capability set — what a real
 * application (a "sphere") actually holds, checked before every real
 * privileged operation.
 */
export class CapabilitySet {
  constructor() {
    this._grants = [];
  }
  grant(capability) {
    this._grants.push(capability);
  }
  /** pure check against every currently-held grant — never trusts a capability that was never verified first (see `verifyCapability`). */
  can(resource, action) {
    return this._grants.some((c) => capabilityAllows(c, { resource, action }));
  }
}
