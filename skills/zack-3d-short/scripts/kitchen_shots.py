# "Mom was crying" - 15 shots, 31.5 s @30fps, synced to kitchen/words.json (Fenrir voice).
# Living room (kid laughing at TV on the sofa) -> hears mom crying -> kitchen: confession, onion, gas science, tears, twist.
# Opens renders/kitchen.blend (kitchen + living room + mom + kid), keys every frame, saves renders/kitchen_anim.blend
# Run: blender -b renders/kitchen.blend -P kitchen_shots.py -- <out_dir> <samples> <width> <frames|all|none>
import bpy, math, os, sys, json, random, wave
import numpy as np
from mathutils import Vector, Matrix, Quaternion, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders/kshots")
SAMPLES = int(argv[1]) if len(argv) > 1 else 24
WIDTH = int(argv[2]) if len(argv) > 2 else 720
FRAMES = argv[3] if len(argv) > 3 else "none"
HERE = os.path.dirname(os.path.abspath(__file__)); KD = os.path.join(HERE, "kitchen")
sys.path.insert(0, HERE); import doc_pose as D
X, Y, Z = D.X, D.Y, D.Z
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT"

sc = bpy.context.scene; FPS = 30; DUR = 31.5; N = int(DUR * FPS)
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = N
cam = bpy.data.objects["Cam"]; cd = cam.data
MOM = bpy.data.objects["Mom_rig"]; KID = bpy.data.objects["Kid_rig"]
MOMB = bpy.data.objects["Mom_body"]; KIDB = bpy.data.objects["Kid_body"]
for o in (MOM, KID, cam): o.animation_data_clear(); o.rotation_mode = "XYZ"
RIG_OF_INIT = True
SOFA = Vector(sc["sofa_pos"]); SEAT_Z = float(sc["sofa_seat_z"]); TV = Vector(sc["tv_pos"])

def smooth(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)
def lerp(a, b, k): return a + (b - a) * k
def Rz(deg): return Matrix.Rotation(math.radians(deg), 3, Z)
def upd(): bpy.context.view_layer.update()

# ---------------------------------------------------------------- voice loudness (kid's talking mouth)
LOUD = np.zeros(N + 2)
vp = os.path.join(KD, "vo.wav")
if os.path.exists(vp):
    wv = wave.open(vp); sr = wv.getframerate(); ch = wv.getnchannels()
    raw = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32).reshape(-1, ch).mean(1) / 32768
    for f in range(N):
        a = raw[int(f / FPS * sr): int((f + 1) / FPS * sr)]
        LOUD[f] = float(np.sqrt((a ** 2).mean())) if len(a) else 0
    LOUD /= max(1e-4, np.percentile(LOUD, 95))

# ---------------------------------------------------------------- faces
def sym(**kw):
    out = {}
    for k, v in kw.items():
        if k.endswith("_"): out[k[:-1] + "Left"] = v; out[k[:-1] + "Right"] = v
        else: out[k] = v
    return out
EXPR = {
    "neutral": sym(mouthSmile_=0.12),
    "happy":   sym(mouthSmile_=0.75, cheekSquint_=0.45, eyeSquint_=0.25, browOuterUp_=0.2, jawOpen=0.12),
    "laugh":   sym(mouthSmile_=0.62, cheekSquint_=0.6, eyeSquint_=0.55, browOuterUp_=0.3, browInnerUp=0.2, jawOpen=0.4, mouthLowerDown_=0.3),
    "shock":   sym(eyeWide_=0.9, browInnerUp=0.9, browOuterUp_=0.8, jawOpen=0.55, mouthFunnel=0.25),
    "panic":   sym(eyeWide_=0.8, browInnerUp=1.0, mouthStretch_=0.6, mouthFrown_=0.4, jawOpen=0.2, mouthLowerDown_=0.4),
    "guilty":  sym(browInnerUp=0.7, mouthFrown_=0.5, mouthPress_=0.45, eyeLookDown_=0.55, mouthRollLower=0.3, mouthStretch_=0.2),
    "crying":  sym(browInnerUp=1.0, browDown_=0.15, eyeSquint_=0.7, mouthFrown_=0.8, mouthStretch_=0.35, cheekSquint_=0.5,
                   jawOpen=0.18, mouthLowerDown_=0.35, noseSneer_=0.3),
    "sting":   sym(eyeSquint_=0.9, browDown_=0.5, browInnerUp=0.5, noseSneer_=0.5, cheekSquint_=0.6, mouthFrown_=0.3),
    "angry":   sym(browDown_=0.85, eyeSquint_=0.4, eyeWide_=0.25, noseSneer_=0.75, mouthPress_=0.5, mouthFrown_=0.55, mouthStretch_=0.35, jawForward=0.2),
    "relieved": sym(mouthSmile_=0.5, browInnerUp=0.35, cheekSquint_=0.2),
}
BOOST = 1.6
# brighter, natural teeth (the MPFB teeth material comes out dark grey)
for o in bpy.data.objects:
    if "teeth" in o.name.lower():
        for sl in o.material_slots:
            m = sl.material
            if m and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED":
                        for l in list(n.inputs["Base Color"].links): m.node_tree.links.remove(l)
                        tx = next((x for x in m.node_tree.nodes if x.type == "TEX_IMAGE"), None)
                        if tx: m.node_tree.links.new(tx.outputs["Color"], n.inputs["Base Color"])   # real teeth+gum texture, no dark tint
                        n.inputs["Roughness"].default_value = 0.28; n.inputs["Coat Weight"].default_value = 0.3
                        n.inputs["Subsurface Weight"].default_value = 0.15
EXKEYS = {b: [k for k in b.data.shape_keys.key_blocks if k.name.startswith("!ex-")] for b in (MOMB, KIDB)}
def blinks(seed):
    rnd = random.Random(seed); out = []; t = 0.7
    while t < DUR: out.append(t); t += rnd.uniform(2.0, 3.6)
    return out
BLINK = {MOMB: blinks(3), KIDB: blinks(8)}
def blink_amt(body, t):
    for b in BLINK[body]:
        d = (t - b) * FPS
        if 0 <= d <= 8: return [0, 0.35, 0.8, 1, 1, 0.8, 0.5, 0.2, 0][int(d)]
    return 0.0
RIG_OF = {}
def set_face(body, t, e1, e2=None, k=0.0, talk=0.0, f=0):
    """shape keys for the face; the mouth opening is done with the JAW BONE so the lower teeth + tongue open with it"""
    a = EXPR[e1]; b = EXPR[e2] if e2 else a
    jaw = 0.0
    for kb in EXKEYS[body]:
        u = kb.name[4:]
        v = lerp(a.get(u, 0.0), b.get(u, 0.0), k) * BOOST
        if u == "jawOpen":
            jaw = min(1.0, v + talk * 0.35); v = jaw * 0.25          # bone does most of the opening
        if u == "mouthFunnel": v += talk * 0.15
        if u.startswith("eyeBlink"): v = max(v, blink_amt(body, t))
        kb.value = min(1.0, v); kb.keyframe_insert("value", frame=f)
    arm = RIG_OF[body]; jb = arm.pose.bones["jaw"]; jb.matrix_basis.identity()
    upd(); hb = arm.pose.bones["head"]; left = (arm.matrix_world.to_3x3() @ hb.matrix.to_3x3() @ Vector((1, 0, 0))).normalized()
    D.rot_world(arm, jb, left, 17.0 * jaw)
    jb.keyframe_insert("rotation_quaternion" if jb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)

TEARS = {"mom": [o for o in bpy.data.objects if o.name.startswith(("Mom_Tear", "Mom_Lid"))],
         "kid": [o for o in bpy.data.objects if o.name.startswith(("Kid_Tear", "Kid_Lid"))]}
def set_tears(who, amount, f):
    for o in TEARS[who]:
        o.hide_render = amount <= 0.01; o.keyframe_insert("hide_render", frame=f)
        o.data.bevel_factor_end = 1.0 if "Lid" in o.name else max(0.02, min(1.0, amount))
        o.data.keyframe_insert("bevel_factor_end", frame=f)

RIG_OF.update({MOMB: MOM, KIDB: KID})
# ---------------------------------------------------------------- legs: IK with knee poles (standing, walking, sitting)
RIG = {}
for arm in (MOM, KID):
    arm.location = (0, 0, 0); arm.rotation_euler = (0, 0, 0)
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in list(pb.constraints): pb.constraints.remove(c)
    upd(); P = arm.pose.bones
    feet = {}
    for s in ("L", "R"):
        a = P["lowerleg02." + s].tail
        feet[s] = (abs(a.x), a.y, a.z, (arm.matrix_world @ P["foot." + s].matrix).to_3x3().normalized())
    hip = (P["upperleg01.L"].head + P["upperleg01.R"].head) / 2
    thigh = (P["upperleg01.L"].head - P["lowerleg01.L"].head).length
    shin = (P["lowerleg01.L"].head - P["lowerleg02.L"].tail).length
    tg, rt, pl = {}, {}, {}
    for s in ("L", "R"):
        e = bpy.data.objects.new(arm.name + "_IK_" + s, None); sc.collection.objects.link(e); tg[s] = e
        r = bpy.data.objects.new(arm.name + "_FR_" + s, None); sc.collection.objects.link(r); rt[s] = r
        p = bpy.data.objects.new(arm.name + "_POLE_" + s, None); sc.collection.objects.link(p); pl[s] = p
        c = P["lowerleg02." + s].constraints.new("IK"); c.target = e; c.chain_count = 4; c.use_stretch = False; c.use_tail = True
        c.pole_target = p
        cr = P["foot." + s].constraints.new("COPY_ROTATION"); cr.target = r; cr.owner_space = "WORLD"; cr.target_space = "WORLD"
    RIG[arm] = dict(feet=feet, hip=hip.copy(), thigh=thigh, shin=shin, tg=tg, rt=rt, pl=pl)
def set_poles(arm, loc, yaw, f):
    R = RIG[arm]
    for s, sx in (("L", 1), ("R", -1)):
        R["pl"][s].location = Vector(loc) + Rz(yaw) @ Vector((sx * 0.14, -1.2, R["hip"].z * 0.5))
        R["pl"][s].keyframe_insert("location", frame=f)
# calibrate the pole angle per leg on a deep knee bend (knee must go forward)
for arm in (MOM, KID):
    R = RIG[arm]; arm.location = (0, 0, -R["thigh"] * 0.8); set_poles(arm, (0, 0, 0), 0, 0)
    for s, sx in (("L", 1), ("R", -1)):
        fx, fy, fz, frest = R["feet"][s]; R["tg"][s].location = (sx * fx, fy, fz)
        R["rt"][s].rotation_euler = frest.to_euler()
    for s in ("L", "R"):
        c = arm.pose.bones["lowerleg02." + s].constraints[0]; best = None
        for a in range(-180, 180, 10):
            c.pole_angle = math.radians(a); upd()
            k = arm.matrix_world @ arm.pose.bones["lowerleg01." + s].head; h = arm.matrix_world @ arm.pose.bones["upperleg01." + s].head
            score = k.y + 2 * abs(k.x - h.x)
            if best is None or score < best[0]: best = (score, a)
        c.pole_angle = math.radians(best[1]); print("POLE", arm.name, s, best[1])
    arm.location = (0, 0, 0)

def feet_standing(arm, loc, yaw, f):
    R = RIG[arm]
    for s, sx in (("L", 1), ("R", -1)):
        fx, fy, fz, frest = R["feet"][s]
        p = Vector(loc) + Rz(yaw) @ Vector((sx * fx, fy, 0))
        R["tg"][s].location = (p.x, p.y, fz); R["tg"][s].keyframe_insert("location", frame=f)
        R["rt"][s].rotation_euler = (Rz(yaw) @ frest).to_euler(); R["rt"][s].keyframe_insert("rotation_euler", frame=f)
    set_poles(arm, loc, yaw, f)

def sit_kid(f, swing=0.0):
    """kid on the sofa: hips on the cushion, lower legs hang (they don't reach the floor), feet swing a little"""
    R = RIG[KID]; yaw = 0.0
    hip_w = Vector((SOFA.x - 0.55, SOFA.y - 0.2, SEAT_Z + 0.075))
    loc = hip_w - R["hip"]
    for s, sx in (("L", 1), ("R", -1)):
        fx, fy, fz, frest = R["feet"][s]
        knee = hip_w + Vector((sx * 0.08, -R["thigh"] * 0.96, -0.03))
        sw = swing * math.sin(sx * 0.9 + swing * 0)
        ank = knee + Vector((0, 0.06 - 0.05 * sw, -R["shin"] * 0.97))
        R["tg"][s].location = ank; R["tg"][s].keyframe_insert("location", frame=f)
        R["rt"][s].rotation_euler = (Matrix.Rotation(math.radians(-15), 3, X) @ frest).to_euler(); R["rt"][s].keyframe_insert("rotation_euler", frame=f)
    set_poles(KID, Vector((loc.x, loc.y, 0)), yaw, f)
    return Vector((loc.x, loc.y, 0)), yaw, loc.z

# kid walk (walk.py gait, scaled to his legs)
KS = RIG[KID]["hip"].z / 0.92
T_GAIT = 0.9; DUTY = 0.6; HALF = 0.22 * KS; V = 2 * HALF / (DUTY * T_GAIT)

# ---------------------------------------------------------------- arms
POSE = [f"{b}.{s}" for b in ("shoulder01", "upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist") for s in ("L", "R")] + \
       ["spine05", "spine04", "spine03", "spine01", "neck01", "neck02", "head"] + \
       [f"finger{f_}-{j}.{s}" for f_ in "12345" for j in (1, 2, 3) for s in ("L", "R")]
def wp(arm, v): return arm.matrix_world @ v
def reach(arm, sd, Wt, pole):
    P = arm.pose.bones; u1, u2, l1, l2 = (P[f"{b}.{sd}"] for b in ("upperarm01", "upperarm02", "lowerarm01", "lowerarm02"))
    upd(); a = u1.length + u2.length; b = l1.length + l2.length
    S = wp(arm, u1.head); u = Wt - S; d = min(u.length, a + b - 0.003); dn = u.normalized()
    x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(0.0, a * a - x * x))
    pl = (pole - dn * pole.dot(dn)).normalized(); E = S + dn * x + pl * h
    D.aim(arm, u1, E - S); D.aim(arm, u2, E - S); upd(); D.aim(arm, l1, Wt - wp(arm, l1.head))
    for _ in range(3):
        for bone, chain in ((u1, (u1, u2)), (l1, (l1,))):
            upd(); o = wp(arm, bone.head); wr = wp(arm, l2.tail)
            q = (wr - o).rotation_difference(Wt - o)
            for bb in chain:
                upd(); M = arm.matrix_world @ bb.matrix
                bb.matrix = arm.matrix_world.inverted() @ Matrix.Translation(o) @ q.to_matrix().to_4x4() @ Matrix.Translation(-o) @ M
    upd()
def body_frame(arm):
    yaw = arm.rotation_euler.z; return Vector((math.sin(yaw), -math.cos(yaw), 0)), Vector((math.cos(yaw), math.sin(yaw), 0))
def chest(arm): upd(); return wp(arm, arm.pose.bones["spine01"].head)
def lean(arm, deg):
    fwd, left = body_frame(arm)
    D.rot_world(arm, arm.pose.bones["spine03"], left, deg * 0.6); D.rot_world(arm, arm.pose.bones["spine05"], left, deg * 0.4)
def head_turn(arm, yaw_deg, pitch_deg=0.0):
    fwd, left = body_frame(arm)
    if yaw_deg: D.rot_world(arm, arm.pose.bones["neck01"], Z, yaw_deg * 0.5); D.rot_world(arm, arm.pose.bones["head"], Z, yaw_deg * 0.5)
    if pitch_deg: D.rot_world(arm, arm.pose.bones["head"], left, pitch_deg)
def key_pose(arm, f):
    for n in POSE:
        pb = arm.pose.bones.get(n)
        if pb: pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
def eye_mid(arm):
    upd(); P = arm.pose.bones; return (wp(arm, P["eye.L"].head) + wp(arm, P["eye.R"].head)) / 2

# ---------------------------------------------------------------- props
onion_hand = bpy.data.objects["OnionSpare"]; onion_cut = bpy.data.objects["OnionWhole"]; knife = bpy.data.objects["Knife"]
remote = bpy.data.objects["Remote"]
for o in (onion_hand, knife, remote): o.rotation_mode = "QUATERNION"
onion_home = onion_hand.matrix_world.copy(); knife_home = knife.matrix_world.copy()
# onion gas: soft volumetric puffs (noise density with a round falloff), drifting and growing
gm = bpy.data.materials.new("GasVolume"); nt = gm.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
outn = nt.nodes.new("ShaderNodeOutputMaterial"); vol = nt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.85, 0.97, 0.8, 1); vol.inputs["Emission Color"].default_value = (0.8, 1.0, 0.75, 1)
vol.inputs["Emission Strength"].default_value = 2.5; vol.inputs["Anisotropy"].default_value = 0.3
tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"
nz.inputs["Scale"].default_value = 2.6; nz.inputs["Detail"].default_value = 6; nz.inputs["Roughness"].default_value = 0.6
info = nt.nodes.new("ShaderNodeObjectInfo")
add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"; nt.links.new(info.outputs["Random"], add.inputs[0]); add.inputs[1].default_value = 0.0
nt.links.new(add.outputs[0], nz.inputs["W"]); nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; nt.links.new(tc.outputs["Object"], ln.inputs[0])
fall = nt.nodes.new("ShaderNodeMapRange"); fall.inputs["From Min"].default_value = 1.0; fall.inputs["From Max"].default_value = 0.2
nt.links.new(ln.outputs["Value"], fall.inputs["Value"])
ramp = nt.nodes.new("ShaderNodeMapRange"); ramp.inputs["From Min"].default_value = 0.48; ramp.inputs["From Max"].default_value = 0.75
nt.links.new(nz.outputs["Fac"], ramp.inputs["Value"])
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; nt.links.new(ramp.outputs["Result"], mul.inputs[0]); nt.links.new(fall.outputs["Result"], mul.inputs[1])
dens = nt.nodes.new("ShaderNodeMath"); dens.operation = "MULTIPLY"; dens.inputs[1].default_value = 170.0; nt.links.new(mul.outputs[0], dens.inputs[0])
nt.links.new(dens.outputs[0], vol.inputs["Density"]); nt.links.new(vol.outputs[0], outn.inputs["Volume"])
GAS_T = add.inputs[1]
GAS = []; grnd = random.Random(11)
for i in range(16):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0); g = bpy.context.active_object; g.name = f"GasPuff{i:02d}"
    g.data.materials.append(gm); g.hide_render = True
    GAS.append((g, grnd.uniform(0, 1), grnd.uniform(-1, 1), grnd.uniform(-1, 1), grnd.uniform(0.7, 1.3)))

# ---------------------------------------------------------------- layout
BOARD_P = bpy.data.objects["Board"].location.copy()
MOM_POS = Vector((BOARD_P.x + 0.02, 1.8 - 0.62 - 0.3, 0))
KID_STOP = Vector((0.95, -0.35, 0))
def yaw_to(a, b):
    d = (Vector(b) - Vector(a)); return math.degrees(math.atan2(d.x, -d.y))
KID_YAW = yaw_to(KID_STOP, MOM_POS); MOM_YAW = yaw_to(MOM_POS, KID_STOP)

SHOTS = [(0.0, "couch"), (1.65, "tvscreen"), (2.8, "laugh"), (3.85, "hear"), (5.35, "momback"), (6.95, "ohno"), (8.0, "bagtest"),
         (10.5, "confess"), (13.75, "onion"), (17.3, "cut"), (20.0, "gas"), (21.5, "flood"), (25.85, "twoshot"), (27.95, "angry"), (29.5, "kidcry")]
LIVING = ("couch", "tvscreen", "laugh", "hear", "ohno", "bagtest")
def shot_at(t):
    cur = SHOTS[0]
    for s in SHOTS:
        if t >= s[0]: cur = s
    i = SHOTS.index(cur); t1 = SHOTS[i + 1][0] if i + 1 < len(SHOTS) else DUR
    return cur[1], (t - cur[0]) / (t1 - cur[0]), t - cur[0]

def set_cam(loc, tgt, lens, focus, f, fstop=2.8):
    cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); cd.lens = lens
    cd.dof.use_dof = True; cd.dof.focus_distance = (Vector(focus) - Vector(loc)).length; cd.dof.aperture_fstop = fstop
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    cd.keyframe_insert("lens", frame=f); cd.dof.keyframe_insert("focus_distance", frame=f); cd.dof.keyframe_insert("aperture_fstop", frame=f)
def place_char(arm, loc, yaw, z, f):
    arm.location = (loc.x, loc.y, z); arm.rotation_euler = (0, 0, math.radians(yaw))
    arm.keyframe_insert("location", frame=f); arm.keyframe_insert("rotation_euler", frame=f)

# ---------------------------------------------------------------- per-frame bake
for f in range(1, N + 1):
    t = (f - 1) / FPS; sc.frame_set(f)
    shot, u, ts = shot_at(t)
    for arm in (MOM, KID):
        for n in POSE:
            pb = arm.pose.bones.get(n)
            if pb: pb.matrix_basis.identity()
    talk = 0.0
    laughing = shot in ("couch", "tvscreen", "laugh") or (shot == "hear" and u < 0.25)
    bounce = abs(math.sin(t * 8.5)) if laughing else 0.0
    # kid placement
    if shot in LIVING or shot == "momback":
        kloc, kyaw, kz = sit_kid(f, swing=math.sin(t * 2.2) if laughing else 0.0)
    else:
        kloc, kyaw, kz = KID_STOP, KID_YAW, -0.012; feet_standing(KID, kloc, kyaw, f)
    place_char(KID, kloc, kyaw, kz, f)
    # mom: back to camera at the board for the "momback" + "cut" shots, turned to the kid otherwise
    if shot in ("momback", "cut") or shot in LIVING:
        mloc, myaw = MOM_POS, 180.0
    else:
        mloc, myaw = MOM_POS + Vector((0.05, -0.12, 0)), MOM_YAW
    place_char(MOM, mloc, myaw, -0.012, f); feet_standing(MOM, mloc, myaw, f)
    upd()
    D.relaxed_hands(KID); D.relaxed_hands(MOM)
    breathe = math.sin(2 * math.pi * t / 3.4)
    # ---- kid body
    if shot in LIVING or shot == "momback":
        lean(KID, -10 + 5 * bounce); head_turn(KID, 0, -6 * bounce)
        if shot == "hear": head_turn(KID, 38 * smooth((u - 0.15) * 3), 4 * smooth((u - 0.15) * 3))
        if shot == "ohno": head_turn(KID, 30, 0); lean(KID, 6)
        D.pose_arms(KID, yaw_deg=kyaw)
        fwd, left = body_frame(KID); c = chest(KID)
        # right hand: remote on the thigh; left hand on the belly while laughing
        thigh_top = wp(KID, KID.pose.bones["upperleg01.L"].head).z + 0.085
        def on_thigh(sx, fw):
            hp = wp(KID, KID.pose.bones["upperleg01." + ("L" if sx > 0 else "R")].head)
            return Vector((hp.x, hp.y, thigh_top)) + fwd * fw + left * (sx * 0.02)
        reach(KID, "R", on_thigh(-1, 0.17) + Vector((0, 0, 0.015 * bounce)), -fwd * 0.4 - left + Vector((0, 0, 0.2)))
        if laughing:
            reach(KID, "L", c + fwd * 0.15 + left * 0.03 + Vector((0, 0, -0.13)), -fwd * 0.4 + left + Vector((0, 0, -0.2)))
        else:
            reach(KID, "L", on_thigh(1, 0.17), -fwd * 0.4 + left + Vector((0, 0, 0.2)))
    elif shot == "confess":
        lean(KID, 4 + 2 * math.sin(t * 5)); head_turn(KID, 0, -3)
        D.pose_arms(KID, yaw_deg=kyaw)
        fwd, left = body_frame(KID); c = chest(KID)
        for sd, sx in (("L", 1), ("R", -1)):
            reach(KID, sd, c + fwd * 0.22 + left * (sx * 0.035) + Vector((0, 0, -0.02 + 0.012 * math.sin(t * 11))), -fwd * 0.2 + left * sx + Vector((0, 0, -0.7)))
        talk = min(1.0, LOUD[f - 1] * 1.1)
    else:
        lean(KID, 1.2 * breathe); D.pose_arms(KID, yaw_deg=kyaw, elbow=12 + 2 * breathe)
        if shot == "kidcry": head_turn(KID, 0, 6 * smooth(u))
    # ---- mom body
    if myaw == 180.0:
        lean(MOM, 12)
        sob = math.sin(2 * math.pi * t * 2.3) * (0 if shot == "cut" else 1)
        D.rot_world(MOM, MOM.pose.bones["spine03"], Z, 1.5 * sob)
        D.rot_world(MOM, MOM.pose.bones["neck01"], body_frame(MOM)[1], 3 * abs(sob))
        fwd, left = body_frame(MOM)
        chop = abs(math.sin(2 * math.pi * t * 1.6))
        if shot == "cut":
            k_ = abs(math.sin(math.pi * ts * 1.3)); oc = onion_cut.matrix_world.translation
            KNIFE_ROOT = oc - Rz(15.0) @ Vector((0.1, 0, 0)) + Vector((0, 0, 0.085 - 0.075 * k_))
            grip = KNIFE_ROOT + Rz(15.0) @ Vector((-0.06, 0, 0.03))
            reach(MOM, "R", grip + Vector((0, 0, 0.035)), -fwd * 0.2 - left + Vector((0, 0, -0.8)))
            reach(MOM, "L", oc + Vector((0.035, 0.05, 0.075)), -fwd * 0.2 + left + Vector((0, 0, -0.8)))
        else:
            reach(MOM, "R", Vector((BOARD_P.x - 0.12, BOARD_P.y, 0.97 + 0.07 * chop)), -fwd * 0.2 - left + Vector((0, 0, -0.8)))
            reach(MOM, "L", Vector((BOARD_P.x + 0.08, BOARD_P.y - 0.02, 0.96)), -fwd * 0.2 + left + Vector((0, 0, -0.8)))
    elif shot == "onion":
        lean(MOM, -2); D.pose_arms(MOM, yaw_deg=myaw)
        fwd, left = body_frame(MOM); hd = eye_mid(MOM); up = smooth(u / 0.3)
        Wt = (chest(MOM) + fwd * 0.1 - left * 0.15 + Vector((0, 0, -0.2))).lerp(hd + fwd * 0.17 - left * 0.24 + Vector((0, 0, -0.08)), up)
        reach(MOM, "R", Wt, -fwd * 0.2 - left + Vector((0, 0, -0.8)))
    else:
        lean(MOM, 1.5 * breathe); D.pose_arms(MOM, yaw_deg=myaw, elbow=12 + 2 * breathe)
        if shot == "angry":
            fwd, left = body_frame(MOM); c = chest(MOM)
            for sd, sx in (("L", 1), ("R", -1)):
                reach(MOM, sd, c + left * (sx * 0.2) - fwd * 0.02 + Vector((0, 0, -0.33)), -fwd * 0.6 + left * sx * 0.8)
            lean(MOM, -3)
    key_pose(KID, f); key_pose(MOM, f)
    # ---- faces + tears
    K = {"couch": ("laugh",), "tvscreen": ("laugh",), "laugh": ("laugh",), "hear": ("laugh", "shock", smooth((u - 0.15) * 4)),
         "momback": ("shock",), "ohno": ("shock", "panic", smooth(u * 2)), "bagtest": ("panic",),
         "confess": ("panic", "guilty", 0.5 + 0.5 * math.sin(t * 3)), "onion": ("guilty", "shock", smooth(u * 2)), "cut": ("shock",),
         "gas": ("shock",), "flood": ("shock",), "twoshot": ("shock", "relieved", smooth(u * 2)),
         "angry": ("relieved", "shock", smooth(u * 3)), "kidcry": ("panic", "crying", smooth(u * 1.6))}[shot]
    # laughing pulses the jaw
    set_face(KIDB, t, K[0], K[1] if len(K) > 1 else None, K[2] if len(K) > 2 else 0, talk + (0.5 * bounce if laughing else 0), f)
    M = {"momback": ("crying",), "confess": ("crying", "shock", smooth(u * 2)), "onion": ("shock", "relieved", smooth((u - 0.4) * 2.5)),
         "cut": ("crying",), "gas": ("neutral", "sting", smooth(u * 1.3)), "flood": ("sting", "crying", smooth(u)),
         "twoshot": ("relieved", "happy", smooth(u * 1.5)), "angry": ("happy", "angry", smooth(u * 3.5)), "kidcry": ("angry",)}.get(shot, ("crying",))
    set_face(MOMB, t, M[0], M[1] if len(M) > 1 else None, M[2] if len(M) > 2 else 0, 0.0, f)
    mt = {"momback": 0.8, "confess": 1.0, "onion": 1.0, "twoshot": 0.9, "flood": smooth(u * 1.4)}.get(shot, 0.0)
    set_tears("mom", mt, f)
    set_tears("kid", smooth((u - 0.2) * 1.6) if shot == "kidcry" else 0.0, f)
    # ---- props
    upd()
    if shot in LIVING or shot == "momback":
        w_ = wp(KID, KID.pose.bones["lowerarm02.R"].tail); fwd, left = body_frame(KID)
        remote.location = w_ + fwd * 0.04 + Vector((0, 0, -0.015)); remote.rotation_quaternion = Quaternion(Z, math.radians(kyaw + 10))
    else:
        remote.location = (SOFA.x - 0.2, SOFA.y - 0.15, SEAT_Z + 0.02); remote.rotation_quaternion = Quaternion(Z, math.radians(30))
    remote.keyframe_insert("location", frame=f); remote.keyframe_insert("rotation_quaternion", frame=f)
    if shot == "onion":
        wb = MOM.pose.bones["wrist.R"]; w0 = wp(MOM, wb.head); w1 = wp(MOM, wb.tail); hd_ = (w1 - w0).normalized()
        palm = w0 + hd_ * 0.055 + Vector((0, 0, 0.045))            # sits on the palm, fingers curl round it
        onion_hand.matrix_world = Matrix.Translation(palm)
    else:
        onion_hand.matrix_world = onion_home
    onion_hand.keyframe_insert("location", frame=f); onion_hand.keyframe_insert("rotation_quaternion", frame=f); onion_hand.keyframe_insert("scale", frame=f)
    on = onion_cut.matrix_world.translation
    if shot == "cut":
        k_ = abs(math.sin(math.pi * ts * 1.3)); kyw = 15.0
        knife.location = on - Rz(kyw) @ Vector((0.1, 0, 0)) + Vector((0, 0.0, 0.085 - 0.075 * k_))
        knife.rotation_quaternion = Euler((0, 0, math.radians(kyw))).to_quaternion()
    else:
        knife.matrix_world = knife_home
    knife.keyframe_insert("location", frame=f); knife.keyframe_insert("rotation_quaternion", frame=f)
    # gas puffs
    GAS_T.default_value = t * 0.35; GAS_T.keyframe_insert("default_value", frame=f)
    eye = wp(MOM, MOM.pose.bones["eye.R"].head); mfwd = body_frame(MOM)[0]
    for g, ph, ox, oy, sz in GAS:
        vis = shot in ("cut", "gas", "flood")
        if vis:
            life = (ph + t * 0.35) % 1.0
            if shot == "cut":
                p = on + Vector((0, 0, 0.04)) + Vector((ox * 0.02 * (1 + life * 2.5), oy * 0.02 * (1 + life * 2.5), life * 0.32))
                r = 0.018 + 0.05 * life * sz
            else:
                src = eye + Vector((0, 0, -0.42)) + mfwd * 0.16
                p = src.lerp(eye + mfwd * 0.025, life ** 0.8) + (Vector((ox, oy, 0)) * 0.03 + Vector((math.sin(t * 1.7 + ph * 9), 0, 0)) * 0.012) * (1 - life)
                r = (0.02 + 0.035 * life * sz) * (0.45 if shot == "flood" else 1.0)
                if shot == "flood" and ph > 0.5: vis = False          # thinner smoke in the eye close-up (hide, never scale to ~0: crashes Cycles)
            if vis: g.location = p; g.scale = (r,) * 3
        g.hide_render = not vis
        g.keyframe_insert("location", frame=f); g.keyframe_insert("scale", frame=f); g.keyframe_insert("hide_render", frame=f)
    # ---- camera
    upd(); kh = eye_mid(KID); mh = eye_mid(MOM); kfwd = body_frame(KID)[0]; mfwd = body_frame(MOM)[0]
    if shot == "couch":
        set_cam(Vector((SOFA.x - 0.15 + 0.1 * u, SOFA.y - 2.35 + 0.2 * u, 1.05)), Vector((SOFA.x - 0.4, SOFA.y, 0.72)), 30, kh, f, 4.0)
    elif shot == "tvscreen":
        set_cam(kh + Vector((0.32, 0.42, 0.06)), TV + Vector((0, 0, -0.04)), 38, TV, f, 4.0)
    elif shot == "laugh":
        set_cam(kh + kfwd * (0.72 - 0.1 * u) + Vector((0.08, 0, -0.03)), kh + Vector((0, 0, -0.04)), 55, kh, f, 2.0)
    elif shot == "hear":
        set_cam(kh + kfwd * (0.62 - 0.12 * smooth(u)) + Vector((0.05, 0, -0.02)), kh + Vector((0, 0, -0.03)), 55, kh, f, 2.0)
    elif shot == "momback":
        set_cam(Vector((1.25 - 0.2 * u, -1.9, 1.35)), Vector((MOM_POS.x + 0.1, MOM_POS.y + 0.2, 1.1)), 30, Vector(MOM_POS) + Vector((0, 0, 1.2)), f, 4.0)
    elif shot == "ohno":
        set_cam(kh + kfwd * (0.6 - 0.25 * smooth(u)) + Vector((0.1, 0, -0.02)), kh + Vector((0.03, 0, -0.03)), 55, kh, f, 2.0)
    elif shot == "bagtest":
        bt = bpy.data.objects["BagTest"].location
        set_cam(bt + Vector((-0.1 + 0.05 * u, -0.55 + 0.18 * smooth(u), 0.18)), bt + Vector((0, 0, 0.1)), 50, bt + Vector((0, 0, 0.1)), f, 2.4)
    elif shot == "confess":
        set_cam(kh + kfwd * 1.35 + Vector((0.15, 0, -0.25)), kh + Vector((0, 0, -0.28)), 40, kh, f, 2.8)
    elif shot == "onion":
        set_cam(mh + mfwd * (1.35 - 0.2 * u) - body_frame(MOM)[1] * 0.12 + Vector((0, 0, -0.1)), mh + Vector((0, 0, -0.1)) - body_frame(MOM)[1] * 0.1, 40, mh, f, 2.8)
    elif shot == "cut":
        set_cam(on + Vector((0.22 - 0.03 * u, -0.21, 0.2)), on + Vector((-0.05, 0.0, 0.05)), 42, on, f, 4.0)
    elif shot == "gas":
        side = body_frame(MOM)[1]
        set_cam(mh + side * 0.45 + mfwd * 0.34 + Vector((0, 0, -0.16 + 0.08 * u)), mh + mfwd * 0.06 + Vector((0, 0, -0.14 + 0.1 * u)), 40, mh, f, 3.2)
    elif shot == "flood":
        e = wp(MOM, MOM.pose.bones["eye.R"].head)
        set_cam(e + mfwd * (0.32 - 0.08 * u) + Vector((0, 0, -0.012)), e + Vector((0, 0, -0.014)), 85, e + mfwd * 0.03, f, 3.2)
    elif shot == "twoshot":
        mid = (kh + mh) / 2; side = Vector((-(mh - kh).y, (mh - kh).x, 0)).normalized()
        if side.dot(Vector((1.2, -2.0, 0)) - Vector((mid.x, mid.y, 0))) < 0: side = -side
        set_cam(mid + side * (3.0 - 0.15 * u) + Vector((0, 0, -0.1)), mid + Vector((0, 0, -0.25)), 24, mid, f, 5.6)
    elif shot == "angry":
        set_cam(mh + mfwd * (0.62 - 0.12 * u) + Vector((0, 0, -0.04)), mh + Vector((0, 0, -0.04)), 60, mh, f, 2.0)
    elif shot == "kidcry":
        set_cam(kh + kfwd * (0.62 - 0.14 * u) + Vector((0, 0, -0.03)), kh + Vector((0, 0, -0.03)), 60, kh, f, 2.0)
    if f % 90 == 0: print("BAKED", f, shot, flush=True)
    if shot in ("cut", "onion") and abs(u - 0.5) < 0.02:
        upd(); print("DBG", shot, "knife", tuple(round(v, 3) for v in knife.matrix_world.translation), "onion_cut", tuple(round(v, 3) for v in on),
              "onion_hand", tuple(round(v, 3) for v in onion_hand.matrix_world.translation),
              "palmR", tuple(round(v, 3) for v in wp(MOM, MOM.pose.bones["wrist.R"].tail)), "cam", tuple(round(v, 3) for v in cam.location), flush=True)

r = sc.render; r.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.volume_step_rate = 2.0
r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2; r.use_motion_blur = False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "kitchen_anim.blend"))
if FRAMES != "none":
    frames = range(1, N + 1) if FRAMES == "all" else [int(x) for x in FRAMES.split(",")]
    for f in frames:
        sc.frame_set(f); r.filepath = os.path.join(OUT, f"k_{f:04d}.png"); bpy.ops.render.render(write_still=True); print("FRAME", f, flush=True)
