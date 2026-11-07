"""Film 11, the compositor. Six worlds, one inside the other: in each room a screen shows the world before it; the camera goes back from that screen, then dives into the screen of this world (where the voice asks and the screen does it), then goes back again, and the next room takes over.
Act 1 (the question) and act 3 (the rules, the break, the end) are pictures of the screens page, with a glass break written here.
Usage: python3 compose11.py --from 0 --to 3000 [--workers 4]      (UI frames: /tmp/os11/ui/<mode>/NNNNN.jpg, the stills: /tmp/os10/st, the output: /tmp/os11/out)"""
import argparse, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'timeline11.json')))
FPS, OW, OH = TL['fps'], TL['width'], TL['height']
ST = os.environ.get('ST', '/tmp/os10/st'); UI = os.environ.get('UI', '/tmp/os11/ui'); OUT = os.environ.get('OUT', '/tmp/os11/out')
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


# ---------------------------------------------------------------------------------------------------------------- act 1
def act1(t): return ui('act1', t)


# ---------------------------------------------------------------------------------------------------------------- the six worlds
def prev_frame(i, t):
    """The picture that the screen of world i shows when the camera is in front of it: the last picture of the world before (held)."""
    if i == 1: return act1(S[0]['s0'] + .35)
    return world(i - 1, min(t, S[i - 2]['out'][1]))

def fade_content(prev, now, t, hand):
    a = smooth(ramp(t, hand[0], hand[1]))
    if a <= 0: return prev
    if a >= 1: return now
    return Image.blend(prev, now, a)

_memo = {}
def world(i, t):
    k = (i, round(t * FPS))
    if k in _memo: return _memo[k]
    sc = S[i - 1]; env = sc['env']
    base = still(env); mask = still(env + '_mask'); scr = screens(env)
    back, dive, out, hand = sc['back'], sc['dive'], sc['out'], sc['hand']
    if env in ('R1', 'R4'):
        q1 = scr['SCR_P1' if env == 'R1' else 'SCR_P3']; Hs, pv = phone_views(q1)
        views = {'video': pv['video'], 'full': FULL, 'native': pv['native']}
        keys = [(back[0], 'video'), (back[1], 'full'), (dive[0], 'full'), (dive[1], 'native'), (out[0], 'native'), (out[1], 'full')]
        q = jitter(path_quad(keys, t, views), t)
        content = fade_content(letterbox(prev_frame(i, t)), ui('s%d' % i, t), t, hand)
        fr = paint(base, q, [(content, Hs, q1, mask)])
    elif env in ('R2', 'R0', 'R3'):
        tvn = {'R2': 'SCR_TV1', 'R0': 'SCR_TV0', 'R3': 'SCR_TV2'}[env]; tv = scr[tvn]
        views = {'tv': tv, 'full': FULL}
        keys = [(back[0], 'tv'), (back[1], 'full'), (dive[0], 'full'), (dive[1], 'tv'), (out[0], 'tv'), (out[1], 'full')]
        q = jitter(path_quad(keys, t, views), t)
        content = fade_content(prev_frame(i, t), ui('s%d' % i, t), t, hand)
        items = [(content, rect_matrix(1920, 1080, tv), tv, mask)]
        extra = {'R2': 'SCR_P2', 'R0': 'SCR_P0'}.get(env)
        if extra: items.append((dark_phone(t, sc['cmd'][0]), rect_matrix(PW, PH, scr[extra]), scr[extra], mask))
        fr = paint(base, q, items)
    else:  # R5: three phones
        qa, qb, qc = scr['SCR_P5a'], scr['SCR_P5b'], scr['SCR_P5c']; Hs, pv = phone_views(qa)
        views = {'video': pv['video'], 'full': FULL, 'native': pv['native'], 'trio': bbox_view([qa, qb, qc])}
        ag = sc['agent']
        keys = [(back[0], 'video'), (back[1], 'full'), (dive[0], 'full'), (dive[1], 'native'), (ag[0] - .3, 'native'), (ag[0] + 1.3, 'trio'), (out[0], 'trio'), (out[1], 'full')]
        q = jitter(path_quad(keys, t, views), t)
        content = fade_content(letterbox(prev_frame(i, t)), ui('s5a', t), t, hand)
        items = [(content, Hs, qa, mask), (ui('s5b', t), rect_matrix(PW, PH, qb), qb, mask), (ui('s5c', t), rect_matrix(PW, PH, qc), qc, mask)]
        fr = paint(base, q, items)
    if len(_memo) > 30: _memo.pop(next(iter(_memo)))
    _memo[k] = fr; return fr


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
def frame_at(t):
    if t < S[0]['s0']: return act1(t)
    for i in range(len(S), 0, -1):
        end = S[i]['s0'] if i < len(S) else S[-1]['out'][1]
        if S[i - 1]['s0'] <= t < end: return world(i, t)
    e6 = S[-1]['out'][1]
    if t < A3['shatter']:
        return glitch(world(6, e6 - 1.0 / FPS), ui('act3a', t), ramp(t, e6, e6 + .35))
    u = t - A3['shatter']; logo = ui('act3b', t)
    img = shatter(ui('act3a', A3['shatter']), logo, u) if u < 2.2 else logo
    f = ramp(u, 0, .12) * (1 - ramp(u, .12, .45))
    if f > 0: img = Image.blend(img, Image.new('RGB', (OW, OH), (255, 255, 255)), f * .8)
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
