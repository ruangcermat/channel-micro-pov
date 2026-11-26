# Adds the living room (sofa, TV, backpack with the F test) next to the kitchen, inside renders/kitchen.blend.
# The room is appended from renders/doc_room.blend (without Doc), shifted to x+12, plus a flat TV on a low cabinet.
# Run: blender -b renders/kitchen.blend -P living_room.py -- <out_png|none> <samples> <width>
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "none"; SAMPLES = int(argv[1]) if len(argv) > 1 else 20; WIDTH = int(argv[2]) if len(argv) > 2 else 540
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, "assets")
sc = bpy.context.scene
OFF = Vector((12.0, 0.0, 0.0))
SKIP = ("Human", "Hood", "IK_", "FootRot_", "Cam", "Sun", "ViewRig", "SkyCard")
with bpy.data.libraries.load(os.path.join(HERE, "renders", "doc_room.blend"), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if not n.startswith(SKIP)]
added = []
for o in dst.objects:
    if o is None or o.type == "ARMATURE": continue
    if o.parent and o.parent.type == "ARMATURE": continue
    sc.collection.objects.link(o); added.append(o)
for o in added:
    if o.parent is None or o.parent not in added: o.parent = None; o.location = o.location + OFF
    o.name = "LR_" + o.name
print("LIVING ROOM objects", len(added))

def plain(name, col, rough=0.5, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name); b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if emit: b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = emit
    return m
def box(name, c, s, mat, bevel=0.2):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)), verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat)
    if bevel:
        bv = ob.modifiers.new("b", "BEVEL"); bv.width = min(min(s) * bevel, 0.01); bv.segments = 2
    return ob
def place(asset, loc, rot_z=0.0, scale=1.0, name=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, asset, asset + ".gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name or ("P_" + asset), None); sc.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.location = loc; root.rotation_euler = (0, 0, math.radians(rot_z)); root.scale = (scale,) * 3
    return root

# front wall (the TV wall) - the room was open on the camera side
wm = next((m for m in bpy.data.materials if m.name.startswith("Wall")), None)
bm = bmesh.new(); pts = [(OFF.x - 2.4, -3.2, 0), (OFF.x + 2.4, -3.2, 0), (OFF.x + 2.4, -3.2, 2.7), (OFF.x - 2.4, -3.2, 2.7)]
vs = [bm.verts.new(p) for p in pts]; f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
for l in f.loops: l[uv].uv = (l.vert.co.x, l.vert.co.z)
me = bpy.data.meshes.new("LR_WallF"); bm.to_mesh(me); bm.free(); wf = bpy.data.objects.new("LR_WallF", me); sc.collection.objects.link(wf)
me.materials.append(wm or plain("LRWall", (0.9, 0.85, 0.75), 0.8))

# TV on a low cabinet, facing the sofa
TVX = OFF.x + 1.15
place("modern_wooden_cabinet", (TVX, -2.92, 0), 0, 0.75, name="TVCabinet")
box("TVFrame", (TVX, -2.86, 1.12), (1.3, 0.05, 0.76), plain("TVBlack", (0.015, 0.015, 0.018), 0.25), 0.1)
box("TVFoot", (TVX, -2.86, 0.6), (0.36, 0.2, 0.02), plain("TVBlack2", (0.02, 0.02, 0.02), 0.3), 0.2)
box("TVNeck", (TVX, -2.87, 0.68), (0.06, 0.03, 0.16), plain("TVBlack3", (0.02, 0.02, 0.02), 0.3), 0.2)
# screen: emissive image (cartoon), image sequence of 3 drawings
sm = bpy.data.materials.new("TVScreen"); nt = sm.node_tree; bsdf = nt.nodes["Principled BSDF"]
tx = nt.nodes.new("ShaderNodeTexImage"); img = bpy.data.images.load(os.path.join(HERE, "tex", "tvshow_01.png"))
img.source = "SEQUENCE"; tx.image = img; tx.image_user.frame_duration = 3; tx.image_user.use_cyclic = True; tx.image_user.use_auto_refresh = True
tx.image_user.frame_start = 1; tx.image_user.frame_offset = 0
nt.links.new(tx.outputs["Color"], bsdf.inputs["Base Color"]); nt.links.new(tx.outputs["Color"], bsdf.inputs["Emission Color"])
bsdf.inputs["Emission Strength"].default_value = 2.2; bsdf.inputs["Roughness"].default_value = 0.15
bm = bmesh.new(); w, h = 1.24, 0.70
vs = [bm.verts.new((TVX + x, -2.832, 1.12 + z)) for x, z in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
f = bm.faces.new(vs); uvl = bm.loops.layers.uv.new()
for l, c in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]): l[uvl].uv = c
me = bpy.data.meshes.new("TVScreen"); bm.to_mesh(me); bm.free(); scr = bpy.data.objects.new("TVScreen", me); sc.collection.objects.link(scr); me.materials.append(sm)
tvl = bpy.data.lights.new("TVGlow", "AREA"); tvl.size = 1.2; tvl.energy = 45; tvl.color = (0.7, 0.85, 1.0)
tvo = bpy.data.objects.new("TVGlow", tvl); sc.collection.objects.link(tvo); tvo.location = (TVX, -2.75, 1.12)
tvo.rotation_euler = (Vector((TVX, 0.8, 0.8)) - tvo.location).to_track_quat("-Z", "Y").to_euler()

# backpack on the sofa next to where the kid sits, the F test poking out
SOFA = Vector((OFF.x + 1.15, 1.08, 0))
bp = box("SofaBackpack", (SOFA.x + 0.62, SOFA.y - 0.1, 0.76), (0.3, 0.17, 0.38), plain("BackpackFab2", (0.12, 0.25, 0.55), 0.8), 0.45)
bp.modifiers.new("s", "SUBSURF").levels = 2; bp.rotation_euler = (math.radians(-12), 0, math.radians(8))
box("BackpackPocket", (SOFA.x + 0.62, SOFA.y - 0.205, 0.7), (0.22, 0.04, 0.16), plain("Pocket", (0.08, 0.18, 0.42), 0.8), 0.4)
pm = bpy.data.materials.new("PaperLR"); pn = pm.node_tree; pt = pn.nodes.new("ShaderNodeTexImage")
pt.image = bpy.data.images.load(os.path.join(HERE, "tex", "math_test.png"))
pn.links.new(pt.outputs["Color"], pn.nodes["Principled BSDF"].inputs["Base Color"])
bm = bmesh.new(); pw, ph = 0.2, 0.26
vs = [bm.verts.new((x, 0, z)) for x, z in ((-pw / 2, 0), (pw / 2, 0), (pw / 2, ph), (-pw / 2, ph))]
f = bm.faces.new(vs); uvl = bm.loops.layers.uv.new()
for l, c in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]): l[uvl].uv = c
me = bpy.data.meshes.new("BagTest"); bm.to_mesh(me); bm.free(); bt = bpy.data.objects.new("BagTest", me); sc.collection.objects.link(bt); me.materials.append(pm)
bt.location = (SOFA.x + 0.63, SOFA.y - 0.19, 0.84); bt.rotation_euler = (math.radians(-18), 0, math.radians(8))
# remote control
box("Remote", (OFF.x + 0.0, 0, 0), (0.045, 0.16, 0.02), plain("RemoteBlack", (0.03, 0.03, 0.035), 0.4), 0.3)
# sofa seat height for the kid
bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
hits = []
for dx in (-0.62, -0.55, -0.48):
    hit, loc, *_ = sc.ray_cast(dg, Vector((SOFA.x + dx, SOFA.y - 0.22, 1.2)), Vector((0, 0, -1)))
    if hit: hits.append(loc.z)
sc["sofa_seat_z"] = sorted(hits)[len(hits) // 2] if hits else 0.5; sc["sofa_pos"] = list(SOFA); sc["tv_pos"] = [TVX, -2.832, 1.12]
print("SOFA SEAT", sc["sofa_seat_z"], hits)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "kitchen.blend"))
if OUT != "none":
    cam = bpy.data.objects["Cam"]; cam.data.lens = 22
    cam.location = (OFF.x + 0.2, -2.6, 1.45); cam.rotation_euler = (Vector((OFF.x + 0.9, 1.0, 0.75)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    r = sc.render; r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2; sc.cycles.samples = SAMPLES
    r.filepath = os.path.abspath(OUT); bpy.ops.render.render(write_still=True); print("RENDERED", r.filepath)
