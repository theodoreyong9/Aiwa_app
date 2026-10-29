"""Film 3, the 3D scene, in Blender (Cycles, path traced: the room is lit by an HDRI and by its own lights, the screens are emissive and light the room).
The screens are drawn elsewhere (HTML pages rendered to frames: the phone, the television) and read here frame by frame; the labels and the title cards are drawn over the render
by overlay.html from anchors.json, which this script writes (where each tracked point is in the picture, at each frame).

  /tmp/bpyenv/bin/python scene3d.py -- --out frames/ --fps 24 --width 1920 --height 1080 --samples 64 [--from 0 --to 100] [--still 12.5]
Resumable: a frame already on disk is kept."""
import json, math, os, sys, time
T0 = time.time()
import numpy as np
import bpy, bmesh, mathutils
from bpy_extras.object_utils import world_to_camera_view

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'video-kit', 'shots', 'blender'))
import kit
A = kit.args
OUT, FPS = A('out', '/tmp/os3/b'), A('fps', 24, int)
WIDTH, HEIGHT, SAMPLES = A('width', 1920, int), A('height', 1080, int), A('samples', 64, int)
PH_DIR, TV_DIR = A('phdir', '/tmp/os3/ph2'), A('tvdir', '/tmp/os3/tv2')
WIN = A('window', 0.0, float)                  # > 0: the PAUSE window (seconds): the room is held at t = 50 while the television shows something else (its own frames), the camera breathes and comes back
TVX_DIR = A('tvxdir', '/tmp/os3/tvx')
SRC_FPS = A('srcfps', 24, int)            # the rate the screen frames were drawn at
ASSETS = A('assets', '/tmp/ph')
TL = json.load(open(os.path.join(HERE, 'timeline.json'))); T = TL['T']
TOTAL = T['total']; NFR = int(round(TOTAL * FPS))
DF = (6.0, 7.4)                                  # the dot leaves the dark and docks on the phone

# ------------------------------------------------------------------ maths
def clamp(x, a=0.0, b=1.0): return min(b, max(a, x))
def ramp(t, a, b): return clamp((t - a) / (b - a))
def sm(x): return x * x * (3 - 2 * x)
def sm5(x): return x * x * x * (x * (x * 6 - 15) + 10)
def seg(t, a, b): return sm(ramp(t, a, b))
def mix(a, b, k): return a + (b - a) * k
def rnd(i): s = math.sin(i * 127.1 + 311.7) * 43758.5453; return s - math.floor(s)
def V(*a): return mathutils.Vector(a if len(a) == 3 else a[0])

# ------------------------------------------------------------------ scene
S = kit.reset(width=WIDTH, height=HEIGHT, samples=SAMPLES, fps=FPS)
S.cycles.use_adaptive_sampling = True; S.cycles.adaptive_threshold = 0.02; S.cycles.adaptive_min_samples = 16
S.cycles.denoiser = 'OPENIMAGEDENOISE'
B = A('bounces', 6, int)
S.cycles.max_bounces = B; S.cycles.diffuse_bounces = min(3, B); S.cycles.glossy_bounces = min(4, B); S.cycles.transmission_bounces = min(4, B); S.cycles.volume_bounces = 0
S.cycles.use_denoising = A('denoise', 1, int) == 1
S.cycles.use_light_tree = A('ltree', 1, int) == 1
S.cycles.sample_clamp_indirect = 4.0; S.cycles.caustics_reflective = False; S.cycles.caustics_refractive = False; S.cycles.blur_glossy = 0.4
S.cycles.volume_step_rate = 1.5; S.cycles.volume_max_steps = 96
S.render.use_persistent_data = True; S.render.image_settings.file_format = 'JPEG'; S.render.image_settings.quality = 96
S.view_settings.look = 'AgX - Punchy' if 'AgX - Punchy' in [l.identifier for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else 'None'
S.view_settings.exposure = 0.0

def hexc(h, a=1.0): return kit.rgba(h, a)

def node_mat(name, base='#222228', rough=.5, metal=0.0, emit=None, es=0.0, coat=0.0, ior=1.45, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = hexc(base) if isinstance(base, str) else base
    p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    p.inputs['Coat Weight'].default_value = coat; p.inputs['IOR'].default_value = ior; p.inputs['Alpha'].default_value = alpha
    if emit is not None:
        p.inputs['Emission Color'].default_value = hexc(emit) if isinstance(emit, str) else emit; p.inputs['Emission Strength'].default_value = es
    return m

def emissive(name, color, strength, light=False):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    if not light: m.cycles.emission_sampling = 'NONE'
    for n in list(nt.nodes): nt.nodes.remove(n)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = hexc(color) if isinstance(color, str) else color; e.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
    return m

def set_emit(m, strength=None, color=None, fac=None):
    nt = m.node_tree; e = [n for n in nt.nodes if n.type == 'EMISSION'][0]
    if strength is not None: e.inputs['Strength'].default_value = strength
    if color is not None: e.inputs['Color'].default_value = hexc(color) if isinstance(color, str) else color
    if fac is not None:
        mx = [n for n in nt.nodes if n.type == 'MIX_SHADER'][0]; mx.inputs['Fac'].default_value = fac

def add(obj, parent=None):
    if obj.name not in bpy.context.scene.collection.objects: bpy.context.scene.collection.objects.link(obj)
    if parent: obj.parent = parent
    return obj

def box(name, size, loc, mat, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    if bevel > 0: bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=bevel, segments=3, affect='EDGES')
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o.location = loc; o.data.materials.append(mat); add(o)
    for p in me.polygons: p.use_smooth = bevel > 0
    return o

def sphere(name, r, loc, mat, seg=16):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2 + 1, radius=r)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); o.location = loc; o.data.materials.append(mat); add(o); return o

def torus(name, R, r, mat, loc=(0, 0, 0)):
    bm = bmesh.new(); n, m_ = 64, 8
    vs = [[bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))) for b in [2 * math.pi * j / m_ for j in range(m_)]] for a in [2 * math.pi * i / n for i in range(n)]]
    for i in range(n):
        for j in range(m_): bm.faces.new((vs[i][j], vs[(i + 1) % n][j], vs[(i + 1) % n][(j + 1) % m_], vs[i][(j + 1) % m_]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); o.location = loc; o.data.materials.append(mat); add(o); return o

def cyl(name, mat, r=.0012):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r, radius2=r, depth=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o.data.materials.append(mat); add(o); return o

def place_cyl(o, a, b, r=None):
    a, b = V(a), V(b); d = b - a; L = d.length
    if L < 1e-6: o.hide_render = True; return
    o.hide_render = False; o.location = (a + b) / 2; o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    o.scale = (1, 1, L) if r is None else (r, r, L)

def glow(name, color, size):
    """A soft halo that always faces the camera (what a lens does with a bright point)."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; m.cycles.emission_sampling = 'NONE'
    for n in list(nt.nodes): nt.nodes.remove(n)
    tc = nt.nodes.new('ShaderNodeTexCoord'); g = nt.nodes.new('ShaderNodeTexGradient'); g.gradient_type = 'SPHERICAL'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Location'].default_value = (-1, -1, 0); mp.inputs['Scale'].default_value = (2, 2, 1)
    cr = nt.nodes.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (0, 0, 0, 1); cr.color_ramp.elements[1].position = 1.0; cr.color_ramp.elements[1].color = (1, 1, 1, 1)
    mid = cr.color_ramp.elements.new(.7); mid.color = (.1, .1, .1, 1); mid2 = cr.color_ramp.elements.new(.9); mid2.color = (.45, .45, .45, 1)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = hexc(color); e.inputs['Strength'].default_value = 2.0
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader'); out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], g.inputs['Vector']); nt.links.new(g.outputs['Fac'], cr.inputs['Fac'])
    nt.links.new(cr.outputs['Color'], mx.inputs['Fac']); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for l in f.loops: l[uv].uv = (l.vert.co.x / size + .5, l.vert.co.y / size + .5)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o.data.materials.append(m); add(o)
    c = o.constraints.new('TRACK_TO'); c.target = CAM; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
    o['mat'] = m.name; o.visible_shadow = False; o.visible_glossy = False; o.visible_diffuse = False; o.visible_transmission = False; return o

def glow_set(o, strength=None, color=None):
    m = bpy.data.materials[o['mat']]; e = [n for n in m.node_tree.nodes if n.type == 'EMISSION'][0]
    if strength is not None: e.inputs['Strength'].default_value = strength
    if color is not None: e.inputs['Color'].default_value = hexc(color)

# ------------------------------------------------------------------ camera
cam_data = bpy.data.cameras.new('cam'); cam_data.sensor_fit = 'VERTICAL'; cam_data.sensor_height = 24
cam_data.dof.use_dof = True; cam_data.dof.aperture_fstop = 2.8; cam_data.clip_start = 0.01; cam_data.clip_end = 60
CAM = bpy.data.objects.new('cam', cam_data); bpy.context.scene.collection.objects.link(CAM); S.camera = CAM

# ------------------------------------------------------------------ the room
FLOOR_Z = -0.549                                                   # the table is a real one, 0.549 m high: its top is the zero
kit.hdri(f'{ASSETS}/ph-neon_photostudio/neon_photostudio_2k.hdr', strength=0.55, rotation=math.radians(40), visible=False, backdrop='#010205')

# the floor: polished dark concrete that reflects the room
fl_m = node_mat('floor', '#0c0d11', rough=.22, metal=0.0, coat=.4)
nt = fl_m.node_tree; nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 8
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .08; nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
rmp = nt.nodes.new('ShaderNodeMapRange'); rmp.inputs['To Min'].default_value = .16; rmp.inputs['To Max'].default_value = .5; nt.links.new(nz.outputs['Fac'], rmp.inputs['Value']); nt.links.new(rmp.outputs['Result'], nt.nodes['Principled BSDF'].inputs['Roughness'])
floor = box('floor', (14, 14, .05), (0, 1.5, FLOOR_Z - .025), fl_m)

# the back wall: walnut slats in front of a light that glows between them
WALL_Y = 3.4
glow_wall = bpy.data.materials.new('wallglow'); glow_wall.use_nodes = True; nt = glow_wall.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
tc = nt.nodes.new('ShaderNodeTexCoord'); sp = nt.nodes.new('ShaderNodeSeparateXYZ'); mpr = nt.nodes.new('ShaderNodeMapRange'); mpr.inputs['From Min'].default_value = -3.5; mpr.inputs['From Max'].default_value = 3.5
cr = nt.nodes.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = hexc('#6a3cff'); cr.color_ramp.elements[1].color = hexc('#14d6a8'); cr.color_ramp.elements[0].position = .05; cr.color_ramp.elements[1].position = .95
em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 5.0; out = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tc.outputs['Object'], sp.inputs[0]); nt.links.new(sp.outputs['X'], mpr.inputs['Value']); nt.links.new(mpr.outputs['Result'], cr.inputs['Fac']); nt.links.new(cr.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs['Surface'])
WALL_EMISSION = em
STRIPS = []
for gx, gcol in ((-2.0, '#6a3cff'), (-0.9, '#2a6cff'), (1.1, '#14d6a8'), (2.2, '#6a3cff')):
    gm_ = emissive('strip', gcol, 1.0, light=True); box('strip', (.22, .02, 3.4), (gx, WALL_Y + .1, .9), gm_); STRIPS.append(gm_)
slat_m = node_mat('slat', '#2a1a12', rough=.45, metal=0.0, coat=.1)
for i in range(-80, 81):
    x = i * .1
    s = box('slat', (.055, .06, 3.4), (x, WALL_Y, .9), slat_m, bevel=.004)
# floating shelf with books, right of the television
shelf_m = node_mat('shelf', '#14161d', rough=.5)
box('shelf', (1.3, .26, .035), (1.55, WALL_Y - .35, 1.05), shelf_m, bevel=.004)
for i in range(11):
    h = .17 + rnd(i) * .1; w = .035 + rnd(i + 9) * .03
    box('book', (w, .19, h), (1.05 + i * .085, WALL_Y - .35, 1.05 + .0175 + h / 2), node_mat('bk%d' % i, tuple(list(__import__('colorsys').hls_to_rgb(rnd(i + 3), .22 + rnd(i + 5) * .12, .35))) + (1,), rough=.6), bevel=.003)

def load_gltf(path, scale=1.0, loc=(0, 0, 0), yaw=0.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new('root', None); bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.scale = (scale,) * 3; root.rotation_euler = (0, 0, yaw); root.location = loc
    bpy.context.view_layer.update(); return root

def zmin(root):
    pts = [o.matrix_world @ V(c) for o in [root, *root.children_recursive] if o.type == 'MESH' for c in o.bound_box]
    return min(p.z for p in pts), max(p.z for p in pts)

def tame(root, mul=(.5, .46, .44)):
    for o in [root, *root.children_recursive]:
        if o.type != 'MESH': continue
        for sl in o.material_slots:
            nt = sl.material.node_tree; p = nt.nodes.get('Principled BSDF')
            if p is None: continue
            l = [l for l in nt.links if l.to_socket == p.inputs['Base Color']]
            if not l: continue
            src = l[0].from_socket; mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0; mx.inputs[7].default_value = (*mul, 1)
            nt.links.new(src, mx.inputs[6]); nt.links.new(mx.outputs[2], p.inputs['Base Color'])
desk = load_gltf(f'{ASSETS}/ph-WoodenTable_01/WoodenTable_01_2k.gltf', 1.0, (0.2, 0, 0))
tame(desk); z0, z1 = zmin(desk); desk.location.z -= z1       # its top at zero
bpy.context.view_layer.update()
lamp = load_gltf(f'{ASSETS}/ph-industrial_pipe_lamp/industrial_pipe_lamp_2k.gltf', 1.0, (-.5, .15, 0), .7); lamp.location.z -= zmin(lamp)[0]
spec = load_gltf(f'{ASSETS}/ph-round_spectacles/round_spectacles_2k.gltf', 1.0, (-.2, -.18, 0), .5); spec.location.z -= zmin(spec)[0]
plant = load_gltf(f'{ASSETS}/ph-potted_plant_04/potted_plant_04_2k.gltf', 1.6, (.55, 1.88, 0), 0)
# the low cabinet the television stands on
cab_m = node_mat('cabinet', '#101218', rough=.35, coat=.3)
cab = box('cabinet', (1.9, .42, .5), (0, 1.95, FLOOR_Z + .25), cab_m, bevel=.01)
CAB_TOP = FLOOR_Z + .5; plant.location.z = CAB_TOP - zmin(plant)[0] + .0
plant.location.x = .62
bpy.context.view_layer.update()

# the television
TVC = V(-.05, 1.9, CAB_TOP + .05 + .366)                          # its centre
tv_body_m = node_mat('tvbody', '#050507', rough=.25, metal=.8)
box('tvbody', (1.34, .035, .78), (TVC.x, TVC.y + .02, TVC.z), tv_body_m, bevel=.008)
box('tvfoot', (.45, .14, .02), (TVC.x, TVC.y + .02, CAB_TOP + .01), tv_body_m, bevel=.004)
box('tvneck', (.12, .03, .06), (TVC.x, TVC.y + .03, CAB_TOP + .05), tv_body_m, bevel=.004)
def screen_mat(name, rough=.06, es=1.0):
    m = node_mat(name, '#000000', rough=rough, coat=.0, ior=1.5)
    nt = m.node_tree; p = nt.nodes['Principled BSDF']; p.inputs['Specular IOR Level'].default_value = .25; tex = nt.nodes.new('ShaderNodeTexImage'); tex.interpolation = 'Cubic'; tex.extension = 'EXTEND'
    nt.links.new(tex.outputs['Color'], p.inputs['Emission Color']); p.inputs['Emission Strength'].default_value = es; return m
tv_m = screen_mat('tvscreen', rough=.4, es=1.6)
# uv of the plane: a box is not mapped as an image: make a clean quad
def quad(name, w, h, mat, loc, rot=(0, 0, 0), uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in ((-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2))]
    f = bm.faces.new(vs); u = bm.loops.layers.uv.new('UVMap')
    for l, c in zip(f.loops, uv): l[u].uv = c
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); o.data.materials.append(mat); o.location = loc; o.rotation_euler = rot; add(o)
    for p in me.polygons: p.use_smooth = True
    return o
tvs = quad('tvscreen', 1.3, .731, tv_m, (TVC.x, TVC.y - .0, TVC.z))
tvs.location.y = TVC.y + .0 - .0155                                 # a hair in front of the body

# the phone: body of brushed metal, glass, a screen read from the phone frames
PW, PH_, PD = .074, .162, .0085
SCR_W, SCR_H = .0695, .1575                                           # 720x1600 is 0.45: the screen keeps the phone's own picture ratio
phone = bpy.data.objects.new('phone', None); bpy.context.scene.collection.objects.link(phone)
def phone_body():
    pts = kit._rounded_rect(PW, PH_, .0105, seg=10)
    bm = bmesh.new(); f = bm.faces.new([bm.verts.new((x, -PD / 2, z)) for x, z in pts])
    if f.normal.y > 0: f.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[f]); mv = [v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, PD, 0), verts=mv); bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=.0009, segments=3, affect='EDGES')
    me = bpy.data.meshes.new('phbody'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new('phbody', me); o.data.materials.append(node_mat('phframe', '#202228', rough=.28, metal=1.0)); add(o, phone); return o
phone_body()
ph_glass = node_mat('phglass', '#000000', rough=.08, ior=1.35, coat=.0)
phg = quad('phglass', PW - .0015, PH_ - .0015, ph_glass, (0, -PD / 2 - .00008, 0)); phg.parent = phone
ph_m = screen_mat('phscreen', rough=.05, es=1.0)
phs = quad('phscreen', SCR_W, SCR_H, ph_m, (0, -PD / 2 - .0002, 0)); phs.parent = phone
# the lens island on the back, the side buttons
box('island', (.028, .002, .036), (.0, PD / 2 + .0008, .052), node_mat('isl', '#0b0b0e', rough=.2, metal=.9), bevel=.0008).parent = phone
for k, (dz, hh) in enumerate(((.02, .014), (-.005, .02))):
    b = box('btn', (.0008, .003, hh), (PW / 2 + .0003, 0, dz), node_mat('btn', '#202228', rough=.3, metal=1.0)); b.parent = phone

# the green dot and its halo
GREEN = '#35f08a'
dot_m = emissive('dot', GREEN, 90.0); dot = sphere('dot', .0042, (0, 0, 0), dot_m, seg=20); dot_glow = glow('dotglow', GREEN, .05)
dot_light = bpy.data.objects.new('dotlight', bpy.data.lights.new('dl', 'POINT')); dot_light.data.color = (.2, 1, .5); dot_light.data.energy = .0; dot_light.data.shadow_soft_size = .004; bpy.context.scene.collection.objects.link(dot_light)

# lights: a warm key, a violet and a blue rim, a soft top
def light(name, kind, loc, energy, color, size=.5, target=None, spot=0.9):
    l = bpy.data.lights.new(name, kind); l.energy = energy; l.color = hexc(color)[:3]
    if kind == 'AREA': l.size = size
    if kind == 'SPOT': l.spot_size = spot; l.spot_blend = .6; l.shadow_soft_size = size
    o = bpy.data.objects.new(name, l); o.location = loc; bpy.context.scene.collection.objects.link(o)
    if target is not None:
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return o
aim = bpy.data.objects.new('aim', None); aim.location = (.2, 0, 0); bpy.context.scene.collection.objects.link(aim)
KEY = light('key', 'SPOT', (1.1, -1.2, 1.7), 0, '#ffd2a0', .35, aim, .75)
RIM1 = light('rim1', 'AREA', (-1.6, -.2, .9), 0, '#7a5cff', 1.0, aim)
RIM2 = light('rim2', 'AREA', (1.8, 1.0, .7), 0, '#2ad6c0', 1.0, aim)
TOP = light('top', 'AREA', (0, .5, 2.2), 0, '#aab8ff', 2.0, aim)
LAMPL = light('lamp', 'POINT', (-.5, .13, .3), 0, '#ffb060'); LAMPL.data.shadow_soft_size = .02
PHL = light('phl', 'POINT', (0, 0, 0), 0, '#bfd0ff'); PHL.data.shadow_soft_size = .02

# haze: a thin fog filling the room, so that lights have beams and distance has depth
haze_m = bpy.data.materials.new('haze'); haze_m.use_nodes = True; nt = haze_m.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
pv = nt.nodes.new('ShaderNodeVolumePrincipled'); pv.inputs['Density'].default_value = 0.012; pv.inputs['Anisotropy'].default_value = .55; pv.inputs['Color'].default_value = (.8, .85, 1, 1)
out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(pv.outputs[0], out.inputs['Volume'])
HAZE_ON = A('haze', 1, int)
HAZE = box('haze', (9, 8, 4), (0, 1.0, .8), haze_m); HAZE.display_type = 'WIRE'
if not HAZE_ON: HAZE.hide_render = True

# dust motes: one mesh of small octahedra, moved every frame
ND = 380
dust_base = np.array([[(rnd(i) - .5) * 3.2 + .2, (rnd(i + 1000) - .5) * 4.2 + .6, rnd(i + 2000) * 1.6 - .25] for i in range(ND)])
dust_sz = np.array([.0011 + rnd(i + 3000) * .0016 for i in range(ND)])
oct_ = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
dust_faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
dme = bpy.data.meshes.new('dust'); dme.from_pydata([tuple(v) for _ in range(ND) for v in oct_], [], [(f[0] + 6 * i, f[1] + 6 * i, f[2] + 6 * i) for i in range(ND) for f in dust_faces]); dme.update()
dust_m = emissive('dustm', '#cfd8ff', 5.0); dme.materials.append(dust_m)
dust = bpy.data.objects.new('dust', dme); bpy.context.scene.collection.objects.link(dust); dust.visible_shadow = False; dust.visible_glossy = False

# ------------------------------------------------------------------ system 1: the node object
NODE_C = V(.78, -.1, .34)
NODE = bpy.data.objects.new('NODE', None); NODE.location = NODE_C; bpy.context.scene.collection.objects.link(NODE)
ico_bm = bmesh.new(); bmesh.ops.create_icosphere(ico_bm, subdivisions=4, radius=1.0)
ico_me = bpy.data.meshes.new('core'); ico_bm.to_mesh(ico_me); ico_bm.free()
for p in ico_me.polygons: p.use_smooth = True
core_m = node_mat('core', '#8fb8ff', rough=.12, metal=1.0, coat=1.0)
core = bpy.data.objects.new('core', ico_me); core.data.materials.append(core_m); add(core, NODE)
dirs = np.array([v.co[:] for v in ico_me.vertices]); dirs /= np.linalg.norm(dirs, axis=1)[:, None]
def radii():
    cube = 1 / np.max(np.abs(dirs), axis=1) * .8; octa = 1 / np.sum(np.abs(dirs), axis=1) * 1.15; bulb = .8 + .25 * np.cos(dirs[:, 2] * 6)
    return [np.ones(len(dirs)), cube, octa, bulb]
RADII = radii()
def morph_core(w):
    r = sum(wi * ri for wi, ri in zip(w, RADII)); ico_me.vertices.foreach_set('co', (dirs * r[:, None]).ravel()); ico_me.update()
NODES = [dict(c='#ff9a5c', a=0, r=.17, t0=29.0), dict(c='#ff9a5c', a=2.1, r=.17, t0=29.6), dict(c='#ff9a5c', a=4.2, r=.17, t0=30.2),
         dict(c='#6ff0b8', a=1.0, r=.26, t0=32.2, shape=1), dict(c='#b48cff', a=3.3, r=.27, t0=33.4, shape=2)]
for i, n in enumerate(NODES):
    m = emissive('nd%d' % i, n['c'], 6.0)
    if n.get('shape') == 1: bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=.026); me = bpy.data.meshes.new('oct'); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new('nd', me); o.data.materials.append(m); add(o, NODE)
    elif n.get('shape') == 2: o = box('nd', (.036, .036, .036), (0, 0, 0), m, bevel=.004); o.parent = NODE
    else: o = torus('nd', .022, .0065, m); o.parent = NODE
    n['o'] = o; n['mat'] = m; n['g'] = glow('ndg%d' % i, n['c'], .1); n['g'].parent = NODE; o.hide_render = True; n['g'].hide_render = True
LINKM = emissive('link', '#cfe0ff', 5.0); LINKS = [cyl('lk%d' % i, LINKM, .0008) for i in range(14)]
for l in LINKS: l.parent = NODE; l.hide_render = True
RINGM = [emissive('ring%d' % i, '#8fb8ff', 3.0) for i in range(8)]
RINGS = []
for i in range(8):
    r = torus('ring%d' % i, 1.0, .01, RINGM[i]); r.parent = NODE; r.hide_render = True; RINGS.append(r)
SCEN = [V(-.34, -.1, .1), V(-.2, .08, -.05), V(-.02, -.06, .14), V(.16, .1, 0), V(.34, -.02, .1)]
SCEN = [V(p.x, p.z, p.y) for p in SCEN]                                 # three.js y up -> here z up
SCEN_M = emissive('scn', '#ffe27a', 8.0); SCEN_O = [sphere('sc%d' % i, .0105, p, SCEN_M) for i, p in enumerate(SCEN)]
for o in SCEN_O: o.parent = NODE; o.hide_render = True
SCEN_L = [cyl('sl%d' % i, SCEN_M, .0007) for i in range(4)]
for l in SCEN_L: l.parent = NODE; l.hide_render = True
for o in SCEN_O + SCEN_L: o.location.z -= .14 if o in SCEN_O else 0
PULSE = sphere('pulse', .014, (0, 0, 0), emissive('pulse', '#ffffff', 40.0)); PULSE.parent = NODE; PULSE.hide_render = True

# ------------------------------------------------------------------ system 2: the world
WORLD_C = V(-.78, -.15, .36)
WORLD = bpy.data.objects.new('WORLD', None); WORLD.location = WORLD_C; bpy.context.scene.collection.objects.link(WORLD)
gm = bpy.data.materials.new('globe'); gm.use_nodes = True; nt = gm.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
tc = nt.nodes.new('ShaderNodeTexCoord'); vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 120; vo.feature = 'F1'
nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.6; nz.inputs['Detail'].default_value = 4
dotmask = nt.nodes.new('ShaderNodeMapRange'); dotmask.inputs['From Min'].default_value = .10; dotmask.inputs['From Max'].default_value = .17; dotmask.inputs['To Min'].default_value = 1; dotmask.inputs['To Max'].default_value = 0; dotmask.clamp = True
land = nt.nodes.new('ShaderNodeMapRange'); land.inputs['From Min'].default_value = .46; land.inputs['From Max'].default_value = .54; land.inputs['To Min'].default_value = .25; land.inputs['To Max'].default_value = 1.0
mulc = nt.nodes.new('ShaderNodeVectorMath'); mulc.operation = 'SCALE'
em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = hexc('#6aa8ff'); em.inputs['Strength'].default_value = 5.0
tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader'); out = nt.nodes.new('ShaderNodeOutputMaterial')
mm = nt.nodes.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'
nt.links.new(tc.outputs['Object'], vo.inputs['Vector']); nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(vo.outputs['Distance'], dotmask.inputs['Value'])
nt.links.new(nz.outputs['Fac'], land.inputs['Value']); nt.links.new(dotmask.outputs['Result'], mm.inputs[0]); nt.links.new(land.outputs['Result'], mm.inputs[1])
nt.links.new(mm.outputs[0], mx.inputs['Fac']); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
GLOBE_EM = em
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0); me = bpy.data.meshes.new('globe'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
GLOBE = bpy.data.objects.new('globe', me); GLOBE.data.materials.append(gm); GLOBE.scale = (.15,) * 3; add(GLOBE, WORLD)
CORE = sphere('gcore', .146, (0, 0, 0), node_mat('gcore', '#05070e', rough=.3), seg=32); CORE.parent = WORLD
PINS_DIR = [V(.5, .8, .3), V(-.7, .6, .4), V(.2, .84, -.5), V(-.3, -.65, .7), V(.8, -.6, .1), V(-.85, -.5, -.2)]
PINS_DIR = [d.normalized() for d in PINS_DIR]
PIN_M = emissive('pin', '#ffd05a', 20.0); PINS = []
for d in PINS_DIR:
    o = sphere('pin', .0075, d * .156, PIN_M); o.parent = GLOBE_PARENT = WORLD; o.hide_render = True; PINS.append(o)
ARC_PAIRS = [(0, 1), (1, 2), (2, 4), (0, 3), (3, 5), (4, 1)]
ARC_M = [emissive('arc%d' % i, '#8fb8ff', 4.0) for i in range(len(ARC_PAIRS))]
ARC_CURVES = []; ARCS = []
for i, (a, b) in enumerate(ARC_PAIRS):
    A_, B_ = PINS_DIR[a] * .156, PINS_DIR[b] * .156; mid = (PINS_DIR[a] + PINS_DIR[b]).normalized() * .27
    pts = [(1 - u) ** 2 * A_ + 2 * u * (1 - u) * mid + u * u * B_ for u in [float(x) for x in np.linspace(0, 1, 40)]]; ARC_CURVES.append(pts)
    cd = bpy.data.curves.new('arc', 'CURVE'); cd.dimensions = '3D'; cd.bevel_depth = .0007; sp = cd.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p_, v_ in zip(sp.points, pts): p_.co = (v_.x, v_.y, v_.z, 1)
    o = bpy.data.objects.new('arc', cd); cd.materials.append(ARC_M[i]); add(o, WORLD); o.hide_render = True; ARCS.append(o)
ARCDOT = sphere('arcdot', .006, (0, 0, 0), emissive('arcdot', '#ffffff', 60.0)); ARCDOT.parent = WORLD; ARCDOT.hide_render = True
RADAR_M = [emissive('radar%d' % i, '#6a8cff', 3.0) for i in range(3)]
RADARS = [torus('radar%d' % i, 1.0, .006, RADAR_M[i]) for i in range(3)]
for r in RADARS: r.hide_render = True
NEAR_POS = [V(-.35, .55, 0), V(.55, .6, 0), V(.15, -.45, 0)]
NEAR_POS = [V(.27 + p.x * 1.0, -.06 - p.y * 1.0 * -1, 0) for p in NEAR_POS]
NEAR_M = emissive('near', '#ffd05a', 12.0); NEARS = []
for p in NEAR_POS:
    top = sphere('near', .0095, (p.x, p.y, .225), NEAR_M); stem = cyl('nearstem', NEAR_M, .0018); place_cyl(stem, (p.x, p.y, 0), (p.x, p.y, .225), .0018); NEARS.append((top, stem))
    top.hide_render = True; stem.hide_render = True

# the stream that carries the phone's screen to the television
NC = 120
cme = bpy.data.meshes.new('cast'); cme.from_pydata([tuple(v) for _ in range(NC) for v in oct_], [], [(f[0] + 6 * i, f[1] + 6 * i, f[2] + 6 * i) for i in range(NC) for f in dust_faces]); cme.update()
CASTM = emissive('castm', '#7fd4ff', 14.0); cme.materials.append(CASTM)
CAST = bpy.data.objects.new('cast', cme); bpy.context.scene.collection.objects.link(CAST); CAST.hide_render = True
LRINGM = emissive('lring', GREEN, 6.0); LRINGS = [torus('lr%d' % i, 1.0, .0006, LRINGM) for i in range(3)]
for r in LRINGS: r.hide_render = True
HALO = glow('halo', '#6a8cff', .5); HALO.hide_render = True
HALO.constraints.clear(); HALO.rotation_euler = (0, 0, 0)


# ------------------------------------------------------------------ what is made above the phone: a chrome shape that becomes Docs, Médias, App, Page; then the smart contract
CT_DIR, IC_DIR = A('ctdir', '/tmp/os3/ct'), A('icdir', '/tmp/os3/ic')
SH_C = V(.27, -.04, .125)
sh_bm = bmesh.new(); bmesh.ops.create_icosphere(sh_bm, subdivisions=6, radius=1.0)
sh_me = bpy.data.meshes.new('shape'); sh_bm.to_mesh(sh_me); sh_bm.free()
for p_ in sh_me.polygons: p_.use_smooth = True
sh_m = node_mat('shape', '#9fc4ff', rough=.1, metal=1.0, coat=1.0)
SHAPE = bpy.data.objects.new('shape', sh_me); SHAPE.data.materials.append(sh_m); SHAPE.location = SH_C; bpy.context.scene.collection.objects.link(SHAPE); SHAPE.hide_render = True
sh_dirs = np.array([v.co[:] for v in sh_me.vertices]); sh_dirs /= np.linalg.norm(sh_dirs, axis=1)[:, None]
def box_r(d, ex): return 1 / (np.sum((np.abs(d) / np.array(ex)) ** 4, axis=1) ** .25)   # a rounded box: a smooth shape, not a jagged one
SH_R = [box_r(sh_dirs, (.62, .1, .8)), box_r(sh_dirs, (.95, .1, .56)), box_r(sh_dirs, (.42, .09, .8)), np.ones(len(sh_dirs)) * .78]   # a page, a film frame, a phone, a globe
SH_TINT = ['#52d6a0', '#6b9bf5', '#e09a7c', '#e8c14a']
def morph_shape(w):
    r = sum(wi * ri for wi, ri in zip(w, SH_R)); sh_me.vertices.foreach_set('co', (sh_dirs * r[:, None]).ravel()); sh_me.update()
# the contract: a card that rises from the phone
ct_m = screen_mat('contract', rough=.35, es=1.5)
CARD = quad('card', .18, .1125, ct_m, (.27, -.03, .15), rot=(math.radians(-14), 0, math.radians(-5))); CARD.hide_render = True
# the campaign: pairs « a file + a connector » fall one by one onto the super agent; each landing sends a wave and the pair is multiplied into copies that ride the wave outward (campaign.py holds the schedule)
sys.path.insert(0, HERE)
import campaign as CP
G2 = A('ic2dir', '/tmp/os3/ic2')
def tile_mat(n_):
    tm = bpy.data.materials.new('tile_' + n_); tm.use_nodes = True; tm.cycles.emission_sampling = 'NONE'; nt = tm.node_tree
    for nd in list(nt.nodes): nt.nodes.remove(nd)
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(f'{G2}/{n_}.png'); tx.image.alpha_mode = 'STRAIGHT'
    em_ = nt.nodes.new('ShaderNodeEmission'); em_.inputs['Strength'].default_value = 2.2; tr_ = nt.nodes.new('ShaderNodeBsdfTransparent'); mx_ = nt.nodes.new('ShaderNodeMixShader'); ou_ = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tx.outputs['Color'], em_.inputs['Color']); nt.links.new(tx.outputs['Alpha'], mx_.inputs['Fac']); nt.links.new(tr_.outputs[0], mx_.inputs[1]); nt.links.new(em_.outputs[0], mx_.inputs[2]); nt.links.new(mx_.outputs[0], ou_.inputs['Surface'])
    return tm
TILE_M = {n_: tile_mat(n_) for n_ in CP.FILES + CP.CHANNELS}
def facing_quad(size, mat):
    q = quad('cpt', size, size, mat, (0, 0, 0)); q.hide_render = True; q.visible_shadow = False
    c_ = q.constraints.new('TRACK_TO'); c_.target = CAM; c_.track_axis = 'TRACK_NEGATIVE_Y'; c_.up_axis = 'UP_Z'; return q
SCHED = CP.schedule()
FALLERS = [(facing_quad(.07, TILE_M[CP.FILES[0]]), facing_quad(.07, TILE_M[CP.CHANNELS[0]])) for _ in range(8)]      # the pairs on their way down
COPIES = [facing_quad(.048, TILE_M[CP.FILES[0]]) for _ in range(54)]                                                 # the copies that ride the waves
BOND_M = emissive('bond', '#ffffff', 9.0); BONDS = [cyl('bond', BOND_M, .0013) for _ in range(8)]
for o in BONDS: o.hide_render = True
WAVE_M = [emissive('wave%d' % i, '#9fd0ff', 3.0) for i in range(8)]
WAVES = [torus('wave%d' % i, 1.0, .0075, WAVE_M[i]) for i in range(8)]
for o in WAVES: o.hide_render = True
def set_tile(q, name):
    if q.material_slots[0].material is not TILE_M[name]: q.material_slots[0].material = TILE_M[name]
def eo3(x): return 1 - (1 - x) ** 3
def campaign_state(t):
    """What the campaign shows at t: the pairs falling, the waves, the copies riding them, and how much each wave lights a given radius."""
    falling, waves, copies = [], [], []
    for p in SCHED:
        if p['t0'] <= t < p['t1']:
            u = (t - p['t0']) / CP.FALL; falling.append((p, u))
        w = (t - p['t1']) / CP.WAVE
        if 0 <= w < 1:
            waves.append((p, w))
            for k in range(3):
                ang = math.radians(p['a'] + k * 120); rad = .04 + .5 * eo3(w) * (.85 + .15 * ((p['n'] + k) % 3) / 2)
                copies.append((p, k, ang, rad, w))
    return falling, waves, copies

# ------------------------------------------------------------------ the camera path (x, y, z metres)
K = [  # t, camera, target, fov (vertical)
 [0, (.34, -.42, .30), (.28, -.04, .0), 30], [1.0, (.33, -.40, .29), (.28, -.04, .0), 30], [3.7, (.32, -.43, .29), (.28, -.04, .0), 30],
 [5.8, (.42, -1.10, .27), (.08, .50, .34), 38], [11.0, (.44, -1.12, .28), (.07, .52, .34), 38], [14.4, (.24, -.80, .31), (.27, -.06, .30), 36],
 [17.3, (.21, -.80, .31), (.27, -.06, .30), 36],
 [20.7, (.20, -.80, .31), (.27, -.06, .30), 36],
 [23.0, (.26, -1.2, .42), (.04, .90, .44), 40], [26.0, (.16, -1.0, .50), (-.06, 1.10, .47), 38], [28.4, (.55, -1.05, .38), (.38, -.05, .34), 38],
 [31.0, (.74, -.86, .36), (.78, -.10, .34), 34], [34.5, (.92, -.82, .40), (.78, -.10, .34), 34], [37.5, (.62, -.98, .50), (.76, -.10, .33), 37],
 [40.2, (.28, -1.15, .46), (.10, -.10, .34), 42], [42.5, (-.30, -.84, .40), (-.62, -.12, .35), 38], [45.0, (-.20, -1.0, .55), (-.15, .9, .50), 40],
 [47.5, (-.06, -.55, .50), (-.05, 1.9, .40), 40], [50.0, (-.05, -.20, .46), (-.05, 1.9, .40), 37], [53.0, (-.08, -.95, .55), (-.05, 1.9, .40), 40],
 [57.0, (0, -2.4, .62), (-.05, 1.9, .40), 42], [67, (0, -3.4, .65), (-.05, 1.9, .40), 44]]
def hermite(p0, p1, m0, m1, s):
    s2, s3 = s * s, s * s * s; return p0 * (2 * s3 - 3 * s2 + 1) + m0 * (s3 - 2 * s2 + s) + p1 * (-2 * s3 + 3 * s2) + m1 * (s3 - s2)
def cam_at_k(t, K):
    i = 0
    while i < len(K) - 2 and t > K[i + 1][0]: i += 1
    a, b, p, n = K[i], K[i + 1], K[max(0, i - 1)], K[min(len(K) - 1, i + 2)]
    dt = b[0] - a[0]; s = clamp((t - a[0]) / dt); e = mix(s, sm(s), .45); out = {}
    for name, idx in (('pos', 1), ('tgt', 2)):
        out[name] = V([hermite(a[idx][k], b[idx][k], (b[idx][k] - p[idx][k]) / max(1e-3, b[0] - p[0]) * dt, (n[idx][k] - a[idx][k]) / max(1e-3, n[0] - a[0]) * dt, e) for k in range(3)])
    out['fov'] = mix(a[3], b[3], e); return out

# during the campaign the camera comes closer to the super agent (the old path before and after is kept exactly: the shots around it are rendered already)
K_CAMP = [k_ if k_[0] != 37.5 else [37.5, (.70, -.78, .44), (.78, -.10, .36), 31] for k_ in K]
K_CAMP.insert(K_CAMP.index([k_ for k_ in K_CAMP if k_[0] == 37.5][0]) + 1, [39.0, (.68, -.80, .43), (.78, -.10, .36), 31])
def cam_at(t):
    a_, b_ = cam_at_k(t, K), cam_at_k(t, K_CAMP); w = seg(t, 36.0, 38.0) * (1 - seg(t, 39.6, 41.2))
    return {'pos': a_['pos'] * (1 - w) + b_['pos'] * w, 'tgt': a_['tgt'] * (1 - w) + b_['tgt'] * w, 'fov': mix(a_['fov'], b_['fov'], w)}

PH0 = V(.27, -.06, .081)
def phone_pose(t):
    up = sm5(ramp(t, 11.3, 14.3)); down = sm5(ramp(t, 28.2, 30.4)); lev = up * (1 - down)
    lay = sm5(ramp(t, 11.3, 13.1))                                         # 0: lying on the table, 1: upright
    pos = V(PH0.x - lev * .04, PH0.y - lev * .08, PH0.z + lev * .22 + math.sin(t * 1.7) * .004 * lev)
    pos.z = mix(.0046, pos.z, lay)
    lean = mix(math.radians(-90), mix(math.radians(14), math.radians(4), lev), lay)
    return pos, lean, (math.radians(-9) + lev * .28 * math.sin((t - 16.6) * .55)), lev

# ------------------------------------------------------------------ labels: tracked anchors, written for the overlay
ANCH = {}
def anchor(frame, key, world, a=1.0):
    ndc = world_to_camera_view(S, CAM, V(world))
    ANCH.setdefault(frame, {})[key] = [round(ndc.x, 5), round(1 - ndc.y, 5), round(ndc.z, 4), round(a, 3)]

def set_image(mat, path):
    tex = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
    if tex.image is None or tex.image.filepath != path:
        if tex.image is not None: bpy.data.images.remove(tex.image)
        tex.image = bpy.data.images.load(path)
    else: tex.image.reload()

def frame_path(d, t):
    i = clamp(round(t * SRC_FPS), 0, int(round(TOTAL * SRC_FPS)) - 1); return os.path.join(d, '%05d.jpg' % int(i))

def stage(t, a, b): return seg(t, a, a + .5) * (1 - seg(t, b - .5, b))

KEEP_DARK = {'dot', 'dotglow', 'dotlight', 'cam'}
ORIG_HIDE = {o.name: o.hide_render for o in bpy.data.objects}
DARK_STATE = [False]

def update(t, f, win=None):
    # the first seconds are black: nothing of the room is there, only the dot
    dark_now = t < T['reveal'][0] - .05
    if dark_now:
        for o in bpy.data.objects:
            if o.name.split('.')[0] not in KEEP_DARK: o.hide_render = True
    elif DARK_STATE[0]:
        for o in bpy.data.objects: o.hide_render = ORIG_HIDE.get(o.name, o.hide_render)
    DARK_STATE[0] = dark_now
    c = cam_at(t); pos = c['pos'] + V((math.sin(t * .9) * .003, math.sin(t * .6 + 2) * .002, math.sin(t * 1.3 + 1) * .0025)); tgt = c['tgt']
    if win is not None:                                                  # the pause: the camera breathes in and comes back to exactly where it was
        s_ = clamp(win / WIN); amt = math.sin(math.pi * s_) ** 2; tw = t + win
        pos = pos + V((math.sin(tw * .9) - math.sin(t * .9)) * .003, (math.sin(tw * .6 + 2) - math.sin(t * .6 + 2)) * .002, (math.sin(tw * 1.3 + 1) - math.sin(t * 1.3 + 1)) * .0025) * amt
        pos = pos + (tgt - pos).normalized() * .22 * amt + V(.05 * amt * math.sin(s_ * math.pi * 2), 0, .012 * amt)
    CAM.location = pos; CAM.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler(); cam_data.lens = 12 / math.tan(math.radians(c['fov']) / 2)
    cam_data.dof.focus_distance = max(.08, (tgt - pos).length)
    lit = seg(t, T['reveal'][0], T['reveal'][1]); dark = seg(t, 50.5, 54.5); end_dark = seg(t, 56.0, 58.5)
    # light follows the story: black until the phone arrives, the room dims for the end
    S.view_settings.exposure = -.6 * end_dark
    KEY.data.energy = 520 * lit * (1 - dark * .85); RIM1.data.energy = 260 * lit * (1 - dark * .9); RIM2.data.energy = 200 * lit * (1 - dark * .9); TOP.data.energy = 90 * lit * (1 - dark * .8)
    LAMPL.data.energy = 18 * lit * (1 - dark * .7)
    for i_, sm_ in enumerate(STRIPS): set_emit(sm_, 7.0 * lit * (1 - dark * .8) * (.85 + .15 * math.sin(t * 1.4 + i_)))
    bpy.data.worlds[0].node_tree.nodes['Background'].inputs['Strength'].default_value = .55 * lit * (1 - dark * .8) + .0001
    pv.inputs['Density'].default_value = .012 * lit + .0002
    # screens
    set_image(tv_m, frame_path(TV_DIR, t) if win is None else os.path.join(TVX_DIR, '%05d.jpg' % f)); set_image(ph_m, frame_path(PH_DIR, t))
    tv_m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.7
    # phone
    pp, lean, yaw, lev = phone_pose(t); phone.location = pp; phone.rotation_euler = (lean, 0, yaw); phone.hide_render = t < T['reveal'][0]
    ph_m.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.35 if t >= T['reveal'][0] else 0.0
    PHL.location = pp + V(0, -.12, .04); PHL.data.energy = 0.6 * lit
    bpy.context.view_layer.update()
    # the dot
    blink = 1.0 if any(b <= t < b + .45 for b in T['dotBlink']) else 0.0
    corner = phone.matrix_world @ V(PW / 2 - .004, -PD / 2 - .0005, PH_ / 2 - .004)
    dp = corner; vis = blink if t < T['reveal'][0] else 1.0
    breathe = (.7 + .3 * math.sin(t * 5)) if 1.0 < t < 23.6 else .9
    dot.location = dp; dot_glow.location = dp; dot.hide_render = vis < .01; dot_glow.hide_render = vis < .01
    set_emit(dot_m, 90.0 * breathe); glow_set(dot_glow, 2.2 * vis * breathe); dot_glow.scale = (1 + .2 * breathe,) * 3
    dot_light.location = dp; dot_light.data.energy = .5 * vis * breathe * lit + (.5 * vis if t < T['reveal'][0] else 0)
    # listening rings round the phone
    for i, r in enumerate(LRINGS):
        k = (t - T['unlock'] - i * .5) / 1.5; on = T['unlock'] <= t < T['unlock'] + 3.2 and k > 0; ff = (k % 1) if on else 0
        r.hide_render = not on
        if on: r.location = pp; r.rotation_euler = (lean + math.pi / 2, 0, yaw); r.scale = (.05 + ff * .2,) * 3; set_emit(LRINGM, 6.0 * (1 - ff) * (1 - ramp(t, T['unlock'] + 2.2, T['unlock'] + 3.2)))
    # halo under the levitating phone
    HALO.hide_render = lev < .02; HALO.location = (pp.x, pp.y, .004); HALO.rotation_euler = (0, 0, 0); HALO.scale = ((1 + lev * .4),) * 3; glow_set(HALO, 2.4 * lev)
    # the stream to the television
    cast_on = seg(t, T['cast'][0] - .4, T['cast'][0] + .3) * (1 - seg(t, T['cast'][1] - .2, T['cast'][1] + .8)); CAST.hide_render = cast_on < .01
    if cast_on >= .01:
        a_ = phone.matrix_world @ V(0, 0, .02); b_ = V(TVC.x, TVC.y - .02, TVC.z); m_ = (a_ + b_) / 2 + V(0, 0, .25)
        arr = np.zeros((NC, 3))
        for i in range(NC):
            u = ((i / NC) + t * .55) % 1; p_ = a_ * (1 - u) ** 2 + m_ * 2 * u * (1 - u) + b_ * u * u; j = rnd(i) * .03
            arr[i] = (p_.x + math.sin(t * 3 + i) * j, p_.y, p_.z + math.cos(t * 2 + i) * j)
        verts = (arr[:, None, :] + oct_[None] * .0035 * cast_on).reshape(-1, 3); cme.vertices.foreach_set('co', verts.ravel()); cme.update()
    # node system
    n_on = seg(t, 28.6, 29.4) * (1 - seg(t, 40.3, 41.0)); NODE.hide_viewport = False
    vis_n = n_on > .01
    for o in (core,): o.hide_render = not vis_n
    NODE.scale = (n_on + .001,) * 3
    ph = (t - 28.6) / 11.8; st = ph * 3.2; si = int(clamp(st, 0, 3.0)); sf = sm(clamp(st - si, 0, 1)); w = [0, 0, 0, 0]; w[min(3, si)] += 1 - sf; w[min(3, si + 1)] += sf
    if vis_n:
        morph_core(w); core.scale = (.055 + .008 * math.sin(t * 2),) * 3; core.rotation_euler = (t * .5, t * .7, 0)
        import colorsys; r_, g_, b_ = colorsys.hls_to_rgb((.58 + ph * .4) % 1, .5, .7); core_m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (r_ ** 2.2, g_ ** 2.2, b_ ** 2.2, 1)
    npos = []
    for i, n in enumerate(NODES):
        k = seg(t, n['t0'], n['t0'] + .8); ang = n['a'] + t * (.35 if i < 3 else -.28); r = n['r'] * k
        ps = V((math.cos(ang) * r, math.sin(ang) * r, math.sin(t * .8 + i) * .03 + (0 if i < 3 else (.07 if i == 3 else -.07))))
        n['o'].location = ps; n['o'].scale = (k + .001,) * 3; n['o'].rotation_euler = (t, t * .8, 0); n['o'].hide_render = not (vis_n and k > .01)
        n['g'].location = ps; n['g'].hide_render = n['o'].hide_render; glow_set(n['g'], 1.6 * k); npos.append(ps if k > .5 else None)
    li = 0
    def seg_link(a, b):
        nonlocal li
        if a is None or b is None or li >= len(LINKS): return
        place_cyl(LINKS[li], a, b, .0008 * 1.0); li += 1
    seg_link(npos[0], npos[1]); seg_link(npos[1], npos[2]); seg_link(npos[2], npos[0])
    O = V(0, 0, 0)
    for i, p_ in enumerate(npos):
        if p_ is not None and (i >= 3 or t > 31): seg_link(O, p_)
    if npos[3] is not None: seg_link(npos[3], npos[0])
    if npos[4] is not None: seg_link(npos[4], npos[1])
    for j in range(li, len(LINKS)): LINKS[j].hide_render = True
    if not vis_n:
        for l in LINKS: l.hide_render = True
    for r in RINGS: r.hide_render = True
    for o in SCEN_O + SCEN_L: o.hide_render = True
    PULSE.hide_render = True
    # world
    w_on = seg(t, T['world'][0] - .2, T['world'][0] + .8) * (1 - seg(t, 45.2, 46.0)); vw = w_on > .01
    WORLD.scale = (w_on + .001,) * 3; GLOBE.hide_render = not vw; CORE.hide_render = not vw; GLOBE.rotation_euler = (0, 0, t * .35)
    set_emit_node = GLOBE_EM; GLOBE_EM.inputs['Strength'].default_value = 5.0 * w_on
    for i, p_ in enumerate(PINS):
        p_.hide_render = not (vw and t > T['world'][0] + 1.0 + i * .2); p_.location = (mathutils.Matrix.Rotation(t * .35, 3, 'Z') @ (PINS_DIR[i] * .156))
    for i, a_ in enumerate(ARCS):
        k = seg(t, T['world'][0] + 1.4 + i * .3, T['world'][0] + 2.0 + i * .3); a_.hide_render = not (vw and k > .02); a_.rotation_euler = (0, 0, t * .35); set_emit(ARC_M[i], 4.0 * k * w_on)
    ai = int(t * 1.2) % len(ARCS); u2 = (t * 1.2) % 1; ARCDOT.hide_render = not (vw and w_on > .5)
    if not ARCDOT.hide_render: ARCDOT.location = mathutils.Matrix.Rotation(t * .35, 3, 'Z') @ ARC_CURVES[ai][min(39, int(u2 * 39))]
    for i, r in enumerate(RADARS):
        k = (t - T['world'][0] - i * .9) / 2.7; on = T['world'][0] <= t < 46 and k > 0; ff = (k % 1) if on else 0
        r.hide_render = not on
        if on: r.location = (PH0.x, PH0.y, .004); r.scale = (.15 + ff * .9,) * 3; set_emit(RADAR_M[i], 3.0 * (1 - ff) * (1 - seg(t, 45.2, 46)))
    for i, (top, stem) in enumerate(NEARS):
        k = seg(t, T['world'][0] + .9 + i * .35, T['world'][0] + 1.4 + i * .35) * (1 - seg(t, 45.2, 46)); top.hide_render = stem.hide_render = k < .01; top.scale = (k + .001,) * 3
    # the chrome shape above the phone: a page, a film frame, an app, a page of the web
    c0, c1 = T['create']; sh_on = seg(t, c0 - .2, c0 + .5) * (1 - seg(t, c1, c1 + .5)); SHAPE.hide_render = sh_on < .01
    if sh_on >= .01:
        st_ = clamp((t - c0) / (c1 - c0), 0, .9999) * 4; si_ = int(st_); sf_ = sm(clamp((st_ - si_ - .35) / .5, 0, 1)); w4 = [0, 0, 0, 0]; w4[si_] += 1 - sf_; w4[min(3, si_ + 1)] += sf_
        morph_shape(w4); SHAPE.scale = (.05 * sh_on,) * 3; SHAPE.rotation_euler = (t * .25, 0, t * .6); SHAPE.location = SH_C + V(0, 0, math.sin(t * 1.4) * .006)
        tcol = SH_TINT[min(3, si_ + (1 if sf_ > .5 else 0))]; sh_m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = hexc(tcol)
    # the smart contract: a card that rises and signs itself
    k0, k1 = T['contract']; card_on = seg(t, k0, k0 + .6) * (1 - seg(t, k1 - .4, k1)); CARD.hide_render = card_on < .01
    if card_on >= .01:
        CARD.location = (.27, -.03, .09 + .07 * card_on + math.sin(t * 1.2) * .004); CARD.scale = (card_on,) * 3
        set_image(ct_m, os.path.join(CT_DIR, '%05d.jpg' % int(clamp(round(t * 24), 0, 335))))
    # the campaign: pairs fall onto the super agent, each landing sends a wave, the pair is multiplied into copies that ride it
    falling, waves, copies = campaign_state(t)
    base_c = NODE.matrix_world.translation
    for i, (qa, qb) in enumerate(FALLERS):
        mine = [x for x in falling if x[0]['n'] % 8 == i]
        if not mine: qa.hide_render = qb.hide_render = BONDS[i].hide_render = True; continue
        p, u = mine[0]; fall = u * u * (1.6 - .6 * u); top = .34; x = p['x'] * (1 - u) ** 2
        c_ = V(base_c.x + x, base_c.y - .03, base_c.z + top * (1 - fall)); sc = n_on * (1 - ramp(u, .9, 1.0))
        set_tile(qa, p['file']); set_tile(qb, p['chan'])
        qa.location = c_ + V(-.048, 0, 0); qb.location = c_ + V(.048, 0, 0); qa.scale = qb.scale = (max(.001, sc),) * 3; qa.hide_render = qb.hide_render = sc < .02
        BONDS[i].hide_render = sc < .02; place_cyl(BONDS[i], qa.location + V(.03, 0, 0), qb.location - V(.03, 0, 0), None)
    for i, wv in enumerate(WAVES):
        mine = [x for x in waves if x[0]['n'] % 8 == i]
        if not mine: wv.hide_render = True; continue
        p, w = mine[0]; r = .04 + .5 * eo3(w); wv.hide_render = False; wv.location = base_c + V(0, 0, -.015); wv.rotation_euler = (0, 0, 0); wv.scale = (r, r, r * .6)
        set_emit(WAVE_M[i], 6.0 * (1 - w) ** 1.5 * n_on)
    for j, q in enumerate(COPIES):
        if j >= len(copies): q.hide_render = True; continue
        p, k, ang, rad, w = copies[j]; set_tile(q, p['file'] if k % 2 == 0 else p['chan'])
        q.location = base_c + V(math.cos(ang) * rad, math.sin(ang) * rad * .55, .02 + .04 * math.sin(w * math.pi)); sc = n_on * ramp(w, 0, .08) * (1 - ramp(w, .65, 1.0)); q.scale = (max(.001, sc),) * 3; q.hide_render = sc < .02
    land = max([math.exp(-((t - p['t1']) / .09) ** 2) for p in SCHED] + [0])
    if vis_n: core.scale = (core.scale[0] * (1 + .35 * land),) * 3
    # dust
    td = t if win is None else t + 3.0 * math.sin(math.pi * clamp(win / WIN))
    mv = np.stack([np.sin(td * .18 + np.arange(ND)) * .12, np.cos(td * .15 + np.arange(ND) * .7) * .12, np.sin(td * .12 + np.arange(ND) * 1.7) * .08 + ((td * .01 * (1 + np.array([rnd(i) for i in range(ND)]))) % 1.6) * 0], axis=1)
    cen = dust_base + mv; verts = (cen[:, None, :] + oct_[None] * dust_sz[:, None, None]).reshape(-1, 3); dme.vertices.foreach_set('co', verts.ravel()); dme.update()
    set_emit(dust_m, 3.0 * lit * (1 - dark * .6))
    # anchors for the labels
    for i, k_ in enumerate(('cc1', 'cc2', 'cc3', 'gpt', 'loc')): anchor(f, k_, NODE.matrix_world @ NODES[i]['o'].location, stage(t, NODES[i]['t0'] + .4, 36.5 if i < 3 else 39.8) * (1 if vis_n else 0))
    for i, (top, stem) in enumerate(NEARS): anchor(f, 'p%d' % (i + 1), top.location, stage(t, T['world'][0] + 1.2 + i * .35, 45))
    for k_, i in (('w1', 0), ('w2', 2), ('w3', 4)):
        wp = WORLD.matrix_world @ PINS[i].location; front = (wp - WORLD.location).dot(CAM.location - WORLD.location) > 0
        anchor(f, k_, wp, stage(t, T['world'][0] + 2.4 + i * .2, 45) * (1 if front else .35))
    anchor(f, 'listen', phone.matrix_world @ V(PW / 2, -PD / 2, PH_ / 2), stage(t, 3.8, 7.2))
    for k_, dx, a0, a1 in (('doc', -.42, 5.6, 8.8), ('med', -.14, 6.0, 8.8), ('app', .14, 6.4, 8.8), ('pag', .42, 6.8, 8.8)): anchor(f, k_, (TVC.x + dx, TVC.y - .02, TVC.z + .12), stage(t, a0, a1))
    anchor(f, 'sc', (TVC.x + .28, TVC.y - .02, TVC.z - .06), stage(t, 9.4, 11.4))
    anchor(f, 'agent', NODE.matrix_world.translation, stage(t, 36.4, 40.4) * (1 if vis_n else 0))

def main():
    os.makedirs(OUT, exist_ok=True)
    still = A('still', None, float)
    a, b = A('from', 0, int), A('to', NFR if WIN <= 0 else int(round(WIN * FPS)), int)
    if still is not None:
        f = int(round(still * FPS)); update(still, f); S.render.filepath = os.path.join(OUT, 'still_%s.jpg' % str(still).replace('.', '_')); bpy.ops.render.render(write_still=True); return
    if A('anchorsonly', 0, int):                                         # only where the tracked points are, without drawing (to rebuild the labels of a render that was cut and resumed)
        for f in range(a, min(b, NFR)): update(f / FPS, f)
        json.dump(ANCH, open(os.path.join(OUT, 'anchors.only.%05d.json' % a), 'w')); print('anchors', a, b); return
    if WIN > 0:                                                          # the pause window: frame k is the room at t = 50, k / fps into the pause
        for k in range(int(round(WIN * FPS))):
            path = os.path.join(OUT, '%05d.jpg' % k)
            if k < a or k >= b or (os.path.exists(path) and os.path.getsize(path) > 2000 and not os.path.exists(path + '.part')): continue
            open(path + '.part', 'w').close(); update(T['closed'][0], k, win=k / FPS)
            S.render.filepath = path; bpy.ops.render.render(write_still=True); os.remove(path + '.part'); print('FRAME', k, round(time.time() - T0, 1), flush=True)
        print('done', a, b); return
    for f in range(a, min(b, NFR)):
        path = os.path.join(OUT, '%05d.jpg' % f)
        if os.path.exists(path) and os.path.getsize(path) > 2000 and not os.path.exists(path + '.part'): continue
        open(path + '.part', 'w').close(); t = f / FPS; update(t, f)
        S.render.filepath = path; bpy.ops.render.render(write_still=True); os.remove(path + '.part')
        print('FRAME', f, round(time.time() - T0, 1), flush=True)
        if f % 10 == 0: json.dump(ANCH, open(os.path.join(OUT, 'anchors.%05d.json' % a), 'w'))
    json.dump(ANCH, open(os.path.join(OUT, 'anchors.%05d.json' % a), 'w'))
    print('done', a, b)
main()
