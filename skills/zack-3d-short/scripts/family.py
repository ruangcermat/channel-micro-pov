# Mom + kid for the kitchen short, built with MPFB2 (CC0) like Doc. Relaxed arms, blink keys,
# expression test renders. Run:
#   blender -b --factory-startup -P family.py -- <out_dir> <samples> <width> <views>
# views: pair (both full body), mom_<expr>, kid_<expr>  e.g. pair,mom_neutral,kid_shock
import bpy, sys, os, math, addon_utils
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders/family")
SAMPLES = int(argv[1]) if len(argv) > 1 else 32
RESW = int(argv[2]) if len(argv) > 2 else 720
VIEWS = argv[3].split(",") if len(argv) > 3 else ["pair"]
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE); import doc_pose as D

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
from bl_ext.blender_org.mpfb.services.humanservice import HumanService
from bl_ext.blender_org.mpfb.services.faceservice import FaceService
scene = bpy.context.scene

# expressions in ARKit face units (MPFB faceunits01)
def sym(**kw):
    out = {}
    for k, v in kw.items():
        if k.endswith("_"):
            out[k[:-1] + "Left"] = v; out[k[:-1] + "Right"] = v
        else: out[k] = v
    return out
EXPR = {
    "neutral": sym(mouthSmile_=0.12),
    "happy":   sym(mouthSmile_=0.75, cheekSquint_=0.45, eyeSquint_=0.25, browOuterUp_=0.2, jawOpen=0.12),
    "shock":   sym(eyeWide_=0.9, browInnerUp=0.9, browOuterUp_=0.8, jawOpen=0.55, mouthFunnel=0.25),
    "panic":   sym(eyeWide_=0.8, browInnerUp=1.0, mouthStretch_=0.6, mouthFrown_=0.4, jawOpen=0.2, mouthLowerDown_=0.4),
    "guilty":  sym(browInnerUp=0.7, mouthFrown_=0.5, mouthPress_=0.45, eyeLookDown_=0.55, mouthRollLower=0.3, mouthStretch_=0.2),
    "crying":  sym(browInnerUp=1.0, browDown_=0.15, eyeSquint_=0.7, mouthFrown_=0.8, mouthStretch_=0.35, cheekSquint_=0.5,
                   jawOpen=0.18, mouthLowerDown_=0.35, noseSneer_=0.3),
    "angry":   sym(browDown_=0.65, eyeSquint_=0.35, eyeWide_=0.15, noseSneer_=0.6, mouthPress_=0.4, mouthFrown_=0.4, mouthStretch_=0.25, jawForward=0.15),
    "relieved": sym(mouthSmile_=0.45, browInnerUp=0.35, eyeBlink_=0.35, cheekSquint_=0.2),
}

T = lambda n, v: {"target": n, "value": v}
def make(name, pheno, targets, hair, brows, suit, shoes, skin, tex):
    info = HumanService._create_default_human_info_dict()
    info["phenotype"].update(pheno)
    info["targets"] = targets
    info["rig"] = "default"
    info["eyes"] = "high-poly/high-poly.mhclo"; info["eyebrows"] = f"{brows}/{brows}.mhclo"
    info["eyelashes"] = "eyelashes01/eyelashes01.mhclo"; info["teeth"] = "teeth_base/teeth_base.mhclo"
    info["tongue"] = "tongue01/tongue01.mhclo"; info["hair"] = f"{hair}/{hair}.mhclo"
    info["clothes"] = [f"{suit}/{suit}.mhclo", f"{shoes}/{shoes}.mhclo"]
    info["skin_mhmat"] = f"{skin}/{skin}.mhmat"; info["skin_material_type"] = "ENHANCED_SSS"
    st = HumanService.get_default_deserialization_settings(); st["scale"] = 0.1
    before = set(bpy.data.objects)
    body = HumanService.deserialize_from_dict(info, st)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    arm.name = name + "_rig"; body.name = name + "_body"
    # our painted tee texture (only on this character's garment)
    img = bpy.data.images.load(os.path.join(HERE, "tex", tex), check_existing=True)
    for o in new:
        for sl in getattr(o, "material_slots", []):
            m = sl.material
            if m and m.node_tree and suit in m.name.lower() + " " + " ".join(n.image.filepath.lower() for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image):
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and "diffuse" in n.image.filepath.lower():
                        n.image = img; print("TEX", name, o.name)
    # skinny jeans: push the cloth out 6 mm so the sock tops never poke through at the ankles
    for o in new:
        if o.type == "MESH" and suit in o.name.lower():
            dm = o.modifiers.new("ClothOut", "DISPLACE"); dm.strength = 0.006; dm.mid_level = 0.0
    # skin: matte
    def walk(nt):
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Roughness"].default_value = max(n.inputs["Roughness"].default_value, 0.5)
                n.inputs["Coat Weight"].default_value = 0.0
            if n.type == "GROUP" and n.node_tree: walk(n.node_tree)
    for sl in body.material_slots:
        if sl.material and sl.material.node_tree: walk(sl.material.node_tree)
    # load every face unit we use so the shape keys exist, then reset
    allk = {}
    for e in EXPR.values(): allk.update({k: 0.01 for k in e})
    allk.update({"eyeBlinkLeft": 0.01, "eyeBlinkRight": 0.01})
    FaceService.set_expression(body, allk)
    print("BODY", name, tuple(round(v, 2) for v in body.dimensions), len(body.data.shape_keys.key_blocks), "keys")
    return arm, body, new

BOOST = float(os.environ.get('EXPR_BOOST', '1.6'))   # Zack-style: big readable faces
def set_expr(body, name):
    kb = body.data.shape_keys.key_blocks
    want = EXPR[name]
    for k in kb:                                   # ONLY face-expression keys; never the body-shape ($md-) keys
        if not k.name.startswith("!ex-"): continue
        k.value = min(1.0, want.get(k.name[4:], 0.0) * BOOST)

MOM, MOMB, MOMO = make("Mom",
    {"gender": 0.0, "age": 0.6, "muscle": 0.45, "weight": 0.58, "height": 0.45, "proportions": 0.65, "cupsize": 0.55, "firmness": 0.5,
     "race": {"caucasian": 0.85, "asian": 0.05, "african": 0.10}},
    [T("head-oval", 0.3), T("r-eye-scale-incr", 0.25), T("l-eye-scale-incr", 0.25), T("nose-scale-horiz-decr", 0.2),
     T("r-cheek-bones-incr", 0.3), T("l-cheek-bones-incr", 0.3)],
    "long01", "eyebrow010", "female_casualsuit01", "shoes06", "young_caucasian_female", "mom_tee_diffuse.png")
KID, KIDB, KIDO = make("Kid",
    {"gender": 1.0, "age": 0.16, "muscle": 0.5, "weight": 0.5, "height": 0.5, "proportions": 0.5,
     "race": {"caucasian": 0.85, "asian": 0.05, "african": 0.10}},
    [T("r-eye-scale-incr", 0.35), T("l-eye-scale-incr", 0.35), T("head-round", 0.3)],
    "short01", "eyebrow001", "male_casualsuit06", "shoes05", "young_caucasian_male", "kid_tee_diffuse.png")

# stand them side by side, relaxed arms (never the A-pose)
MOM.location = (-0.42, 0, 0); KID.location = (0.42, 0, 0)
for arm in (MOM, KID):
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="POSE")
    D.relaxed_hands(arm); D.pose_arms(arm)
    for sd, sx in (("L", 1), ("R", -1)):            # feet under the hips, not the wide A-stance
        D.rot_world(arm, arm.pose.bones["upperleg01." + sd], Vector((0, 1, 0)), sx * 4.5)
        D.rot_world(arm, arm.pose.bones["foot." + sd], Vector((0, 1, 0)), -sx * 4.5)
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.update()


# ---------------------------------------------------------------- tears: glossy water streams down the cheeks
M_TEAR = bpy.data.materials.new("Tear"); tb = M_TEAR.node_tree.nodes["Principled BSDF"]
tb.inputs["Base Color"].default_value = (0.85, 0.93, 1.0, 1); tb.inputs["Roughness"].default_value = 0.03
tb.inputs["Transmission Weight"].default_value = 0.85; tb.inputs["IOR"].default_value = 1.33
tb.inputs["Coat Weight"].default_value = 1.0; tb.inputs["Coat Roughness"].default_value = 0.02
tb.inputs["Specular IOR Level"].default_value = 0.9
def add_tears(arm, body, name):
    """two tear streams + a wet line on each lower lid, projected onto the face; grow via bevel_factor_end"""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); be = body.evaluated_get(dg); Mi = body.matrix_world.inverted()
    def surf(p):
        o = Mi @ (p + Vector((0, -0.25, 0))); d = (Mi.to_3x3() @ Vector((0, 1, 0))).normalized()
        hit, loc, nrm, _ = be.ray_cast(o, d, distance=0.5)
        if not hit: return None
        n = (body.matrix_world.to_3x3() @ nrm).normalized()
        return body.matrix_world @ loc + n * 0.0009
    out = []
    for sd, sx in (("L", 1), ("R", -1)):
        eye = arm.matrix_world @ arm.pose.bones["eye." + sd].head
        pts = []
        for i in range(9):                                     # from the lower lid, curving out and down the cheek
            t = i / 8
            p = eye + Vector((sx * (0.002 + 0.010 * t + 0.004 * t * t), 0, -0.011 - 0.050 * t - 0.012 * t * t))
            q = surf(p)
            if q: pts.append(q)
        lid = [surf(eye + Vector((sx * x, 0, -0.0105 + 0.0025 * (x / 0.012) ** 2))) for x in (-0.011, -0.006, 0.0, 0.006, 0.011)]
        for nm, P, r in ((f"{name}_Tear{sd}", pts, 0.0021), (f"{name}_Lid{sd}", [q for q in lid if q], 0.0007)):
            cu = bpy.data.curves.new(nm, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = r; cu.bevel_resolution = 3
            cu.use_fill_caps = True
            sp = cu.splines.new("POLY"); sp.points.add(len(P) - 1)
            for i, q in enumerate(P): sp.points[i].co = (*q, 1)
            # thicker bead at the bottom of the stream
            if "Tear" in nm:
                for i in range(len(P)): sp.points[i].radius = 0.8 + 1.6 * (i / max(1, len(P) - 1)) ** 3
            ob = bpy.data.objects.new(nm, cu); scene.collection.objects.link(ob); cu.materials.append(M_TEAR)
            mw = ob.matrix_world.copy(); ob.parent = arm; ob.parent_type = "BONE"; ob.parent_bone = "head"
            bpy.context.view_layer.update(); ob.matrix_world = mw
            ob.hide_render = True; out.append(ob)
    return out
TEARS = {"mom": add_tears(MOM, MOMB, "Mom"), "kid": add_tears(KID, KIDB, "Kid")}

# ---------------------------------------------------------------- studio (Zack blue, same as Doc)
import bmesh
bg_m = bpy.data.materials.new("Backdrop"); b = bg_m.node_tree.nodes["Principled BSDF"]
ZB = (0.085, 0.371, 0.730, 1)
b.inputs["Base Color"].default_value = tuple(c * 0.55 for c in ZB[:3]) + (1,); b.inputs["Roughness"].default_value = 0.95
b.inputs["Emission Color"].default_value = ZB; b.inputs["Emission Strength"].default_value = 0.10
bm = bmesh.new(); prof = [(-6 + i * 0.5, 0.0) for i in range(12)]
for i in range(13):
    a = math.pi / 2 * i / 12; prof.append((1.0 + 2.5 * math.sin(a), 2.5 - 2.5 * math.cos(a)))
for i in range(1, 6): prof.append((3.5, 2.5 + i * 1.2))
cols = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in [-9 + i for i in range(19)]]
for a_, b_ in zip(cols, cols[1:]):
    for j in range(len(prof) - 1): bm.faces.new((a_[j], b_[j], b_[j + 1], a_[j + 1]))
me = bpy.data.meshes.new("Backdrop"); bm.to_mesh(me); bm.free(); me.shade_smooth()
bd = bpy.data.objects.new("Backdrop", me); scene.collection.objects.link(bd); me.materials.append(bg_m)
def area(name, loc, size, energy, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.size = size; l.energy = energy; l.color = color
    o = bpy.data.objects.new(name, l); scene.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("Key", (-2.2, -2.8, 3.0), 2.2, 420, (1.0, 0.90, 0.80))
area("Fill", (2.6, -2.2, 1.6), 3.0, 110, (0.85, 0.93, 1.0))
area("Rim", (1.4, 2.0, 2.6), 1.2, 160, (0.9, 1.0, 1.0))
area("RimL", (-1.6, 1.8, 2.2), 1.2, 100, (0.9, 1.0, 1.0))
world = bpy.data.worlds.new("W"); scene.world = world
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.2, 0.55, 0.7, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.2
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d); scene.collection.objects.link(cam); scene.camera = cam

r = scene.render; r.engine = "CYCLES"; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6; scene.view_settings.view_transform = "Khronos PBR Neutral"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "family.blend"))

def head_pos(arm):
    bpy.context.view_layer.update()
    return arm.matrix_world @ arm.pose.bones["head"].head
for v in VIEWS:
    if v in ("momfull", "kidfull"):
        arm = MOM if v == "momfull" else KID
        hz = head_pos(arm).z + 0.12; cx = arm.location.x
        r.resolution_x = RESW; r.resolution_y = int(RESW * 16 / 9) // 2 * 2
        cam_d.lens = 50; cam.location = (cx + 0.15, -hz * 1.9 - 0.4, hz * 0.62); tgt = Vector((cx, 0, hz * 0.5))
    elif v == "pair":
        r.resolution_x = RESW; r.resolution_y = int(RESW * 1.25)
        cam_d.lens = 55; cam.location = (0, -3.9, 0.95); tgt = Vector((0, 0, 0.8))
    else:
        who, ex = v.split("_", 1)
        arm, body = (MOM, MOMB) if who == "mom" else (KID, KIDB)
        set_expr(body, ex)
        for t in TEARS["mom"] + TEARS["kid"]: t.hide_render = True
        if ex == "crying":
            for t in TEARS[who]: t.hide_render = False
        h = head_pos(arm) + Vector((0, 0, 0.045 if who == "kid" else 0.06))
        r.resolution_x = RESW; r.resolution_y = RESW
        cam_d.lens = 85; cam.location = h + Vector((0.12, -1.25, 0.02)); tgt = h
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    r.filepath = os.path.join(OUT, f"{v}.png"); bpy.ops.render.render(write_still=True); print("RENDERED", v, flush=True)
    for bdy in (MOMB, KIDB): set_expr(bdy, "neutral")
