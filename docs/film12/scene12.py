"""Film 12, the universe: six dioramas (one for each use) on a black mirror floor, path traced in Blender (Cycles), and a wide shot of the six together.
Each shot writes <out>/<S>.png (the picture, the screens lit by a flat colour), <S>_mask.png (white = the screens), <S>_depth.png (16 bits, distance along the axis over ZMAX) and <S>.json (camera, screens in pixels and in the world).
  /tmp/bpyenv/bin/python scene12.py -- --shot S1|S2|S3|S4|S5|S6|WIDE --out /tmp/os12/st --width 2880 --height 1620 --samples 64"""
import json, math, os, sys, time
import numpy as np
import bpy, bmesh, mathutils
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'skills', 'kit', 'video-kit', 'shots', 'blender'))
import kit
A = kit.args
SHOT, OUT = A('shot', 'S1'), A('out', '/tmp/os12/st')
W, H, SAMPLES = A('width', 3840, int), A('height', 2160, int), A('samples', 128, int)
VARIANT, FRAME, MASK = A('variant', 'on'), A('frame', -1, int), A('mask', 1, int)
ASSETS = A('assets', '/tmp/ph')
NFRAMES = 36                                   # the phone taken from the console: frames 0..35

def clamp(x, a=0.0, b=1.0): return min(b, max(a, x))
def sm(x): x = clamp(x); return x * x * (3 - 2 * x)
def sm5(x): x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10)
def mix(a, b, k): return a + (b - a) * k
def rnd(i): s = math.sin(i * 127.1 + 311.7) * 43758.5453; return s - math.floor(s)
def V(*a): return mathutils.Vector(a if len(a) == 3 else a[0])
def hexc(h, a=1.0): return kit.rgba(h, a)

S = kit.reset(width=W, height=H, samples=SAMPLES, fps=24)
S.cycles.use_adaptive_sampling = True; S.cycles.adaptive_threshold = 0.012; S.cycles.adaptive_min_samples = 24
S.cycles.denoiser = 'OPENIMAGEDENOISE'; S.cycles.use_denoising = True
S.cycles.max_bounces = 8; S.cycles.diffuse_bounces = 3; S.cycles.glossy_bounces = 4; S.cycles.transmission_bounces = 4; S.cycles.volume_bounces = 0
S.cycles.sample_clamp_indirect = 5.0; S.cycles.caustics_reflective = False; S.cycles.caustics_refractive = False
S.render.image_settings.file_format = 'PNG'; S.render.image_settings.color_depth = '16'
LOOKS = [l.identifier for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items]
S.view_settings.look = 'AgX - Base Contrast' if 'AgX - Base Contrast' in LOOKS else 'None'

def node_mat(name, base='#222228', rough=.5, metal=0.0, emit=None, es=0.0, coat=0.0, ior=1.45, alpha=1.0, spec=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = hexc(base) if isinstance(base, str) else base
    p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    p.inputs['Coat Weight'].default_value = coat; p.inputs['IOR'].default_value = ior; p.inputs['Alpha'].default_value = alpha
    if spec is not None: p.inputs['Specular IOR Level'].default_value = spec
    if emit is not None:
        p.inputs['Emission Color'].default_value = hexc(emit) if isinstance(emit, str) else emit; p.inputs['Emission Strength'].default_value = es
    return m

def emissive(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = hexc(color) if isinstance(color, str) else color; e.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], out.inputs['Surface'])
    return m

def add(obj, parent=None):
    if obj.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(obj)
    if parent: obj.parent = parent
    return obj

def box(name, size, loc, mat, bevel=0.0, seg=3):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=bevel, segments=seg, affect='EDGES')
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o.location = loc; o.data.materials.append(mat); add(o)
    for p in me.polygons: p.use_smooth = bevel > 0
    return o

def load_gltf(path, scale=1.0, loc=(0, 0, 0), yaw=0.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new('root', None); bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.scale = (scale,) * 3; root.rotation_euler = (0, 0, yaw); root.location = loc
    bpy.context.view_layer.update(); return root

def zrange(root):
    pts = [o.matrix_world @ V(c) for o in [root, *root.children_recursive] if o.type == 'MESH' for c in o.bound_box]
    return min(p.z for p in pts), max(p.z for p in pts)

def tame(root, mul=(.5, .46, .44)):
    """Darkens the colour texture of a model (a table in daylight becomes a table at night)."""
    for o in [root, *root.children_recursive]:
        if o.type != 'MESH': continue
        for sl in o.material_slots:
            nt = sl.material.node_tree; p = nt.nodes.get('Principled BSDF')
            if p is None: continue
            l = [l for l in nt.links if l.to_socket == p.inputs['Base Color']]
            if not l: continue
            src = l[0].from_socket; mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0; mx.inputs[7].default_value = (*mul, 1)
            nt.links.new(src, mx.inputs[6]); nt.links.new(mx.outputs[2], p.inputs['Base Color'])

def light(name, kind, loc, energy, color, size=.5, target=None, spot=0.9):
    l = bpy.data.lights.new(name, kind); l.energy = energy; l.color = hexc(color)[:3]
    if kind == 'AREA': l.size = size
    if kind == 'SPOT': l.spot_size = spot; l.spot_blend = .6; l.shadow_soft_size = size
    if kind == 'POINT': l.shadow_soft_size = size
    o = bpy.data.objects.new(name, l); o.location = loc; bpy.context.scene.collection.objects.link(o)
    if target is not None:
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return o

def empty(name, loc):
    o = bpy.data.objects.new(name, None); o.location = loc; bpy.context.scene.collection.objects.link(o); return o

def noise_bump(m, scale=40.0, strength=.05, detail=8):
    nt = m.node_tree; nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = detail
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = strength; nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])

# ------------------------------------------------------------------ the devices
SCREENS = {}                                     # name -> (object, mat)
def quad(name, w, h, mat, loc, rot=(0, 0, 0)):
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in ((-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2))]
    bm.faces.new(vs); me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); o.data.materials.append(mat); o.location = loc; o.rotation_euler = rot; add(o)
    for p in me.polygons: p.use_smooth = True
    return o

def screen_mat(name, glow, es, rough=.07):
    m = node_mat(name, '#000000', rough=rough, ior=1.5, spec=.5)
    p = m.node_tree.nodes['Principled BSDF']; p.inputs['Emission Color'].default_value = hexc(glow); p.inputs['Emission Strength'].default_value = es
    return m

PW, PH_, PD = .0745, .1625, .0085
SCR_W, SCR_H = .0695, .1545                       # the screen of the phone: its own picture ratio
def make_phone(name, loc, rot, glow='#31416f', es=1.1, body='#2b2d34', dark=False):
    """A phone: body of brushed metal, a glass front, a screen (a quad named SCR_<name>), a camera island on the back, side keys. Its front looks toward -Y."""
    ph = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(ph)
    pts = kit._rounded_rect(PW, PH_, .0105, seg=12)
    bm = bmesh.new(); f = bm.faces.new([bm.verts.new((x, -PD / 2, z)) for x, z in pts])
    if f.normal.y > 0: f.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[f]); mv = [v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, PD, 0), verts=mv); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=.0010, segments=4, affect='EDGES')
    me = bpy.data.meshes.new(name + 'body'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name + 'body', me); o.data.materials.append(node_mat(name + 'frame', body, rough=.32, metal=1.0)); add(o, ph)
    glass = quad(name + 'glass', PW - .0016, PH_ - .0016, node_mat(name + 'glass', '#010103', rough=.05, ior=1.5, spec=.5), (0, -PD / 2 - .00006, 0)); glass.parent = ph
    sc = quad('SCR_' + name, SCR_W, SCR_H, screen_mat(name + 'scr', '#000000' if dark else glow, 0 if dark else es), (0, -PD / 2 - .00022, 0)); sc.parent = ph
    box(name + 'isl', (.027, .0022, .037), (-.0, PD / 2 + .0009, PH_ / 2 - .028), node_mat(name + 'isl', '#101014', rough=.18, metal=.9), bevel=.0009).parent = ph
    for k in range(3):
        c = bpy.data.objects.new(name + 'lens', None); lens_m = node_mat(name + 'lensm', '#050508', rough=.05, metal=.2, coat=1.0)
        l = box(name + 'lens', (.0085, .0016, .0085), (-.006 + (k % 2) * .012, PD / 2 + .0021, PH_ / 2 - .019 - (k // 2) * .0115 - .002), lens_m, bevel=.003, seg=2); l.parent = ph
    box(name + 'key', (.0009, .0034, .014), (PW / 2 + .00035, 0, .018), node_mat(name + 'key', body, rough=.3, metal=1.0), bevel=.0003).parent = ph
    box(name + 'key2', (.0009, .0034, .022), (PW / 2 + .00035, 0, -.012), node_mat(name + 'key2', body, rough=.3, metal=1.0), bevel=.0003).parent = ph
    ph.location = loc; ph.rotation_euler = rot
    SCREENS['SCR_' + name] = sc
    return ph, sc

def make_tv(name, center, width=1.3, glow='#31416f', es=1.5, yaw=0.0, stand=True, floor_z=None):
    """A thin television: black glass in a slim frame on a foot. Its front looks toward -Y; centre of the screen at `center`."""
    h = width * 9 / 16
    body = node_mat(name + 'body', '#07070a', rough=.3, metal=.8)
    root = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(root)
    b = box(name + 'frame', (width + .03, .034, h + .03), (0, .02, 0), body, bevel=.008); b.parent = root
    sc = quad('SCR_' + name, width, h, screen_mat(name + 'scr', glow, es, rough=.09), (0, .0025, 0)); sc.parent = root
    foot_z = (floor_z - center[2]) if floor_z is not None else -h / 2 - .1
    if stand:
        box(name + 'foot', (.42, .16, .018), (0, .04, foot_z + .009), body, bevel=.004).parent = root
        box(name + 'neck', (.1, .03, h / 2 + .03 + (-foot_z) - h / 2 - .018 - .0), (0, .035, (foot_z + .018 + (-h / 2 - .01)) / 2), body, bevel=.004).parent = root
    root.location = center; root.rotation_euler = (0, 0, yaw)
    SCREENS['SCR_' + name] = sc
    return root, sc

# ------------------------------------------------------------------ camera
def make_camera(loc, target, lens=50, fstop=2.2, focus=None, shift=(0, 0), roll=0.0):
    cd = bpy.data.cameras.new('cam'); cd.lens = lens; cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36; cd.clip_start = .01; cd.clip_end = 80
    cd.shift_x, cd.shift_y = shift
    cam = bpy.data.objects.new('cam', cd); bpy.context.scene.collection.objects.link(cam); S.camera = cam; cam.location = loc
    tgt = empty('camtarget', target)
    c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    f = focus if focus is not None else tgt
    cd.dof.use_dof = fstop is not None; cd.dof.focus_object = f; cd.dof.aperture_fstop = fstop or 8
    return cam, tgt

def corners_px(obj, cam):
    """The four corners of a screen in pixels of the picture: top-left, top-right, bottom-right, bottom-left (as the picture shows them)."""
    bpy.context.view_layer.update()
    w, h = obj.dimensions.x, obj.dimensions.z
    pts = []
    for p in ((-w / 2, 0, h / 2), (w / 2, 0, h / 2), (w / 2, 0, -h / 2), (-w / 2, 0, -h / 2)):
        co = world_to_camera_view(S, cam, obj.matrix_world @ V(p)); pts.append((co.x * W, (1 - co.y) * H))
    return pts

# ------------------------------------------------------------------ the shots
def wood_floor(z, size=14, tone='#1b130e'):
    m = node_mat('floor', tone, rough=.32, coat=.35); noise_bump(m, 6.0, .06)
    nt = m.node_tree; tc = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.inputs['Scale'].default_value = 7.0; wv.inputs['Distortion'].default_value = 4.0; wv.inputs['Detail'].default_value = 3
    rmp = nt.nodes.new('ShaderNodeMapRange'); rmp.inputs['To Min'].default_value = .18; rmp.inputs['To Max'].default_value = .55
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector']); nt.links.new(wv.outputs['Fac'], rmp.inputs['Value']); nt.links.new(rmp.outputs['Result'], nt.nodes['Principled BSDF'].inputs['Roughness'])
    return box('floor', (size, size, .05), (0, 2, z - .025), m)

def wall(y, tone='#1a1c23', width=14, height=5, z0=-.5, rough=.85):
    m = node_mat('wall', tone, rough=rough); noise_bump(m, 80.0, .02, 6)
    return box('wall', (width, .05, height), (0, y, z0 + height / 2), m)

def desk_scene(top=.74):
    """The wooden table of the library: the top of the table at height `top` above the floor (z = 0)."""
    desk = load_gltf(f'{ASSETS}/ph-WoodenTable_01/WoodenTable_01_2k.gltf', 1.0, (0, 0, 0))
    tame(desk, (.36, .33, .32))
    z0, z1 = zrange(desk); desk.location.z = top - z1
    bpy.context.view_layer.update(); return desk

TOPZ = .74
NIGHT = '#010208'

# ------------------------------------------------------------------ the stations (a diorama = a set of things standing on the black mirror floor; the local frame: floor z=0, the front looks toward -Y)
def st_S1():
    """Sessions: a phone lying on a wooden desk, a lamp, a notebook, a pair of glasses."""
    desk_scene(TOPZ)
    nb = load_gltf(f'{ASSETS}/ph-binder_notebook/binder_notebook_2k.gltf', 1.0, (.16, .12, TOPZ), .35); nb.location.z = TOPZ - zrange(nb)[0]
    lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (-.34, .22, TOPZ), .7); lamp.location.z = TOPZ - zrange(lamp)[0]
    spec = load_gltf(f'{ASSETS}/ph-round_spectacles/round_spectacles_2k.gltf', 1.0, (.27, -.1, TOPZ), -.5); spec.location.z = TOPZ - zrange(spec)[0]
    ph, sc = make_phone('P1', (0.0, 0.0, TOPZ + PD / 2 + .0004), (-math.pi / 2, 0, math.radians(8)), glow='#3a4c80', es=1.3)
    aim = empty('aim', (0, 0, TOPZ))
    light('lampL', 'POINT', (-.34, .22, TOPZ + .36), 26, '#ff9a4a', .03)
    light('key', 'SPOT', (-.5, -.2, TOPZ + .8), 70, '#ffc58a', .1, aim, 1.0)
    light('rim', 'AREA', (.9, .5, TOPZ + .35), 70, '#6c8cff', .8, aim)
    light('fill', 'AREA', (0, -.9, TOPZ + .7), 9, '#9aa8ff', 1.2, aim)
    return {'cam': (.3, -.62, TOPZ + .46), 'look': (0, .02, TOPZ + .01), 'lens': 36, 'fstop': 2.8, 'focus': sc, 'device': 'SCR_P1', 'k': 2.4, 'accent': '#ff9a4a'}

def st_S2():
    """Campaign: a television on a console, a plant, a lamp and a phone beside the television."""
    console = box('console', (2.4, .42, .42), (0, 0, .21), node_mat('console', '#1a1612', rough=.38, coat=.2), bevel=.012)
    TOP = .42
    tv, tvs = make_tv('TV1', (0, .04, TOP + .1 + .395), 1.4, glow='#aab6dc', es=1.5, floor_z=TOP)
    plant = load_gltf(f'{ASSETS}/ph-potted_plant_04/potted_plant_04_2k.gltf', 2.0, (-1.12, 0, TOP), 0.3); plant.location.z = TOP - zrange(plant)[0]
    lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (1.12, 0, TOP), .9); lamp.location.z = TOP - zrange(lamp)[0]
    ph, sc = make_phone('P2', (-.62, -.2, TOP + PD / 2 + .0004), (-math.pi / 2, 0, math.radians(16)), glow='#4a5a8a', es=1.2)
    aim = empty('aim', (0, -.1, TOP + .3))
    light('lampL', 'POINT', (1.1, -.1, TOP + .45), 90, '#ff9a4a', .06)
    light('key', 'AREA', (1.4, -1.8, 2.2), 260, '#ffd9b0', 1.4, aim)
    light('cool', 'AREA', (-2.2, -1.6, 1.4), 70, '#6f86ff', 1.5, aim)
    return {'cam': (0.0, -3.4, 1.12), 'look': (0, 0, .85), 'lens': 32, 'fstop': 2.6, 'focus': tvs, 'device': 'SCR_TV1', 'k': 1.6, 'accent': '#6f86ff'}

def st_S3():
    """Interface: a smartphone propped on a notebook on a desk; behind it, out of focus, the lights of a city."""
    desk_scene(TOPZ)
    nb = load_gltf(f'{ASSETS}/ph-binder_notebook/binder_notebook_2k.gltf', 1.0, (.02, .16, TOPZ), .2); nb.location.z = TOPZ - zrange(nb)[0]
    bpy.context.view_layer.update()
    spec = load_gltf(f'{ASSETS}/ph-round_spectacles/round_spectacles_2k.gltf', 1.0, (-.26, -.04, TOPZ), .9); spec.location.z = TOPZ - zrange(spec)[0]
    lean = math.radians(-21)
    ph, sc = make_phone('P3', (.0, -.0, TOPZ + PH_ / 2 * math.cos(abs(lean)) + .003), (lean, 0, math.radians(-7)), glow='#4b5b8c', es=1.4)
    # the city: a hundred small lights on a far plane (they become the bokeh)
    for i in range(160):
        x = (rnd(i) - .5) * 5.0; z = TOPZ - .1 + rnd(i + 31) * 1.7; c = ['#ffb36b', '#ff7aa0', '#7aa8ff', '#9ff0ff', '#ffe29a'][int(rnd(i + 7) * 5)]
        s = .018 + rnd(i + 3) * .04
        box('city%d' % i, (s, s, s), (x, 2.6 + rnd(i + 5) * 1.2, z), emissive('cm%d' % i, c, 18 + 30 * rnd(i + 9)))
    aim = empty('aim', (0, 0, TOPZ + .07))
    light('key', 'AREA', (-.5, -.3, TOPZ + .5), 36, '#ffc89a', .5, aim)
    light('rim', 'AREA', (.7, .5, TOPZ + .3), 80, '#7f9cff', .8, aim)
    return {'cam': (.13, -.62, TOPZ + .12), 'look': (0, 0, TOPZ + .085), 'lens': 60, 'fstop': 2.0, 'focus': sc, 'device': 'SCR_P3', 'k': 2.4, 'accent': '#7f9cff'}

def st_S4():
    """Discovery: a large television on a low stand between two light strips (violet and teal), a plant, a lamp."""
    cab = box('cabinet', (2.0, .46, .5), (0, 0, .25), node_mat('cab', '#0f1117', rough=.34, coat=.25), bevel=.012)
    tv, tvs = make_tv('TV0', (0, .02, .5 + .1 + .37), 1.3, glow='#34508f', es=1.8, floor_z=.5)
    plant = load_gltf(f'{ASSETS}/ph-potted_plant_04/potted_plant_04_2k.gltf', 1.7, (1.15, 0, .5), 0.0); plant.location.z = .5 - zrange(plant)[0]
    lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (-1.05, 0, .5), 2.0); lamp.location.z = .5 - zrange(lamp)[0]
    box('strip', (.12, .02, 2.6), (-1.55, .5, 1.3), emissive('strip', '#6a4cff', 7.0))
    box('strip2', (.12, .02, 2.6), (1.55, .5, 1.3), emissive('strip2', '#1ad0a8', 5.0))
    aim = empty('aim', (0, 0, .8))
    light('lampL', 'POINT', (-1.0, -.1, .85), 40, '#ff9f55', .03)
    light('rim', 'AREA', (-1.8, -1.2, 1.6), 40, '#5c6cff', 1.2, aim)
    light('fillS4', 'AREA', (.9, -2.0, 1.4), 30, '#8aa0ff', 1.2, aim)
    return {'cam': (0.0, -3.4, 1.15), 'look': (0, 0, .95), 'lens': 32, 'fstop': 2.6, 'focus': tvs, 'device': 'SCR_TV0', 'k': 1.6, 'accent': '#6a4cff'}

def st_S5():
    """Adaptation: three smartphones standing on a workshop table (the owner's, a friend's, a recruiter's)."""
    desk_scene(TOPZ)
    nb = load_gltf(f'{ASSETS}/ph-binder_notebook/binder_notebook_2k.gltf', 1.0, (.0, .2, TOPZ), .1); nb.location.z = TOPZ - zrange(nb)[0]
    lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (.42, .26, TOPZ), 2.4); lamp.location.z = TOPZ - zrange(lamp)[0]
    lean = math.radians(-19); first = None
    for n, x, yaw, gl in (('P5a', -.19, 9, '#4b5b8c'), ('P5b', .0, 0, '#3f6f7a'), ('P5c', .19, -9, '#6a4b8c')):
        ph, sc = make_phone(n, (x, -.02, TOPZ + PH_ / 2 * math.cos(abs(lean)) + .003), (lean, 0, math.radians(yaw)), glow=gl, es=1.3); first = first or sc
    aim = empty('aim', (0, 0, TOPZ + .08))
    light('key', 'AREA', (-.6, -.3, TOPZ + .5), 40, '#ffc89a', .5, aim)
    light('rim', 'AREA', (.8, .5, TOPZ + .35), 80, '#7f9cff', .9, aim)
    light('lampL', 'POINT', (.42, .26, TOPZ + .3), 30, '#ff9a4a', .03)
    return {'cam': (.04, -.92, TOPZ + .17), 'look': (0, 0, TOPZ + .09), 'lens': 42, 'fstop': 3.4, 'focus': SCREENS['SCR_P5b'], 'device': 'SCR_P5a', 'k': 2.4, 'accent': '#ffb070', 'devices': ['SCR_P5a', 'SCR_P5b', 'SCR_P5c']}

def st_S6():
    """Freedom: a large television on a cabinet before a brick wall, a plant, a lamp."""
    FZ = 0.0
    bm = node_mat('brick', '#3a2420', rough=.8); noise_bump(bm, 160.0, .22, 6)
    nt = bm.node_tree; tc = nt.nodes.new('ShaderNodeTexCoord'); br = nt.nodes.new('ShaderNodeTexBrick'); br.inputs['Scale'].default_value = 9.0; br.inputs['Mortar Size'].default_value = .012
    br.inputs['Color1'].default_value = hexc('#3a2420'); br.inputs['Color2'].default_value = hexc('#2a1a16'); br.inputs['Mortar'].default_value = hexc('#120e0c')
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); cb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(tc.outputs['Object'], sp.inputs[0]); nt.links.new(sp.outputs['X'], cb.inputs['X']); nt.links.new(sp.outputs['Z'], cb.inputs['Y'])
    nt.links.new(cb.outputs[0], br.inputs['Vector']); nt.links.new(br.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    box('brickwall', (5.0, .05, 3.0), (0, .62, 1.5), bm)
    cab = box('cab', (2.4, .45, .46), (0, 0, .23), node_mat('cab3', '#14161c', rough=.3, coat=.3), bevel=.012)
    TOP = .46
    tv, tvs = make_tv('TV2', (0, .05, TOP + .1 + .42), 1.5, glow='#8e9ac4', es=1.5, floor_z=TOP)
    plant = load_gltf(f'{ASSETS}/ph-potted_plant_04/potted_plant_04_2k.gltf', 2.3, (-1.45, -.05, TOP), 0.8); plant.location.z = TOP - zrange(plant)[0]
    lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (1.4, -.05, TOP), 2.2); lamp.location.z = TOP - zrange(lamp)[0]
    aim = empty('aim', (0, -.1, TOP + .4))
    light('lampL', 'POINT', (1.35, -.1, TOP + .5), 70, '#ff9448', .06)
    light('key', 'AREA', (-1.6, -1.7, 2.4), 150, '#9fb4ff', 1.6, aim)
    light('warm', 'AREA', (2.0, -1.8, 1.5), 60, '#ffb070', 1.2, aim)
    return {'cam': (0.0, -3.6, 1.2), 'look': (0, 0, .98), 'lens': 32, 'fstop': 2.6, 'focus': tvs, 'device': 'SCR_TV2', 'k': 1.6, 'accent': '#ff9448'}

STATIONS = {'S1': st_S1, 'S2': st_S2, 'S3': st_S3, 'S4': st_S4, 'S5': st_S5, 'S6': st_S6}
POS = {'S1': (-6.5, 7), 'S3': (0, 7), 'S5': (6.5, 7), 'S2': (-6.5, 15), 'S4': (0, 15), 'S6': (6.5, 15)}      # the stations in the void: the phones in front (they are made bigger), the televisions behind

def place(name):
    """Builds one station, scaled, turned to face the middle, standing at its place on the arc. Returns (root, info)."""
    before = set(bpy.data.objects); info = STATIONS[name](); new = [o for o in bpy.data.objects if o not in before]
    root = empty('root_' + name, (0, 0, 0))
    for o in new:
        if o.parent is None and o is not root: o.parent = root
    root.location = (POS[name][0], POS[name][1], 0); root.rotation_euler = (0, 0, 0); root.scale = (info['k'],) * 3
    for o in new:                                                    # a lamp made bigger by the scale is less strong at its new distance: the same light as before
        if o.type == 'LIGHT': o.data.energy *= info['k'] ** 2
    bpy.context.view_layer.update(); info['root'] = root; return root, info

def universe_world():
    kit.hdri(f'{ASSETS}/ph-neon_photostudio/neon_photostudio_2k.hdr', strength=.05, rotation=math.radians(30), visible=False, backdrop=NIGHT)
    m = node_mat('mirror', '#03040a', rough=.07, metal=0.0, spec=1.0, coat=.3)
    pl = box('mirrorfloor', (120, 120, .05), (0, 20, -.025), m)

def dust(n=260, spread=((-14, 14), (-3, 24), (.1, 7)), seed=5):
    for i in range(n):
        r = lambda k: rnd(i * 13 + k + seed * 1000)
        p = (spread[0][0] + r(1) * (spread[0][1] - spread[0][0]), spread[1][0] + r(2) * (spread[1][1] - spread[1][0]), spread[2][0] + r(3) * (spread[2][1] - spread[2][0]))
        s = .012 + r(4) * .03; c = ['#9fb4ff', '#ffe9c4', '#c9a6ff', '#9ff0ff'][int(r(5) * 4)]
        box('dust%d' % i, (s, s, s), p, emissive('dm%d' % i, c, 6 + 14 * r(6)))

def export_screens(cam, names=None):
    out = {}
    for n, o in SCREENS.items():
        if names and n not in names: continue
        if o.name not in bpy.context.scene.objects: continue
        bpy.context.view_layer.update(); M = o.matrix_world; w, h = o.dimensions.x, o.dimensions.z
        loc = [(-w / 2, 0, h / 2), (w / 2, 0, h / 2), (w / 2, 0, -h / 2), (-w / 2, 0, -h / 2)]
        world = [list(M @ V(p)) for p in loc]
        px = corners_px(o, cam)
        out[n] = {'px': px, 'world': world, 'center': list(M @ V(0, 0, 0)), 'normal': list((M.to_3x3() @ V(0, -1, 0)).normalized()), 'up': list((M.to_3x3() @ V(0, 0, 1)).normalized()),
                  'w': math.dist(world[0], world[1]), 'h': math.dist(world[1], world[2])}
    return out

ZMAX = 48.0
def render_passes(tag, cam, info_extra):
    os.makedirs(OUT, exist_ok=True)
    S.render.filepath = os.path.join(OUT, tag + '.png'); bpy.ops.render.render(write_still=True)
    K = {'fx': cam.data.lens / cam.data.sensor_width * W, 'fy': cam.data.lens / cam.data.sensor_width * W, 'cx': W / 2, 'cy': H / 2}
    info = {'width': W, 'height': H, 'K': K, 'cam': [list(r) for r in cam.matrix_world], 'zmax': ZMAX, 'screens': export_screens(cam, info_extra.get('devices'))}
    info.update({k: v for k, v in info_extra.items() if k in ('lens', 'k', 'accent', 'device', 'devices', 'cam_local', 'look_local')})
    json.dump(info, open(os.path.join(OUT, tag + '.json'), 'w'))
    # the mask (white = the screens) and the depth (the distance along the axis of the camera, over ZMAX, 16 bits)
    wh = emissive('mwhite', '#ffffff', 1.0); bk = emissive('mblack', '#000000', 1.0)
    dm = bpy.data.materials.new('depthm'); dm.use_nodes = True; nt = dm.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    cd = nt.nodes.new('ShaderNodeCameraData'); mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = 0; mr.inputs['From Max'].default_value = ZMAX; mr.clamp = True
    cc = nt.nodes.new('ShaderNodeCombineColor'); em = nt.nodes.new('ShaderNodeEmission'); outn = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(cd.outputs['View Z Depth'], mr.inputs['Value'])
    for i in range(3): nt.links.new(mr.outputs['Result'], cc.inputs[i])
    nt.links.new(cc.outputs[0], em.inputs['Color']); nt.links.new(em.outputs[0], outn.inputs['Surface'])
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]
    orig = {o.name: list(o.data.materials) for o in meshes}
    S.world.use_nodes = True
    bgn = [n for n in S.world.node_tree.nodes if n.type == 'BACKGROUND']
    for n in S.world.node_tree.nodes:
        if n.type == 'TEX_ENVIRONMENT': n.mute = True
    bg_old = [(n.inputs['Strength'].default_value, tuple(n.inputs['Color'].default_value)) for n in bgn]
    S.cycles.samples = 16; S.cycles.use_denoising = False; S.cycles.use_adaptive_sampling = False
    S.view_settings.view_transform = 'Raw'; S.view_settings.look = 'None'
    for n in bgn: n.inputs['Strength'].default_value = 0.0
    for o in meshes: o.data.materials.clear(); o.data.materials.append(wh if o.name.startswith('SCR_') else bk)
    S.render.filepath = os.path.join(OUT, tag + '_mask.png'); bpy.ops.render.render(write_still=True)
    for n in bgn: n.inputs['Strength'].default_value = 1.0; n.inputs['Color'].default_value = (1, 1, 1, 1)
    for o in meshes: o.data.materials.clear(); o.data.materials.append(dm)
    S.render.filepath = os.path.join(OUT, tag + '_depth.png'); bpy.ops.render.render(write_still=True)

def main():
    t0 = time.time(); universe_world()
    if SHOT == 'WIDE':
        infos = {}
        for n in STATIONS: infos[n] = place(n)[1]
        dust(380, ((-16, 16), (-2, 26), (.05, 8)))
        cam, tgt = make_camera((0.0, -4.2, 8.2), (0.0, 12.0, 1.1), lens=27, fstop=9.0)
        names = [d for i in infos.values() for d in (i.get('devices') or [i['device']])]
        extra = {'devices': names}
    else:
        root, info = place(SHOT)
        dust(160, ((-3, 3), (-2, 4), (.05, 3)), seed=int(SHOT[1]))
        M = root.matrix_world; cam, tgt = make_camera(M @ V(info['cam']), M @ V(info['look']), lens=info['lens'], fstop=info['fstop'], focus=info['focus'])
        extra = {'devices': info.get('devices') or [info['device']], 'device': info['device'], 'k': info['k'], 'lens': info['lens'], 'accent': info['accent']}
    bpy.context.view_layer.update()
    render_passes(SHOT, cam, extra)
    print('station', SHOT, 'in %.0fs' % (time.time() - t0))

main()
