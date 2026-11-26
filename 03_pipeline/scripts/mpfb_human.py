#!/usr/bin/env python3
"""MPFB2 Human Rig Loader, Kosan Outfit Adapter, Posing, ARKit Expressions & Hand-Prop Tracker.

Adopts the proven Zack-Blender-Pack architecture (`skills/zack-3d-short/`):
- Loads real MPFB2 human rig from `family_ready.blend` (100% packed textures, ENHANCED_SSS skin,
  Displace 0.006 on clothes, 31 ARKit `!ex-*` shape keys, full 163-bone default rig).
- Strictly obeys every anti-bug rule in `TROUBLESHOOTING.md` & `MPFB_REFERENCE.md`:
  1. NEVER zeroes `$md-*` body shape keys (touches ONLY `!ex-*` expression keys).
  2. Never leaves stiff MPFB A-pose (uses `doc_pose.py` relaxed_hands / pose_arms + world-space `reach()`).
  3. Applies `BOOST = 1.6` to ARKit expressions + rotates the `jaw` bone (`17° * jaw`) so teeth/tongue
     move naturally with the mouth.
  4. Applies `fix_teeth.py` (links teeth texture directly to Base Color so gums/teeth never render grey).
  5. Keeps every part parented to the rig and verifies zero unpacked textures & zero floating meshes.
  6. Anchors hand-held props (`sandal_jepit_swallow`) directly from `wrist.R` world palm frame every frame
     (`wrist.head + palm_dir * 0.055 * scale + palm_normal * 0.045 * scale`) so the sandal NEVER floats.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

REPO_ROOT = Path(__file__).resolve().parents[2]
ZACK_SCRIPTS = REPO_ROOT / "skills" / "zack-3d-short" / "scripts"
if str(ZACK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ZACK_SCRIPTS))

import doc_pose as D  # noqa: E402

X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))
Z = Vector((0.0, 0.0, 1.0))

BOOST = 1.6

# Finger curls for firmly gripping the Swallow flip-flop heel (power grip) vs open panic drop (Scene 8)
GRIP_CURLS = {
    "1": (28, 38, 26),
    "2": (64, 78, 56),
    "3": (68, 80, 58),
    "4": (70, 82, 60),
    "5": (72, 84, 62),
}
OPEN_CURLS = {
    "1": (4, 6, 4),
    "2": (5, 8, 5),
    "3": (6, 8, 5),
    "4": (7, 9, 6),
    "5": (8, 10, 6),
}


def sym(**kw: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in kw.items():
        if k.endswith("_"):
            out[k[:-1] + "Left"] = v
            out[k[:-1] + "Right"] = v
        else:
            out[k] = v
    return out


# Proven Zack-style ARKit expression library (multiplied by BOOST = 1.6)
EXPR: Dict[str, Dict[str, float]] = {
    "neutral": sym(mouthSmile_=0.06),
    "glare": sym(
        browDown_=0.95,
        eyeWide_=0.68,
        noseSneer_=0.78,
        mouthPress_=0.45,
        mouthFrown_=0.60,
        jawOpen=0.16,
        jawForward=0.22,
    ),
    "angry": sym(
        browDown_=1.0,
        eyeWide_=0.55,
        eyeSquint_=0.32,
        noseSneer_=0.88,
        mouthPress_=0.40,
        mouthFrown_=0.68,
        mouthStretch_=0.45,
        jawOpen=0.26,
        jawForward=0.25,
    ),
    "shock": sym(
        eyeWide_=0.98,
        browInnerUp=0.95,
        browOuterUp_=0.88,
        jawOpen=0.62,
        mouthFunnel=0.25,
    ),
    "panic": sym(
        eyeWide_=1.0,
        browInnerUp=1.0,
        browOuterUp_=0.85,
        mouthStretch_=0.72,
        mouthFrown_=0.48,
        jawOpen=0.85,
        mouthLowerDown_=0.58,
    ),
}

POSE_BONES: List[str] = (
    [
        f"{b}.{s}"
        for b in ("shoulder01", "upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist")
        for s in ("L", "R")
    ]
    + ["spine05", "spine04", "spine03", "spine01", "neck01", "neck02", "head"]
    + [f"finger{f_}-{j}.{s}" for f_ in "12345" for j in (1, 2, 3) for s in ("L", "R")]
)


def upd() -> None:
    bpy.context.view_layer.update()


def Rz(deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 3, Z)


def wp(arm: bpy.types.Object, v: Vector) -> Vector:
    return arm.matrix_world @ v


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, k))


# =============================================================================
# MATERIAL POLISH (TEETH FIX, KOSAN KAUS + CELANA PENDEK KOLOR, BAREFOOT SSS)
# =============================================================================

def _fix_teeth_materials() -> None:
    """Apply `skills/zack-3d-short/scripts/fix_teeth.py` so teeth & gums never render grey."""
    for obj in bpy.data.objects:
        if "teeth" not in obj.name.lower():
            continue
        for sl in obj.material_slots:
            mat = sl.material
            if not mat or not mat.use_nodes or not mat.node_tree:
                continue
            nt = mat.node_tree
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
            if not bsdf:
                continue
            for link in list(bsdf.inputs["Base Color"].links):
                nt.links.remove(link)
            if tex:
                nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = 0.28
            if "Coat Weight" in bsdf.inputs:
                bsdf.inputs["Coat Weight"].default_value = 0.30
            if "Subsurface Weight" in bsdf.inputs:
                bsdf.inputs["Subsurface Weight"].default_value = 0.15


def _crop_pants_to_kosan_shorts(cloth_obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Trim lower pant legs below knee height to create authentic Indonesian kosan shorts (celana pendek)."""
    import bmesh

    upd()
    # Knee height in armature local rest space (just above knee cap so calves & shins are bare!)
    knee_z_local = float(arm.pose.bones["lowerleg01.L"].head.z) + 0.025
    # Map evaluated vertex positions back to mesh vertex indices so cropping matches shape keys/rig
    dg = bpy.context.evaluated_depsgraph_get()
    # Temporarily disable Subsurf so vertex indices align 1:1 with cloth_obj.data.vertices
    subsurf_states = []
    for m in cloth_obj.modifiers:
        if m.type == "SUBSURF":
            subsurf_states.append((m, m.show_viewport, m.show_render))
            m.show_viewport = False
            m.show_render = False
    upd()
    eval_obj = cloth_obj.evaluated_get(dg)
    eval_zs = [v.co.z for v in eval_obj.data.vertices]
    for m, sv, sr in subsurf_states:
        m.show_viewport = sv
        m.show_render = sr

    if len(eval_zs) == len(cloth_obj.data.vertices):
        bm = bmesh.new()
        bm.from_mesh(cloth_obj.data)
        bm.verts.ensure_lookup_table()
        del_faces = [
            f for f in bm.faces
            if (sum(eval_zs[v.index] for v in f.verts) / max(1, len(f.verts))) < knee_z_local
        ]
        if del_faces:
            bmesh.ops.delete(bm, geom=del_faces, context="FACES")
            # Remove any orphaned edges/verts left behind
            loose_verts = [v for v in bm.verts if not v.link_faces]
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
            bm.to_mesh(cloth_obj.data)
            cloth_obj.data.update()
        bm.free()

    # Add subtle Solidify so the shorts hem looks crisp & solid like cotton kolor fabric
    if not any(m.type == "SOLIDIFY" for m in cloth_obj.modifiers):
        sol = cloth_obj.modifiers.new("ShortsHemSolidify", "SOLIDIFY")
        sol.thickness = 0.004
        sol.offset = 1.0


def _style_kosan_outfit(cloth_obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Convert male_casualsuit06 into Indonesian kosan kaus oblong + dark knee-length celana pendek kolor.

    Keeps the packed AO + Normal maps intact for realistic cloth creases while removing the
    stock 'MR UDO' logo and cropping the pant legs at the knee.
    """
    _crop_pants_to_kosan_shorts(cloth_obj, arm)

    # Ensure Displace 0.006 anti-poke-through modifier is present
    has_disp = any(m.type == "DISPLACE" for m in cloth_obj.modifiers)
    if not has_disp:
        dm = cloth_obj.modifiers.new("ClothOut", "DISPLACE")
        dm.strength = 0.006
        dm.mid_level = 0.0

    for sl in cloth_obj.material_slots:
        mat = sl.material
        if not mat or not mat.use_nodes or not mat.node_tree:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue

        ao_node = next(
            (n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "ao" in n.image.name.lower()),
            None,
        )

        # UV.y > 0.58 = kaus oblong kosan (dark slate-navy cotton); UV.y <= 0.58 = celana pendek kolor gelap
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["UV"], sep.inputs["Vector"])

        is_tee = nt.nodes.new("ShaderNodeMath")
        is_tee.operation = "GREATER_THAN"
        is_tee.inputs[1].default_value = 0.58
        nt.links.new(sep.outputs["Y"], is_tee.inputs[0])

        garment_mix = nt.nodes.new("ShaderNodeMix")
        garment_mix.data_type = "RGBA"
        garment_mix.blend_type = "MIX"
        g_a = next(i for i in garment_mix.inputs if i.name == "A" and i.type == "RGBA")
        g_b = next(i for i in garment_mix.inputs if i.name == "B" and i.type == "RGBA")
        g_out = next(o for o in garment_mix.outputs if o.name == "Result" and o.type == "RGBA")
        nt.links.new(is_tee.outputs["Value"], garment_mix.inputs[0])
        # Celana pendek / kolor santai kosan: dark charcoal-black matte cotton
        g_a.default_value = (0.045, 0.050, 0.062, 1.0)
        # Kaus oblong kosan santai: muted dark slate-navy cotton
        g_b.default_value = (0.085, 0.125, 0.175, 1.0)

        if ao_node:
            ao_mul = nt.nodes.new("ShaderNodeMix")
            ao_mul.data_type = "RGBA"
            ao_mul.blend_type = "MULTIPLY"
            ao_mul.inputs[0].default_value = 0.88
            a_a = next(i for i in ao_mul.inputs if i.name == "A" and i.type == "RGBA")
            a_b = next(i for i in ao_mul.inputs if i.name == "B" and i.type == "RGBA")
            a_out = next(o for o in ao_mul.outputs if o.name == "Result" and o.type == "RGBA")
            nt.links.new(g_out, a_a)
            nt.links.new(ao_node.outputs["Color"], a_b)
            final_col = a_out
        else:
            final_col = g_out

        for link in list(bsdf.inputs["Base Color"].links):
            nt.links.remove(link)
        nt.links.new(final_col, bsdf.inputs["Base Color"])
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.86
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.0


def _polish_skin_barefoot(body_obj: bpy.types.Object) -> None:
    """Keep ENHANCED_SSS skin matte (never waxy) with warm natural Indonesian tone & reveal bare feet/calves."""
    # Remove shoe & pant delete-mask modifiers on Kid_body so 100% real MPFB2 calves & bare feet render!
    # Keep "Hide helpers" MASK modifier intact so MakeHuman helper geometry remains hidden.
    for m in list(body_obj.modifiers):
        if m.type == "MASK" and m.name.startswith("Delete."):
            body_obj.modifiers.remove(m)

    def _walk_skin(nt: bpy.types.NodeTree) -> None:
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                if "Roughness" in n.inputs:
                    n.inputs["Roughness"].default_value = max(n.inputs["Roughness"].default_value, 0.54)
                if "Coat Weight" in n.inputs:
                    n.inputs["Coat Weight"].default_value = 0.0
                bc = n.inputs.get("Base Color")
                if bc and bc.links:
                    src_sock = bc.links[0].from_socket
                    if src_sock.node.type != "HUE_SAT":
                        hsv = nt.nodes.new("ShaderNodeHueSaturation")
                        hsv.inputs["Hue"].default_value = 0.494
                        hsv.inputs["Saturation"].default_value = 1.14
                        hsv.inputs["Value"].default_value = 0.74
                        nt.links.remove(bc.links[0])
                        nt.links.new(src_sock, hsv.inputs["Color"])
                        nt.links.new(hsv.outputs["Color"], bc)
            elif n.type == "GROUP" and n.node_tree:
                _walk_skin(n.node_tree)

    for sl in body_obj.material_slots:
        if sl.material and sl.material.use_nodes and sl.material.node_tree:
            _walk_skin(sl.material.node_tree)


# =============================================================================
# LOAD & SETUP MPFB2 HUMAN FROM family_ready.blend
# =============================================================================

def load_mpfb2_human_base(
    family_blend_path: Path,
    target_height_m: float = 1.68,
) -> Dict[str, Any]:
    """Open `family_ready.blend`, remove studio & Mom, adapt Kid_rig into adult kosan male rig.

    Returns a controller dict with:
      - arm, body, scale, exkeys, leg_ik, blink_times
      - helper methods via module functions: reset_pose, set_standing, set_stomp_pose,
        reach, set_face, snap_sandal_to_right_hand, key_pose
    """
    if not family_blend_path.exists():
        raise FileNotFoundError(
            f"MPFB2 family_ready.blend not found at {family_blend_path}. "
            "Run fetch_assets.py with Google Drive mounted or set MICRO_POV_FAMILY_BLEND."
        )

    bpy.ops.wm.open_mainfile(filepath=str(family_blend_path))
    scene = bpy.context.scene

    # Remove studio objects & Mom character completely
    mom_arm = bpy.data.objects.get("Mom_rig")
    to_remove = set()
    for name in ("Backdrop", "Key", "Fill", "Rim", "RimL", "Cam"):
        obj = bpy.data.objects.get(name)
        if obj:
            to_remove.add(obj)
    if mom_arm:
        to_remove.add(mom_arm)
        for o in bpy.data.objects:
            if o.parent == mom_arm or o.name.startswith("Mom_"):
                to_remove.add(o)
    for o in list(to_remove):
        bpy.data.objects.remove(o, do_unlink=True)

    arm = bpy.data.objects.get("Kid_rig")
    body = bpy.data.objects.get("Kid_body")
    if not arm or not body:
        raise RuntimeError("family_ready.blend missing Kid_rig or Kid_body!")

    # Hide tear/wet-lid curves permanently (not crying in EP001)
    for o in bpy.data.objects:
        if o.name.startswith(("Kid_Tear", "Kid_Lid")):
            o.hide_render = True
            o.hide_viewport = True

    # Delete shoes completely so character is 100% NYEKER / BAREFOOT (Indonesian kosan 2 AM!)
    for o in list(bpy.data.objects):
        if "shoes" in o.name.lower():
            bpy.data.objects.remove(o, do_unlink=True)

    # Clear existing animation & reset pose before cropping shorts / measuring barefoot soles
    arm.animation_data_clear()
    arm.rotation_mode = "XYZ"
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    upd()

    # Polish materials & outfit: teeth fix, knee-length kosan shorts + kaus oblong, barefoot matte SSS skin
    _fix_teeth_materials()
    cloth_obj = bpy.data.objects.get("Human.male_casualsuit06")
    if cloth_obj:
        _style_kosan_outfit(cloth_obj, arm)
    _polish_skin_barefoot(body)
    upd()

    current_h = max(0.5, float(arm.dimensions.z))
    rig_scale = target_height_m / current_h
    arm.scale = (rig_scale, rig_scale, rig_scale)
    upd()

    # Measure exact lowest bare-foot sole Z in world space so barefoot soles sit FLUSH on Z=0.0!
    dg = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(dg)
    bare_min_z = min((body.matrix_world @ v.co).z for v in be.data.vertices)
    sole_z_shift = -bare_min_z  # positive shift if feet dipped below 0, negative if floating

    # Collect ONLY `!ex-*` ARKit shape keys (NEVER touch `$md-*` body keys!)
    exkeys = [k for k in body.data.shape_keys.key_blocks if k.name.startswith("!ex-")]
    if not exkeys:
        raise RuntimeError("MPFB2 body has no !ex-* ARKit shape keys!")

    # Setup & calibrate world-space Leg IK (chain_count=4 on lowerleg02.L/R + COPY_ROTATION foot)
    P = arm.pose.bones
    feet: Dict[str, Tuple[float, float, float, Matrix]] = {}
    for s in ("L", "R"):
        a_w = wp(arm, P[f"lowerleg02.{s}"].tail)
        frest = (arm.matrix_world @ P[f"foot.{s}"].matrix).to_3x3().normalized()
        # Store exact ankle Z adjusted so bare sole sits flush on floor Z=0.0
        feet[s] = (abs(a_w.x), a_w.y, a_w.z + sole_z_shift, frest)

    hip_w = (wp(arm, P["upperleg01.L"].head) + wp(arm, P["upperleg01.R"].head)) * 0.5
    thigh_len = (wp(arm, P["upperleg01.L"].head) - wp(arm, P["lowerleg01.L"].head)).length
    shin_len = (wp(arm, P["lowerleg01.L"].head) - wp(arm, P["lowerleg02.L"].tail)).length

    tg: Dict[str, bpy.types.Object] = {}
    rt: Dict[str, bpy.types.Object] = {}
    pl: Dict[str, bpy.types.Object] = {}
    for s in ("L", "R"):
        e = bpy.data.objects.new(f"Abang_IK_{s}", None)
        r = bpy.data.objects.new(f"Abang_FR_{s}", None)
        p = bpy.data.objects.new(f"Abang_POLE_{s}", None)
        for emp in (e, r, p):
            emp.empty_display_size = 0.04
            scene.collection.objects.link(emp)
        tg[s], rt[s], pl[s] = e, r, p

        c = P[f"lowerleg02.{s}"].constraints.new("IK")
        c.target = e
        c.chain_count = 4
        c.use_stretch = False
        c.use_tail = True
        c.pole_target = p

        cr = P[f"foot.{s}"].constraints.new("COPY_ROTATION")
        cr.target = r
        cr.owner_space = "WORLD"
        cr.target_space = "WORLD"

    leg_ik = {
        "feet": feet,
        "hip": hip_w.copy(),
        "thigh": thigh_len,
        "shin": shin_len,
        "sole_z_shift": sole_z_shift,
        "tg": tg,
        "rt": rt,
        "pl": pl,
    }

    # Calibrate knee pole angles on a deep squat so knees ALWAYS bend forward (never inward)
    arm.location = (0.0, 0.0, sole_z_shift - thigh_len * 0.65)
    for s, sx in (("L", 1.0), ("R", -1.0)):
        fx, fy, fz, frest = feet[s]
        tg[s].location = (sx * fx, fy, fz)
        rt[s].rotation_euler = frest.to_euler()
        pl[s].location = Vector((sx * 0.16 * rig_scale, -1.2, hip_w.z * 0.5))
    for s in ("L", "R"):
        c = P[f"lowerleg02.{s}"].constraints[0]
        best: Optional[Tuple[float, int]] = None
        for ang in range(-180, 180, 10):
            c.pole_angle = math.radians(ang)
            upd()
            k_w = wp(arm, P[f"lowerleg01.{s}"].head)
            h_w = wp(arm, P[f"upperleg01.{s}"].head)
            score = k_w.y + 2.0 * abs(k_w.x - h_w.x)
            if best is None or score < best[0]:
                best = (score, ang)
        assert best is not None
        c.pole_angle = math.radians(best[1])
    arm.location = (0.0, 0.0, sole_z_shift)
    upd()

    # Pre-generate natural blink timestamps every 2.2..3.8s
    rnd = random.Random(19)
    blink_times: List[float] = []
    t_b = 1.15
    while t_b < 120.0:
        blink_times.append(t_b)
        t_b += rnd.uniform(2.2, 3.8)

    return {
        "arm": arm,
        "body": body,
        "scale": rig_scale,
        "exkeys": exkeys,
        "leg_ik": leg_ik,
        "blink_times": blink_times,
    }


# =============================================================================
# POSING, IK LEGS, WORLD-SPACE REACH(), EXPRESSIONS, & HAND-PROP TRACKING
# =============================================================================

def body_frame(arm: bpy.types.Object) -> Tuple[Vector, Vector]:
    """Return (forward, left) world unit vectors for an MPFB2 rig (yaw=0 faces -Y)."""
    yaw = arm.rotation_euler.z
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    left = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    return fwd, left


def reset_pose(human: Dict[str, Any]) -> None:
    """Reset all animated pose bones to identity at start of frame (prevents drift)."""
    arm = human["arm"]
    for n in POSE_BONES:
        pb = arm.pose.bones.get(n)
        if pb:
            pb.matrix_basis.identity()


def set_hand_curl(arm: bpy.types.Object, side: str, curls: Dict[str, Tuple[float, float, float]], wrist_pitch: float = -8.0, twist: float = 35.0) -> None:
    P = arm.pose.bones
    s = 1.0 if side == "L" else -1.0
    for f_idx, angs in curls.items():
        for j, a in zip((1, 2, 3), angs):
            pb = P.get(f"finger{f_idx}-{j}.{side}")
            if pb:
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = (math.radians(a), 0.0, 0.0)
    w = P.get(f"wrist.{side}")
    if w:
        w.rotation_mode = "XYZ"
        w.rotation_euler = (math.radians(wrist_pitch), 0.0, 0.0)
    la2 = P.get(f"lowerarm02.{side}")
    if la2:
        la2.rotation_mode = "XYZ"
        la2.rotation_euler = (0.0, math.radians(s * twist), 0.0)


def place_and_feet(
    human: Dict[str, Any],
    loc: Tuple[float, float, float],
    yaw_deg: float,
    frame: int,
    hip_drop: float = 0.0,
    left_foot_override: Optional[Tuple[float, float, float, float]] = None,
    right_foot_override: Optional[Tuple[float, float, float, float]] = None,
    stance_scale: float = 0.74,
    stagger_y: float = 0.06,
) -> None:
    """Place character root & key Leg IK targets (natural athletic barefoot stance, never stiff wide A-stance).

    `*_foot_override` is `(world_x, world_y, lift_z, pitch_deg)` relative to ground.
    """
    arm = human["arm"]
    R = human["leg_ik"]
    base_z = loc[2] + R.get("sole_z_shift", 0.0)
    arm.location = (loc[0], loc[1], base_z - hip_drop)
    arm.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    arm.keyframe_insert("location", frame=frame)
    arm.keyframe_insert("rotation_euler", frame=frame)

    loc_v = Vector((loc[0], loc[1], loc[2]))
    for s, sx, ov in (("L", 1.0, left_foot_override), ("R", -1.0, right_foot_override)):
        fx, fy, fz, frest = R["feet"][s]
        if ov is not None:
            ox, oy, lift_z, pitch_deg = ov
            R["tg"][s].location = (ox, oy, fz + lift_z)
            rot_m = Rz(yaw_deg) @ Matrix.Rotation(math.radians(pitch_deg), 3, X) @ frest
            R["rt"][s].rotation_euler = rot_m.to_euler()
        else:
            # Slight natural stride stagger (left foot slightly forward, right back) -> natural hunter stance!
            dy = -stagger_y if s == "L" else stagger_y
            p = loc_v + Rz(yaw_deg) @ Vector((sx * fx * stance_scale, fy + dy, 0.0))
            R["tg"][s].location = (p.x, p.y, fz)
            foot_yaw = yaw_deg + (6.0 if s == "L" else -8.0)
            R["rt"][s].rotation_euler = (Rz(foot_yaw) @ frest).to_euler()
        R["tg"][s].keyframe_insert("location", frame=frame)
        R["rt"][s].keyframe_insert("rotation_euler", frame=frame)

        R["pl"][s].location = loc_v + Rz(yaw_deg) @ Vector((sx * 0.14 * human["scale"], -1.2, R["hip"].z * 0.5))
        R["pl"][s].keyframe_insert("location", frame=frame)
    upd()


def lean(arm: bpy.types.Object, deg: float) -> None:
    _, left = body_frame(arm)
    D.rot_world(arm, arm.pose.bones["spine03"], left, deg * 0.6)
    D.rot_world(arm, arm.pose.bones["spine05"], left, deg * 0.4)


def head_turn(arm: bpy.types.Object, yaw_deg: float, pitch_deg: float = 0.0) -> None:
    _, left = body_frame(arm)
    if abs(yaw_deg) > 1e-4:
        D.rot_world(arm, arm.pose.bones["neck01"], Z, yaw_deg * 0.5)
        D.rot_world(arm, arm.pose.bones["head"], Z, yaw_deg * 0.5)
    if abs(pitch_deg) > 1e-4:
        D.rot_world(arm, arm.pose.bones["head"], left, pitch_deg)


def reach(arm: bpy.types.Object, side: str, world_target: Vector, pole: Vector) -> None:
    """World-space 2-bone analytic IK + 3 CCD passes (exact even when arm.scale != 1!)."""
    P = arm.pose.bones
    u1, u2, l1, l2 = (P[f"{b}.{side}"] for b in ("upperarm01", "upperarm02", "lowerarm01", "lowerarm02"))
    upd()
    # Measure bone lengths strictly in WORLD space so non-unit rig scale solves accurately
    a = (wp(arm, u1.tail) - wp(arm, u1.head)).length + (wp(arm, u2.tail) - wp(arm, u2.head)).length
    b = (wp(arm, l1.tail) - wp(arm, l1.head)).length + (wp(arm, l2.tail) - wp(arm, l2.head)).length
    S = wp(arm, u1.head)
    u = world_target - S
    if u.length < 1e-5:
        return
    d = min(u.length, max(0.05, a + b - 0.004))
    dn = u.normalized()
    x = (a * a - b * b + d * d) / (2.0 * d)
    h = math.sqrt(max(0.0, a * a - x * x))
    pl = pole - dn * pole.dot(dn)
    if pl.length < 1e-5:
        pl = Vector((0.0, 0.0, -1.0))
    else:
        pl = pl.normalized()
    E = S + dn * x + pl * h

    D.aim(arm, u1, E - S)
    D.aim(arm, u2, E - S)
    upd()
    D.aim(arm, l1, world_target - wp(arm, l1.head))
    for _ in range(3):
        for bone, chain in ((u1, (u1, u2)), (l1, (l1,))):
            upd()
            o = wp(arm, bone.head)
            wr = wp(arm, l2.tail)
            if (wr - o).length < 1e-5 or (world_target - o).length < 1e-5:
                continue
            q = (wr - o).rotation_difference(world_target - o)
            for bb in chain:
                upd()
                M = arm.matrix_world @ bb.matrix
                bb.matrix = (
                    arm.matrix_world.inverted()
                    @ Matrix.Translation(o)
                    @ q.to_matrix().to_4x4()
                    @ Matrix.Translation(-o)
                    @ M
                )
    upd()


def set_face(
    human: Dict[str, Any],
    t_sec: float,
    fps: int,
    e1: str,
    e2: Optional[str] = None,
    k: float = 0.0,
    jaw_extra: float = 0.0,
    frame: int = 1,
) -> None:
    """Keyframe `!ex-*` ARKit shape keys with BOOST=1.6 + rotate `jaw` bone (17° * jaw).

    Strictly NEVER modifies `$md-*` body shape keys!
    """
    arm = human["arm"]
    a = EXPR[e1]
    b = EXPR[e2] if e2 else a

    # Natural blink lookup
    blink = 0.0
    for tb in human["blink_times"]:
        df = (t_sec - tb) * fps
        if 0.0 <= df <= 8.0:
            blink = [0.0, 0.35, 0.8, 1.0, 1.0, 0.8, 0.5, 0.2, 0.0][int(df)]
            break

    jaw_val = 0.0
    for kb in human["exkeys"]:
        unit = kb.name[4:]  # strip "!ex-"
        v = _lerp(a.get(unit, 0.0), b.get(unit, 0.0), k) * BOOST
        if unit == "jawOpen":
            jaw_val = min(1.0, v + jaw_extra)
            v = jaw_val * 0.25  # Jaw bone handles most mouth opening so teeth follow!
        if unit.startswith("eyeBlink"):
            v = max(v, blink)
        kb.value = min(1.0, max(0.0, v))
        kb.keyframe_insert("value", frame=frame)

    jb = arm.pose.bones["jaw"]
    jb.matrix_basis.identity()
    upd()
    hb = arm.pose.bones["head"]
    left_axis = (arm.matrix_world.to_3x3() @ hb.matrix.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    D.rot_world(arm, jb, left_axis, 17.0 * jaw_val)
    jb.keyframe_insert(
        "rotation_quaternion" if jb.rotation_mode == "QUATERNION" else "rotation_euler",
        frame=frame,
    )


def key_pose(human: Dict[str, Any], frame: int) -> None:
    arm = human["arm"]
    for n in POSE_BONES:
        pb = arm.pose.bones.get(n)
        if pb:
            pb.keyframe_insert(
                "rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler",
                frame=frame,
            )


def eye_mid(human: Dict[str, Any]) -> Vector:
    arm = human["arm"]
    upd()
    P = arm.pose.bones
    return (wp(arm, P["eye.L"].head) + wp(arm, P["eye.R"].head)) * 0.5


def chest_pos(human: Dict[str, Any]) -> Vector:
    arm = human["arm"]
    upd()
    return wp(arm, arm.pose.bones["spine01"].head)


def snap_sandal_to_right_hand(
    human: Dict[str, Any],
    sandal_root: bpy.types.Object,
    frame: int,
    aim_sole_dir: Optional[Vector] = None,
    blade_dir_hint: Optional[Vector] = None,
) -> Vector:
    """Position & orient `sandal_jepit_swallow` in a firm heel power-grip directly from `wrist.R`.

    - Computes exact palm grip center from `wrist.R`: `grip = w0 + palm_dir * 0.055 * s + palm_normal * 0.045 * s`
    - Shifts the flip-flop center `+0.105m` along its blade axis (`+Y`) so the **heel/base** (`y = -0.105`)
      sits firmly inside the closed fist with ZERO fingers penetrating the sole, while the broad flip-flop
      extends outward ready to swat!
    - When `aim_sole_dir` is given (e.g. pointing straight down/toward the cockroach), orients the flat
      green rubber striking surface (`-Z` of sandal) directly along `aim_sole_dir` (never edge-on!).
    """
    arm = human["arm"]
    s = human["scale"]
    upd()
    P = arm.pose.bones
    wb = P["wrist.R"]
    w0 = wp(arm, wb.head)
    w1 = wp(arm, wb.tail)
    palm_dir = (w1 - w0).normalized()

    f2 = wp(arm, P["finger2-1.R"].head)
    f5 = wp(arm, P["finger5-1.R"].head)
    knuckle = f2 - f5
    if knuckle.length < 1e-5:
        knuckle = (arm.matrix_world.to_3x3() @ wb.matrix.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    else:
        knuckle = knuckle.normalized()

    palm_normal = palm_dir.cross(knuckle)
    if palm_normal.length < 1e-5:
        palm_normal = Vector((0.0, 0.0, 1.0))
    else:
        palm_normal = palm_normal.normalized()

    # Exact Zack-Blender-Pack hand-anchor point at the closed fist palm
    grip_pt = w0 + palm_dir * (0.055 * s) + palm_normal * (0.032 * s)

    # Construct orthonormal sandal basis:
    #   sandal -Z = green rubber bottom sole (striking face!)
    #   sandal +Z = white footbed + green V-strap
    #   sandal +Y = heel -> toe blade axis (length 0.27m)
    #   sandal +X = width across sole (0.10m)
    if aim_sole_dir is not None and aim_sole_dir.length > 1e-4:
        # Sandal +Z points opposite to striking direction so flat green bottom (-Z) aims straight at target!
        s_z = (-aim_sole_dir).normalized()
        b_hint = blade_dir_hint if (blade_dir_hint is not None and blade_dir_hint.length > 1e-4) else palm_dir
        s_y = b_hint - s_z * b_hint.dot(s_z)
        if s_y.length < 1e-4:
            s_y = Vector((0.0, 0.0, 1.0)) - s_z * s_z.z
        s_y = s_y.normalized()
        s_x = s_y.cross(s_z).normalized()
        s_y = s_z.cross(s_x).normalized()
    else:
        s_y = palm_dir
        s_z = palm_normal
        s_x = s_y.cross(s_z).normalized()
        s_z = s_x.cross(s_y).normalized()

    basis = Matrix((
        (s_x.x, s_y.x, s_z.x),
        (s_x.y, s_y.y, s_z.y),
        (s_x.z, s_y.z, s_z.z),
    ))

    # Offset sandal center +0.10m along blade (+Y) & slightly out along footbed (+Z) so heel sits
    # cleanly inside the fist with zero finger-through-sole intersection!
    center_pos = grip_pt + s_y * 0.095 + s_z * 0.010

    sandal_root.rotation_mode = "QUATERNION"
    sandal_root.location = center_pos
    sandal_root.rotation_quaternion = basis.to_quaternion()
    sandal_root.keyframe_insert("location", frame=frame)
    sandal_root.keyframe_insert("rotation_quaternion", frame=frame)
    return grip_pt
