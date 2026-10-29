"""The desk: one continuous scenic shot in real 3D. A wooden table in a warm room (Poly Haven interior light, CC0), a binder notebook, a pair of round spectacles on it, a plant, a lamp
(Poly Haven models, CC0), and a phone leaning on the notebook, its screen the Aiwa widget then the lock screen. The camera starts on the phone, then glides and pulls focus to the spectacles.
  /tmp/bpyenv/bin/python desk-shot.py -- --out frames/ --ph /tmp/ph --screen scr/%04d.jpg --frames 100 [--still 40 --width 960 --height 540 --samples 32]"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'video-kit', 'shots', 'blender'))
import bpy, mathutils
import kit

ph = kit.args('ph', '/tmp/ph')
N = kit.args('frames', 100, int)
kit.reset(transparent=False)
s = bpy.context.scene
kit.hdri(os.path.join(ph, 'ph-lythwood_lounge', 'lythwood_lounge_2k.hdr'), strength=0.85, rotation=math.radians(200), visible=True)
# low key: the room lights the scene as before, but the camera sees it 12 times darker (a dark, warm, out-of-focus room behind the desk)
_nt = s.world.node_tree; _bg = _nt.nodes['Background']; _env = [n for n in _nt.nodes if n.type == 'TEX_ENVIRONMENT'][0]
_dim = _nt.nodes.new('ShaderNodeBackground'); _dim.inputs['Strength'].default_value = 0.035; _nt.links.new(_env.outputs['Color'], _dim.inputs['Color'])
_ray = _nt.nodes.new('ShaderNodeLightPath'); _mix = _nt.nodes.new('ShaderNodeMixShader')
_nt.links.new(_ray.outputs['Is Camera Ray'], _mix.inputs['Fac']); _nt.links.new(_bg.outputs['Background'], _mix.inputs[1]); _nt.links.new(_dim.outputs['Background'], _mix.inputs[2])
_nt.links.new(_mix.outputs['Shader'], _nt.nodes['World Output'].inputs['Surface'])

def load(asset, gltf, height=None, loc=(0, 0, 0), yaw=0.0):
    return kit.import_asset(os.path.join(ph, asset, gltf), height=height, location=loc, yaw=yaw)

# the table: a plane of wood, 1.2 m wide (the model, set at 0.74 m)
table = load('ph-WoodenTable_01', 'WoodenTable_01_2k.gltf', height=0.74, loc=(0, 0, 0))
top_z = 0.74
book = load('ph-binder_notebook', 'binder_notebook_2k.gltf', height=0.035, loc=(0.02, -0.02, top_z), yaw=math.radians(-12))
spec = load('ph-round_spectacles', 'round_spectacles_2k.gltf', height=0.045, loc=(0.26, -0.03, top_z + 0.036), yaw=math.radians(-28))
plant = load('ph-potted_plant_04', 'potted_plant_04_2k.gltf', height=0.16, loc=(0.52, 0.20, top_z), yaw=math.radians(20))
lamp = load('ph-industrial_pipe_lamp', 'industrial_pipe_lamp_2k.gltf', height=0.42, loc=(-0.45, 0.22, top_z), yaw=math.radians(35))

# the phone: leaning on the book (a block hidden behind holds it), screen toward the camera, a little turned
phone = kit.phone(kit.args('screen'), width=0.0715, height=0.1470, depth=0.0082, corner=0.011, location=(0, 0, 0))
phone.rotation_euler = (math.radians(-22), 0, math.radians(14))        # tilted back, screen up to the camera
phone.location = (-0.15, -0.045, top_z + 0.108)

hud_path = kit.args('hud', '')
if hud_path:
    bpy.ops.mesh.primitive_plane_add(size=1); hud = bpy.context.active_object; hud.name = 'hud'
    hud.location = (0.235, -0.075, top_z + 0.125); hud.scale = (0.13, 0.13, 1.0)
    hm = bpy.data.materials.new('hud'); hm.use_nodes = True; hn = hm.node_tree; hn.nodes.clear()
    tex = hn.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(hud_path)
    em = hn.nodes.new('ShaderNodeEmission'); tr = hn.nodes.new('ShaderNodeBsdfTransparent'); mx = hn.nodes.new('ShaderNodeMixShader'); out = hn.nodes.new('ShaderNodeOutputMaterial')
    hn.links.new(tex.outputs['Color'], em.inputs['Color']); hn.links.new(tex.outputs['Alpha'], mx.inputs['Fac'])
    hn.links.new(tr.outputs[0], mx.inputs[1]); hn.links.new(em.outputs[0], mx.inputs[2]); hn.links.new(mx.outputs[0], out.inputs['Surface'])
    hud.data.materials.append(hm); hud.visible_shadow = False
    for i in range(N):
        t = i / max(1, N - 1); a = max(0.0, min(1.0, (t - 0.74) / 0.10))
        em.inputs['Strength'].default_value = 6.5 * a; em.inputs['Strength'].keyframe_insert('default_value', frame=i)
        hud.scale = (0.13 * (0.9 + 0.1 * a), 0.13 * (0.9 + 0.1 * a), 1.0); hud.keyframe_insert('scale', frame=i)

# a warm lamp light on the scene and a cool rim from the window side, small: the HDRI does the rest
bpy.ops.object.light_add(type='POINT', location=(-0.45, 0.14, top_z + 0.36)); l = bpy.context.active_object; l.data.energy = 70; l.data.color = (1.0, 0.78, 0.55); l.data.shadow_soft_size = 0.05
bpy.ops.object.light_add(type='AREA', location=(0.5, -0.5, top_z + 0.5)); r = bpy.context.active_object; r.data.energy = 40; r.data.size = 0.6; r.data.color = (1.0, 0.45, 0.28)
r.rotation_euler = mathutils.Vector((-0.5, 0.5, -0.7)).to_track_quat('-Z', 'Y').to_euler()

# the camera: starts close on the phone, glides right across the book to the spectacles, focus pulled from the phone to the lenses
bpy.ops.object.camera_add(); cam = bpy.context.active_object; s.camera = cam
cam.data.lens = 50; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.8
focus = bpy.data.objects.new('focus', None); bpy.context.collection.objects.link(focus); cam.data.dof.focus_object = focus
tc = cam.constraints.new('TRACK_TO'); tc.target = focus; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
P = [  # (t, camera position, look-at)
    (0.00, (-0.22, -0.64, top_z + 0.20), (-0.14, -0.04, top_z + 0.13)),
    (0.45, (-0.12, -0.52, top_z + 0.19), (-0.12, -0.04, top_z + 0.13)),
    (0.78, (0.19, -0.37, top_z + 0.115), (0.235, -0.04, top_z + 0.075)),
    (1.00, (0.205, -0.35, top_z + 0.11), (0.24, -0.04, top_z + 0.075)),
]
def at(t):
    for (t0, c0, f0), (t1, c1, f1) in zip(P, P[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0); u = u * u * (3 - 2 * u)
            return [c0[i] + (c1[i] - c0[i]) * u for i in range(3)], [f0[i] + (f1[i] - f0[i]) * u for i in range(3)]
    return list(P[-1][1]), list(P[-1][2])
for i in range(N):
    c, f = at(i / max(1, N - 1))
    # a hand's breathing on the camera
    c = [c[0] + 0.0012 * math.sin(i * 0.31), c[1], c[2] + 0.0010 * math.sin(i * 0.23 + 1)]
    cam.location = c; cam.keyframe_insert('location', frame=i)
    focus.location = f; focus.keyframe_insert('location', frame=i)
if hud_path:
    c = hud.constraints.new('TRACK_TO'); c.target = cam; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
kit.render(kit.args('out', 'frames'))
