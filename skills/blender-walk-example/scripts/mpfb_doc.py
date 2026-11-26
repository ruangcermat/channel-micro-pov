# "Doc" built with MPFB2 (MakeHuman for Blender, CC0 assets) - the method from Mr Omi's video.
# Run: blender -b --factory-startup -P mpfb_doc.py -- <out_dir> <samples> <views> <width>
import bpy, sys, os, math, addon_utils, colorsys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders")
SAMPLES = int(argv[1]) if len(argv) > 1 else 32
VIEWS = argv[2].split(",") if len(argv) > 2 else ["front", "face"]
BG_EMIT = float(os.environ.get("BG_EMIT", "0.10"))
RESW = int(argv[3]) if len(argv) > 3 else 540
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.faceservice import FaceService
from bl_ext.blender_org.mpfb.services.objectservice import ObjectService

scene = bpy.context.scene

# ---------------------------------------------------------------- outfit texture: navy jacket, black tee, dark jeans
SUIT = "male_casualsuit02"                       # long-sleeve top + jeans -> repainted as zip hoodie
DST = os.path.join(HERE, "tex", SUIT + "_hoodie.png")

# ---------------------------------------------------------------- human
info = HumanService._create_default_human_info_dict()
info["phenotype"].update({"gender": 1.0, "age": 0.45, "muscle": 0.5, "weight": 0.42, "height": 0.5,
                          "proportions": 0.6, "race": {"caucasian": 0.9, "asian": 0.05, "african": 0.05}})
T = lambda n, v: {"target": n, "value": v}
info["targets"] = [
    T("r-eye-scale-incr", 0.3), T("l-eye-scale-incr", 0.3),
    T("head-oval", 0.4), T("chin-prominent-incr", 0.3), T("chin-width-incr", 0.15),
    T("r-cheek-bones-incr", 0.35), T("l-cheek-bones-incr", 0.35), T("nose-hump-decr", 0.3),
]
info["rig"] = "default"
info["eyes"] = "high-poly/high-poly.mhclo"
info["eyebrows"] = "eyebrow001/eyebrow001.mhclo"
info["eyelashes"] = "eyelashes01/eyelashes01.mhclo"
info["teeth"] = "teeth_base/teeth_base.mhclo"
info["tongue"] = "tongue01/tongue01.mhclo"
info["hair"] = "short02/short02.mhclo"
info["clothes"] = [SUIT + "/" + SUIT + ".mhclo", "shoes05/shoes05.mhclo"]
info["skin_mhmat"] = "young_caucasian_male2/young_caucasian_male2.mhmat"
info["skin_material_type"] = "ENHANCED_SSS"
settings = HumanService.get_default_deserialization_settings()
settings["scale"] = 0.1
body = HumanService.deserialize_from_dict(info, settings)
print("BODY", body.name, body.dimensions)

# friendly "talking to camera" face (ARKit face units from faceunits01)
FaceService.set_expression(body, {"jawOpen": 0.08, "mouthSmileLeft": 0.35, "mouthSmileRight": 0.35,
                                  "browOuterUpLeft": 0.35, "browOuterUpRight": 0.35, "cheekSquintLeft": 0.2, "cheekSquintRight": 0.2})
# load the blink shapes into the file (so they work later without the add-on), resting open
FaceService.set_expression(body, {"eyeBlinkLeft": 0.01, "eyeBlinkRight": 0.01})
for kb in body.data.shape_keys.key_blocks:
    if "eyeBlink" in kb.name: kb.value = 0.0; print("BLINKKEY", kb.name)

# ---------------------------------------------------------------- swap in our recoloured outfit texture
if os.path.exists(DST):
    img = bpy.data.images.load(DST, check_existing=True)
    for ob in bpy.data.objects:
        for slot in getattr(ob, "material_slots", []):
            m = slot.material
            if not m or not m.node_tree: continue
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image and "casualsuit02_diffuse" in n.image.filepath:
                    n.image = img; print("RETEXTURED", ob.name)
                if n.type == "TEX_IMAGE" and n.image and "casualsuit02_normal" in n.image.filepath:
                    nimg = bpy.data.images.load(os.path.join(HERE, "tex", "male_casualsuit02_normal_flat.png"), check_existing=True)
                    nimg.colorspace_settings.name = "Non-Color"; n.image = nimg; print("RENORMAL", ob.name)

# ---------------------------------------------------------------- relaxed pose: arms down from the A-pose
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm:
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    names = [b.name for b in arm.pose.bones]
    print("BONES", [n for n in names if "arm" in n.lower() or "shoulder" in n.lower()][:20])
    def rot_world(pb, axis, deg):
        bpy.context.view_layer.update()
        head = arm.matrix_world @ pb.head
        R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
        pb.matrix = arm.matrix_world.inverted() @ R @ arm.matrix_world @ pb.matrix
        bpy.context.view_layer.update()
    for side, s in (("L", 1), ("R", -1)):
        ua = next((arm.pose.bones[n] for n in names if n.lower().startswith("upperarm01") and n.endswith("." + side)), None)
        fa = next((arm.pose.bones[n] for n in names if n.lower().startswith("lowerarm01") and n.endswith("." + side)), None)
        if ua: rot_world(ua, "Y", s * 50)          # bring arm down to the side
        ul = next((arm.pose.bones[n] for n in names if n.lower().startswith("upperleg01") and n.endswith("." + side)), None)
        if ul: rot_world(ul, "Y", s * 5)           # feet closer together
        if fa: rot_world(fa, "Y", -s * 22)          # forearms hang by the thighs, not in front
    bpy.ops.object.mode_set(mode="OBJECT")

# ---------------------------------------------------------------- hood: rolled fleece collar + folded hood behind the neck
import bmesh
def ellipsoid_bm(bm, c, r, rot=(0, 0, 0)):
    tmp = bmesh.new(); bmesh.ops.create_uvsphere(tmp, u_segments=32, v_segments=16, radius=1.0)
    from mathutils import Euler
    M = Matrix.Translation(c) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((r[0], r[1], r[2], 1))
    bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
    me_t = bpy.data.meshes.new("t"); tmp.to_mesh(me_t); tmp.free(); bm.from_mesh(me_t); bpy.data.meshes.remove(me_t)
if arm and "neck01" in arm.pose.bones:
    bpy.context.view_layer.update()
    P = arm.matrix_world @ arm.pose.bones["neck01"].head
    print("NECK", P)
    bm = bmesh.new()
    # collar roll: ring of blobs around the neck, front dips down to the zip
    for i in range(28):
        a = 2 * math.pi * i / 28
        x, y = math.sin(a) * 0.088, -math.cos(a) * 0.078 + 0.012
        front = max(0.0, math.cos(a))               # 1 at the front
        z = -0.035 * front ** 2 + 0.012 * (1 - front)
        ellipsoid_bm(bm, P + Vector((x, y, z - 0.016)), (0.024, 0.024, 0.02 - 0.006 * front))
    # folded hood lying on the upper back
    ellipsoid_bm(bm, P + Vector((0, 0.085, -0.035)), (0.115, 0.045, 0.085), rot=(math.radians(-18), 0, 0))
    ellipsoid_bm(bm, P + Vector((0, 0.105, -0.075)), (0.09, 0.035, 0.06), rot=(math.radians(-25), 0, 0))
    me = bpy.data.meshes.new("Hood"); bm.to_mesh(me); bm.free()
    hood = bpy.data.objects.new("Hood", me); scene.collection.objects.link(hood)
    bpy.ops.object.select_all(action="DESELECT"); hood.select_set(True); bpy.context.view_layer.objects.active = hood
    m = hood.modifiers.new("rm", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.005
    bpy.ops.object.modifier_apply(modifier="rm")
    m = hood.modifiers.new("sm", "SMOOTH"); m.factor = 0.6; m.iterations = 8
    bpy.ops.object.modifier_apply(modifier="sm")
    me.shade_smooth()
    hm = bpy.data.materials.new("HoodFleece"); hb = hm.node_tree.nodes["Principled BSDF"]
    hb.inputs["Base Color"].default_value = (0.012, 0.017, 0.045, 1); hb.inputs["Roughness"].default_value = 0.95
    hb.inputs["Sheen Weight"].default_value = 0.1
    nt = hm.node_tree; nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 400
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.15
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], hb.inputs["Normal"])
    me.materials.append(hm)
    mw = hood.matrix_world.copy()
    hood.parent = arm; hood.parent_type = "BONE"; hood.parent_bone = "neck01"
    bpy.context.view_layer.update(); hood.matrix_world = mw

# ---------------------------------------------------------------- skin: matte, pores (print the node layout so we can tune it)
def walk(nt, depth=0):
    for n in nt.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Roughness"].default_value = max(n.inputs["Roughness"].default_value, 0.52)
            n.inputs["Coat Weight"].default_value = 0.0
            print("SKIN principled tuned", depth)
        if n.type == "GROUP" and n.node_tree: walk(n.node_tree, depth + 1)
for slot in body.material_slots:
    if slot.material and slot.material.node_tree:
        print("SKINMAT", slot.material.name, [n.type for n in slot.material.node_tree.nodes][:20])
        walk(slot.material.node_tree)

# ---------------------------------------------------------------- studio
import bmesh
rig = bpy.data.objects.new("ViewRig", None); scene.collection.objects.link(rig)
bg_m = bpy.data.materials.new("Backdrop")
bsdf = bg_m.node_tree.nodes["Principled BSDF"]
ZB = (0.085, 0.371, 0.730, 1)   # Zack blue, sRGB 82,164,222 (measured in the tutorial)
bsdf.inputs["Base Color"].default_value = tuple(c * 0.55 for c in ZB[:3]) + (1,); bsdf.inputs["Roughness"].default_value = 0.95
bsdf.inputs["Emission Color"].default_value = ZB; bsdf.inputs["Emission Strength"].default_value = BG_EMIT
bm = bmesh.new(); prof = [(-6 + i * 0.5, 0.0) for i in range(12)]
for i in range(13):
    a = math.pi / 2 * i / 12; prof.append((1.0 + 2.5 * math.sin(a), 2.5 - 2.5 * math.cos(a)))
for i in range(1, 6): prof.append((3.5, 2.5 + i * 1.2))
cols = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in [-9 + i for i in range(19)]]
for a, b in zip(cols, cols[1:]):
    for j in range(len(prof) - 1): bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
me = bpy.data.meshes.new("Backdrop"); bm.to_mesh(me); bm.free(); me.shade_smooth()
bd = bpy.data.objects.new("Backdrop", me); scene.collection.objects.link(bd); me.materials.append(bg_m); bd.parent = rig

def area(name, loc, size, energy, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.size = size; l.energy = energy; l.color = color
    o = bpy.data.objects.new(name, l); scene.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 1.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); o.parent = rig
area("Key", (-2.2, -2.8, 3.0), 2.2, 420, (1.0, 0.90, 0.80))
area("Fill", (2.6, -2.2, 1.6), 3.0, 110, (0.85, 0.93, 1.0))
area("Rim", (1.4, 2.0, 2.6), 1.2, 160, (0.9, 1.0, 1.0))
area("RimL", (-1.6, 1.8, 2.2), 1.2, 100, (0.9, 1.0, 1.0))
world = bpy.data.worlds.new("W"); scene.world = world
wbg = world.node_tree.nodes.get("Background")
wbg.inputs["Color"].default_value = (0.2, 0.55, 0.7, 1); wbg.inputs["Strength"].default_value = 0.2

cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam)
scene.camera = cam; cam.parent = rig
H = body.dimensions.z if body.dimensions.z > 0.5 else 1.75
def set_view(name):
    ang = {"front": 0, "threequarter": -35, "side": -90, "back": 180, "face": -10}[name]
    rig.rotation_euler = (0, 0, math.radians(ang))
    if name == "face":
        cam_d.lens = 85; cam.location = (0, -1.4, H * 0.90); tgt = Vector((0, 0, H * 0.895))
    else:
        cam_d.lens = 70; cam.location = (0, -4.6, H * 0.58); tgt = Vector((0, 0, H * 0.52))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()

r = scene.render; r.engine = "CYCLES"
r.resolution_x = RESW; r.resolution_y = int(RESW * 1.6)
scene.cycles.device = "CPU"; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
# keep the blue saturated but stop highlights burning to white (AgX + punchy look)
# keeps the blue's hue/saturation like Standard, but rolls highlights off instead of clipping
try: scene.view_settings.view_transform = "Khronos PBR Neutral"
except Exception as e: print("VT", e); scene.view_settings.view_transform = "AgX"
r.use_motion_blur = True

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "doc_mpfb.blend"))
for v in VIEWS:
    set_view(v); r.filepath = os.path.join(OUT, f"mpfb_{v}.png")
    bpy.ops.render.render(write_still=True); print("RENDERED", r.filepath)
