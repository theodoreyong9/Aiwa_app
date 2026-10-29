// The primitives a Wesolowski proof is built from: modular exponentiation, primality, hash-to-prime.

export function modPow(base, exponent, modulus) {
  if (modulus === 1n) return 0n;
  let result = 1n;
  let b = base % modulus;
  for (let e = exponent; e > 0n; e >>= 1n) {
    if (e & 1n) result = (result * b) % modulus;
    b = (b * b) % modulus;
  }
  return result;
}

// Miller-Rabin with these bases is deterministic for every n below 3.3e24, far beyond a hash-to-prime output here.
const WITNESSES = [2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n, 23n, 29n, 31n, 37n];

export function isProbablePrime(n) {
  if (n < 2n) return false;
  for (const p of WITNESSES) {
    if (n === p) return true;
    if (n % p === 0n) return false;
  }
  let d = n - 1n;
  let r = 0n;
  while (d % 2n === 0n) { d /= 2n; r += 1n; }
  witnesses: for (const a of WITNESSES) {
    let x = modPow(a, d, n);
    if (x === 1n || x === n - 1n) continue;
    for (let i = 0n; i < r - 1n; i++) {
      x = (x * x) % n;
      if (x === n - 1n) continue witnesses;
    }
    return false;
  }
  return true;
}

/** A prime of `bitLength` bits derived from a message (Fiat-Shamir): hash it, then walk to the next odd prime. */
export async function hashToPrime(message, bitLength = 128) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', message));
  let candidate = digest.reduce((n, byte) => (n << 8n) | BigInt(byte), 0n) % (1n << BigInt(bitLength));
  candidate |= (1n << BigInt(bitLength - 1)) | 1n;       // the top bit (so the length is exact) and oddness
  while (!isProbablePrime(candidate)) candidate += 2n;
  return candidate;
}
