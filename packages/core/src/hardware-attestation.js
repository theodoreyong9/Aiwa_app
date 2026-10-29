// A domain's minimal independence hypothesis: attestation that it is not backed solely by an actor who can fabricate
// arbitrary identities and observations in software alone. A binary gate on observation eligibility that
// causal-tick.js reports as a SEPARATE signal: never a weight, never a vote. AIWA works fully without it.
//
// A two-hop signature chain: origin domain --[issues]--> hardware root --[binds]--> this domain.
//
// Honest limit: nothing here can verify from software that a hardware root's key really lives on non-clonable
// hardware. What it verifies is a traceable chain of signatures from a known origin.

import { toHex, fromHex, sha256Hex } from './bytes.js';
import { signHex, verifyHex } from './signing.js';

const MIN_INDEPENDENT_ROOTS = 2;
const utf8 = new TextEncoder();

function canonicalIssuance({ originDomain, hardwareRootPubkey, issuedAt, nonce }) {
  return JSON.stringify({ originDomain, hardwareRootPubkey, issuedAt, nonce });
}
function canonicalBinding({ hardwareRootPubkey, boundDomain, boundAt }) {
  return JSON.stringify({ hardwareRootPubkey, boundDomain, boundAt });
}

export async function issueHardwareRoot(originKeypair, originDomain, hardwareRootPubkeyBytes, { issuedAt = Date.now(), nonce = crypto.randomUUID() } = {}) {
  const fields = { originDomain, hardwareRootPubkey: toHex(hardwareRootPubkeyBytes), issuedAt, nonce };
  const originSignature = signHex(utf8.encode(canonicalIssuance(fields)), originKeypair.secretKey.slice(0, 32));
  return { ...fields, originSignature, originSignerPubkey: toHex(originKeypair.publicKey.toBytes()) };
}

export async function bindHardwareRoot(hardwareRootSecretKey, hardwareRootPubkeyBytes, boundDomain, { boundAt = Date.now() } = {}) {
  const fields = { hardwareRootPubkey: toHex(hardwareRootPubkeyBytes), boundDomain, boundAt };
  return { ...fields, bindingSignature: signHex(utf8.encode(canonicalBinding(fields)), hardwareRootSecretKey) };
}

export async function verifyHardwareAttestation(attestation, expectedDomain) {
  const { issuance, binding } = attestation ?? {};
  if (!issuance || !binding) return false;
  if (binding.boundDomain !== expectedDomain) return false;
  if (binding.hardwareRootPubkey !== issuance.hardwareRootPubkey) return false;

  try {
    // The signing key must really BE the claimed origin's own key, not merely a valid signature by SOME key.
    if ((await sha256Hex(fromHex(issuance.originSignerPubkey))) !== issuance.originDomain) return false;
    if (!verifyHex(utf8.encode(canonicalIssuance(issuance)), issuance.originSignature, issuance.originSignerPubkey)) return false;
    return verifyHex(utf8.encode(canonicalBinding(binding)), binding.bindingSignature, binding.hardwareRootPubkey);
  } catch {
    return false;
  }
}

export async function isIndependenceAttested(attestations, domain) {
  const distinctRoots = new Set();
  for (const attestation of attestations ?? []) {
    if (await verifyHardwareAttestation(attestation, domain)) {
      distinctRoots.add(attestation.binding.hardwareRootPubkey);
    }
  }
  return distinctRoots.size >= MIN_INDEPENDENT_ROOTS;
}

export { MIN_INDEPENDENT_ROOTS };
