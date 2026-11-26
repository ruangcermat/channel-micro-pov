# Doc walks in from the right, stops in front of the chair, turns to face camera and sits down.
# Footstep planner (planted IK feet, heel/toe), body follows the steps, relaxed arms, blinks.
# Run: blender -b renders/doc_room.blend -P room_sit.py -- <out_dir> <samples> <width> <frames|all|none>
import bpy, math, os, sys
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "renders/sit")
SAMPLES = int(argv[1]) if len(argv) > 1 else 40
WIDTH = int(argv[2]) if len(argv) > 2 else 720
FRAMES = argv[3] if len(argv) > 3 else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); import doc_pose as D
X, Y, Z = D.X, D.Y, D.Z
os.makedirs(OUT, exist_ok=True)
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"

sc = bpy.context.scene; FPS = 30
arm = D.get_arm(); P = arm.pose.bones; cam = bpy.data.objects["Cam"]
for o in list(bpy.data.objects):
    if o.name.startswith(("IK_", "FootRot_")): bpy.data.objects.remove(o, do_unlink=True)
for o in (arm, cam):
    if o.animation_data: o.animation_data_clear()
for pb in P:
    for c in list(pb.constraints): pb.constraints.remove(c)
    pb.matrix_basis.identity()
arm.location = (0, 0, 0); arm.rotation_mode = "XYZ"; arm.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()

# hood: ride on the upper back (spine01), not the neck, so it never swings off when the head turns
hood = bpy.data.objects.get("Hood")
if hood:
    mw = hood.matrix_world.copy()
    me = hood.data; cen = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    for v in me.vertices:                       # flatter, lower, tucked onto the upper back
        d = v.co - cen
        if d.y > 0:  d.y *= 0.45                # back face of the fold: lie flat against the back
        v.co = cen + Vector((d.x * 1.04, d.y * 0.85 - 0.014, d.z * 0.82 - 0.012))
    hood.parent = arm; hood.parent_type = "BONE"; hood.parent_bone = "spine01"
    bpy.context.view_layer.update(); hood.matrix_world = mw
    print("HOOD reparented to spine01")

def smooth(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)
def lerp(a, b, k): return a + (b - a) * k
def Rz(deg): return Matrix.Rotation(math.radians(deg), 3, Z)

# ---------------------------------------------------------------- measure Doc + chair
W = arm.matrix_world
HIP0 = (W @ P["upperleg01.L"].head + W @ P["upperleg01.R"].head) / 2
THIGH = (P["upperleg01.L"].head - P["lowerleg01.L"].head).length
SHIN = (P["lowerleg01.L"].head - P["lowerleg02.L"].tail).length
print("SHIN", round(SHIN, 3))
print("HIP0", tuple(round(v, 3) for v in HIP0), "THIGH", round(THIGH, 3))
CHX, CHY = -0.55, 0.55
ANK_Z_ = 0.065
arm.location = (5, 5, 0); bpy.context.view_layer.update()       # out of the ray's way
dg = bpy.context.evaluated_depsgraph_get(); seat = []
for i in range(18):
    yy = 0.15 + 0.04 * i
    hit, loc, *_ = sc.ray_cast(dg, Vector((CHX, yy, 0.62)), Vector((0, 0, -1)))
    if hit: seat.append((yy, loc.z))
print("SEAT PROFILE", [(round(a, 2), round(b, 3)) for a, b in seat])
SEAT_Z = max(z for y_, z in seat if 0.35 < z < 0.5)
SEAT_FRONT = min(y_ for y_, z in seat if z > SEAT_Z - 0.04)
HIP_SEAT = Vector((CHX, SEAT_FRONT + 0.22, max(SEAT_Z + 0.11, ANK_Z_ + SHIN + 0.05)))   # thighs level, resting on the seat     # hip joints over the seat's front half
FEET_Y = HIP_SEAT.y - THIGH * 0.97 - 0.03                          # shins near vertical, feet a touch forward
ANK_Y, ANK_Z, FOOT_X = -0.017, 0.065, 0.10
STAND = Vector((CHX, FEET_Y - ANK_Y, 0))                           # where he stops (body origin)
print("SEAT_Z", round(SEAT_Z, 3), "SEAT_FRONT", SEAT_FRONT, "STAND", tuple(round(v, 3) for v in STAND))

# ---------------------------------------------------------------- timeline
V = 0.83; X_START = 1.62; WALK_YAW = -90.0          # walking toward -X
D_DEC = 0.9                                          # deceleration time
T_DEC = (X_START - STAND.x - V * D_DEC / 2) / V      # cruise until here
T_STOP = T_DEC + D_DEC
def walk_u(t):                                       # distance travelled
    if t <= T_DEC: return V * t
    tau = min(t - T_DEC, D_DEC); return V * T_DEC + V * (tau - tau * tau / (2 * D_DEC))
def walk_speed(t):
    if t <= T_DEC: return V
    return max(0.0, V * (1 - (t - T_DEC) / D_DEC))
WALK_Y = STAND.y - 0.16                              # walk a little in front of the chair, step back during the turn
def walk_pos(t): return Vector((X_START - walk_u(t), WALK_Y, 0))

# footsteps: (side, t_land, ankle_xy, yaw, heel_toe)
steps = []
def foot_at(body, yaw, side):
    sx = 1 if side == "L" else -1
    return body.xy + (Rz(yaw) @ Vector((sx * FOOT_X, ANK_Y, 0))).xy
t, side = -1.0, "R"
while True:
    tb = t + 0.3
    pos = walk_pos(tb)
    steps.append((side, t, foot_at(pos, WALK_YAW, side), WALK_YAW, walk_speed(t) / V))
    if tb >= T_STOP and len([s for s in steps if s[1] > T_STOP - 0.6]) >= 2: break
    t += 0.5 + 0.12 * (1 - walk_speed(t) / V); side = "L" if side == "R" else "R"
LAST_WALK = steps[-1][1]
# stepping turn to face the camera (left turn, -90 -> 0)
T_TURN = LAST_WALK + 0.2
TURN_END = T_TURN + 1.35
def turn_pos(t): return Vector((STAND.x, lerp(WALK_Y, STAND.y, smooth((t - T_TURN - 0.1) / (TURN_END - T_TURN))), 0))
turn_steps = [("L", T_TURN + 0.45, -45.0), ("R", T_TURN + 0.85, -10.0), ("L", T_TURN + 1.2, 0.0), ("R", T_TURN + 1.5, 0.0)]
for sd, tl, yw in turn_steps:
    steps.append((sd, tl, foot_at(turn_pos(tl + 0.15), yw, sd), yw, 0.15))
def body_yaw(t): return lerp(WALK_YAW, 0.0, smooth((t - T_TURN) / (TURN_END - T_TURN)))
T_SIT = T_TURN + 1.75; SIT_DUR = 1.5
N = int(round((T_SIT + SIT_DUR + 1.4) * FPS))
sc.render.fps = FPS; sc.frame_start = 1; sc.frame_end = N
print("TIMES dec", round(T_DEC, 2), "stop", round(T_STOP, 2), "turn", round(T_TURN, 2), "sit", round(T_SIT, 2), "frames", N)

def foot_state(side, t):
    my = [s for s in steps if s[0] == side]
    prev = [s for s in my if s[1] <= t]; nxt = [s for s in my if s[1] > t]
    cur = prev[-1] if prev else my[0]
    if not nxt:
        k = (t - cur[1]) / 0.08 if cur[4] > 0.5 else 1
        return cur[2], ANK_Z, cur[3], -14 * cur[4] * (1 - smooth(k))
    n = nxt[0]; ht = n[4]
    swing = 0.4 if ht > 0.5 else 0.32
    lift = n[1] - swing
    if t < lift:                                   # planted
        pitch = 0.0
        dt = t - cur[1]
        if cur[4] > 0.5 and dt < 0.08: pitch = -14 * cur[4] * (1 - dt / 0.08)
        peel = 0.18 * ht
        if ht > 0.05 and t > lift - peel:          # heel peels, pivot on the ball
            k = smooth((t - (lift - peel)) / peel); pitch = 32 * ht * k
            z = ANK_Z + 0.115 * math.sin(math.radians(pitch))
            fwd = (Rz(cur[3]) @ Vector((0, -1, 0))).xy
            return cur[2] + fwd * 0.04 * k * ht, z, cur[3], pitch
        return cur[2], ANK_Z, cur[3], pitch
    s = (t - lift) / swing
    toe0 = 32 * ht
    a = cur[2] + (Rz(cur[3]) @ Vector((0, -1, 0))).xy * 0.04 * ht
    xy = a.lerp(n[2], smooth(s))
    z_off = ANK_Z + 0.115 * math.sin(math.radians(toe0)) * (1 - smooth(s * 2.2))
    lift_h = 0.07 if ht > 0.5 else 0.045
    z = max(z_off, ANK_Z) + lift_h * math.sin(math.pi * min(1, s * 1.15)) ** 1.3
    pitch = toe0 * (1 - smooth(s / 0.55)) - 14 * ht * smooth((s - 0.55) / 0.45)
    yaw = lerp(cur[3], n[3], smooth(s))
    return xy, z, yaw, pitch

# ---------------------------------------------------------------- IK rig
foot_rest = {s: (W @ P["foot." + s].matrix).to_3x3().normalized() for s in ("L", "R")}
TGT, ROT, POLE = {}, {}, {}
for s in ("L", "R"):
    e = bpy.data.objects.new("IK_" + s, None); sc.collection.objects.link(e); TGT[s] = e
    r = bpy.data.objects.new("FootRot_" + s, None); sc.collection.objects.link(r); ROT[s] = r
    c = P["lowerleg02." + s].constraints.new("IK"); c.target = e; c.chain_count = 4; c.use_stretch = False; c.use_tail = True
    cr = P["foot." + s].constraints.new("COPY_ROTATION"); cr.target = r; cr.owner_space = "WORLD"; cr.target_space = "WORLD"
    pl = bpy.data.objects.new("IKPole_" + s, None); sc.collection.objects.link(pl); POLE[s] = pl
    c.pole_target = pl
POLE_OFF = lambda sx: Vector((sx * 0.14, -1.2, 0.45))         # in front of the knee, body space
def place_poles(loc, yaw):
    for sd, sx in (("L", 1), ("R", -1)):
        POLE[sd].location = Vector((loc.x, loc.y, 0)) + Rz(yaw) @ POLE_OFF(sx)
# calibrate pole angle on the seated pose: knee must point forward (-Y), over the foot
seat_loc = HIP_SEAT - HIP0
arm.location = seat_loc; arm.rotation_euler = (0, 0, 0); place_poles(seat_loc, 0)
for sd, sx in (("L", 1), ("R", -1)):
    TGT[sd].location = (STAND.x + sx * FOOT_X, FEET_Y, ANK_Z)
    ROT[sd].rotation_euler = foot_rest[sd].to_euler()
for sd in ("L", "R"):
    c = P["lowerleg02." + sd].constraints[0]; best = None
    for a in range(-180, 180, 10):
        c.pole_angle = math.radians(a); bpy.context.view_layer.update()
        k = arm.matrix_world @ P["lowerleg01." + sd].head; h = arm.matrix_world @ P["upperleg01." + sd].head
        score = k.y + 2 * abs(k.x - h.x) - 0.5 * k.z
        if best is None or score < best[0]: best = (score, a, k.copy())
    c.pole_angle = math.radians(best[1]); print("POLE", sd, best[1], "knee", tuple(round(v, 3) for v in best[2]))

POSE_BONES = D.ARM_KEY_BONES + [f"{b}.{s}" for b in ("lowerarm02", "wrist") for s in ("L", "R")] + \
             ["spine05", "spine04", "spine03", "spine01", "neck01", "neck02"] + \
             [f"finger{f}-{j}.{s}" for f in "12345" for j in (1, 2, 3) for s in ("L", "R")]
POSE_BONES = [n for n in POSE_BONES if n in P]

def body_state(t):
    """armature location, yaw, sit progress"""
    yaw = body_yaw(t)
    if t < T_STOP:
        pos = walk_pos(t)
        ph = 4 * math.pi * (t - steps[0][1]) / 1.0
        amp = walk_speed(t) / V
        z = lerp(-0.02, -0.032 + 0.014 * (0.5 - 0.5 * math.cos(ph)), amp)
    else:
        pos = turn_pos(t); z = -0.02
        if T_TURN < t < TURN_END + 0.3: z -= 0.008 * math.sin(math.pi * (t - T_TURN) / (TURN_END + 0.3 - T_TURN))
    s = (t - T_SIT) / SIT_DUR
    if s > 0:
        hip_stand = pos + Vector((0, 0, z)) + HIP0
        dy = HIP_SEAT.y - hip_stand.y; dz = HIP_SEAT.z - hip_stand.z
        ky = smooth(min(1, s * 1.1)); kz = smooth(s / 0.95)       # knees bend with the lean from the first frame
        pos = pos + Vector((0, dy * ky, 0)); z = z + dz * kz
    return Vector((pos.x, pos.y, z)), yaw, max(0.0, min(1.0, s))

def wpos(v): return arm.matrix_world @ v
def blend_dir(a, b, k): return a.normalized().lerp(b.normalized(), k).normalized()
def hands_on_thighs(yaw, k):
    """two-bone solve: wrist lands on top of the thigh, elbow relaxed back/out"""
    bpy.context.view_layer.update()
    back = Rz(yaw) @ Vector((0, 1, 0))
    for sd, sx in (("L", 1), ("R", -1)):
        H = wpos(P["upperleg01." + sd].head); K = wpos(P["lowerleg01." + sd].head)
        side = Rz(yaw) @ Vector((sx, 0, 0))
        ax = (K - H).normalized(); nrm = ax.cross(side).normalized()          # thigh's top/front surface normal
        if nrm.z + nrm.dot(-back) < 0: nrm = -nrm
        T = H + (K - H) * 0.6 + nrm * 0.14 + side * 0.035                     # hand rests on the thigh surface
        Wt = T + (H - K).normalized() * 0.07 + nrm * 0.02
        W0 = wpos(P["lowerarm02." + sd].tail)                                    # where the hanging wrist is now
        arc = math.sin(math.pi * k)
        Wt = W0.lerp(Wt, k) + (nrm * 0.07 + side * 0.06) * arc                  # travel over the thigh, never through it
        kk = k; k = 1.0          # wrist sits a little behind the palm
        u1, u2, l1, l2 = (P[f"{b}.{sd}"] for b in ("upperarm01", "upperarm02", "lowerarm01", "lowerarm02"))
        a = u1.length + u2.length; b = l1.length + l2.length
        S = wpos(u1.head); u = Wt - S; d = min(u.length, a + b - 0.002); dn = u.normalized()
        x = (a * a - b * b + d * d) / (2 * d); h = math.sqrt(max(0.0, a * a - x * x))
        pole = back * 0.8 + side * 0.6; pole = (pole - dn * pole.dot(dn)).normalized()
        E = S + dn * x + pole * h
        cur_up = wpos(u1.tail) - wpos(u1.head)
        upd = blend_dir(cur_up, E - S, k)
        D.aim(arm, u1, upd); D.aim(arm, u2, upd)
        bpy.context.view_layer.update()
        cur_fa = wpos(l1.tail) - wpos(l1.head)
        D.aim(arm, l1, blend_dir(cur_fa, Wt - wpos(l1.head), k))
        for _ in range(3):      # CCD passes: true wrist (lowerarm02 tail) onto the target
            for bone, chain in ((u1, (u1, u2)), (l1, (l1,))):
                bpy.context.view_layer.update()
                o = wpos(bone.head); wr = wpos(l2.tail)
                q = (wr - o).rotation_difference(Wt - o)
                q = Quaternion().slerp(q, k)
                for bb in chain:
                    bpy.context.view_layer.update(); M = arm.matrix_world @ bb.matrix
                    R = Matrix.Translation(o) @ q.to_matrix().to_4x4() @ Matrix.Translation(-o)
                    bb.matrix = arm.matrix_world.inverted() @ R @ M
                    if bb is u1: bpy.context.view_layer.update()
        # lay the hand flat along the thigh, fingers toward the knee
        bpy.context.view_layer.update()
        wb = P["wrist." + sd]; cur = wpos(wb.tail) - wpos(wb.head)
        D.aim(arm, wb, blend_dir(cur, (K - H).normalized() + Vector((0, 0, -0.35)) - side * 0.15, kk))
        if k > 0.99 and f in (N,):
            print("HAND", sd, "wrist", tuple(round(v, 3) for v in wpos(l2.tail)), "target", tuple(round(v, 3) for v in Wt))

for f in range(1, N + 1):
    t = (f - 1) / FPS
    sc.frame_set(f)
    loc, yaw, s = body_state(t)
    arm.location = loc; arm.rotation_euler = (0, 0, math.radians(yaw))
    arm.keyframe_insert("location", frame=f); arm.keyframe_insert("rotation_euler", frame=f)
    place_poles(loc, yaw)
    for pl in POLE.values(): pl.keyframe_insert("location", frame=f)
    for sd in ("L", "R"):
        xy, z, fyaw, pitch = foot_state(sd, t)
        TGT[sd].location = (xy.x, xy.y, z); TGT[sd].keyframe_insert("location", frame=f)
        ROT[sd].rotation_euler = (Rz(fyaw) @ Matrix.Rotation(math.radians(pitch), 3, X) @ foot_rest[sd]).to_euler()
        ROT[sd].keyframe_insert("rotation_euler", frame=f)
    bpy.context.view_layer.update()
    for n in POSE_BONES: P[n].matrix_basis.identity()
    # spine: walk twist, sit lean (forward while lowering, settles slightly back)
    amp = walk_speed(t) / V if t < T_STOP else 0.0
    ph = 2 * math.pi * (t - steps[0][1])
    fwd_axis = Rz(yaw) @ X
    lean = 0.0
    if s > 0: lean = 26 * math.sin(math.pi * min(1, s / 0.85)) ** 1.2 * (1 - smooth((s - 0.6) / 0.4)) + 4 * smooth(s)
    if lean: D.rot_world(arm, P["spine05"], fwd_axis, lean * 0.55); D.rot_world(arm, P["spine03"], fwd_axis, lean * 0.45)
    D.rot_world(arm, P["spine05"], Z, 4 * amp * math.sin(ph)); D.rot_world(arm, P["spine03"], Z, -5 * amp * math.sin(ph))
    if lean: D.rot_world(arm, P["neck02"], fwd_axis, -lean * 0.6)
    # breathing once seated
    if s >= 1: D.rot_world(arm, P["spine03"], fwd_axis, 0.8 * math.sin(2 * math.pi * (t - T_SIT) / 3.6))
    # arms: walk swing -> settle -> reach to thighs while sitting
    swL = 14 * amp * math.cos(ph); swR = 14 * amp * math.cos(ph + math.pi)
    ks = smooth(s / 0.8)
    up_fwd = lerp(0, 24, ks); fore_fwd = lerp(0, 38, ks); out = lerp(0.16, 0.10, ks); fore_out = lerp(0.10, -0.12, ks)
    elbow = 12 + 10 * max(0, -math.cos(ph)) * amp
    D.relaxed_hands(arm, twist=lerp(35, 75, smooth(s / 0.8)))
    D.pose_arms(arm, yaw_deg=yaw, swing_L=swL, swing_R=swR, elbow=elbow, up_fwd=up_fwd, fore_fwd=fore_fwd, out=out, fore_out=fore_out)
    kh = smooth((s - 0.3) / 0.55)
    if kh > 0: hands_on_thighs(yaw, kh)
    for n in POSE_BONES:
        pb = P[n]; pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)

# blinks on every mesh that carries blink keys (body + any eyelash proxy)
import random
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.data.shape_keys and any("eyeBlink" in k.name for k in ob.data.shape_keys.key_blocks):
        keys = [k for k in ob.data.shape_keys.key_blocks if "eyeBlink" in k.name]
        rnd = random.Random(7); tt = 0.9 * FPS
        for k in keys: k.value = 0.0; k.keyframe_insert("value", frame=1)
        while tt < N - 8:
            fb = int(tt)
            for k in keys:
                for df, v in ((0, 0.0), (3, 1.0), (4, 1.0), (8, 0.0)): k.value = v; k.keyframe_insert("value", frame=fb + df)
            tt += rnd.uniform(2.0, 3.4) * FPS
        print("BLINKS on", ob.name)

# ---------------------------------------------------------------- camera: slow pan with him + gentle push-in
for f in range(1, N + 1):
    t = (f - 1) / FPS; k = smooth(t / (N / FPS))
    bx = body_state(t)[0].x
    tx = lerp(0.35, -0.3, smooth((1.6 - bx) / 2.0))
    cam.location = (lerp(0.45, 0.3, k), lerp(-2.7, -2.25, k), lerp(1.1, 1.02, k))
    tgt = Vector((tx, 0.4, lerp(0.8, 0.7, k)))
    cam.rotation_euler = (tgt - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)

r = sc.render; r.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2
r.use_motion_blur = True; r.motion_blur_shutter = 0.5
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "doc_room_sit.blend"))
if FRAMES != "none":
    frames = range(1, N + 1) if FRAMES == "all" else [int(x) for x in FRAMES.split(",")]
    for f in frames:
        sc.frame_set(f); r.filepath = os.path.join(OUT, f"sit_{f:04d}.png")
        bpy.ops.render.render(write_still=True); print("FRAME", f, flush=True)
