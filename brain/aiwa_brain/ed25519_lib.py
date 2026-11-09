"""Ed25519 signature check (RFC 8032), in plain Python: the brain has no dependency, and a few events are checked at a time. `sign` and `public_key` exist for the tests (the phone signs elsewhere)."""
import hashlib

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _inv(x):
    return pow(x, _P - 2, _P)


def _x_of(y, sign):
    xx = (y * y - 1) * _inv(_D * y * y + 1) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P:
        x = x * _I % _P
    if (x * x - xx) % _P:
        return None
    if x & 1 != sign:
        x = _P - x
    return x


_BY = 4 * _inv(5) % _P
_B = (_x_of(_BY, 0), _BY, 1, _x_of(_BY, 0) * _BY % _P)


def _add(a, b):
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    aa, bb = (y1 - x1) * (y2 - x2) % _P, (y1 + x1) * (y2 + x2) % _P
    cc, dd = 2 * t1 * t2 * _D % _P, 2 * z1 * z2 % _P
    e, f, g, h = bb - aa, dd - cc, dd + cc, bb + aa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s, point):
    out = (0, 1, 1, 0)
    while s:
        if s & 1:
            out = _add(out, point)
        point = _add(point, point)
        s >>= 1
    return out


def _encode(point):
    zi = _inv(point[2])
    x, y = point[0] * zi % _P, point[1] * zi % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _secret(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    return (a & ((1 << 254) - 8)) | (1 << 254), h[32:]


def public_key(seed):
    return _encode(_mul(_secret(seed)[0], _B))


def sign(seed, message):
    a, prefix = _secret(seed)
    public = _encode(_mul(a, _B))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _Q
    r_enc = _encode(_mul(r, _B))
    h = int.from_bytes(hashlib.sha512(r_enc + public + message).digest(), "little") % _Q
    return r_enc + ((r + h * a) % _Q).to_bytes(32, "little")


def _decode(raw):
    if len(raw) != 32:
        return None
    y = int.from_bytes(raw, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    if y >= _P:
        return None
    x = _x_of(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def _same(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % _P == 0 and (a[1] * b[2] - b[1] * a[2]) % _P == 0


def verify(signature, message, public):
    """True when `signature` (64 bytes) is the signature of `message` by `public` (32 bytes)."""
    try:
        if len(signature) != 64 or len(public) != 32:
            return False
        point, r_point = _decode(public), _decode(signature[:32])
        s = int.from_bytes(signature[32:], "little")
        if point is None or r_point is None or s >= _Q:
            return False
        h = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _Q
        return _same(_mul(s, _B), _add(r_point, _mul(h, point)))
    except Exception:
        return False
