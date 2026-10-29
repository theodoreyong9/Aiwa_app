"""Building blocks for the 3D shot of a film. NOT scenes: functions. The shot is a short script written for the film (shots/blender/examples/ shows two), that imports an asset
(from asset-research) or makes a shape, changes it to the look of the film, stages it, moves the camera, and renders PNG frames. Blender runs headless, on the CPU (Cycles).

  import kit
  kit.reset(width=1920, height=1080, samples=48)
  obj = kit.import_asset('assets/chair/ArmChair_01_2k.gltf', height=1.0)      # a glTF / GLB / OBJ / FBX, set on the floor, centred, scaled to a height in metres
  kit.recolor(obj, '#26c6b0', mode='tint', strength=0.35)                       # to the palette of the film: tint, replace or emission
  kit.floor('gloss')                                                              # 'gloss' (dark reflective) · 'cyc' (white studio) · 'none'
  kit.light_rig('rim', target=obj, accent='#26c6b0')                              # 'studio' · 'rim' · 'daylight' · 'neon' · 'moody'   (or kit.hdri('lights/dawn_2k.hdr'))
  cam = kit.camera(lens=42, target=obj, fstop=2.6)
  kit.move(cam, 'orbit', frames=120, radius=(6, 4.5), arc=(-50, -10))             # 'dolly-in' · 'dolly-out' · 'orbit' · 'crane-up' · 'static' · 'handheld'
  kit.render('frames/', frames=120)                                               # PNG 00000.png …   (--still 40 renders only that frame, to look at it first)

Run:  python3.13 shot.py -- --out frames/ [--frames 120 --width 1920 --height 1080 --samples 48 --still 40]      (needs `pip install bpy`, Python 3.13: sh video-kit/src/shots-setup.sh)
The grade (look of the film) and the bloom are NOT done here: they are the same for every shot of the film and are applied after, by `video-kit transform`.
"""
import math, os, sys
import bpy
import mathutils


def args(name, default=None, cast=str):
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return cast(a[a.index(f'--{name}') + 1]) if f'--{name}' in a else default


def rgba(hex_or_tuple, a=1.0):
    if isinstance(hex_or_tuple, str):
        h = hex_or_tuple.lstrip('#')
        lin = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in lin]      # sRGB to linear, as Blender wants it
        return (*lin, a)
    return tuple(hex_or_tuple) if len(hex_or_tuple) == 4 else (*hex_or_tuple, a)


_state = {'frames': 1, 'fps': 30}


def reset(width=None, height=None, samples=None, fps=30, transparent=None):
    width, height, samples = width or args('width', 1920, int), height or args('height', 1080, int), samples or args('samples', 48, int)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'CYCLES'; s.cycles.device = 'CPU'; s.cycles.samples = samples; s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage, s.render.fps = width, height, 100, fps
    s.render.image_settings.file_format = 'PNG'
    transparent = args('transparent', 0, int) == 1 if transparent is None else transparent
    s.render.film_transparent = transparent; s.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'   # a shot laid over a page (assemble --clips) keeps its alpha
    names = [t.identifier for t in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items]
    s.view_settings.view_transform = 'AgX' if 'AgX' in names else 'Filmic'
    world = bpy.data.worlds.new('w'); s.world = world; world.use_nodes = True
    bg = world.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.008, 0.008, 0.02, 1); bg.inputs['Strength'].default_value = 1.0
    _state.update(frames=args('frames', 120, int), fps=fps)
    return s


def bounds(root):
    pts = []
    for o in [root, *root.children_recursive]:
        if o.type == 'MESH':
            pts += [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
    if not pts:
        raise RuntimeError('the asset has no mesh')
    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def import_asset(path, height=None, location=(0, 0, 0), yaw=0.0):
    """Import an asset, parent it to one empty, set it on the floor (z = 0), centred, scaled to `height` metres (the largest dimension if None is kept as it is)."""
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.gltf', '.glb'): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == '.obj': bpy.ops.wm.obj_import(filepath=path)
    elif ext == '.fbx': bpy.ops.import_scene.fbx(filepath=path)
    elif ext in ('.usd', '.usdc', '.usda'): bpy.ops.wm.usd_import(filepath=path)
    else: raise ValueError(f'cannot import {ext}')
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new('asset', None); bpy.context.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    bpy.context.view_layer.update()
    lo, hi = bounds(root)
    size = hi - lo
    k = (height / size.z) if height and size.z > 1e-6 else 1.0
    centre = (lo + hi) / 2
    root.scale = (k, k, k)
    root.location = (location[0] - centre.x * k, location[1] - centre.y * k, location[2] - lo.z * k)
    root.rotation_euler = (0, 0, yaw)
    bpy.context.view_layer.update()
    return root


def material(name, color, metallic=0.0, rough=0.5, emit=None, glass=False, emit_strength=6.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = rgba(color); p.inputs['Metallic'].default_value = metallic; p.inputs['Roughness'].default_value = rough
    if glass:
        p.inputs['Transmission Weight'].default_value = 1.0; p.inputs['IOR'].default_value = 1.45; p.inputs['Roughness'].default_value = 0.02
    if emit:
        p.inputs['Emission Color'].default_value = rgba(emit); p.inputs['Emission Strength'].default_value = emit_strength
    return m


def recolor(root, color, mode='tint', strength=0.4, only=None):
    """Bring an asset to the palette of the film. mode: 'tint' (mix the colour into what is there), 'replace' (the colour only), 'emission' (it glows).
    only: a word that the name of the material must contain (e.g. 'metal', 'wood'); None = all the materials of the asset."""
    c = rgba(color)
    for o in [root, *root.children_recursive]:
        if o.type != 'MESH': continue
        for slot in o.material_slots:
            m = slot.material
            if not m or not m.use_nodes or (only and only.lower() not in m.name.lower()): continue
            m.node_tree.nodes  # the shader nodes are changed in place: textures stay, the colour is mixed in
            p = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if not p: continue
            if mode == 'emission':
                p.inputs['Emission Color'].default_value = c; p.inputs['Emission Strength'].default_value = 4.0 * max(0.2, strength)
            elif mode == 'replace' or not p.inputs['Base Color'].links:
                base = p.inputs['Base Color'].default_value
                p.inputs['Base Color'].default_value = c if mode == 'replace' else tuple(base[i] * (1 - strength) + c[i] * strength for i in range(3)) + (1.0,)
            else:
                mix = m.node_tree.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'; mix.inputs['Factor'].default_value = strength; mix.inputs['B'].default_value = c
                src = p.inputs['Base Color'].links[0].from_socket
                m.node_tree.links.new(src, mix.inputs['A']); m.node_tree.links.new(mix.outputs['Result'], p.inputs['Base Color'])


def floor(kind='gloss', size=60, z=0.0, rough=None):
    if kind == 'none': return None
    bpy.ops.mesh.primitive_plane_add(size=size); f = bpy.context.active_object
    f.location = (0, 0, z - 0.001)
    f.data.materials.append(material('floor', (0.02, 0.02, 0.03) if kind == 'gloss' else (0.92, 0.92, 0.94), rough=(rough if rough is not None else (0.12 if kind == 'gloss' else 0.8))))
    return f


def _area(name, loc, energy, color, size, target):
    bpy.ops.object.light_add(type='AREA', location=loc)
    l = bpy.context.active_object; l.name = name; l.data.energy, l.data.color, l.data.size = energy, color[:3], size
    c = l.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l


def _focus(target):
    if target is None: return None
    if target.type == 'EMPTY' and target.name.startswith('asset'):
        lo, hi = bounds(target); f = bpy.data.objects.new('focus', None); bpy.context.collection.objects.link(f); f.location = (lo + hi) / 2; return f
    return target


def light_rig(style='studio', target=None, accent='#26c6b0', scale=1.0):
    t = _focus(target) or bpy.data.objects.new('t', None)
    if t.users == 0: bpy.context.collection.objects.link(t)
    a = rgba(accent); k = scale
    if style == 'studio':   _area('key', (-4 * k, -5 * k, 4.5 * k), 650, (1, .95, .9), 3 * k, t); _area('fill', (4 * k, -4 * k, 2 * k), 160, (.7, .75, 1), 4 * k, t); _area('top', (0, 0, 6 * k), 200, (1, 1, 1), 4 * k, t)
    elif style == 'rim':    _area('key', (-4 * k, -5 * k, 4.5 * k), 500, (1, .95, .9), 3 * k, t); _area('rim', (4 * k, 4 * k, 3 * k), 380, a, 2.5 * k, t); _area('fill', (3 * k, -5 * k, 1.5 * k), 140, (.6, .65, 1), 4 * k, t)
    elif style == 'daylight': _area('sun', (6 * k, -4 * k, 7 * k), 1800, (1, .93, .82), 2 * k, t); _area('sky', (-3 * k, -3 * k, 5 * k), 500, (.7, .8, 1), 8 * k, t)
    elif style == 'neon':   _area('l1', (-4 * k, -3 * k, 2 * k), 700, a, 2 * k, t); _area('l2', (4 * k, -3 * k, 2 * k), 700, (1, .25, .6), 2 * k, t); _area('back', (0, 5 * k, 3 * k), 300, (.4, .5, 1), 3 * k, t)
    elif style == 'moody':  _area('key', (-5 * k, -4 * k, 3 * k), 420, (1, .8, .6), 1.5 * k, t); _area('rim', (4 * k, 5 * k, 2 * k), 250, a, 2 * k, t)
    else: raise ValueError(f'unknown light style {style}')


def hdri(path, strength=1.0, rotation=0.0, visible=True, backdrop='#050509'):
    """The light and the reflections of a real place or studio (an HDRI). visible=False: the camera does not see it, it sees a plain dark backdrop (the picture of the studio stays out of the shot)."""
    w = bpy.context.scene.world; nt = w.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(path)
    m = nt.nodes.new('ShaderNodeMapping'); m.inputs['Rotation'].default_value[2] = rotation
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], m.inputs['Vector']); nt.links.new(m.outputs['Vector'], env.inputs['Vector'])
    bg = nt.nodes['Background']; bg.inputs['Strength'].default_value = strength; nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    if not visible:
        out = nt.nodes['World Output']
        dark = nt.nodes.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = rgba(backdrop); dark.inputs['Strength'].default_value = 1.0
        ray = nt.nodes.new('ShaderNodeLightPath'); mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(ray.outputs['Is Camera Ray'], mix.inputs['Fac']); nt.links.new(bg.outputs['Background'], mix.inputs[1]); nt.links.new(dark.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])


def camera(lens=42, target=None, fstop=2.8):
    bpy.ops.object.camera_add(); cam = bpy.context.active_object; bpy.context.scene.camera = cam
    cam.data.lens = lens
    f = _focus(target)
    if f is not None:
        cam.data.dof.use_dof = fstop is not None and fstop > 0; cam.data.dof.focus_object = f; cam.data.dof.aperture_fstop = fstop or 8
        c = cam.constraints.new('TRACK_TO'); c.target = f; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
        cam['focus'] = f.name
    return cam


def move(cam, kind='orbit', frames=None, radius=(6, 4.5), arc=(-45, -10), height=(1.4, 1.0), amount=0.02, seed=1):
    """Keyframe the camera around its target. orbit: an arc (degrees) at a distance; dolly-in/out: along the line to the target; crane-up: rises; handheld: small drift on top of a static camera."""
    frames = frames or _state['frames']
    f = bpy.data.objects[cam['focus']].location if 'focus' in cam else mathutils.Vector((0, 0, 0))
    rnd = __import__('random').Random(seed)
    for i in range(frames):
        t = i / max(1, frames - 1); e = t * t * (3 - 2 * t)
        lerp = lambda p, q, k: p + (q - p) * k
        mid = math.radians((arc[0] + arc[1]) / 2)
        if kind == 'orbit': a, r = math.radians(lerp(arc[0], arc[1], e)), lerp(radius[0], radius[1], e)
        elif kind == 'dolly-in': a, r = mid, lerp(radius[0], radius[1], e)
        elif kind == 'dolly-out': a, r = mid, lerp(radius[1], radius[0], e)
        elif kind in ('static', 'handheld', 'crane-up'): a, r = mid, radius[0]
        else: raise ValueError(f'unknown move {kind}')
        h = lerp(height[0], height[1], e) if kind != 'static' and kind != 'handheld' else height[0]
        x = f.x + math.sin(a) * r; y = f.y - math.cos(a) * r; z = f.z + h
        if kind == 'handheld': x += (rnd.random() - .5) * amount * 4; z += (rnd.random() - .5) * amount * 4
        cam.location = (x, y, z); cam.keyframe_insert('location', frame=i)


def beam(src, dst, color='#26c6b0', radius=0.3, strength=7.0):
    """A soft cone of light from a point to another (a signal, a scan, a projector). Nearly transparent, brighter toward the far end."""
    src, dst = mathutils.Vector(src), mathutils.Vector(dst); d = dst - src
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.015, radius2=radius, depth=d.length); b = bpy.context.active_object
    m = bpy.data.materials.new('beam'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = rgba(color); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.07; out = nt.nodes.new('ShaderNodeOutputMaterial')      # Fac = the share of the second shader (the light): 7 %, the rest lets the picture through
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs['Surface'])
    b.data.materials.append(m); b.location = src + d / 2; b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = d.to_track_quat('Z', 'Y'); b.visible_shadow = False
    return b


def signal(src, dst, color='#26c6b0', count=26, size=0.04, cycles=2.0, frames=None, strength=14.0):
    """A signal travelling from a point to another: small glowing beads that run along the line, growing as they go (an optical signal, a message, a scan). Opaque and cheap: no transparency to tune."""
    frames = frames or _state['frames']
    src, dst = mathutils.Vector(src), mathutils.Vector(dst)
    mat = material('signal', color, emit=color, emit_strength=strength)
    beads = []
    for i in range(count):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=16, ring_count=8); b = bpy.context.active_object
        b.data.materials.append(mat); b.visible_shadow = False; beads.append(b)
    for f in range(frames):
        for i, b in enumerate(beads):
            u = ((i / count) + cycles * f / max(1, frames - 1)) % 1.0
            b.location = src + (dst - src) * u
            b.scale = (size * (0.5 + 1.8 * u),) * 3
            b.keyframe_insert('location', frame=f); b.keyframe_insert('scale', frame=f)
    return beads


def _rounded_rect(w, h, r, seg=8):
    pts = []
    for (cx, cy), a0 in zip([(w / 2 - r, h / 2 - r), (-w / 2 + r, h / 2 - r), (-w / 2 + r, -h / 2 + r), (w / 2 - r, -h / 2 + r)], [0, 90, 180, 270]):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def phone(screen, frames=None, width=0.075, height=0.1475, depth=0.0085, corner=0.0105, color='#14141c', location=(0, 0, 0), yaw=0.0):
    """A phone standing up, its screen an IMAGE SEQUENCE: the screen of an interface drawn elsewhere (a page rendered with Chromium frame by frame) on a body of rounded
    metal and glass, lit by the scene, reflecting the HDRI. `screen` is a pattern of numbered files that go with the frames of THIS render (screen % 4d.png: the image of
    frame 0 first, one image for each frame rendered: make that list by taking the page's frames at the render's own rate). The screen faces -Y. Sizes in metres. Returns the object."""
    import bmesh
    frames = frames or _state['frames']
    bm = bmesh.new()
    pts = _rounded_rect(width, height, corner)
    face = bm.faces.new([bm.verts.new((x, -depth / 2, z)) for x, z in pts])
    if face.normal.y > 0: face.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uv = bm.loops.layers.uv.new('uv')
    for f in bm.faces:
        front = f.normal.y < -0.9 and abs(f.calc_center_median().y + depth / 2) < 1e-6
        f.material_index = 0 if front else 1
        if front:
            for l in f.loops: l[uv].uv = ((l.vert.co.x + width / 2) / width, (l.vert.co.z + height / 2) / height)
    mesh = bpy.data.meshes.new('phone'); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new('phone', mesh); bpy.context.collection.objects.link(obj)
    for f in mesh.polygons: f.use_smooth = True
    obj.location = location; obj.rotation_euler = (0, 0, math.radians(yaw))
    mat = bpy.data.materials.new('screen'); mat.use_nodes = True
    nt = mat.node_tree; p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (0, 0, 0, 1); p.inputs['Roughness'].default_value = 0.12; p.inputs['Metallic'].default_value = 0.0
    tex = nt.nodes.new('ShaderNodeTexImage')
    first = screen % 1 if '%' in screen else screen
    img = bpy.data.images.load(first); img.source = 'SEQUENCE'
    tex.image = img; tex.image_user.frame_duration = frames; tex.image_user.frame_start = 0; tex.image_user.frame_offset = 0; tex.image_user.use_auto_refresh = True
    nt.links.new(tex.outputs['Color'], p.inputs['Emission Color']); p.inputs['Emission Strength'].default_value = 1.0
    obj.data.materials.append(mat); obj.data.materials.append(material('phone-body', color, metallic=0.85, rough=0.28))
    return obj


def _ramp(nt, stops, fac):
    """A colour ramp node fed by `fac` (a socket): stops = [(position, '#hex'), ...]."""
    r = nt.nodes.new('ShaderNodeValToRGB')
    while len(r.color_ramp.elements) < len(stops): r.color_ramp.elements.new(1.0)
    for e, (pos, col) in zip(r.color_ramp.elements, stops): e.position = pos; e.color = rgba(col)
    nt.links.new(fac, r.inputs['Fac'])
    return r


def _noise(nt, scale, detail=8.0, rough=0.55):
    tc = nt.nodes.new('ShaderNodeTexCoord'); n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail; n.inputs['Roughness'].default_value = rough
    nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
    return n


def planet(kind='earth', radius=1.0, location=(0, 0, 0), spin=(25, 0), tilt=20, frames=None, seed=0.0):
    """A planet made of nothing but procedural textures (no image of any real planet): 'earth' (oceans, continents, clouds that turn faster, a thin atmosphere) or 'mars' (rust, dark plains, relief).
    It turns `spin[0]` degrees over the shot (from the left side to the right) around its tilted axis. Light it with a sun lamp (`kit.sun`). Returns the object. A rendered illustration, never presented as a photograph."""
    frames = frames or _state['frames']
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=96, ring_count=48, location=location); o = bpy.context.active_object; o.name = 'planet-' + kind
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new(kind); m.use_nodes = True; nt = m.node_tree; p = nt.nodes['Principled BSDF']
    if kind == 'earth':
        n = _noise(nt, 4.2 + seed, 7.0, 0.5)
        col = _ramp(nt, [(0.0, '#04153f'), (0.42, '#0d3f94'), (0.5, '#1c63bd'), (0.52, '#3b7f3f'), (0.6, '#6f8a45'), (0.68, '#a58f5a'), (0.76, '#e4e1d6')], n.outputs['Fac'])
        rough = _ramp(nt, [(0.0, '#303030'), (0.5, '#303030'), (0.52, '#d8d8d8'), (1.0, '#d8d8d8')], n.outputs['Fac'])
        nt.links.new(col.outputs['Color'], p.inputs['Base Color']); nt.links.new(rough.outputs['Color'], p.inputs['Roughness'])
        p.inputs['Specular IOR Level'].default_value = 0.6
    elif kind == 'mars':
        n = _noise(nt, 2.2 + seed, 10.0, 0.6)
        col = _ramp(nt, [(0.0, '#5a2418'), (0.4, '#9a3f2a'), (0.55, '#c8603f'), (0.8, '#e0a070')], n.outputs['Fac'])
        nt.links.new(col.outputs['Color'], p.inputs['Base Color']); p.inputs['Roughness'].default_value = 0.95
        b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = 0.5; b.inputs['Distance'].default_value = 0.04
        nt.links.new(n.outputs['Fac'], b.inputs['Height']); nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    else:
        raise ValueError(f'unknown planet {kind}')
    o.data.materials.append(m)
    layers = [o]
    if kind == 'earth':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.012, segments=96, ring_count=48, location=location); c = bpy.context.active_object; c.name = 'clouds'; bpy.ops.object.shade_smooth()
        cm = bpy.data.materials.new('clouds'); cm.use_nodes = True; cn = cm.node_tree; cn.nodes.clear()
        nz = _noise(cn, 3.4 + seed, 6.0, 0.62); mask = _ramp(cn, [(0.0, '#000000'), (0.52, '#000000'), (0.66, '#ffffff')], nz.outputs['Fac'])
        tr = cn.nodes.new('ShaderNodeBsdfTransparent'); df = cn.nodes.new('ShaderNodeBsdfDiffuse'); df.inputs['Color'].default_value = (1, 1, 1, 1)
        mx = cn.nodes.new('ShaderNodeMixShader'); out = cn.nodes.new('ShaderNodeOutputMaterial')
        cn.links.new(mask.outputs['Color'], mx.inputs['Fac']); cn.links.new(tr.outputs[0], mx.inputs[1]); cn.links.new(df.outputs[0], mx.inputs[2]); cn.links.new(mx.outputs[0], out.inputs['Surface'])
        c.data.materials.append(cm)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.05, segments=96, ring_count=48, location=location); a = bpy.context.active_object; a.name = 'atmosphere'; bpy.ops.object.shade_smooth()
        am = bpy.data.materials.new('atmosphere'); am.use_nodes = True; an = am.node_tree; an.nodes.clear()
        lw = an.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
        rim = _ramp(an, [(0.5, '#000000'), (0.95, '#ffffff')], lw.outputs['Fresnel'])   # Fresnel is bright at the rim, dark at the centre: a thin glow at the edge only
        em = an.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = rgba('#6aa8ff'); em.inputs['Strength'].default_value = 1.4
        tr2 = an.nodes.new('ShaderNodeBsdfTransparent'); mx2 = an.nodes.new('ShaderNodeMixShader'); out2 = an.nodes.new('ShaderNodeOutputMaterial')
        an.links.new(rim.outputs['Color'], mx2.inputs['Fac']); an.links.new(tr2.outputs[0], mx2.inputs[1]); an.links.new(em.outputs[0], mx2.inputs[2]); an.links.new(mx2.outputs[0], out2.inputs['Surface'])
        a.data.materials.append(am)
        layers += [c, a]
    for ob in layers:
        ob.rotation_euler = (math.radians(tilt), 0, 0)
    for i in range(frames):
        t = i / max(1, frames - 1)
        for ob in layers:
            k = 1.7 if ob.name == 'clouds' else 1.0
            ob.rotation_euler = (math.radians(tilt), math.radians(spin[1]), math.radians(spin[0] * t * k))
            ob.keyframe_insert('rotation_euler', frame=i)
    return o


def sun(direction=(-0.6, 0.5, -0.6), strength=4.5, color=(1, .96, .9)):
    """A sun lamp that shines along `direction` (from the upper left and the front by default: the phase of a planet seen from the camera at -Y)."""
    bpy.ops.object.light_add(type='SUN'); l = bpy.context.active_object; l.data.energy = strength; l.data.color = color; l.data.angle = math.radians(1.5)
    l.rotation_euler = mathutils.Vector(direction).to_track_quat('-Z', 'Y').to_euler()
    return l


def render(out_dir, frames=None):
    frames = frames or _state['frames']
    os.makedirs(out_dir, exist_ok=True)
    s = bpy.context.scene; s.frame_start, s.frame_end = 0, frames - 1
    still = args('still', None, int)
    rng = [still] if still is not None else range(frames)
    for f in rng:
        path = os.path.join(out_dir, '%05d.png' % f)
        if still is None and os.path.exists(path) and os.path.getsize(path) > 0 and not os.path.exists(path + '.part'):
            continue   # a render that was cut short starts again where it stopped
        open(path + '.part', 'w').close()
        s.frame_set(f); s.render.filepath = path; bpy.ops.render.render(write_still=True)
        os.remove(path + '.part')
    print('frames', len(list(rng)), 'in', out_dir)
