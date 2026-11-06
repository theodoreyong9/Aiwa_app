"""Film 10, the compositor: lays the picture of each screen on the screen of the still of the room (Cycles), frame by frame, and pulls the camera back from screen to screen.

The levels (a level = a room with its screens):  L0 the night room (television 0)  ->  L1 the desk (phone 1)  ->  L2 the living room (television 1 and phone 2)  ->  L3 the loft (television 2)  ->  L4 the phone 3 in the city night.
A television shows the frame of the level before it (the exact recursion: the view ends where the screen fills the picture, so the two frames are the same one); a phone shows what the application shows (frames of ui10.html), and the first picture of a phone is the frame before it, letterboxed.
Usage:  python3 compose10.py --from 0 --to 2640 [--workers 4] [--dev]      (dev: 960x540 previews of /tmp/os10/pv instead of the stills)
"""
import argparse, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(HERE, 'timeline10.json')))
FPS, OW, OH = TL['fps'], TL['width'], TL['height']
ST = os.environ.get('ST', '/tmp/os10/st'); UI = os.environ.get('UI', '/tmp/os10/ui'); OUT = os.environ.get('OUT', '/tmp/os10/out'); BG = os.environ.get('BG', '/tmp/os10/bgframes')
SW, SH = 2880, 1620                        # the size of the stills (the previews are scaled up to it)
FRAME_RECT_P3 = json.load(open(os.environ.get('P3RECT', '/tmp/os10/p3rect.json'))) if os.path.exists(os.environ.get('P3RECT', '/tmp/os10/p3rect.json')) else [43.2, 851.7, 993.7, 558.9]


# ---------------------------------------------------------------------------------------------------------------- geometry
def homog(src, dst):
    """3x3 matrix sending the four points src to the four points dst."""
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    h = np.linalg.solve(np.array(A, float), np.array(b, float))
    return np.append(h, 1).reshape(3, 3)

def apply(H, pts):
    out = []
    for x, y in pts:
        p = H @ np.array([x, y, 1.0]); out.append((p[0] / p[2], p[1] / p[2]))
    return out

def coeffs_inv(H):
    """PIL wants, for each output pixel, where to read in the input: the inverse matrix."""
    Hi = np.linalg.inv(H); Hi = Hi / Hi[2, 2]
    return tuple(Hi.flatten()[:8])

def warp(img, H, size, resample=Image.BICUBIC):
    return img.transform(size, Image.PERSPECTIVE, coeffs_inv(H), resample)

def area_scale(q):
    return math.sqrt(abs(0.5 * sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4))))

def smooth(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)

def ease(x):
    x = max(0.0, min(1.0, x)); return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2

def ramp(t, a, b):
    return max(0.0, min(1.0, (t - a) / (b - a)))

def lerp_q(a, b, s):
    return [(a[i][0] + (b[i][0] - a[i][0]) * s, a[i][1] + (b[i][1] - a[i][1]) * s) for i in range(4)]

def zoom_lerp(a, b, s):
    """Even zoom: the width of the view changes by the same ratio at every step (a straight line of the corners would rush at the start)."""
    r = area_scale(b) / max(1e-6, area_scale(a))
    s2 = s if abs(r - 1) < 1e-3 else (r ** s - 1) / (r - 1)
    return lerp_q(a, b, s2)


# ---------------------------------------------------------------------------------------------------------------- the stills
_cache = {}
def still(tag, mask=False):
    key = (tag, mask)
    if key in _cache: return _cache[key]
    p = os.path.join(ST, tag + ('_mask' if mask else '') + '.png')
    im = Image.open(p).convert('L' if mask else 'RGB')
    if im.size != (SW, SH): im = im.resize((SW, SH), Image.LANCZOS)
    if len(_cache) > 12: _cache.pop(next(iter(_cache)))
    _cache[key] = im; return im

def screens(tag):
    j = json.load(open(os.path.join(ST, tag + '.json'))); sx = SW / j['width']
    return {n: [(x * sx, y * sx) for x, y in q] for n, q in j['screens'].items()}

_ui_range = {}
def ui(mode, t):
    """The frame of the screens page `mode` at time t (a picture of the folder UI/<mode>, named by the number of the frame; the nearest one is taken at the ends)."""
    d = os.path.join(UI, mode)
    if mode not in _ui_range:
        n = sorted(int(f[:5]) for f in os.listdir(d) if f.endswith('.jpg')); _ui_range[mode] = (n[0], n[-1])
    lo, hi = _ui_range[mode]; i = max(lo, min(hi, int(round(t * FPS))))
    return Image.open(os.path.join(d, '%05d.jpg' % i)).convert('RGB')


# ---------------------------------------------------------------------------------------------------------------- the content of a phone (1080 x 2400)
PW, PH = 1080, 2400
def letterbox(frame, y0=None):
    c = Image.new('RGB', (PW, PH), (16, 19, 46)); f = frame.resize((PW, 607), Image.LANCZOS)
    c.paste(f, (0, (PH - 607) // 2 if y0 is None else y0)); return c

def p0_screen(t):
    """The phone of the night room: dark, then it wakes (a soft light and a listening mark)."""
    c = Image.new('RGB', (PW, PH), (3, 4, 10)); a = smooth(ramp(t, TL['voice']['wake'], TL['voice']['wake'] + .7))
    if a > 0:
        g = Image.new('L', (PW, PH), 0); d = ImageDraw.Draw(g); r = 260 + 22 * math.sin(t * 5)
        d.ellipse((540 - r, 1100 - r, 540 + r, 1100 + r), fill=255); g = g.filter(ImageFilter.GaussianBlur(120))
        col = Image.new('RGB', (PW, PH), (110, 98, 230)); c = Image.composite(col, c, g.point(lambda v: int(v * a * .9)))
        d2 = ImageDraw.Draw(c); d2.ellipse((540 - 40, 1100 - 40, 540 + 40, 1100 + 40), fill=(200, 210, 255))
    return c


# ---------------------------------------------------------------------------------------------------------------- the levels
def Q_views(level, quads, t=None):
    """The views of a level: name -> four corners in still pixels."""
    W, H = SW, SH; full = [(0, 0), (W, 0), (W, H), (0, H)]; v = {'full': full}
    for name, q in quads.items():
        v['screen:' + name] = q
    return v

def phone_views(q, video_rect):
    """For a phone: 'video' (a 16:9 rectangle of its screen), 'native' (its whole height filling the picture, the sides left to the room)."""
    Hs = homog([(0, 0), (PW, 0), (PW, PH), (0, PH)], q)
    x0, y0, w, h = video_rect
    video = apply(Hs, [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)])
    aspw = PH * OW / OH; nx0 = PW / 2 - aspw / 2
    native = apply(Hs, [(nx0, 0), (nx0 + aspw, 0), (nx0 + aspw, PH), (nx0, PH)])
    return Hs, {'video': video, 'native': native}

def path_quad(keys, t, views):
    """keys: [(time, viewname)...] ; between two keys the view changes with a cubic ease and an even zoom; before the first and after the last it holds."""
    if t <= keys[0][0]: return views[keys[0][1]]
    for (t0, n0), (t1, n1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return views[n0] if n0 == n1 else zoom_lerp(views[n0], views[n1], ease((t - t0) / (t1 - t0)))
    return views[keys[-1][1]]

def jitter(q, t):
    """A hand: a very small drift that fades out when the view is close (so that the close views meet the frame before them exactly)."""
    k = max(0.0, min(1.0, (area_scale(q) / SW - .55) / .45))
    if k <= 0: return q
    dx = k * (3.2 * math.sin(t * 1.3) + 1.6 * math.sin(t * 3.1 + 1)); dy = k * (2.4 * math.sin(t * 1.1 + 2) + 1.2 * math.sin(t * 2.7))
    return [(x + dx, y + dy) for x, y in q]

def paint(base, quad, items, size=(OW, OH)):
    """base: still (PIL, still size); quad: the view; items: [(content image, content->still matrix or None for a rect that fills the screen quad, screen quad, screen mask still)].
    Returns the frame."""
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
        S = np.diag([f, f, 1.0]); Hf = Hcs @ np.linalg.inv(S)
        pad = np.asarray(warp(small, Hf, size), float)
        m = np.asarray(warp(mask.convert('L'), Hc, size, Image.BILINEAR), float) / 255.0
        poly = Image.new('L', size, 0); ImageDraw.Draw(poly).polygon(apply(Hc, sq), fill=255)
        poly = np.asarray(poly.filter(ImageFilter.MaxFilter(5)), float) / 255.0
        m = np.minimum(m, poly)[..., None]
        out = out * (1 - m) + pad * m
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def rect_matrix(w, h, q):
    return homog([(0, 0), (w, 0), (w, h), (0, h)], q)


# ---- L0: the night room
def L0(t):
    sc = screens('R0'); tv, p0 = sc['SCR_TV0'], sc['SCR_P0']
    k = smooth(ramp(t, *TL['R0']['tvOn']))
    base = Image.blend(still('R0_off'), still('R0'), k) if k > 0 else still('R0_off')
    mask = still('R0_mask')
    full = [(0, 0), (SW, 0), (SW, SH), (0, SH)]
    mid = zoom_lerp(full, tv, .62)
    q = path_quad([(TL['R0']['in'], 'full'), (TL['R0']['push'][1], 'mid'), (TL['R0']['zoom'][1], 'tv')], t, {'full': full, 'mid': mid, 'tv': tv})
    q = jitter(q, t)
    tvimg = ui('tv0', t)
    items = [(tvimg, rect_matrix(1920, 1080, tv), tv, mask), (p0_screen(t), rect_matrix(PW, PH, p0), p0, mask)]
    fr = paint(base, q, items)
    # the phone wakes: a halo around it
    a = smooth(ramp(t, TL['voice']['wake'], TL['voice']['wake'] + .8)) * (1 - .35 * smooth(ramp(t, 8.5, 9.5)))
    if a > 0:
        Hc = homog(q, [(0, 0), (OW, 0), (OW, OH), (0, OH)]); halo = Image.new('L', (OW, OH), 0)
        ImageDraw.Draw(halo).polygon(apply(Hc, p0), fill=255); halo = halo.filter(ImageFilter.GaussianBlur(max(6, area_scale(apply(Hc, p0)) * .5)))
        col = Image.new('RGB', (OW, OH), (90, 80, 200)); fr = Image.composite(Image.blend(fr, col, .5), fr, halo.point(lambda v: int(v * a * .55)))
    return fr


# ---- L1: the desk
def L1(t):
    sc = screens('R1'); q1 = sc['SCR_P1']; mask = still('R1_mask')
    Hs, pv = phone_views(q1, (0, (PH - 607) / 2, PW, 607))
    full = [(0, 0), (SW, 0), (SW, SH), (0, SH)]
    views = {'full': full, 'video': pv['video'], 'native': pv['native']}
    R = TL['R1']
    q = path_quad([(R['back'][0], 'video'), (R['back'][1], 'full'), (R['dive'][0], 'full'), (R['dive'][1], 'native'), (R['out'][0], 'native'), (R['out'][1], 'full')], t, views)
    q = jitter(q, t)
    prev = letterbox(render(0, min(t, R['back'][0])))
    a = smooth(ramp(t, R['handoff'][0] + .05, R['handoff'][1]))
    content = Image.blend(prev, ui('p1', t), a) if a < 1 else ui('p1', t)
    return paint(still('R1'), q, [(content, Hs, q1, mask)])


# ---- L2: the living room
BLUR = lambda im, r: im.filter(ImageFilter.GaussianBlur(r)) if r > .3 else im
def L2(t):
    R, P = TL['R2'], TL['P2']
    k = int(math.floor((t - R['pick'][0]) * FPS))
    anim = 0 <= k
    kk = max(0, min(35, k)) if anim else None
    tag = ('R2_%02d' % kk) if anim else 'R2'
    base = still(tag); mask = still(tag + '_mask'); sc = screens(tag)
    # a smooth start of the pick (the first frames of the animation are cross-faded with the rest picture)
    if anim and k < 3: base = Image.blend(still('R2'), base, (k + 1) / 4)
    tv, p2 = sc['SCR_TV1'], sc['SCR_P2']
    sc35 = screens('R2_35'); Hs, pv = phone_views(sc35['SCR_P2'], (0, (PH - 607) / 2, PW, 607))
    full = [(0, 0), (SW, 0), (SW, SH), (0, SH)]
    views = {'tv': screens('R2')['SCR_TV1'], 'full': full, 'native': pv['native']}
    q = path_quad([(R['out'][0], 'tv'), (R['out'][1], 'full'), (R['toNative'][0], 'full'), (R['toNative'][1], 'native'), (P['out'][0], 'native'), (P['out'][1], 'full')], t, views)
    q = jitter(q, t)
    tvc = render(1, min(t, TL['R1']['out'][1]))
    blur = 12 * (kk / 35.0) if anim else 0
    tvc = BLUR(tvc, blur)
    items = [(tvc, rect_matrix(1920, 1080, tv), tv, mask), (ui('p2', t), rect_matrix(PW, PH, p2), p2, mask)]
    return paint(base, q, items)


# ---- L3: the loft
def L3(t):
    sc = screens('R3'); tv = sc['SCR_TV2']; R = TL['R3']
    full = [(0, 0), (SW, 0), (SW, SH), (0, SH)]
    q = path_quad([(R['out'][0], 'tv'), (R['out'][1], 'full')], t, {'tv': tv, 'full': full}); q = jitter(q, t)
    tvc = render(2, min(t, TL['P2']['out'][1]))
    return paint(still('R3'), q, [(tvc, rect_matrix(1920, 1080, tv), tv, still('R3_mask'))])


# ---- L4: the phone in the city night
def L4(t):
    sc = screens('R4'); q4 = sc['SCR_P3']; P = TL['P3']
    Hs, pv = phone_views(q4, FRAME_RECT_P3)
    full = [(0, 0), (SW, 0), (SW, SH), (0, SH)]
    views = {'full': full, 'video': pv['video'], 'native': pv['native']}
    q = path_quad([(TL['R3']['out'][1], 'video'), (P['toNative'][0], 'video'), (P['toNative'][1], 'native'), (P['back'][0], 'native'), (P['back'][1], 'full'), (P['dive'][0], 'full'), (P['dive'][1], 'native'), (P['stop'], 'native')], t, views)
    q = jitter(q, t)
    return paint(still('R4'), q, [(ui('p3', t), Hs, q4, still('R4_mask'))])


LEVELS = [L0, L1, L2, L3, L4]
_memo = {}
def render(level, t):
    key = (level, round(t * FPS))
    if key in _memo: return _memo[key]
    im = LEVELS[level](t)
    if len(_memo) > 40: _memo.pop(next(iter(_memo)))
    _memo[key] = im; return im


# ---------------------------------------------------------------------------------------------------------------- the whole film
def frame_at(t):
    if t < TL['title'][1]: return ui('title', t)
    if t < TL['R1']['back'][0]: return render(0, t)
    if t < TL['R2']['out'][0]: return render(1, t)
    if t < TL['R3']['out'][0]: return render(2, t)
    if t < TL['R3']['out'][1]: return render(3, t)
    if t <= TL['end']['black'][0]: return render(4, t)
    if t < TL['end']['card'][0]: return Image.new('RGB', (OW, OH), (2, 3, 8))
    return ui('end', t)

def work(args):
    a, b = args
    os.makedirs(OUT, exist_ok=True); os.makedirs(BG, exist_ok=True)
    for i in range(a, b):
        t = i / FPS; fr = frame_at(t)
        fr.save(os.path.join(OUT, '%05d.jpg' % i), quality=95)
        if TL['R3']['out'][0] <= t <= TL['R3']['out'][1] + .05:        # the loft is the video seen in the profile of the last phone
            fr.save(os.path.join(BG, '%05d.jpg' % i), quality=95)
    return b

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--from', dest='a', type=int, default=0); ap.add_argument('--to', dest='b', type=int, default=int(TL['total'] * FPS)); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--levels', default='', help='comma list of levels to render alone (0..4) at the frames given, for a check')
    o = ap.parse_args()
    if o.levels:
        os.makedirs(OUT, exist_ok=True)
        for i in range(o.a, o.b, max(1, (o.b - o.a) // 6)):
            for L in map(int, o.levels.split(',')): render(L, i / FPS).save(os.path.join(OUT, 'chk_L%d_%05d.jpg' % (L, i)), quality=92)
        sys.exit(0)
    from multiprocessing import Pool
    step = 24; jobs = [(i, min(o.b, i + step)) for i in range(o.a, o.b, step)]
    with Pool(o.workers) as p:
        for done in p.imap(work, jobs): print('frames up to', done, flush=True)
