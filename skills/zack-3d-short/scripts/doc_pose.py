# Shared pose helpers for every Doc shot: relaxed arms/hands (never the stiff MPFB base pose) and blinking.
import bpy, math, os, random
from mathutils import Vector, Matrix

X = Vector((1, 0, 0)); Y = Vector((0, 1, 0)); Z = Vector((0, 0, 1))
CURLS = {"1": (8, 14, 10), "2": (18, 28, 18), "3": (22, 32, 20), "4": (26, 36, 22), "5": (30, 40, 24)}

def get_arm():
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")

def get_body():
    return next(o for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys
                and any("eyeBlink" in k.name for k in o.data.shape_keys.key_blocks))

def _update(): bpy.context.view_layer.update()

def rot_world(arm, pb, axis, deg):
    _update(); head = arm.matrix_world @ pb.head
    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
    pb.matrix = arm.matrix_world.inverted() @ R @ arm.matrix_world @ pb.matrix

def aim(arm, pb, d):
    """point a bone (head->tail) along world direction d"""
    _update(); M = arm.matrix_world @ pb.matrix
    q = (M.to_3x3() @ Vector((0, 1, 0))).normalized().rotation_difference(d.normalized())
    h = M.translation.copy()
    pb.matrix = arm.matrix_world.inverted() @ Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ M

def relaxed_hands(arm, twist=35):
    P = arm.pose.bones
    for side, s in (("L", 1), ("R", -1)):
        for f, angs in CURLS.items():
            for j, a in zip((1, 2, 3), angs):
                pb = P.get(f"finger{f}-{j}.{side}")
                if pb: pb.rotation_mode = "XYZ"; pb.rotation_euler = (math.radians(a), 0, 0)
        w = P.get(f"wrist.{side}")
        if w: w.rotation_mode = "XYZ"; w.rotation_euler = (math.radians(-8), 0, 0)
        la2 = P.get(f"lowerarm02.{side}")
        if la2: la2.rotation_mode = "XYZ"; la2.rotation_euler = (0, math.radians(s * twist), 0)

def arm_dirs(yaw_deg=0.0, swing=0.0, elbow=12.0, up_fwd=0.0, fore_fwd=0.0, side=1, out=0.16, fore_out=0.10):
    """world directions for upper arm and forearm. yaw = body facing (0 = facing -Y).
    swing: + = arm back. up_fwd/fore_fwd: extra forward reach (deg) e.g. hands on thighs when sitting."""
    Rz = Matrix.Rotation(math.radians(yaw_deg), 3, Z)
    up = Matrix.Rotation(math.radians(swing - up_fwd), 3, X) @ Vector((side * out, 0.0, -1.0))
    fa = Matrix.Rotation(math.radians(swing - up_fwd - elbow - fore_fwd), 3, X) @ Vector((side * fore_out, 0.0, -1.0))
    return Rz @ up, Rz @ fa

def pose_arms(arm, yaw_deg=0.0, swing_L=0.0, swing_R=0.0, elbow=12.0, up_fwd=0.0, fore_fwd=0.0, shoulder_drop=8.0, out=0.16, fore_out=0.10):
    P = arm.pose.bones
    for side, s, sw in (("L", 1, swing_L), ("R", -1, swing_R)):
        rot_world(arm, P["shoulder01." + side], Matrix.Rotation(math.radians(yaw_deg), 3, Z) @ Y, s * shoulder_drop)
        up, fa = arm_dirs(yaw_deg, sw, elbow, up_fwd, fore_fwd, s, out, fore_out)
        aim(arm, P["upperarm01." + side], up); aim(arm, P["upperarm02." + side], up)
        aim(arm, P["lowerarm01." + side], fa)

ARM_KEY_BONES = [f"{b}.{s}" for b in ("shoulder01", "upperarm01", "upperarm02", "lowerarm01") for s in ("L", "R")]

def key_bones(arm, names, frame):
    for n in names:
        pb = arm.pose.bones[n]
        pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=frame)

def add_blinks(n_frames, fps=30, seed=3, start=None):
    """natural blinks every 2-4 s: close in 3 frames, hold 1, open in 4"""
    body = get_body()
    keys = [k for k in body.data.shape_keys.key_blocks if "eyeBlink" in k.name]
    rnd = random.Random(seed)
    t = start if start is not None else rnd.uniform(0.6, 1.4) * fps
    for k in keys: k.value = 0.0; k.keyframe_insert("value", frame=1)
    while t < n_frames - 8:
        f = int(t)
        for k in keys:
            for df, v in ((0, 0.0), (3, 1.0), (4, 1.0), (8, 0.0)):
                k.value = v; k.keyframe_insert("value", frame=f + df)
        t += rnd.uniform(2.0, 4.0) * fps
    return keys
