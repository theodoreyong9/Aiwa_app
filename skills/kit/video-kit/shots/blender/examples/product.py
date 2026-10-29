"""An example of a shot script (one among the ways to use kit.py): an object on a dark gloss floor, a rim light in the accent colour, a slow orbit, a shallow depth of field.
Without --asset, a made-up stand-in (a rounded block with a glowing line) is used, so the script always runs.

  python3.13 product.py -- --out frames/ [--asset path/to/model.glb --size 1.0 --accent 26c6b0 --frames 120 --still 40 --width 960 --height 540 --samples 24]
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy
import kit

kit.reset()
asset = kit.args('asset', None)
accent = '#' + kit.args('accent', '26c6b0')
if asset:
    obj = kit.import_asset(asset, height=kit.args("size", 1.0, float))
    kit.recolor(obj, accent, mode='tint', strength=0.25)
else:
    bpy.ops.mesh.primitive_cube_add(size=1); b = bpy.context.active_object
    b.scale = (1.2, 0.7, 0.5); b.location = (0, 0, 0.25)
    mod = b.modifiers.new('bevel', 'BEVEL'); mod.width = 0.12; mod.segments = 6
    b.data.materials.append(kit.material('body', '#101018', metallic=0.4, rough=0.3))
    bpy.ops.mesh.primitive_cube_add(size=1); g = bpy.context.active_object
    g.scale = (0.9, 0.02, 0.03); g.location = (0, -0.36, 0.3); g.data.materials.append(kit.material('line', accent, emit=accent))
    obj = bpy.data.objects.new('asset', None); bpy.context.collection.objects.link(obj)
    for o in (b, g): o.parent = obj
kit.floor('gloss')
kit.light_rig('rim', target=obj, accent=accent)
cam = kit.camera(lens=50, target=obj, fstop=2.6)
kit.move(cam, 'orbit', radius=(4.5, 3.4), arc=(-50, -15), height=(1.2, 0.8))
kit.render(kit.args('out', 'frames'))
