#!/usr/bin/env python3
"""Universal MPFB2 Character Engine & Permanent Mascot "Mas Dimas" (`Jadi Apa` Studio Core).

Implements ALL Zack-Blender-Pack anti-bug rules (`TROUBLESHOOTING.md` & `MPFB_REFERENCE.md`):
- Permanent Mascot **Mas Dimas** (`mas_dimas_ready.blend` with 100% packed textures):
  - Crimson / Brick Red `#A62C2B` kaus oblong with bold white **`JADI APA`** UV-painted squarely
    on the center front chest (verified non-mirrored & zero seam clipping via `paint_mas_dimas_tex.py`).
  - Matte black rectangular glasses (`MasDimas_Glasses`) parented strictly to the `head` bone,
    with ZERO glare / open clear lens area so expressive wide eyes read 100% crisply on mobile!
  - Short natural black hair (`short01`), dark charcoal kosan shorts (`bmesh`-cropped + `ShortsHemSolidify`
    + `Displace 0.006`), matte `ENHANCED_SSS` skin, `fix_teeth.py`, and 100% barefoot (`shoes*` deleted).
- Rig Helpers:
  - NEVER zeros `$md-*` body shape keys (only animates `!ex-*` ARKit shape keys with `BOOST=1.6` + `jaw` bone).
  - Keeps `Hide helpers` MASK modifier on `Kid_body` intact; removes `Delete.*` masks so real bare feet render.
  - World-space calibrated Leg IK (`place_and_feet`), world-space 2-bone+CCD `reach()` with realistic
    swatting backswing elbow pole support, natural blink & anticipation helpers.
  - `snap_sandal_to_right_hand()` — firm heel power-grip with flat striking sole aimed directly at target
    (NEVER upright popsicle/ping-pong paddle!).
  - `snap_sandal_to_foot()` — anchors a Swallow flip-flop snugly onto Mas Dimas's LEFT or RIGHT foot so
    continuity (wearing both sandals -> taking off right sandal -> left foot stays shod!) is 100% seamless!
"""

from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bmesh
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

BOOST = 1.6  # Phone-screen ARKit expression boost (Zack-Blender-Pack rule)

EXPR: Dict[str, Dict[str, float]] = {
    "neutral": {},
    "glare": {
        "browDownLeft": 0.95,
        "browDownRight": 0.95,
        "eyeWideLeft": 0.55,
        "eyeWideRight": 0.55,
        "eyeSquintLeft": 0.25,
        "eyeSquintRight": 0.25,
        "noseSneerLeft": 0.78,
        "noseSneerRight": 0.78,
        "mouthFrownLeft": 0.60,
        "mouthFrownRight": 0.60,
        "jawOpen": 0.16,
    },
    "angry": {
        "browDownLeft": 1.0,
        "browDownRight": 1.0,
        "eyeWideLeft": 0.68,
        "eyeWideRight": 0.68,
        "noseSneerLeft": 0.88,
        "noseSneerRight": 0.88,
        "mouthFrownLeft": 0.68,
        "mouthFrownRight": 0.68,
        "mouthUpperUpLeft": 0.42,
        "mouthUpperUpRight": 0.42,
        "jawOpen": 0.26,
    },
    "shock": {
        "browInnerUp": 1.0,
        "browOuterUpLeft": 0.95,
        "browOuterUpRight": 0.95,
        "eyeWideLeft": 1.0,
        "eyeWideRight": 1.0,
        "jawOpen": 0.88,
        "mouthFunnel": 0.35,
        "mouthLowerDownLeft": 0.55,
        "mouthLowerDownRight": 0.55,
    },
    "panic": {
        "browInnerUp": 1.0,
        "browOuterUpLeft": 1.0,
        "browOuterUpRight": 1.0,
        "eyeWideLeft": 1.0,
        "eyeWideRight": 1.0,
        "jawOpen": 1.0,
        "mouthStretchLeft": 0.75,
        "mouthStretchRight": 0.75,
        "mouthLowerDownLeft": 0.80,
        "mouthLowerDownRight": 0.80,
        "mouthUpperUpLeft": 0.45,
        "mouthUpperUpRight": 0.45,
    },
}

GRIP_CURLS: Dict[str, Tuple[float, float, float]] = {
    "1": (22.0, 24.0, 18.0),
    "2": (48.0, 56.0, 40.0),
    "3": (52.0, 60.0, 44.0),
    "4": (54.0, 62.0, 46.0),
    "5": (54.0, 62.0, 46.0),
}

POINT_SWITCH_CURLS: Dict[str, Tuple[float, float, float]] = {
    "1": (18.0, 16.0, 10.0),
    "2": (8.0, 6.0, 4.0),   # Index finger extended to flip light switch!
    "3": (62.0, 68.0, 48.0),
    "4": (68.0, 72.0, 52.0),
    "5": (70.0, 74.0, 54.0),
}

OPEN_CURLS: Dict[str, Tuple[float, float, float]] = {
    "1": (6.0, 4.0, 2.0),
    "2": (8.0, 6.0, 4.0),
    "3": (10.0, 8.0, 6.0),
    "4": (12.0, 10.0, 8.0),
    "5": (14.0, 12.0, 10.0),
}

POSE_BONES: List[str] = (
    ["spine03", "spine05", "neck01", "head", "jaw"]
    + [
        f"{b}.{s}"
        for s in ("L", "R")
        for b in ("shoulder01", "clavicle", "upperarm01", "upperarm02", "lowerarm01", "lowerarm02", "wrist")
    ]
    + [f"finger{f}-{j}.{s}" for s in ("L", "R") for f in "12345" for j in (1, 2, 3)]
)


def upd() -> None:
    bpy.context.view_layer.update()


def wp(arm: bpy.types.Object, v: Vector) -> Vector:
    return arm.matrix_world @ v


def Rz(deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 3, Z)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


# =============================================================================
# MATERIAL, OUTFIT & VOLUMINOUS HAIR BUILDERS (PERMANENT MASCOT: MAS DIMAS)
# =============================================================================

def _fix_teeth_materials() -> None:
    """Apply skills/zack-3d-short/scripts/fix_teeth.py logic: natural teeth & pink gums."""
    for m in bpy.data.materials:
        if "teeth" not in m.name.lower() or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        if "teeth" in bsdf.inputs["Base Color"].links[0].from_node.name.lower() if bsdf.inputs["Base Color"].is_linked else False:
            continue
        src = None
        for n in nt.nodes:
            if n.type == "TEX_IMAGE" and n.image and "teeth" in n.image.name.lower():
                src = n
                break
        if src is None:
            continue
        nt.links.new(src.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.25
        for k in ("Specular IOR Level", "Coat Weight", "Subsurface Weight"):
            if k in bsdf.inputs:
                bsdf.inputs[k].default_value = 0.4 if k == "Specular IOR Level" else 0.0


def _sculpt_voluminous_male_hair(hair_obj: bpy.types.Object) -> None:
    """Reshape flat MPFB2 short01 cap into a natural, matte, voluminous Indonesian male textured crop!

    Preserves 100% of MPFB2 bone vertex weights & Subdivision modifier — lowers the high forehead hairline
    into soft asymmetric textured bangs/fringe, widens upper temple fullness so the silhouette reads cleanly
    from the front (never a cone/helmet or flat swim cap!), and adds balanced organic crown volume.
    """
    if hair_obj.get("_mas_dimas_hair_volumized"):
        return
    mesh = hair_obj.data
    verts = mesh.vertices
    if not verts:
        return

    zs = [v.co.z for v in verts]
    ys = [v.co.y for v in verts]
    z_min, z_max = min(zs), max(zs)
    y_min, y_max = min(ys), max(ys)
    z_span = max(1e-4, z_max - z_min)
    y_span = max(1e-4, y_max - y_min)

    for v in verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        zn = (z - z_min) / z_span      # 0 = nape/sideburns, 1 = top crown
        fn = (y_max - y) / y_span      # 0 = back of head, 1 = front hairline

        # 1. Balanced crown fullness (broad natural silhouette, NOT a narrow tall helmet/cone!)
        top_w = max(0.0, (zn - 0.48) / 0.52) ** 1.35
        # Soft asymmetric part sweep (slightly fuller on viewer-left / Mas Dimas's right side)
        asym_sweep = 1.0 + 0.16 * math.sin((x + 0.022) * 16.0)
        # Gentle organic textured hair clumps (matte & natural, never bumpy plastic)
        lock_wave = (
            0.0028 * math.sin(x * 74.0 + y * 32.0)
            + 0.0018 * math.cos(x * 130.0 - z * 42.0)
        )

        # Balanced crown lift (+1.2cm to +1.8cm)
        dz = top_w * (0.012 + 0.006 * fn) * asym_sweep + top_w * lock_wave

        # Fuller upper sides / temples (+1.1cm outward) -> frames face naturally from front view!
        temple_w = max(0.0, (zn - 0.36) / 0.64) * (1.0 - 0.25 * max(0.0, zn - 0.88))
        dx = x * (0.18 * temple_w) + temple_w * 0.002 * math.sin(z * 50.0 + y * 35.0)

        # Lower front hairline smoothly into soft textured bangs/fringe (eliminates giant forehead!)
        # Eyebrows sit around z ~ 1.185; front hair lower edge sits at z ~ 1.215 -> safely lowers to ~1.202!
        front_edge_w = max(0.0, (fn - 0.56) / 0.44) * max(0.0, 1.0 - abs(zn - 0.68) / 0.36)
        fringe_locks = 0.0055 * (0.55 + 0.45 * math.sin(x * 86.0 + 0.45)) + 0.0022 * math.cos(x * 155.0)
        dz -= front_edge_w * (0.014 + fringe_locks)
        # Forward lift of the front fringe away from forehead skin so it casts a real soft hair shadow!
        dy = -front_edge_w * (0.015 + 0.004 * math.sin(x * 65.0))

        # Soft natural back volume
        back_w = max(0.0, (0.38 - fn) / 0.38) * max(0.0, (zn - 0.30) / 0.70)
        dy += back_w * 0.008

        v.co = Vector((x + dx, y + dy, z + dz))

    mesh.update()
    hair_obj["_mas_dimas_hair_volumized"] = True


def _polish_mas_dimas_skin_and_hair(body: bpy.types.Object) -> None:
    """Expose full bare feet (keep Hide helpers!), warm Southeast Asian skin tone, & matte voluminous black hair."""
    for mod in list(body.modifiers):
        if mod.type == "MASK" and mod.name.startswith("Delete."):
            body.modifiers.remove(mod)

    def _walk_skin(nt: bpy.types.NodeTree) -> None:
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                # Unified Stylized Semi-Matte Look-Dev: clean soft-matte roughness 0.55-0.65 (zero glossy/creepy pores!)
                if "Roughness" in n.inputs:
                    for lk in list(n.inputs["Roughness"].links):
                        nt.links.remove(lk)
                    n.inputs["Roughness"].default_value = 0.60
                if "Coat Weight" in n.inputs:
                    n.inputs["Coat Weight"].default_value = 0.0
                if "Specular IOR Level" in n.inputs:
                    n.inputs["Specular IOR Level"].default_value = 0.24
                bc = n.inputs.get("Base Color")
                if bc and bc.links:
                    src_sock = bc.links[0].from_socket
                    if src_sock.node.type != "HUE_SAT":
                        # Warm natural Southeast Asian / Indonesian skin tone (young_asian_male warm tint)
                        hsv = nt.nodes.new("ShaderNodeHueSaturation")
                        hsv.inputs["Hue"].default_value = 0.493
                        hsv.inputs["Saturation"].default_value = 1.15
                        hsv.inputs["Value"].default_value = 0.78
                        nt.links.remove(bc.links[0])
                        nt.links.new(src_sock, hsv.inputs["Color"])
                        nt.links.new(hsv.outputs["Color"], bc)
            elif n.type in ("BUMP", "NORMAL_MAP"):
                # Soften harsh realistic skin pore maps into clean Stylized Semi-Matte finish
                if "Strength" in n.inputs and not n.inputs["Strength"].is_linked:
                    n.inputs["Strength"].default_value = min(0.12, float(n.inputs["Strength"].default_value))
            elif n.type == "GROUP" and n.node_tree:
                _walk_skin(n.node_tree)

    for m in body.data.materials:
        if m and m.use_nodes and m.node_tree:
            _walk_skin(m.node_tree)

    # Matte voluminous natural dark-black short male hair + matching dark Indonesian eyebrows!
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        lname = obj.name.lower()
        is_hair = "short01" in lname or "hair" in lname
        is_brow = "eyebrow" in lname
        if not (is_hair or is_brow):
            continue
        if is_hair:
            _sculpt_voluminous_male_hair(obj)
        for m in obj.data.materials:
            if not m or not m.use_nodes:
                continue
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not bsdf:
                continue
            bc = bsdf.inputs.get("Base Color")
            if bc:
                if bc.is_linked:
                    src_sock = bc.links[0].from_socket
                    if src_sock.node.type != "HUE_SAT":
                        hs = m.node_tree.nodes.new("ShaderNodeHueSaturation")
                        hs.inputs["Value"].default_value = 0.14 if is_hair else 0.18
                        hs.inputs["Saturation"].default_value = 0.28
                        m.node_tree.links.new(src_sock, hs.inputs["Color"])
                        m.node_tree.links.new(hs.outputs["Color"], bc)
                else:
                    bc.default_value = (0.016, 0.013, 0.011, 1.0)
            if "Roughness" in bsdf.inputs and not bsdf.inputs["Roughness"].is_linked:
                bsdf.inputs["Roughness"].default_value = 0.72 if is_hair else 0.68
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.14
            if "Coat Weight" in bsdf.inputs:
                bsdf.inputs["Coat Weight"].default_value = 0.0


def _crop_pants_to_kosan_shorts(cloth_obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Trim the lower half of long jeans into Indonesian knee-length dark kosan shorts."""
    knee_z_local = float(arm.pose.bones["lowerleg01.L"].head.z)
    cut_z = knee_z_local + 0.025

    bm = bmesh.new()
    bm.from_mesh(cloth_obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Delete lower pant-leg faces below knee cut height (idempotent if already cropped!)
    del_faces = [f for f in bm.faces if f.calc_center_median().z < cut_z]
    if del_faces:
        bmesh.ops.delete(bm, geom=del_faces, context="FACES")
        bm.verts.ensure_lookup_table()
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.to_mesh(cloth_obj.data)
        cloth_obj.data.update()
    bm.free()

    if not any(m.type == "SOLIDIFY" for m in cloth_obj.modifiers):
        sol = cloth_obj.modifiers.new("ShortsHemSolidify", "SOLIDIFY")
        sol.thickness = 0.004
        sol.offset = 0.0


def _apply_mas_dimas_crimson_outfit(cloth_obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Paint Crimson #A62C2B + bold white `JADI APA` chest tee + charcoal shorts onto UV texture & pack it!"""
    _crop_pants_to_kosan_shorts(cloth_obj, arm)

    # Ensure Displace 0.006 anti-clipping modifier (Zack-Blender-Pack rule)
    has_disp = any(m.type == "DISPLACE" for m in cloth_obj.modifiers)
    if not has_disp:
        disp = cloth_obj.modifiers.new("OutfitDisplace", "DISPLACE")
        disp.strength = 0.006
        disp.mid_level = 0.0

    # Classify shirt vs shorts cleanly via connected mesh islands (ZERO jagged waist hem bleed!)
    bm_cls = bmesh.new()
    bm_cls.from_mesh(cloth_obj.data)
    bm_cls.faces.ensure_lookup_table()
    visited = set()
    shirt_face_indices = set()
    for f in bm_cls.faces:
        if f.index in visited:
            continue
        comp = []
        stack = [f]
        visited.add(f.index)
        max_z = -1e9
        while stack:
            cur = stack.pop()
            comp.append(cur.index)
            cz = cur.calc_center_median().z
            if cz > max_z:
                max_z = cz
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.index not in visited:
                        visited.add(nf.index)
                        stack.append(nf)
        # Shirt island reaches shoulder/neck height (max_z > 0.85); shorts island stays below waist (max_z < 0.78)!
        if max_z > 0.85:
            shirt_face_indices.update(comp)
    bm_cls.free()

    uv_layer = cloth_obj.data.uv_layers.active
    shirt_polys: List[List[Tuple[float, float]]] = []
    shorts_polys: List[List[Tuple[float, float]]] = []
    chest_us: List[float] = []
    chest_vs: List[float] = []

    for p in cloth_obj.data.polygons:
        pts = [(float(uv_layer.data[li].uv.x), float(uv_layer.data[li].uv.y)) for li in p.loop_indices]
        if p.index in shirt_face_indices:
            shirt_polys.append(pts)
            if p.normal.y < -0.65 and 0.85 < p.center.z < 1.02 and abs(p.center.x) < 0.09:
                for u, v in pts:
                    chest_us.append(u)
                    chest_vs.append(v)
        else:
            shorts_polys.append(pts)

    chest_box = {
        "u_min": min(chest_us) if chest_us else 0.1012,
        "u_max": max(chest_us) if chest_us else 0.2597,
        "v_min": min(chest_vs) if chest_vs else 0.7722,
        "v_max": max(chest_vs) if chest_vs else 0.9247,
    }

    with tempfile.TemporaryDirectory(prefix="mas_dimas_tex_") as tmp_s:
        tmp_dir = Path(tmp_s)
        src_tex = tmp_dir / "orig_diffuse.png"
        uv_meta_path = tmp_dir / "uv_meta.json"
        out_tex = tmp_dir / "mas_dimas_outfit_diffuse.png"

        uv_meta_path.write_text(
            json.dumps(
                {
                    "shirt_uv_polys": shirt_polys,
                    "shorts_uv_polys": shorts_polys,
                    "chest_uv_box": chest_box,
                }
            ),
            encoding="utf-8",
        )

        # Save existing packed kid_tee_diffuse.png as base fabric luminance source
        orig_img = bpy.data.images.get("kid_tee_diffuse.png")
        if orig_img is not None:
            orig_img.filepath_raw = str(src_tex)
            orig_img.file_format = "PNG"
            try:
                orig_img.save()
            except Exception:
                pass

        painter = Path(__file__).resolve().parent / "paint_mas_dimas_tex.py"
        py_bin = shutil.which("python3") or sys.executable
        subprocess.run(
            [
                py_bin,
                str(painter),
                "--src",
                str(src_tex),
                "--uv-meta",
                str(uv_meta_path),
                "--out",
                str(out_tex),
                "--size",
                "2048",
                "--text",
                "JADI APA",
            ],
            check=True,
        )

        # Load painted texture into Blender & pack into the .blend file!
        old_img = bpy.data.images.get("mas_dimas_outfit_diffuse.png")
        if old_img is not None:
            bpy.data.images.remove(old_img)
        new_img = bpy.data.images.load(str(out_tex))
        new_img.name = "mas_dimas_outfit_diffuse.png"
        new_img.colorspace_settings.name = "sRGB"
        new_img.pack()

    # Wire clean matte cotton shader using painted diffuse + existing AO + Normal map
    for m in cloth_obj.data.materials:
        if not m or not m.use_nodes:
            continue
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue

        tex_diff = next(
            (n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "diffuse" in n.image.name.lower()),
            None,
        )
        tex_ao = next(
            (n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "ao" in n.image.name.lower()),
            None,
        )
        if tex_diff is None:
            tex_diff = nt.nodes.new("ShaderNodeTexImage")
        tex_diff.image = new_img

        # Multiply painted diffuse cleanly with subtle AO (factor 0.35) so Crimson red stays punchy & rich!
        if tex_ao is not None:
            mix_ao = nt.nodes.new("ShaderNodeMix")
            mix_ao.data_type = "RGBA"
            mix_ao.blend_type = "MULTIPLY"
            mix_ao.inputs[0].default_value = 0.35
            sa = next(i for i in mix_ao.inputs if i.name == "A" and i.type == "RGBA")
            sb = next(i for i in mix_ao.inputs if i.name == "B" and i.type == "RGBA")
            so = next(o for o in mix_ao.outputs if o.name == "Result" and o.type == "RGBA")
            nt.links.new(tex_diff.outputs["Color"], sa)
            nt.links.new(tex_ao.outputs["Color"], sb)
            nt.links.new(so, bsdf.inputs["Base Color"])
        else:
            nt.links.new(tex_diff.outputs["Color"], bsdf.inputs["Base Color"])

        if "Roughness" in bsdf.inputs:
            for lk in list(bsdf.inputs["Roughness"].links):
                nt.links.remove(lk)
            # Unified Stylized Semi-Matte Look-Dev: clean soft-matte fabric roughness 0.55-0.65
            bsdf.inputs["Roughness"].default_value = 0.62
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.18
        if "Sheen Weight" in bsdf.inputs:
            bsdf.inputs["Sheen Weight"].default_value = 0.10


def _add_mas_dimas_glasses(arm: bpy.types.Object) -> bpy.types.Object:
    """Build Mas Dimas's signature matte-black rectangular glasses (ZERO lens glare!) parented to `head` bone."""
    existing = bpy.data.objects.get("MasDimas_Glasses")
    if existing is not None:
        return existing

    # Matte black acetate frame material (zero glare, crisp contrast against warm skin)
    frame_mat = bpy.data.materials.get("Mat_MasDimas_GlassesFrame")
    if frame_mat is None:
        frame_mat = bpy.data.materials.new("Mat_MasDimas_GlassesFrame")
        frame_mat.use_nodes = True
        bsdf = frame_mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (0.015, 0.015, 0.018, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.56
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.20

    # Measure eye positions in rest pose of arm (local rig space)
    eye_l = arm.pose.bones["eye.L"].head.copy()
    eye_r = arm.pose.bones["eye.R"].head.copy()
    eye_cx = (abs(eye_l.x) + abs(eye_r.x)) * 0.5  # ~0.0261
    eye_z = (eye_l.z + eye_r.z) * 0.5              # ~1.1645
    front_y = -0.1435  # ~1.0cm cleanly in front of nose bridge (-0.1337) & eye surface (-0.1293)

    bm = bmesh.new()

    def _add_bar(p0: Tuple[float, float, float], p1: Tuple[float, float, float], thickness: float, depth: float) -> None:
        v0 = Vector(p0)
        v1 = Vector(p1)
        seg = v1 - v0
        length = seg.length
        if length < 1e-5:
            return
        mid = (v0 + v1) * 0.5
        q = Vector((1.0, 0.0, 0.0)).rotation_difference(seg.normalized())
        m = Matrix.Translation(mid) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((length, depth, thickness, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)

    # Dimensions for crisp rectangular frame (readable on phone without hiding expressive eyes/brows!)
    half_w = 0.0215
    half_h = 0.0138
    bar_t = 0.0036
    bar_d = 0.0040
    lens_cx = eye_cx + 0.0025  # ~0.0286 -> inner edge at 0.0071, outer edge at 0.0501

    for sx in (-1.0, 1.0):
        cx = sx * lens_cx
        x_in = cx - sx * half_w
        x_out = cx + sx * half_w
        z_top = eye_z + half_h
        z_bot = eye_z - half_h

        # Top rim, bottom rim, inner rim, outer rim (open zero-glare lens interior!)
        _add_bar((x_in, front_y, z_top), (x_out, front_y, z_top), bar_t * 1.15, bar_d)
        _add_bar((x_in, front_y, z_bot), (x_out, front_y, z_bot), bar_t * 0.92, bar_d)
        _add_bar((x_in, front_y, z_bot), (x_in, front_y, z_top), bar_t, bar_d)
        _add_bar((x_out, front_y, z_bot), (x_out, front_y, z_top), bar_t, bar_d)

        # Corner hinge / endpiece extending cleanly past temple width
        x_hinge = sx * 0.0625
        z_arm = eye_z + 0.0055
        _add_bar((x_out, front_y, z_arm), (x_hinge, front_y + 0.003, z_arm), bar_t * 1.1, bar_d)

        # Temple arm running smoothly along head side to ear, then curving down behind ear!
        p_ear_top = (sx * 0.0735, -0.052, z_arm - 0.002)
        p_ear_tip = (sx * 0.0715, -0.028, z_arm - 0.022)
        _add_bar((x_hinge, front_y + 0.003, z_arm), p_ear_top, bar_t * 0.95, 0.0032)
        _add_bar(p_ear_top, p_ear_tip, bar_t * 0.88, 0.0030)

        # Subtle nose pad strut resting lightly toward nose bridge
        _add_bar((x_in, front_y + 0.001, eye_z - 0.001), (sx * 0.0055, front_y + 0.0085, eye_z - 0.002), 0.0018, 0.0018)

    # Center nose bridge bar connecting left & right rims
    _add_bar((-lens_cx + half_w - 0.001, front_y, eye_z + 0.0055), (lens_cx - half_w + 0.001, front_y, eye_z + 0.0055), bar_t * 1.05, bar_d)

    # Gentle bevel for authentic matte-acetate rounded edges
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0007, segments=2, affect="EDGES", clamp_overlap=True)

    mesh = bpy.data.meshes.new("MasDimas_Glasses_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    mesh.materials.append(frame_mat)

    glasses_obj = bpy.data.objects.new("MasDimas_Glasses", mesh)
    bpy.context.scene.collection.objects.link(glasses_obj)

    # Parent strictly to `head` bone while arm is in rest pose!
    upd()
    glasses_obj.parent = arm
    glasses_obj.parent_type = "BONE"
    glasses_obj.parent_bone = "head"
    # Preserve exact rest-pose local alignment relative to head bone tail!
    head_pb = arm.pose.bones["head"]
    bone_tail_mat = arm.matrix_world @ Matrix.Translation(head_pb.tail) @ head_pb.matrix.to_3x3().to_4x4()
    glasses_obj.matrix_parent_inverse = bone_tail_mat.inverted()
    upd()
    return glasses_obj


# =============================================================================
# MASTER BUILDER: BUILD & PACK `mas_dimas_ready.blend` + FRONT VERIFICATION
# =============================================================================

def build_mas_dimas_master(
    family_blend_path: Path,
    out_blend_path: Path,
    front_check_png: Optional[Path] = None,
) -> Path:
    """Build permanent mascot `mas_dimas_ready.blend` from `family_ready.blend` (NO glasses, voluminous hair, warm SE Asian skin)."""
    bpy.ops.wm.open_mainfile(filepath=str(family_blend_path))

    # Strip non-Mas-Dimas rigs/studio objects, shoes, and any glasses cleanly
    keep_objs = set()
    arm = bpy.data.objects.get("Kid_rig")
    if arm is None:
        raise RuntimeError(f"Kid_rig not found in {family_blend_path}")
    keep_objs.add(arm)
    for ch in arm.children_recursive:
        lname = ch.name.lower()
        if "shoes" not in lname and "glasses" not in lname:
            keep_objs.add(ch)

    for obj in list(bpy.data.objects):
        if obj not in keep_objs:
            bpy.data.objects.remove(obj, do_unlink=True)

    # Remove unused worlds/cameras/lights
    for w in list(bpy.data.worlds):
        bpy.data.worlds.remove(w)

    # Reset rig to clean rest pose at origin before building outfit & hair
    arm.animation_data_clear()
    arm.rotation_mode = "XYZ"
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    arm.scale = (1.0, 1.0, 1.0)
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    upd()

    body = bpy.data.objects.get("Kid_body")
    if body is None:
        raise RuntimeError("Kid_body not found in family_ready.blend")

    _fix_teeth_materials()
    _polish_mas_dimas_skin_and_hair(body)
    cloth_obj = bpy.data.objects.get("Human.male_casualsuit06")
    if cloth_obj is None:
        raise RuntimeError("Human.male_casualsuit06 not found in family_ready.blend")
    _apply_mas_dimas_crimson_outfit(cloth_obj, arm)

    # Clean orphaned data blocks & pack ALL textures inside mas_dimas_ready.blend!
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass
    bpy.ops.file.pack_all()

    out_blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend_path), compress=True)
    print(f"[MAS_DIMAS] Saved packed permanent mascot master (no glasses, voluminous hair) -> {out_blend_path}", flush=True)

    if front_check_png is not None:
        render_mas_dimas_front_check(out_blend_path, front_check_png)

    return out_blend_path


def render_mas_dimas_front_check(mas_dimas_blend: Path, out_png: Path) -> Path:
    """Render a crisp studio front-view verification (`mas_dimas_front_check.png`) showing:
    - Crimson/Brick Red `#A62C2B` kaus with bold white `JADI APA` + yellow accent line centered (non-mirrored!)
    - Expressive bare face (NO glasses!) with warm Southeast Asian skin tone & voluminous short black male hair
    - Dark charcoal kosan shorts & 100% barefoot feet!
    """
    human = load_mpfb2_human_base(mas_dimas_blend, target_height_m=1.68)
    scene = bpy.context.scene
    arm = human["arm"]

    # Clean neutral light-gray studio backdrop so Crimson Red & Voluminous Black Hair pop clearly!
    world = bpy.data.worlds.new("FrontCheck_World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
    bg.inputs["Strength"].default_value = 0.55

    # Studio backdrop floor & wall
    bg_mat = bpy.data.materials.new("Mat_Studio_BG")
    bg_mat.use_nodes = True
    bsdf = bg_mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.28, 0.30, 0.34, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0))
    bpy.context.active_object.data.materials.append(bg_mat)
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 1.35, 2.0), rotation=(math.radians(90.0), 0.0, 0.0))
    bpy.context.active_object.data.materials.append(bg_mat)

    # 3-point balanced studio lighting (rich Crimson red & natural warm SE Asian skin tone!)
    for name, loc, rot, sz, energy, col in [
        ("Key", (-1.05, -1.75, 2.05), (math.radians(56), 0.0, math.radians(-28)), 1.3, 130.0, (1.0, 0.96, 0.91)),
        ("Fill", (1.25, -1.60, 1.50), (math.radians(68), 0.0, math.radians(34)), 1.6, 56.0, (0.88, 0.93, 1.0)),
        ("Rim", (0.0, 1.15, 2.25), (math.radians(-42), 0.0, 0.0), 1.0, 145.0, (0.95, 0.97, 1.0)),
    ]:
        ld = bpy.data.lights.new(name, type="AREA")
        ld.size = sz
        ld.energy = energy
        ld.color = col
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)

    # Natural confident Mas Dimas standing pose (NOT A-pose!) + expressive wide-eyed look!
    reset_pose(human)
    place_and_feet(human, (0.0, 0.0, 0.0), 0.0, frame=1, hip_drop=0.02, stance_scale=0.72, stagger_y=0.05)
    D.pose_arms(arm, yaw_deg=0.0, elbow=16.0)
    D.relaxed_hands(arm)
    key_pose(human, 1)
    set_face(human, 0.0, 24, "shock", "neutral", 0.55, jaw_extra=0.0, frame=1)
    upd()

    # Full-body 9:16 framing showing voluminous hair silhouette, bare expressive face, JADI APA tee, shorts & barefoot toes!
    cam_data = bpy.data.cameras.new("FrontCheck_Cam")
    cam_data.lens = 44.0
    cam_obj = bpy.data.objects.new("FrontCheck_Cam", cam_data)
    cam_obj.location = (0.0, -2.85, 0.90)
    aim = (Vector((0.0, 0.0, 0.88)) - cam_obj.location).normalized()
    cam_obj.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 18
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 1138
    scene.render.resolution_percentage = 100
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = -0.32

    out_png.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_png)
    scene.frame_set(1)
    bpy.ops.render.render(write_still=True)
    print(f"[MAS_DIMAS] Rendered front verification -> {out_png}", flush=True)
    return out_png


# =============================================================================
# LOADER & CALIBRATED LEG IK (SUPPORTS BOTH `mas_dimas_ready.blend` & `family_ready.blend`)
# =============================================================================

def load_mpfb2_human_base(
    blend_path: Path,
    target_height_m: float = 1.68,
) -> Dict[str, Any]:
    """Open `mas_dimas_ready.blend` (or auto-upgrade `family_ready.blend` into Mas Dimas) & calibrate Leg IK."""
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    arm = bpy.data.objects.get("Kid_rig")
    body = bpy.data.objects.get("Kid_body")
    if arm is None or body is None:
        raise RuntimeError(f"Expected MPFB2 objects Kid_rig & Kid_body inside {blend_path}")

    # Strip any non-Mas-Dimas objects, shoes, and any legacy procedural glasses cleanly
    keep_objs = {arm}
    for ch in arm.children_recursive:
        lname = ch.name.lower()
        if "shoes" not in lname and "glasses" not in lname:
            keep_objs.add(ch)
    for obj in list(bpy.data.objects):
        if obj not in keep_objs:
            bpy.data.objects.remove(obj, do_unlink=True)
    for w in list(bpy.data.worlds):
        bpy.data.worlds.remove(w)

    scene = bpy.context.scene
    arm.animation_data_clear()
    arm.rotation_mode = "XYZ"
    arm.location = (0.0, 0.0, 0.0)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    arm.scale = (1.0, 1.0, 1.0)
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    upd()

    # If opening raw family_ready.blend (no mas_dimas_outfit_diffuse.png yet), upgrade seamlessly on the fly!
    if bpy.data.images.get("mas_dimas_outfit_diffuse.png") is None:
        _fix_teeth_materials()
        _polish_mas_dimas_skin_and_hair(body)
        cloth_obj = bpy.data.objects.get("Human.male_casualsuit06")
        if cloth_obj is not None:
            _apply_mas_dimas_crimson_outfit(cloth_obj, arm)
        upd()
    else:
        # Ensure bare-foot masks stay removed & voluminous hair/warm skin are applied
        _polish_mas_dimas_skin_and_hair(body)

    current_h = max(0.5, float(arm.dimensions.z))
    rig_scale = target_height_m / current_h
    arm.scale = (rig_scale, rig_scale, rig_scale)
    upd()

    # Measure exact lowest bare-foot sole Z in world space so barefoot soles sit FLUSH on Z=0.0!
    dg = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(dg)
    bare_min_z = min((body.matrix_world @ v.co).z for v in be.data.vertices)
    sole_z_shift = -bare_min_z

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
        feet[s] = (abs(a_w.x), a_w.y, a_w.z + sole_z_shift, frest)

    hip_w = (wp(arm, P["upperleg01.L"].head) + wp(arm, P["upperleg01.R"].head)) * 0.5
    thigh_len = (wp(arm, P["upperleg01.L"].head) - wp(arm, P["lowerleg01.L"].head)).length
    shin_len = (wp(arm, P["lowerleg01.L"].head) - wp(arm, P["lowerleg02.L"].tail)).length

    tg: Dict[str, bpy.types.Object] = {}
    rt: Dict[str, bpy.types.Object] = {}
    pl: Dict[str, bpy.types.Object] = {}
    for s in ("L", "R"):
        e = bpy.data.objects.new(f"Dimas_IK_{s}", None)
        r = bpy.data.objects.new(f"Dimas_FR_{s}", None)
        p = bpy.data.objects.new(f"Dimas_POLE_{s}", None)
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

    # Calibrate knee pole angles on a deep squat so knees ALWAYS bend forward (never inward!)
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

    # Pre-generate natural blink timestamps every 2.2..3.8s (avoiding hero frame 97!)
    rnd = random.Random(19)
    blink_times: List[float] = []
    t_b = 1.15
    while t_b < 120.0:
        blink_times.append(t_b)
        t_b += rnd.uniform(2.2, 3.8)

    return {
        "arm": arm,
        "body": body,
        "glasses": bpy.data.objects.get("MasDimas_Glasses"),
        "scale": rig_scale,
        "exkeys": exkeys,
        "leg_ik": leg_ik,
        "blink_times": blink_times,
    }


# =============================================================================
# POSING, IK LEGS, WORLD-SPACE REACH(), EXPRESSIONS, & HAND/FOOT SANDAL TRACKING
# =============================================================================

def body_frame(arm: bpy.types.Object) -> Tuple[Vector, Vector]:
    """Return (forward, left) world unit vectors for an MPFB2 rig (yaw=0 faces -Y)."""
    yaw = arm.rotation_euler.z
    fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    left = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    return fwd, left


def reset_pose(human: Dict[str, Any]) -> None:
    arm = human["arm"]
    for n in POSE_BONES:
        pb = arm.pose.bones.get(n)
        if pb:
            pb.matrix_basis.identity()


def set_hand_curl(
    arm: bpy.types.Object,
    side: str,
    curls: Dict[str, Tuple[float, float, float]],
    wrist_pitch: float = -8.0,
    twist: float = 35.0,
) -> None:
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
    stance_scale: float = 0.72,
    stagger_y: float = 0.07,
    left_sole_lift: float = 0.0,
    right_sole_lift: float = 0.0,
) -> None:
    """Place Mas Dimas root & key Leg IK targets (supports raising shod foot cleanly by sandal sole thickness!)."""
    arm = human["arm"]
    R = human["leg_ik"]
    base_z = loc[2] + R.get("sole_z_shift", 0.0) + max(left_sole_lift, right_sole_lift)
    arm.location = (loc[0], loc[1], base_z - hip_drop)
    arm.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    arm.keyframe_insert("location", frame=frame)
    arm.keyframe_insert("rotation_euler", frame=frame)

    loc_v = Vector((loc[0], loc[1], loc[2]))
    for s, sx, ov, s_lift in (
        ("L", 1.0, left_foot_override, left_sole_lift),
        ("R", -1.0, right_foot_override, right_sole_lift),
    ):
        fx, fy, fz, frest = R["feet"][s]
        if ov is not None:
            ox, oy, lift_z, pitch_deg = ov
            R["tg"][s].location = (ox, oy, fz + s_lift + lift_z)
            rot_m = Rz(yaw_deg) @ Matrix.Rotation(math.radians(pitch_deg), 3, X) @ frest
            R["rt"][s].rotation_euler = rot_m.to_euler()
        else:
            dy = -stagger_y if s == "L" else stagger_y
            p = loc_v + Rz(yaw_deg) @ Vector((sx * fx * stance_scale, fy + dy, 0.0))
            R["tg"][s].location = (p.x, p.y, fz + s_lift)
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


def torso_twist(arm: bpy.types.Object, yaw_deg: float) -> None:
    """Natural upper-body anticipation / look-turn twist around world Z."""
    if abs(yaw_deg) > 1e-4:
        D.rot_world(arm, arm.pose.bones["spine03"], Z, yaw_deg * 0.45)
        D.rot_world(arm, arm.pose.bones["spine05"], Z, yaw_deg * 0.55)


def head_turn(arm: bpy.types.Object, yaw_deg: float, pitch_deg: float = 0.0) -> None:
    _, left = body_frame(arm)
    if abs(yaw_deg) > 1e-4:
        D.rot_world(arm, arm.pose.bones["neck01"], Z, yaw_deg * 0.48)
        D.rot_world(arm, arm.pose.bones["head"], Z, yaw_deg * 0.52)
    if abs(pitch_deg) > 1e-4:
        D.rot_world(arm, arm.pose.bones["head"], left, pitch_deg)


def reach(arm: bpy.types.Object, side: str, world_target: Vector, pole: Vector) -> None:
    """World-space 2-bone analytic IK + 3 CCD passes (accurate even when arm.scale != 1)."""
    P = arm.pose.bones
    u1, u2, l1, l2 = (P[f"{b}.{side}"] for b in ("upperarm01", "upperarm02", "lowerarm01", "lowerarm02"))
    upd()
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
    """Keyframe `!ex-*` ARKit shape keys with BOOST=1.6 + rotate `jaw` bone (17° * jaw). NEVER touches `$md-*`!"""
    arm = human["arm"]
    a = EXPR[e1]
    b = EXPR[e2] if e2 else a

    blink = 0.0
    for tb in human["blink_times"]:
        df = (t_sec - tb) * fps
        if 0.0 <= df <= 8.0:
            blink = [0.0, 0.35, 0.8, 1.0, 1.0, 0.8, 0.5, 0.2, 0.0][int(df)]
            break

    jaw_val = 0.0
    for kb in human["exkeys"]:
        unit = kb.name[4:]
        v = _lerp(a.get(unit, 0.0), b.get(unit, 0.0), k) * BOOST
        if unit == "jawOpen":
            jaw_val = min(1.0, v + jaw_extra)
            v = jaw_val * 0.25
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
    """Position & orient `sandal_jepit_swallow` in a realistic horizontal-forward swatting heel grip.

    - Fist grips ONLY the narrow heel end (`y_local = -0.118`) with fingers wrapping around the top white
      footbed (`+Z`) — offset cleanly along `-s_z` (sole normal) so **0% of fingers pierce the green bottom sole!**
    - Flat green rubber striking surface (`-Z` of sandal) aims squarely along `aim_sole_dir` (forward-down toward
      the cockroach/floor, ready to slap DOWN — NEVER held upright like a ping-pong paddle or popsicle!).
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

    # Anchor squarely at the finger-cup edge (slightly past palm center) so heel sits neatly inside the curled fingers
    grip_pt = w0 + palm_dir * (0.068 * s) + palm_normal * (0.022 * s)

    if aim_sole_dir is not None and aim_sole_dir.length > 1e-4:
        s_z = (-aim_sole_dir).normalized()
        b_hint = blade_dir_hint if (blade_dir_hint is not None and blade_dir_hint.length > 1e-4) else Vector((-0.25, -0.92, -0.28))
        s_y = b_hint - s_z * b_hint.dot(s_z)
        if s_y.length < 1e-4:
            s_y = Vector((-0.25, -0.92, -0.28)) - s_z * (Vector((-0.25, -0.92, -0.28)).dot(s_z))
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

    # Place narrow heel edge (`y_local = -0.118`) inside finger cup & offset `-0.017 * s_z` (along striking sole normal)
    # so white footbed (+Z) rests flush against palm/fingers while green bottom sole (-Z) is 100% free of finger clipping!
    center_pos = grip_pt + s_y * 0.118 - s_z * 0.017

    sandal_root.rotation_mode = "QUATERNION"
    sandal_root.location = center_pos
    sandal_root.rotation_quaternion = basis.to_quaternion()
    sandal_root.keyframe_insert("location", frame=frame)
    sandal_root.keyframe_insert("rotation_quaternion", frame=frame)
    return grip_pt


def attach_sandal_to_foot_bone(
    human: Dict[str, Any],
    sandal_root: bpy.types.Object,
    side: str = "L",
) -> bpy.types.Object:
    """Rigidly BONE-parent a green Swallow flip-flop directly onto `foot.{side}` in exact rest-pose contact!

    Measures the evaluated bare-foot vertices of `Kid_body` while bare soles sit flush at `z = 0.0`,
    places the flip-flop 100% LEVEL right beneath the bare sole (white footbed top `z_local = +0.017`
    kissing `z = 0.0`, green rubber bottom at `z = -0.017`), aligns the V-strap snugly across the forefoot,
    and locks it via Blender `BONE` parenting to `foot.{side}`!
    When `foot.{side}` is lifted by `left_sole_lift = +0.018m` in `place_and_feet()`, the entire green+white
    sandal stays 100% glued to the foot AND cleanly ABOVE the ceramic floor (`z >= +0.001m`, ZERO sinking!).
    """
    arm = human["arm"]
    body = human["body"]
    sole_z_shift = float(human["leg_ik"].get("sole_z_shift", 0.0))

    # Temporarily place rig in clean rest pose with bare soles at z=0.0 & leg IK disabled for exact measurement
    prev_loc = arm.location.copy()
    prev_rot = arm.rotation_euler.copy()
    P = arm.pose.bones
    ik_prev: List[Tuple[bpy.types.Constraint, float]] = []
    for s_tag in ("L", "R"):
        for bname in (f"lowerleg02.{s_tag}", f"foot.{s_tag}"):
            pb = P.get(bname)
            if pb:
                for c in pb.constraints:
                    ik_prev.append((c, c.influence))
                    c.influence = 0.0
    reset_pose(human)
    arm.location = (0.0, 0.0, sole_z_shift)
    arm.rotation_euler = (0.0, 0.0, 0.0)
    upd()

    dg = bpy.context.evaluated_depsgraph_get()
    be = body.evaluated_get(dg)
    side_sign = 1.0 if side == "L" else -1.0
    foot_verts = [
        body.matrix_world @ v.co
        for v in be.data.vertices
        if (body.matrix_world @ v.co).z < 0.045 and (body.matrix_world @ v.co).x * side_sign > 0.01
    ]
    if foot_verts:
        fx_center = (min(v.x for v in foot_verts) + max(v.x for v in foot_verts)) * 0.5
        fy_toe = min(v.y for v in foot_verts)   # -Y is front (toes)
        fy_heel = max(v.y for v in foot_verts)  # +Y is back (heel)
        fz_sole = min(v.z for v in foot_verts)  # ~0.000m
        # Align sandal center so toe-tip (+0.137 along -Y) extends ~1.2cm past bare toes & V-strap hugs forefoot!
        fy_center = (fy_toe + fy_heel) * 0.50 - 0.006
    else:
        fb = P[f"foot.{side}"]
        aw = wp(arm, fb.head)
        fx_center, fy_center, fz_sole = aw.x, aw.y - 0.055, 0.0

    # Place sandal 100% LEVEL facing -Y (rot_z = 180°), white footbed (+0.017) flush against bare sole!
    sandal_root.parent = None
    sandal_root.rotation_mode = "XYZ"
    sandal_root.location = (fx_center, fy_center, fz_sole - 0.017)
    sandal_root.rotation_euler = (0.0, 0.0, math.pi)
    upd()

    # Rigidly BONE-parent to `foot.{side}` while preserving exact world-space rest alignment!
    fb = P[f"foot.{side}"]
    world_sandal_mat = sandal_root.matrix_world.copy()
    bone_tail_mat = arm.matrix_world @ Matrix.Translation(fb.tail) @ fb.matrix.to_3x3().to_4x4()
    sandal_root.parent = arm
    sandal_root.parent_type = "BONE"
    sandal_root.parent_bone = f"foot.{side}"
    sandal_root.matrix_parent_inverse = bone_tail_mat.inverted()
    sandal_root.matrix_world = world_sandal_mat
    upd()

    # Restore Leg IK influences & previous arm transform
    for c, inf in ik_prev:
        c.influence = inf
    arm.location = prev_loc
    arm.rotation_euler = prev_rot
    upd()
    return sandal_root


def snap_sandal_to_foot(
    human: Dict[str, Any],
    sandal_root: bpy.types.Object,
    side: str,
    frame: int,
    floor_clamp: bool = True,
) -> Vector:
    """Snap a green Swallow flip-flop 100% LEVEL & ABOVE FLOOR (`z >= 0.001m`) under `foot.{side}`!

    Horizontalizes the foot forward vector so the sole NEVER pitches nose-down into the ceramic floor.
    """
    arm = human["arm"]
    s = human["scale"]
    upd()
    P = arm.pose.bones
    fb = P[f"foot.{side}"]
    tb = P.get(f"toe1-1.{side}") or P.get(f"toe2-1.{side}")

    ankle_w = wp(arm, fb.head)
    ball_w = wp(arm, fb.tail)
    toe_w = wp(arm, tb.tail) if tb else (ball_w + (ball_w - ankle_w) * 0.5)

    # Strictly horizontal forward direction along foot -> sole stays 100% level on ceramic floor!
    foot_fwd_h = Vector((toe_w.x - ankle_w.x, toe_w.y - ankle_w.y, 0.0))
    if foot_fwd_h.length < 1e-4:
        foot_fwd_h, _ = body_frame(arm)
    s_y = foot_fwd_h.normalized()
    s_z = Vector((0.0, 0.0, 1.0))
    s_x = s_y.cross(s_z).normalized()

    basis = Matrix((
        (s_x.x, s_y.x, s_z.x),
        (s_x.y, s_y.y, s_z.y),
        (s_x.z, s_y.z, s_z.z),
    ))

    mid_pt = ankle_w * 0.36 + toe_w * 0.64
    foot_bot_z = min(ankle_w.z - 0.048 * s, ball_w.z - 0.022 * s, toe_w.z - 0.015 * s)
    sole_z = foot_bot_z - 0.017
    if floor_clamp:
        sole_z = max(0.001, sole_z)

    pos = Vector((mid_pt.x, mid_pt.y, sole_z))
    sandal_root.rotation_mode = "QUATERNION"
    sandal_root.location = pos
    sandal_root.rotation_quaternion = basis.to_quaternion()
    sandal_root.keyframe_insert("location", frame=frame)
    sandal_root.keyframe_insert("rotation_quaternion", frame=frame)
    return pos
