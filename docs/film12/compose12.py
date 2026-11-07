"""Film 12, the compositor. Six stations (dioramas in a black mirror void) and a wide shot of the six together. For each station a still with its depth: the camera moves in the room (real parallax, by reprojection of the depth), dives into the screen where the voice asks and the screen does it, comes back; a whip pan leads to the next station.
Act 1 (the question) and act 3 (the rules, the break, the end) are pictures of the screens page, with a glass break written here.
Usage: python3 compose12.py --from 0 --to 3000 [--workers 4]      (UI frames: /tmp/os12/ui/<mode>/NNNNN.jpg, the stills: /tmp/os12/st, the output: /tmp/os12/out)"""
import argparse, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'timeline12.json')))
FPS, OW, OH = TL['fps'], TL['width'], TL['height']
ST = os.environ.get('ST', '/tmp/os12/st'); UI = os.environ.get('UI', '/tmp/os12/ui'); OUT = os.environ.get('OUT', '/tmp/os12/out')
SW, SH = 2880, 1620
PW, PH = 1080, 2400
S = TL['scenes']; V = TL['voice']; A3 = TL['act3']


# ---------------------------------------------------------------------------------------------------------------- geometry (as in film 10)
def homog(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.append(np.linalg.solve(np.array(A, float), np.array(b, float)), 1).reshape(3, 3)

def apply(H, pts):
    out = []
    for x, y in pts:
        p = H @ np.array([x, y, 1.0]); out.append((p[0] / p[2], p[1] / p[2]))
    return out

def coeffs_inv(H):
    Hi = np.linalg.inv(H); Hi = Hi / Hi[2, 2]; return tuple(Hi.flatten()[:8])

def warp(img, H, size, resample=Image.BICUBIC):
    return img.transform(size, Image.PERSPECTIVE, coeffs_inv(H), resample)

def area_scale(q):
    return math.sqrt(abs(0.5 * sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4))))

def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)
def ease(x):
    x = max(0.0, min(1.0, x)); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def ramp(t, a, b): return max(0.0, min(1.0, (t - a) / (b - a)))
def lerp_q(a, b, s): return [(a[i][0] + (b[i][0] - a[i][0]) * s, a[i][1] + (b[i][1] - a[i][1]) * s) for i in range(4)]
def zoom_lerp(a, b, s):
    r = area_scale(b) / max(1e-6, area_scale(a)); s2 = s if abs(r - 1) < 1e-3 else (r ** s - 1) / (r - 1)
    return lerp_q(a, b, s2)

_cache = {}
def still(tag, mask=False):
    key = (tag, mask)
    if key in _cache: return _cache[key]
    im = Image.open(os.path.join(ST, tag + ('_mask' if mask else '') + '.png')).convert('L' if mask else 'RGB')
    if im.size != (SW, SH): im = im.resize((SW, SH), Image.LANCZOS)
    if len(_cache) > 10: _cache.pop(next(iter(_cache)))
    _cache[key] = im; return im
def screens(tag):
    j = json.load(open(os.path.join(ST, tag + '.json'))); sx = SW / j['width']
    return {n: [(x * sx, y * sx) for x, y in q] for n, q in j['screens'].items()}

_rng = {}
def ui(mode, t, ext='jpg', rgba=False):
    d = os.path.join(UI, mode)
    if (mode, ext) not in _rng:
        n = sorted(int(f[:5]) for f in os.listdir(d) if f.endswith('.' + ext)); _rng[(mode, ext)] = (n[0], n[-1]) if n else (0, 0)
    lo, hi = _rng[(mode, ext)]; i = max(lo, min(hi, int(round(t * FPS))))
    return Image.open(os.path.join(d, '%05d.%s' % (i, ext))).convert('RGBA' if rgba else 'RGB')

def letterbox(frame, bg=(16, 19, 46)):
    c = Image.new('RGB', (PW, PH), bg); c.paste(frame.resize((PW, 607), Image.LANCZOS), (0, (PH - 607) // 2)); return c

def paint(base, quad, items, size=(OW, OH)):
    fw, fh = size
    Hc = homog(quad, [(0, 0), (fw, 0), (fw, fh), (0, fh)])
    out = np.asarray(warp(base, Hc, size), float)
    for content, Hs, sq, mask in items:
        cw, ch = content.size
        Hcs = Hc @ Hs
        corners = apply(Hcs, [(0, 0), (cw, 0), (cw, ch), (0, ch)])
        wid = max(math.dist(corners[0], corners[1]), math.dist(corners[3], corners[2]))
        f = min(1.0, max(.12, wid / cw * 1.25))
        small = content if f >= .99 else content.resize((max(8, int(cw * f)), max(8, int(ch * f))), Image.LANCZOS)
        Hf = Hcs @ np.linalg.inv(np.diag([f, f, 1.0]))
        pad = np.asarray(warp(small, Hf, size), float)
        m = np.asarray(warp(mask.convert('L'), Hc, size, Image.BILINEAR), float) / 255.0
        poly = Image.new('L', size, 0); ImageDraw.Draw(poly).polygon(apply(Hc, sq), fill=255)
        poly = np.asarray(poly.filter(ImageFilter.MaxFilter(5)), float) / 255.0
        m = np.minimum(m, poly)[..., None]
        out = out * (1 - m) + pad * m
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def rect_matrix(w, h, q): return homog([(0, 0), (w, 0), (w, h), (0, h)], q)
FULL = [(0, 0), (SW, 0), (SW, SH), (0, SH)]

def phone_views(q):
    Hs = rect_matrix(PW, PH, q)
    y0 = (PH - 607) / 2
    video = apply(Hs, [(0, y0), (PW, y0), (PW, y0 + 607), (0, y0 + 607)])
    aspw = PH * OW / OH; nx0 = PW / 2 - aspw / 2
    native = apply(Hs, [(nx0, 0), (nx0 + aspw, 0), (nx0 + aspw, PH), (nx0, PH)])
    return Hs, {'video': video, 'native': native}

def path_quad(keys, t, views):
    if t <= keys[0][0]: return views[keys[0][1]]
    for (t0, n0), (t1, n1) in zip(keys, keys[1:]):
        if t0 <= t <= t1: return views[n0] if n0 == n1 else zoom_lerp(views[n0], views[n1], ease((t - t0) / (t1 - t0)))
    return views[keys[-1][1]]

def jitter(q, t):
    k = max(0.0, min(1.0, (area_scale(q) / SW - .55) / .45))
    if k <= 0: return q
    dx = k * (3.2 * math.sin(t * 1.3) + 1.6 * math.sin(t * 3.1 + 1)); dy = k * (2.4 * math.sin(t * 1.1 + 2) + 1.2 * math.sin(t * 2.7))
    return [(x + dx, y + dy) for x, y in q]

def bbox_view(quads, pad=.28):
    xs = [p[0] for q in quads for p in q]; ys = [p[1] for q in quads for p in q]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2; w = (max(xs) - min(xs)) * (1 + pad); h = (max(ys) - min(ys)) * (1 + pad)
    if w / h < OW / OH: w = h * OW / OH
    else: h = w * OH / OW
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]

def dark_phone(t, t_on):
    """A phone that listens: black, with a soft light (the voice of the person is heard here)."""
    c = Image.new('RGB', (PW, PH), (3, 4, 10)); a = smooth(ramp(t, t_on - .2, t_on + .5))
    if a > 0:
        g = Image.new('L', (PW, PH), 0); r = 240 + 24 * math.sin(t * 5); ImageDraw.Draw(g).ellipse((540 - r, 1100 - r, 540 + r, 1100 + r), fill=255); g = g.filter(ImageFilter.GaussianBlur(110))
        c = Image.composite(Image.new('RGB', (PW, PH), (110, 98, 230)), c, g.point(lambda v: int(v * a * .9)))
    return c


# ---------------------------------------------------------------------------------------------------------------- the stations: a still with its depth, a camera that moves in the room (the parallax is real), the screens laid on their planes
def quat_from_matrix(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2; return np.array([.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2; q = np.zeros(4); q[0] = (R[k, j] - R[j, k]) / s; q[i + 1] = .25 * s; q[j + 1] = (R[j, i] + R[i, j]) / s; q[k + 1] = (R[k, i] + R[i, k]) / s
    return q
def matrix_from_quat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
def slerp(q0, q1, s):
    d = float(np.dot(q0, q1))
    if d < 0: q1 = -q1; d = -d
    if d > .9995: q = q0 + s * (q1 - q0); return q / np.linalg.norm(q)
    th = math.acos(d); return (math.sin((1 - s) * th) * q0 + math.sin(s * th) * q1) / math.sin(th)
def lerp_pose(A, B, s):
    q = slerp(quat_from_matrix(A[:3, :3]), quat_from_matrix(B[:3, :3]), s); M = np.eye(4); M[:3, :3] = matrix_from_quat(q); M[:3, 3] = A[:3, 3] * (1 - s) + B[:3, 3] * s; return M

def load_depth(tag):
    """The depth pass is a 16 bit PNG (PIL reads only 8 bits of it): read with pypng once, kept as a .npy next to it."""
    p = os.path.join(ST, tag + '_depth.npy')
    if os.path.exists(p): return np.load(p)
    import png
    w, h, rows, info = png.Reader(os.path.join(ST, tag + '_depth.png')).read()
    a = np.vstack([np.array(r, dtype=np.uint16) for r in rows]).reshape(h, w, info['planes'])[..., 0]
    try: np.save(p, a)
    except Exception: pass
    return a

_st = {}
class Station:
    def __init__(self, tag):
        j = json.load(open(os.path.join(ST, tag + '.json'))); self.tag = tag; self.j = j
        im = Image.open(os.path.join(ST, tag + '.png')).convert('RGB').resize((OW, OH), Image.LANCZOS); self.img = np.asarray(im, np.float32)
        d = load_depth(tag)
        d = np.asarray(Image.fromarray(d.astype(np.float32)).resize((OW, OH), Image.BILINEAR), np.float32)
        self.Z = np.maximum(d / 65535.0 * j['zmax'], .05)
        sx = OW / j['width']; self.fx = j['K']['fx'] * sx; self.fy = j['K']['fy'] * sx; self.cx = OW / 2; self.cy = OH / 2
        self.Mw = np.array(j['cam'], float)
        ys, xs = np.mgrid[0:OH, 0:OW]
        X = (xs - self.cx) / self.fx * self.Z; Y = -(ys - self.cy) / self.fy * self.Z
        loc = np.stack([X, Y, -self.Z, np.ones_like(X)]).reshape(4, -1)
        self.P = (self.Mw @ loc)[:3].astype(np.float32)                     # the world points of the picture
        self.col = self.img.reshape(-1, 3)
        full = np.asarray(Image.open(os.path.join(ST, tag + '.png')).convert('RGB'))
        self.PADN = 1300; self.full = Image.fromarray(np.pad(full, ((self.PADN, self.PADN), (self.PADN, self.PADN), (0, 0)), mode='edge'))
    def project(self, Mt, pts):
        Ti = np.linalg.inv(Mt); out = []
        for p in pts:
            q = Ti @ np.array([p[0], p[1], p[2], 1.0]); z = -q[2]; out.append((self.cx + self.fx * q[0] / z, self.cy - self.fy * q[1] / z) if z > 1e-4 else (self.cx, self.cy))
        return out
    def reproject(self, Mt):
        Ti = np.linalg.inv(Mt).astype(np.float32); Q = Ti[:3, :3] @ self.P + Ti[:3, 3:4]
        Zt = -Q[2]; ok = Zt > .03; Zs = np.where(ok, Zt, 1.0)
        u = self.cx + self.fx * Q[0] / Zs; v = self.cy - self.fy * Q[1] / Zs
        iu = np.floor(u).astype(np.int32); iv = np.floor(v).astype(np.int32)
        ok &= (iu >= -1) & (iu < OW) & (iv >= -1) & (iv < OH)
        idx = np.nonzero(ok)[0]; order = idx[np.argsort(-Zt[idx], kind='stable')]
        out = np.zeros((OH, OW, 3), np.float32); m = np.zeros((OH, OW), np.float32); col = self.col[order]; uu = iu[order]; vv = iv[order]
        for du, dv in ((0, 0), (1, 0), (0, 1), (1, 1)):
            a = uu + du; b = vv + dv; g = (a >= 0) & (a < OW) & (b >= 0) & (b < OH)
            out[b[g], a[g]] = col[g]; m[b[g], a[g]] = 1.0
        return pushpull(out, m)

def pushpull(img, m):
    """Fills the holes of a picture from what is around them, at every scale (so that what is left empty by a move of the camera is a soft continuation, not a black spot)."""
    if m.min() >= 1: return img
    L = [(img * m[..., None], m)]
    while min(L[-1][1].shape) > 6:
        c, k = L[-1]; h, w = (c.shape[0] // 2) * 2, (c.shape[1] // 2) * 2
        L.append((c[:h, :w].reshape(h // 2, 2, w // 2, 2, 3).mean((1, 3)), k[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3))))
    c, k = L[-1]; cur = c / np.maximum(k[..., None], 1e-6)
    for c, k in reversed(L[:-1]):
        h, w = c.shape[:2]
        up = np.repeat(np.repeat(cur, 2, 0), 2, 1); up = np.pad(up, ((0, max(0, h - up.shape[0])), (0, max(0, w - up.shape[1])), (0, 0)), mode='edge')[:h, :w]
        fine = c / np.maximum(k[..., None], 1e-6); wgt = np.clip(k * 1.0, 0, 1)[..., None]; cur = wgt * fine + (1 - wgt) * up
    return cur

def get_station(tag):
    if tag not in _st:
        if len(_st) > 2: _st.pop(next(iter(_st)))
        _st[tag] = Station(tag)
    return _st[tag]

def close_pose(st, dev, fill):
    sc = st.j['screens'][dev]; c = np.array(sc['center']); n = np.array(sc['normal']); u = np.array(sc['up'])
    u = u - n * float(np.dot(u, n)); u /= np.linalg.norm(u)
    d = (sc['h'] * st.fy / OH if fill == 'height' else sc['w'] * st.fx / OW) * 1.0
    right = np.cross(u, n); M = np.eye(4); M[:3, 0] = right; M[:3, 1] = u; M[:3, 2] = n; M[:3, 3] = c + n * d
    return M

def drifted(st, dev, k, sway=0.0):
    """The wide camera, a little closer to the device (k = 0..1 of a slow push) and a little aside (sway): a hand, a rail."""
    M = st.Mw.copy(); c = np.array(st.j['screens'][dev]['center']); toward = c - M[:3, 3]
    M[:3, 3] = M[:3, 3] + toward * (.07 * k) + M[:3, 0] * sway * np.linalg.norm(toward)
    # keep looking at the same point
    f = c - M[:3, 3]; f /= np.linalg.norm(f); back = -f; up = np.array([0, 0, 1.0]); right = np.cross(up, back); right /= np.linalg.norm(right); upv = np.cross(back, right)
    M[:3, 0] = right; M[:3, 1] = upv; M[:3, 2] = back
    return M

CONF = {'S1': ('SCR_P1', 'height'), 'S2': ('SCR_TV1', 'width'), 'S3': ('SCR_P3', 'height'), 'S4': ('SCR_TV0', 'width'), 'S5': ('SCR_P5a', 'height'), 'S6': ('SCR_TV2', 'width')}
def station_pose(i, t):
    st = get_station('S%d' % i); dev, fill = CONF['S%d' % i]; sc = S[i - 1]; d0, d1 = sc['dive']; o0, o1 = sc['out']; s0 = sc['s0']
    Mc = close_pose(st, dev, fill)
    k = ramp(t, s0 - .3, d0)
    Mw0 = drifted(st, dev, k, .012 * math.sin(t * .5))
    if t < d0: return Mw0
    if t < d1: return lerp_pose(Mw0, Mc, ease((t - d0) / (d1 - d0)))
    sway = lambda tt: [.0015 * math.sin(tt * 1.7), .0012 * math.sin(tt * 1.3 + 1)]
    if t < o0:
        M = Mc.copy(); dx, dy = sway(t); M[:3, 3] = M[:3, 3] + M[:3, 0] * dx * np.linalg.norm(Mc[:3, 3] - np.array(st.j['screens'][dev]['center'])) + M[:3, 1] * dy * np.linalg.norm(Mc[:3, 3] - np.array(st.j['screens'][dev]['center']))
        return M
    Mw1 = drifted(st, dev, 1.0, .0)
    if t < o1: return lerp_pose(Mc, Mw1, ease((t - o0) / (o1 - o0)))
    return Mw1

def content_for(i, dev, t):
    sc = S[i - 1]
    if dev == 'SCR_P2': return dark_phone(t, sc['cmd'][0])
    mode = {'SCR_P1': 's1', 'SCR_TV1': 's2', 'SCR_P3': 's3', 'SCR_TV0': 's4', 'SCR_P5a': 's5a', 'SCR_P5b': 's5b', 'SCR_P5c': 's5c', 'SCR_TV2': 's6'}[dev]
    return ui(mode, t)

def lay_screens(st, Mt, devs, contents):
    """Lays the pictures on the planes of the screens, seen from the camera Mt."""
    fr = Image.fromarray(np.clip(st_base, 0, 255).astype(np.uint8)) if False else None

def paint_screens(base_img, st, Mt, items):
    size = (OW, OH); out = np.asarray(base_img, np.float32)
    for dev, content in items:
        sc = st.j['screens'][dev]; quad = st.project(Mt, sc['world'])
        cw, ch = content.size; H = homog([(0, 0), (cw, 0), (cw, ch), (0, ch)], quad)
        wid = max(math.dist(quad[0], quad[1]), math.dist(quad[3], quad[2]))
        if wid < 3: continue
        f = min(1.0, max(.1, wid / cw * 1.25)); small = content if f >= .99 else content.resize((max(8, int(cw * f)), max(8, int(ch * f))), Image.LANCZOS)
        pad = np.asarray(warp(small, homog([(0, 0), (small.width, 0), (small.width, small.height), (0, small.height)], quad), size), np.float32)
        big = Image.new('L', (OW * 2, OH * 2), 0); ImageDraw.Draw(big).polygon([(x * 2, y * 2) for x, y in quad], fill=255)
        m = np.asarray(big.resize(size, Image.LANCZOS).filter(ImageFilter.MaxFilter(3)), np.float32)[..., None] / 255.0
        out = out * (1 - m) + pad * m
    return out

def plane_blend(st, Mt, dev, splat):
    """Near the screen the surroundings are magnified a lot: there, the room is taken as a plane (the plane of the screen) and the picture is simply enlarged (clean), while far from it the depth moves things apart (parallax)."""
    sc = st.j['screens'][dev]; k = OW / st.j['width']
    q_src = [(x * 1.0, y * 1.0) for x, y in sc['px']]; q_t = st.project(Mt, sc['world'])
    m = area_scale(q_t) / max(1e-6, area_scale(q_src) * k)
    w = smooth(ramp(m, 1.12, 1.5))
    if w <= 0: return splat
    sx = sum(p[0] for p in q_src) / 4; sy = sum(p[1] for p in q_src) / 4; tx = sum(p[0] for p in q_t) / 4; ty = sum(p[1] for p in q_t) / 4
    sc_ = m * k                                                    # source pixels -> frame pixels (a zoom about the screen: no perspective, so a tilted screen does not stretch the room)
    P = st.PADN
    plane_img = st.full.transform((OW, OH), Image.AFFINE, (1 / sc_, 0, sx + P - tx / sc_, 0, 1 / sc_, sy + P - ty / sc_), Image.BICUBIC)
    plane_img = plane_img.filter(ImageFilter.GaussianBlur(10 + 8 * w))                         # a shallow field: what is around the screen is soft, as it would be with a lens this close
    plane = np.asarray(plane_img, np.float32)
    yy, xx = np.mgrid[0:OH, 0:OW]; vig = np.clip(1 - .55 * (((xx - tx) / (OW * .62)) ** 2 + ((yy - ty) / (OH * .62)) ** 2), .3, 1)[..., None]
    plane = plane * (1 - w + w * vig * .8)
    return splat * (1 - w) + plane * w

def station_frame(i, t, devs=None):
    st = get_station('S%d' % i); Mt = station_pose(i, t)
    base = plane_blend(st, Mt, CONF['S%d' % i][0], st.reproject(Mt))
    devs = devs or [d for d in st.j['screens']]
    items = [(d, content_for(i, d, t)) for d in devs]
    return Image.fromarray(np.clip(paint_screens(base, st, Mt, items), 0, 255).astype(np.uint8))

def wide_frame(t):
    st = get_station('WIDE'); u0, u1 = A3['universe']; k = ramp(t, u0, u1)
    Mw = st.Mw.copy(); center = np.array([0, 12.0, 1.1]); toward = center - Mw[:3, 3]
    Mt = Mw.copy(); Mt[:3, 3] = Mw[:3, 3] + toward * .22 * smooth(k) + Mw[:3, 0] * .25 * math.sin(t * .35) * (1 - .0)
    f = center - Mt[:3, 3]; f /= np.linalg.norm(f); back = -f; right = np.cross(np.array([0, 0, 1.0]), back); right /= np.linalg.norm(right); Mt[:3, 0] = right; Mt[:3, 1] = np.cross(back, right); Mt[:3, 2] = back
    base = st.reproject(Mt)
    HOLD = {'SCR_P1': ('s1', S[0]['agent'][1]), 'SCR_TV1': ('s2', S[1]['agent'][1]), 'SCR_P3': ('s3', S[2]['agent'][1]), 'SCR_TV0': ('s4', S[3]['agent'][1]), 'SCR_P5a': ('s5a', S[4]['agent'][1]), 'SCR_P5b': ('s5b', S[4]['agent'][1]), 'SCR_P5c': ('s5c', S[4]['agent'][1]), 'SCR_TV2': ('s6', S[5]['agent'][1])}
    items = []
    for d, (mode, th) in HOLD.items():
        if d in st.j['screens']: items.append((d, ui(mode, th)))
    if 'SCR_P2' in st.j['screens']: items.append(('SCR_P2', dark_phone(t, 1e9)))
    return Image.fromarray(np.clip(paint_screens(base, st, Mt, items), 0, 255).astype(np.uint8))

def act1(t): return ui('act1', t)

def whip(a, b, p):
    """From picture a to picture b by a fast pan: a goes out to the left, b comes in from the right, both streaked by the speed."""
    W = OW; p = ease(p); xa = -p * W * 1.05; xb = (1 - p) * W * 1.05; amp = math.sin(math.pi * p) ** .8 * 150
    out = np.zeros((OH, OW, 3), np.float32); wsum = np.zeros((OH, OW, 1), np.float32); N = 11
    A = np.asarray(a, np.float32); B = np.asarray(b, np.float32)
    for k in range(N):
        d = (k / (N - 1) - .5) * amp
        for img, x in ((A, xa), (B, xb)):
            sh = int(round(x + d)); v = np.zeros_like(img); wv = np.zeros((OH, OW, 1), np.float32)
            if sh >= 0: v[:, sh:] = img[:, :OW - sh] if sh < OW else 0; wv[:, sh:] = 1 if sh < OW else 0
            else: v[:, :OW + sh] = img[:, -sh:] if -sh < OW else 0; wv[:, :OW + sh] = 1 if -sh < OW else 0
            out += v; wsum += wv
    return Image.fromarray(np.clip(out / np.maximum(wsum, 1), 0, 255).astype(np.uint8))

# ---------------------------------------------------------------------------------------------------------------- the rules: a digital tear, then a glass break
def glitch(a, b, u):
    if u <= 0: return a
    if u >= 1: return b
    n = np.asarray(a, float); m = np.asarray(b, float); rng = np.random.default_rng(int(u * 1000))
    mix = n.copy()
    for _ in range(14):
        y = int(rng.random() * OH); h = int(8 + rng.random() * 70); dx = int((rng.random() - .5) * 240 * (1 - u))
        src = m if rng.random() < u * 1.3 else n
        mix[y:y + h] = np.roll(src[y:y + h], dx, axis=1)
    mix[..., 0] = np.roll(mix[..., 0], int(18 * (1 - u)), axis=1); mix[..., 2] = np.roll(mix[..., 2], -int(18 * (1 - u)), axis=1)
    return Image.fromarray(np.clip(mix, 0, 255).astype(np.uint8))

def shatter(tex, bg, u):
    W, H = OW, OH; gx, gy = 20, 11; cw, ch = W / gx, H / gy
    rng = np.random.default_rng(7)
    jit = {(i, j): ((rng.random() - .5) * cw * .7, (rng.random() - .5) * ch * .7) for i in range(gx + 1) for j in range(gy + 1)}
    pt = lambda i, j: (i * cw + (0 if i in (0, gx) else jit[(i, j)][0]), j * ch + (0 if j in (0, gy) else jit[(i, j)][1]))
    canvas = bg.convert('RGBA'); hit = (W * .5, H * .5); tris = []
    for i in range(gx):
        for j in range(gy):
            a, b, c, d = pt(i, j), pt(i + 1, j), pt(i + 1, j + 1), pt(i, j + 1); tris += [(a, b, c), (a, c, d)]
    cen = lambda tr: ((tr[0][0] + tr[1][0] + tr[2][0]) / 3, (tr[0][1] + tr[1][1] + tr[2][1]) / 3)
    for k in sorted(range(len(tris)), key=lambda k: -math.dist(cen(tris[k]), hit)):
        tr = tris[k]; cx, cy = cen(tr); dist = math.dist((cx, cy), hit)
        v = max(0.0, u - dist / 2200.0); r = np.random.default_rng(k)
        ang = math.atan2(cy - hit[1], cx - hit[0]) + (r.random() - .5) * .5
        speed = 380 + 900 * r.random() * (1 + 400 / (dist + 200))
        dx = math.cos(ang) * speed * v; dy = math.sin(ang) * speed * v + 900 * v * v
        rot = (r.random() - .5) * 420 * v; sc = max(.2, 1 - .25 * v); alpha = max(0.0, 1 - max(0.0, v - .35) / .9)
        if alpha <= 0: continue
        xs = [p[0] for p in tr]; ys = [p[1] for p in tr]
        x0, y0, x1, y1 = int(max(0, min(xs) - 2)), int(max(0, min(ys) - 2)), int(min(W, max(xs) + 3)), int(min(H, max(ys) + 3))
        crop = tex.crop((x0, y0, x1, y1)).convert('RGBA'); m = Image.new('L', crop.size, 0)
        ImageDraw.Draw(m).polygon([(p[0] - x0, p[1] - y0) for p in tr], fill=int(255 * alpha)); crop.putalpha(m)
        if v > 0:
            crop = crop.rotate(rot, expand=True, resample=Image.BILINEAR)
            if sc != 1: crop = crop.resize((max(2, int(crop.width * sc)), max(2, int(crop.height * sc))), Image.BILINEAR)
        px = int(cx + dx - crop.width / 2); py = int(cy + dy - crop.height / 2)
        if px > -crop.width and py > -crop.height and px < W and py < H: canvas.alpha_composite(crop, (px, py))
    return canvas.convert('RGB')


# ---------------------------------------------------------------------------------------------------------------- the whole film
WH = .5                                                   # the whip lasts this long; it starts a quarter of a second before a station begins
def whip_index(t):
    for i in range(1, len(S) + 1):
        w0 = S[i - 1]['s0'] - .25
        if w0 <= t < w0 + WH: return i
    return 0

def frame_at(t):
    e6 = A3['rules'][0]
    if t < e6:
        i = whip_index(t)
        if i:
            w0 = S[i - 1]['s0'] - .25
            a = act1(S[0]['s0'] - .3) if i == 1 else station_frame(i - 1, t)
            return whip(a, station_frame(i, t), ramp(t, w0, w0 + WH))
        done = [j for j in range(1, len(S) + 1) if S[j - 1]['s0'] - .25 + WH <= t]
        return station_frame(done[-1], t) if done else act1(t)
    if t < A3['shatter']:
        return glitch(station_frame(6, min(t, S[-1]['out'][1])), ui('act3a', t), ramp(t, e6, e6 + .35))
    u = t - A3['shatter']; uni = wide_frame(t)
    img = shatter(ui('act3a', A3['shatter']), uni, u) if u < 2.2 else uni
    f = ramp(u, 0, .12) * (1 - ramp(u, .12, .45))
    if f > 0: img = Image.blend(img, Image.new('RGB', (OW, OH), (255, 255, 255)), f * .8)
    if t >= A3['logo'][0] - .1: img = Image.alpha_composite(img.convert('RGBA'), ui('logo', t, 'png', True)).convert('RGB')
    return img

def with_overlay(img, t):
    for i in range(1, len(S) + 1):
        t0 = V['n_s%d' % i]
        if t0 - .25 <= t <= t0 + 7:
            try: img = Image.alpha_composite(img.convert('RGBA'), ui('ov', t, 'png', True)).convert('RGB')
            except Exception: pass
            break
    return img

def work(args):
    a, b = args; os.makedirs(OUT, exist_ok=True)
    for i in range(a, b):
        t = i / FPS; with_overlay(frame_at(t), t).save(os.path.join(OUT, '%05d.jpg' % i), quality=95)
    return b

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--from', dest='a', type=int, default=0); ap.add_argument('--to', dest='b', type=int, default=int(TL['total'] * FPS)); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--check', default='', help='seconds, comma separated: writes OUT/chk_<t>.jpg')
    o = ap.parse_args()
    if o.check:
        os.makedirs(OUT, exist_ok=True)
        for t in map(float, o.check.split(',')): with_overlay(frame_at(t), t).save(os.path.join(OUT, 'chk_%s.jpg' % t), quality=92)
        sys.exit(0)
    from multiprocessing import Pool
    with Pool(o.workers) as p:
        for done in p.imap(work, [(i, min(o.b, i + 24)) for i in range(o.a, o.b, 24)]): print('frames up to', done, flush=True)
