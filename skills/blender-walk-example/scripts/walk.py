# 3-second walk for Doc: IK legs with planted feet (no foot slide), heel strike / toe off,
# hip bob, opposite arm swing, camera dollies with him (Zack style: one smooth axis, slight push-in).
# Run: blender -b renders/doc_mpfb.blend -P walk.py -- <out_dir> <samples> <width> <frames|all> [view]
import bpy, math, os, sys
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders/walk")
SAMPLES = int(argv[1]) if len(argv) > 1 else 40
WIDTH = int(argv[2]) if len(argv) > 2 else 720
FRAMES = argv[3] if len(argv) > 3 else "all"
VIEW = argv[4] if len(argv) > 4 else "threequarter"
os.makedirs(OUT, exist_ok=True)

sc = bpy.context.scene
FPS, SECS = 30, 3.0
N = int(FPS * SECS)
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = N

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
rig = bpy.data.objects["ViewRig"]; cam = bpy.data.objects["Cam"]
P = arm.pose.bones

# ---------------------------------------------------------------- gait numbers
T = 1.0            # one full cycle (two steps), seconds
DUTY = 0.6         # share of the cycle a foot is on the ground
HALF = 0.25        # foot lands this far ahead of the hip (and leaves this far behind)
V = 2 * HALF / (DUTY * T)       # walking speed that keeps planted feet still (0.83 m/s)
Y0 = 1.2           # start position (walks toward -Y)
ANK_Z = 0.065      # ankle height with the foot flat
FOOT_X = 0.098     # ankle width (slightly narrower than rest for a natural line)
ANK_Y = -0.017     # ankle rest offset from the body origin

def body_y(t): return Y0 - V * t
def body_z(t):     # lowest at foot strike (legs spread), highest at mid-stance
    return -0.032 + 0.014 * (0.5 - 0.5 * math.cos(4 * math.pi * t / T))
def smooth(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)

def foot_state(t, offset):
    """world ankle position + foot pitch (deg, + = toe down) for one foot"""
    p = (t / T + offset) % 1.0
    t0 = t - p * T                                   # time this foot last landed
    land_y = lambda tl: body_y(tl) + ANK_Y - HALF
    if p < DUTY:                                     # stance: planted
        y = land_y(t0); z = ANK_Z; pitch = 0.0
        if p < 0.08: pitch = -14 * (1 - p / 0.08)    # heel strike, toe still up
        if p > 0.42:                                 # heel peels off, pivot on the ball
            k = smooth((p - 0.42) / (DUTY - 0.42)); pitch = 32 * k
            z = ANK_Z + 0.115 * math.sin(math.radians(pitch))
            y += 0.04 * k
        return y, z, pitch
    s = (p - DUTY) / (1 - DUTY)                      # swing
    y_from = land_y(t0) + 0.04
    y_to = land_y(t0 + T)
    y = y_from + (y_to - y_from) * smooth(s)
    z_off = ANK_Z + 0.115 * math.sin(math.radians(32)) * (1 - smooth(s * 2.2))
    z = max(z_off, ANK_Z) + 0.07 * math.sin(math.pi * min(1, s * 1.15)) ** 1.3
    pitch = 32 * (1 - smooth(s / 0.55)) - 14 * smooth((s - 0.55) / 0.45)
    return y, z, pitch

# ---------------------------------------------------------------- IK + foot rotation targets
bpy.context.view_layer.update()
foot_rest = {}
for side in ("L", "R"):
    foot_rest[side] = (arm.matrix_world @ P["foot." + side].matrix).to_3x3().normalized()
TGT, ROT = {}, {}
for side in ("L", "R"):
    e = bpy.data.objects.new("IK_" + side, None); sc.collection.objects.link(e); TGT[side] = e
    r = bpy.data.objects.new("FootRot_" + side, None); sc.collection.objects.link(r); ROT[side] = r
    c = P["lowerleg02." + side].constraints.new("IK")
    c.target = e; c.chain_count = 4; c.use_stretch = False; c.use_tail = True
    cr = P["foot." + side].constraints.new("COPY_ROTATION")
    cr.target = r; cr.owner_space = "WORLD"; cr.target_space = "WORLD"

# arms: remember the relaxed base pose, swing on top of it
ARM_BONES = [f"{b}.{s}" for b in ("shoulder01", "upperarm01", "upperarm02", "lowerarm01") for s in ("L", "R")]
BASE = {n: P[n].matrix_basis.copy() for n in ARM_BONES + ["spine03", "spine05", "neck02"]}

def rot_world(pb, axis_vec, deg):
    bpy.context.view_layer.update()
    head = arm.matrix_world @ pb.head
    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis_vec) @ Matrix.Translation(-head)
    pb.matrix = arm.matrix_world.inverted() @ R @ arm.matrix_world @ pb.matrix

X = Vector((1, 0, 0)); Y = Vector((0, 1, 0)); Z = Vector((0, 0, 1))

def aim(pb, d):
    """rotate a bone about its head so it points along world direction d"""
    bpy.context.view_layer.update()
    M = arm.matrix_world @ pb.matrix
    cur = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    q = cur.rotation_difference(d.normalized())
    head = M.translation.copy()
    R = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
    pb.matrix = arm.matrix_world.inverted() @ R @ M

SHOULDER_DROP = float(os.environ.get("SHOULDER_DROP", "8"))
ARM_OUT = float(os.environ.get("ARM_OUT", "0.16"))     # upper arm leans out just enough to clear the hoodie
FORE_OUT = float(os.environ.get("FORE_OUT", "0.10"))
ELBOW = float(os.environ.get("ELBOW", "12"))           # soft natural elbow bend (deg)
SWING = float(os.environ.get("SWING", "14"))

# ---------------------------------------------------------------- relaxed hands (static: no keys needed)
CURL = float(os.environ.get("CURL_SIGN", "1"))
TWIST = float(os.environ.get("TWIST", "35"))      # forearm twist so palms face the thighs
ARM_IN = float(os.environ.get("ARM_IN", "6"))     # upper arms closer to the body
FA_IN = float(os.environ.get("FA_IN", "-4"))        # forearms/hands in toward the thighs
CURLS = {"1": (8, 14, 10), "2": (18, 28, 18), "3": (22, 32, 20), "4": (26, 36, 22), "5": (30, 40, 24)}
for side, s in (("L", 1), ("R", -1)):
    for f, angs in CURLS.items():
        for j, a in zip((1, 2, 3), angs):
            pb = P.get(f"finger{f}-{j}.{side}")
            if pb:
                pb.rotation_mode = "XYZ"; pb.rotation_euler = (math.radians(CURL * a), 0, 0)
    w = P.get(f"wrist.{side}")
    if w: w.rotation_mode = "XYZ"; w.rotation_euler = (math.radians(-8), 0, 0)   # slight relaxed wrist drop
    la2 = P.get(f"lowerarm02.{side}")
    if la2: la2.rotation_mode = "XYZ"; la2.rotation_euler = (0, math.radians(s * TWIST), 0)

# ---------------------------------------------------------------- camera: follows on one axis, slow push-in
ANG = {"front": 0, "threequarter": -35, "side": -90, "hands": -20}[VIEW]
rig.rotation_euler = (0, 0, math.radians(ANG))
cam.data.lens = 50
for o in (arm, rig, cam) + tuple(TGT.values()) + tuple(ROT.values()):
    if o.animation_data: o.animation_data_clear()

for f in range(1, N + 1):
    t = (f - 1) / FPS
    sc.frame_set(f)
    arm.location = (0, body_y(t), body_z(t)); arm.keyframe_insert("location", frame=f)
    rig.location = (0, body_y(t), 0); rig.keyframe_insert("location", frame=f)
    k = smooth(t / SECS)
    if VIEW == "hands":
        cam.location = (0, -2.2, 1.0); tgt = Vector((0, 0, 0.95))
    else:
        cam.location = (0, -4.9 + 0.45 * k, 1.0 - 0.06 * k); tgt = Vector((0, 0, 0.86))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)
    for side, off, sx in (("L", 0.0, 1), ("R", 0.5, -1)):
        y, z, pitch = foot_state(t, off)
        TGT[side].location = (sx * FOOT_X, y, z); TGT[side].keyframe_insert("location", frame=f)
        ROT[side].rotation_euler = (Matrix.Rotation(math.radians(pitch), 3, X) @ foot_rest[side]).to_euler()
        ROT[side].keyframe_insert("rotation_euler", frame=f)
    bpy.context.view_layer.update()
    for n in BASE: P[n].matrix_basis = BASE[n].copy()
    ph = 2 * math.pi * t / T
    for side, off in (("L", 0.0), ("R", 0.5)):
        sw = math.cos(ph + 2 * math.pi * off)           # +1 = this arm back (same-side leg forward)
        s = 1 if side == "L" else -1
        rot_world(P["shoulder01." + side], Y, s * SHOULDER_DROP)   # relaxed, lowered shoulders
        # aim each segment: upper arm hangs straight down just off the body, soft elbow
        up = Matrix.Rotation(math.radians(SWING * sw), 3, X) @ Vector((s * ARM_OUT, 0.0, -1.0))
        bend = ELBOW + 10 * max(0, -sw)
        fa = Matrix.Rotation(math.radians(SWING * sw - bend), 3, X) @ Vector((s * FORE_OUT, 0.0, -1.0))
        aim(P["upperarm01." + side], up); aim(P["upperarm02." + side], up)
        aim(P["lowerarm01." + side], fa)
    rot_world(P["spine05"], Z, 4 * math.sin(ph))          # hips twist with the legs
    rot_world(P["spine03"], Z, -5 * math.sin(ph))         # shoulders counter-twist
    rot_world(P["neck02"], Z, 2.5 * math.sin(ph))         # head stays facing forward
    for n in BASE: P[n].keyframe_insert("rotation_euler" if P[n].rotation_mode != "QUATERNION" else "rotation_quaternion", frame=f)

# linear interpolation everywhere (motion is already sampled every frame)
for o in (arm, rig, cam) + tuple(TGT.values()) + tuple(ROT.values()):
    ad = o.animation_data
    if ad and ad.action:
        try:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
        except Exception: pass

r = sc.render
r.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2
r.use_motion_blur = True; r.motion_blur_shutter = 0.5
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(OUT), "doc_walk.blend"))
frames = range(1, N + 1) if FRAMES == "all" else [int(x) for x in FRAMES.split(",")]
for f in frames:
    sc.frame_set(f); r.filepath = os.path.join(OUT, f"{VIEW}_{f:04d}.png")
    bpy.ops.render.render(write_still=True); print("FRAME", f, flush=True)
