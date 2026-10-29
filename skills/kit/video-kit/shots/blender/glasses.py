"""A product shot of smart glasses, in real 3D (Blender, Cycles, on the CPU): matte frame, glass lenses, a small optical module that glows and sends a beam toward a second pair
in the distance; a slow camera move with a shallow depth of field over a dark reflective floor. Everything is procedural: no model, no texture, no download.

  python3.13 glasses.py --out frames/ [--frames 120 --fps 30 --width 1920 --height 1080 --samples 48 --accent 26c6b0 --seconds 4]
  (needs the `bpy` package: pip install bpy; Python 3.13)

The frames are PNG files 00000.png … ; the film uses them as a full-frame clip (video-kit assemble --clips). A frame of 1920x1080 at 48 samples takes about 10 to 25 s on 4 CPU cores:
render a few frames first (--frames 3 --width 640 --height 360 --samples 16) to look at the picture before the whole shot.
"""
import math, os, sys
import bpy


def arg(name, default, cast=str):
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return cast(a[a.index(f'--{name}') + 1]) if f'--{name}' in a else default


OUT = arg('out', 'frames')
N = arg('frames', 120, int)
FPS = arg('fps', 30, int)
W, H = arg('width', 1920, int), arg('height', 1080, int)
SAMPLES = arg('samples', 48, int)
ACCENT = arg('accent', '26c6b0')
accent = tuple(int(ACCENT[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.fps = FPS
scene.render.image_settings.file_format = 'PNG'
scene.frame_start, scene.frame_end = 0, max(0, N - 1)
scene.view_settings.view_transform = 'Filmic' if 'Filmic' in [t.identifier for t in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items] else 'AgX'


def material(name, color, metallic=0.0, rough=0.5, emit=None, glass=False, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n = m.node_tree.nodes
    p = n['Principled BSDF']
    p.inputs['Base Color'].default_value = color
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    if glass:
        p.inputs['Transmission Weight'].default_value = 1.0
        p.inputs['IOR'].default_value = 1.45
        p.inputs['Roughness'].default_value = 0.02
    if emit:
        p.inputs['Emission Color'].default_value = emit
        p.inputs['Emission Strength'].default_value = 6.0
    return m


def put(obj, mat, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), smooth=True):
    obj.location, obj.rotation_euler, obj.scale = loc, rot, scale
    obj.data.materials.append(mat)
    if smooth:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


frame_mat = material('frame', (0.015, 0.015, 0.02, 1), metallic=0.3, rough=0.32)
glass_mat = material('glass', (0.6, 0.8, 0.85, 1), glass=True)
floor_mat = material('floor', (0.02, 0.02, 0.03, 1), metallic=0.0, rough=0.12)
glow_mat = material('glow', accent, emit=accent)


def glasses(scale=1.0, origin=(0, 0, 0), yaw=0.0, glow=accent):
    """One pair, front plane at y = 0 facing -y, temples going back to +y."""
    parts = []
    gm = material('glow%s' % id(origin), glow, emit=glow)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.62, minor_radius=0.055, major_segments=64, minor_segments=24)
        parts.append(put(bpy.context.active_object, frame_mat, (side * 0.78, 0, 0), (math.pi / 2, 0, 0), (1, 1, 0.82)))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.60, depth=0.02, vertices=64)
        parts.append(put(bpy.context.active_object, glass_mat, (side * 0.78, 0, 0), (math.pi / 2, 0, 0), (1, 0.82, 1)))
        bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=1.9, vertices=16)
        parts.append(put(bpy.context.active_object, frame_mat, (side * 1.42, 0.95, 0.08), (math.pi / 2, 0, 0)))
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.04, major_segments=32, minor_segments=16)
    parts.append(put(bpy.context.active_object, frame_mat, (0, 0, 0.18), (math.pi / 2, 0, 0), (1, 1, 0.8)))
    bpy.ops.mesh.primitive_cube_add(size=1)
    module = put(bpy.context.active_object, gm, (1.45, 0.12, 0.14), (0, 0, 0), (0.2, 0.34, 0.08), smooth=False)
    parts.append(module)
    root = bpy.data.objects.new('pair', None)
    bpy.context.collection.objects.link(root)
    for p in parts:
        p.parent = root
    root.location, root.rotation_euler, root.scale = origin, (0, 0, yaw), (scale,) * 3
    return root, module


pair_a, module_a = glasses(1.0, (0, 0, 0.7), yaw=math.radians(-18))
pair_b, _ = glasses(0.55, (4.2, 5.0, 0.55), yaw=math.radians(160), glow=(1.0, 0.45, 0.3, 1.0))

# the beam: a soft cone from the module toward the second pair, nearly transparent, glowing at the far end
import mathutils
bpy.context.view_layer.update()
src = pair_a.matrix_world @ mathutils.Vector((1.45, 0.12, 0.14))
dst = pair_b.matrix_world @ mathutils.Vector((0.0, 0.0, 0.0))
d = dst - src
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.015, radius2=0.32, depth=d.length)
beam = bpy.context.active_object
bm = bpy.data.materials.new('beam'); bm.use_nodes = True
nt = bm.node_tree; nt.nodes.clear()
em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = accent; em.inputs['Strength'].default_value = 0.9
tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.93
out = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
beam.data.materials.append(bm)
beam.location = src + d / 2
beam.rotation_mode = 'QUATERNION'
beam.rotation_quaternion = d.to_track_quat('Z', 'Y')
beam.visible_shadow = False

bpy.ops.mesh.primitive_plane_add(size=40)
put(bpy.context.active_object, floor_mat, (0, 3, -0.02), smooth=False)

# world: a very dark blue, with a faint horizon glow
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.008, 0.008, 0.02, 1); bg.inputs['Strength'].default_value = 1.0

def area(name, loc, energy, color, size, target):
    bpy.ops.object.light_add(type='AREA', location=loc)
    l = bpy.context.active_object; l.name = name; l.data.energy, l.data.color, l.data.size = energy, color, size
    c = l.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l

focus = bpy.data.objects.new('focus', None); bpy.context.collection.objects.link(focus); focus.location = (1.9, 1.2, 0.8)
area('key', (-4, -5, 4.5), 650, (1.0, 0.95, 0.9), 3.0, focus)
area('rim', (4, 4, 3), 380, accent[:3], 2.5, focus)
area('fill', (3, -5, 1.5), 140, (0.6, 0.65, 1.0), 4.0, focus)

bpy.ops.object.camera_add()
cam = bpy.context.active_object; scene.camera = cam
cam.data.lens = 42; cam.data.dof.use_dof = True; cam.data.dof.focus_object = focus; cam.data.dof.aperture_fstop = 2.6
tc = cam.constraints.new('TRACK_TO'); tc.target = focus; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
for f in range(N):
    t = f / max(1, N - 1)
    e = t * t * (3 - 2 * t)                      # ease in and out
    ang = math.radians(-48 + 30 * e)
    r = 11.5 - 2.2 * e
    cam.location = (math.sin(ang) * r + 0.4, -math.cos(ang) * r, 1.7 - 0.4 * e)
    cam.keyframe_insert('location', frame=f)
    # the module breathes
    module_a.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 5 + 3 * math.sin(t * math.pi * 6)
    module_a.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].keyframe_insert('default_value', frame=f)
scene.render.filepath = os.path.join(OUT, '')
scene.render.use_file_extension = True
for f in range(N):
    scene.frame_set(f)
    scene.render.filepath = os.path.join(OUT, '%05d.png' % f)
    bpy.ops.render.render(write_still=True)
print('frames', N, 'in', OUT)
