#!/usr/bin/env python3
"""Isolated Episode Builder for EP001 — "POV Kamu Jadi Kecoak di Dapur Jam 2 Pagi" (`Jadi Apa`).

Cleanly separated from universal studio core (`03_pipeline/core/`) so EP002–EP100+ can never
break EP001. Uses:
- Permanent Mascot **Mas Dimas** (`mas_dimas_ready.blend` via `core.mpfb_helpers`)
- Reusable 5-Archetype POV Camera Presets (`core.camera_presets`: `insect_ground` + `aerial_erratic`)
- AgX & 2 AM Cinematic Lighting (`core.lighting_utils`)
- 29 real Poly Haven CC0 kosan kitchen props + exact 02:00 wall clock + Broco switches + calendar

Full Continuity Lock (Scenes 01A–08):
- 01A (0.0–1.0s): Dim 2 AM blue + puddle specular + cockroach silhouette shadow; Mas Dimas stands
  by the left-wall switch reaching to press it, WEARING BOTH green Swallow flip-flops.
- 01B (1.05s+): Neon flashes ON; Mas Dimas just clicked the switch & snaps his head toward the
  cockroach in shock — BOTH feet still wear green flip-flops; ZERO sandal in hand!
- Scene 02–07: Mas Dimas stepped forward & took off his RIGHT flip-flop to wield in his right hand
  (athletic backswing elbow + heel power-grip + flat green sole aimed forward-down toward roach).
  RIGHT foot is barefoot (nyeker); LEFT foot KEEPS wearing the left green Swallow flip-flop!
- Scene 05–06: Mas Dimas's LEFT foot (wearing green Swallow flip-flop!) stomps down to block the
  5.5cm fridge under-gap, while his right arm winds up in swat backswing with the right sandal!
- Scene 08: Identical translucent amber-brown veined foreground wings (zero white glare), falling
  green right sandal clearly visible mid-air below his panicked open right hand, and Mas Dimas's
  shocked glasses-wearing face framed in the UPPER-THIRD safe zone (100% clear of MarginV=380
  subtitles & TikTok/Shorts UI) in deep dramatic shadow with razor-sharp rim light!
"""

from __future__ import annotations

import math
import sys
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Euler, Quaternion, Vector

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = REPO_ROOT / "03_pipeline"
SCRIPTS_DIR = PIPELINE_DIR / "scripts"
for _p in (str(PIPELINE_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import camera_presets as cam_lib
from core import lighting_utils as lgt_lib
from core import mpfb_helpers as mh
from pipeline_utils import log
import procedural_props as props


# =============================================================================
# LIGHTING RIG ("JAM 2 PAGI" CINEMATIC BACKLIT SHADOWS + PUDDLE SPECULAR)
# =============================================================================

def setup_world_and_lights(scene: bpy.types.Scene, assets_dir: Path) -> Dict[str, Any]:
    """Configure 2 AM night-blue HDRI + overhead neon + tight halo rim light + roach shadow spot."""
    hdri_path = assets_dir / "hdri" / "small_empty_room_3_1k.hdr"
    bg = lgt_lib.setup_hdri_world(
        scene,
        hdri_path=hdri_path if hdri_path.exists() else None,
        tint_rgba=(0.14, 0.28, 0.58, 1.0),
        tint_mix=0.88,
        strength=0.08,
    )
    if hdri_path.exists():
        log("EP001", f"Loaded cached Poly Haven HDRI (2 AM night-blue tint): {hdri_path.name}")

    # 1. Atmospheric 2 AM moonlight/doorway spill (Scene 01A readable half-dark blue!)
    _, night_data = lgt_lib.add_area_light(
        scene,
        "Light_Night_Blue",
        (1.05, 0.55, 1.48),
        (math.radians(48), math.radians(36), 0.0),
        0.95,
        1.25,
        24.0,
        (0.24, 0.48, 1.0),
    )

    # 2. Overhead TL Fluorescent Neon behind-above Mas Dimas
    neon_obj, neon_data = lgt_lib.add_area_light(
        scene,
        "Light_Neon_Main",
        (0.0, 2.25, 2.56),
        (math.radians(8), 0.0, 0.0),
        0.16,
        1.05,
        0.0,
        (0.92, 0.96, 1.0),
    )

    # 3. Dramatic Boss Backlight behind Mas Dimas's head (narrow spread for crisp halo rim without washing foreground!)
    rim_obj, rim_data = lgt_lib.add_area_light(
        scene,
        "Light_Boss_Backlight",
        (0.0, 2.86, 2.08),
        (math.radians(-42), 0.0, 0.0),
        0.60,
        0.48,
        0.0,
        (0.84, 0.94, 1.0),
        spread_deg=56.0,
    )

    # 4. Controlled foreground floor pool (keeps Indomie spill, tile floor & sandals vivid)
    fg_obj, fg_data = lgt_lib.add_area_light(
        scene,
        "Light_Foreground_Pool",
        (0.25, 0.35, 1.65),
        (math.radians(-6), math.radians(8), 0.0),
        0.55,
        0.55,
        0.0,
        (0.96, 0.94, 0.88),
    )

    # 5. Subtle floor bounce fill (whisper-low in Scene 8 so shocked eyes & glasses read cleanly inside dark shadow!)
    face_fill_obj, face_fill_data = lgt_lib.add_area_light(
        scene,
        "Light_Face_ShadowRead",
        (0.0, 1.75, 1.25),
        (math.radians(102), 0.0, 0.0),
        0.35,
        0.35,
        0.0,
        (0.62, 0.74, 0.95),
    )

    # 6. Cyan Cheat-Code Accent Light (Scene 3 bullet time)
    cyan_data = bpy.data.lights.new(name="Light_Cyan_Accent", type="POINT")
    cyan_data.energy = 0.0
    cyan_data.color = (0.05, 0.92, 1.0)
    cyan_data.shadow_soft_size = 0.10
    cyan_obj = bpy.data.objects.new("Light_Cyan_Accent", cyan_data)
    cyan_obj.location = (0.0, 0.62, 0.28)
    scene.collection.objects.link(cyan_obj)

    # 7. Crisp tiny-radius spotlight strictly for Scene 1 cockroach silhouette shadow + puddle specular glint!
    roach_spot_data = bpy.data.lights.new(name="Light_Roach_ShadowSpot", type="SPOT")
    roach_spot_data.energy = 0.0
    roach_spot_data.color = (0.52, 0.76, 1.0)
    roach_spot_data.shadow_soft_size = 0.004
    roach_spot_data.spot_size = math.radians(56.0)
    roach_spot_data.spot_blend = 0.35
    roach_spot_obj = bpy.data.objects.new("Light_Roach_ShadowSpot", roach_spot_data)
    roach_spot_obj.location = (0.02, -0.11, 0.21)
    aim_dir = (Vector((0.0, 0.15, 0.0)) - roach_spot_obj.location).normalized()
    roach_spot_obj.rotation_euler = aim_dir.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(roach_spot_obj)

    # 8. Grazing cool specular rim on Indomie broth puddle for 01A low-brightness mobile readability!
    puddle_spec_data = bpy.data.lights.new(name="Light_Puddle_Spec", type="AREA")
    puddle_spec_data.shape = "RECTANGLE"
    puddle_spec_data.size = 0.35
    puddle_spec_data.size_y = 0.16
    puddle_spec_data.energy = 0.0
    puddle_spec_data.color = (0.58, 0.80, 1.0)
    puddle_spec_obj = bpy.data.objects.new("Light_Puddle_Spec", puddle_spec_data)
    puddle_spec_obj.location = (0.02, 0.65, 0.18)
    aim_p = (Vector((0.0, 0.22, 0.002)) - puddle_spec_obj.location).normalized()
    puddle_spec_obj.rotation_euler = aim_p.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(puddle_spec_obj)

    return {
        "world_bg": bg,
        "night_light": night_data,
        "neon_light": neon_data,
        "neon_obj": neon_obj,
        "rim_light": rim_data,
        "rim_obj": rim_obj,
        "fg_light": fg_data,
        "fg_obj": fg_obj,
        "face_fill_light": face_fill_data,
        "face_fill_obj": face_fill_obj,
        "cyan_light": cyan_data,
        "roach_spot_light": roach_spot_data,
        "roach_spot_obj": roach_spot_obj,
        "puddle_spec_light": puddle_spec_data,
    }


# =============================================================================
# DENSE KOSAN KITCHEN SET — 29 POLY HAVEN CC0 PROPS + EXACT 02:00 WALL CLOCK
# =============================================================================

def _snap_group_bottom_to_z(objs: List[bpy.types.Object], anchor: bpy.types.Object, target_z: float) -> None:
    bpy.context.view_layer.update()
    min_z = None
    for o in objs:
        if o.type != "MESH" or not o.bound_box:
            continue
        for corner in o.bound_box:
            wz = (o.matrix_world @ Vector(corner)).z
            if min_z is None or wz < min_z:
                min_z = wz
    if min_z is not None:
        anchor.location.z += target_z - min_z


def _import_gltf_prop(
    gltf_path: Path,
    name: str,
    location: Tuple[float, float, float],
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
    snap_to_z: Optional[float] = None,
) -> Optional[bpy.types.Object]:
    if not gltf_path.exists():
        return None
    before = set(bpy.data.objects)
    try:
        bpy.ops.import_scene.gltf(filepath=str(gltf_path))
    except Exception as exc:
        log("WARN", f"Could not import GLTF {gltf_path.name}: {exc}")
        return None
    imported = [o for o in bpy.data.objects if o not in before]
    if not imported:
        return None

    anchor = bpy.data.objects.new(name, None)
    anchor.location = location
    anchor.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    anchor.scale = (scale, scale, scale)
    bpy.context.scene.collection.objects.link(anchor)

    for obj in imported:
        if obj.parent is None:
            obj.parent = anchor

    if snap_to_z is not None:
        _snap_group_bottom_to_z(imported, anchor, snap_to_z)
    return anchor


def _configure_wall_clock_0200(anchor: bpy.types.Object) -> None:
    """Set wall_clock hands strictly to 02:00 (hour=+60deg, minute=0deg) with bold jet-black hands."""
    bpy.context.view_layer.update()
    target_angles_deg = {"hour": 60.0, "minute": 0.0, "second": 180.0}
    hand_black_mat = props.make_material("Mat_ClockHand_JetBlack", (0.006, 0.006, 0.008, 1.0), roughness=0.22)

    for obj in anchor.children_recursive:
        if obj.type != "MESH" or not obj.data.vertices:
            continue
        lname = obj.name.lower()
        matched_key = "hour" if "hour" in lname else ("minute" if "minute" in lname else ("second" if "second" in lname else None))
        if matched_key is not None:
            best_v = max(obj.data.vertices, key=lambda v: v.co.x * v.co.x + v.co.z * v.co.z)
            cur_rad = math.atan2(best_v.co.x, best_v.co.z)
            tgt_rad = math.radians(target_angles_deg[matched_key])
            obj.rotation_mode = "XYZ"
            obj.rotation_euler.y += tgt_rad - cur_rad
            if matched_key in ("hour", "minute"):
                obj.scale = (1.42, 1.0, 1.08)
            obj.data.materials.clear()
            obj.data.materials.append(hand_black_mat)
        else:
            for mat in obj.data.materials:
                if not mat or not mat.use_nodes:
                    continue
                bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf is None:
                    continue
                if "glass" in mat.name.lower() or (
                    "Transmission Weight" in bsdf.inputs and bsdf.inputs["Transmission Weight"].default_value > 0.4
                ):
                    if "Alpha" in bsdf.inputs:
                        bsdf.inputs["Alpha"].default_value = 0.05
                    bsdf.inputs["Roughness"].default_value = 0.05
                    continue
                bc_in = bsdf.inputs.get("Base Color")
                if bc_in and bc_in.is_linked:
                    src_sock = bc_in.links[0].from_socket
                    bc_node = mat.node_tree.nodes.new("ShaderNodeBrightContrast")
                    bc_node.inputs["Bright"].default_value = -0.06
                    bc_node.inputs["Contrast"].default_value = 0.28
                    mat.node_tree.links.new(src_sock, bc_node.inputs["Color"])
                    mat.node_tree.links.new(bc_node.outputs["Color"], bc_in)
                    if "Roughness" in bsdf.inputs and not bsdf.inputs["Roughness"].is_linked:
                        bsdf.inputs["Roughness"].default_value = 0.62
    bpy.context.view_layer.update()
    log("EP001", "Configured Kitchen_WallClock strictly to 02:00 (high-contrast jet-black hands).")


def populate_dense_kosan_kitchen(assets_dir: Path) -> int:
    """Fill the widened kosan kitchen & left shelf with 29 Poly Haven CC0 props."""
    models_dir = assets_dir / "models_3d"

    def _gltf(asset_id: str) -> Path:
        p = models_dir / asset_id / f"{asset_id}_1k.gltf"
        return p if p.exists() else (models_dir / asset_id / f"{asset_id}.gltf")

    counter_top_z = 0.828
    wall_shelf_top_z = 1.495

    sh_scale = 0.88
    sh_x = -0.93
    t1, t2, t3, t4, t5, t6, t7 = [z * sh_scale for z in (0.14, 0.38, 0.66, 0.94, 1.22, 1.51, 1.79)]

    placements = [
        # Floor furniture
        ("cardboard_box_01", "Kardus_DeadEnd_Right", (0.64, 2.48, 0.0), (0.0, 0.0, -18.0), 1.08, 0.0),
        ("modern_wooden_cabinet", "Kitchen_Cabinet_Right", (1.56, 2.15, 0.0), (0.0, 0.0, -90.0), 0.94, 0.0),
        ("Shelf_01", "Kitchen_Shelf_Left", (-1.06, 1.15, 0.0), (0.0, 0.0, 90.0), sh_scale, 0.0),
        ("WoodenChair_01", "Kitchen_Chair_Left", (-0.94, 0.16, 0.0), (0.0, 0.0, 52.0), 0.92, 0.0),
        ("wicker_basket_02", "Kitchen_Basket_Right", (0.84, 1.98, 0.0), (0.0, 0.0, 22.0), 0.98, 0.0),
        ("wooden_bowl_01", "Kitchen_Bowl_Floor", (0.76, 0.72, 0.0), (0.0, 0.0, 25.0), 0.95, 0.0),
        # Packed left shelf (14 real Poly Haven CC0 props!)
        ("wicker_basket_02", "LeftShelf_Basket_T1", (sh_x, 0.96, t1), (0.0, 0.0, 82.0), 0.48, t1),
        ("cardboard_box_01", "LeftShelf_Box_T1", (sh_x, 1.36, t1), (0.0, 0.0, 4.0), 0.42, t1),
        ("pot_enamel_01", "LeftShelf_Pot_T2", (sh_x, 0.94, t2), (0.0, 0.0, 65.0), 0.72, t2),
        ("wooden_bowl_01", "LeftShelf_Bowl_T2", (sh_x, 1.34, t2), (0.0, 0.0, 18.0), 0.72, t2),
        ("jug_01", "LeftShelf_Jug_T3", (sh_x, 0.88, t3), (0.0, 0.0, 75.0), 0.72, t3),
        ("ceramic_vase_01", "LeftShelf_Vase1_T3", (sh_x, 1.18, t3), (0.0, 0.0, 25.0), 0.72, t3),
        ("food_apple_01", "LeftShelf_Apple_T3", (sh_x, 1.42, t3), (0.0, 0.0, 10.0), 1.05, t3),
        ("tea_set_01", "LeftShelf_TeaSet_T4", (sh_x, 1.02, t4), (0.0, 0.0, 90.0), 0.68, t4),
        ("ceramic_vase_02", "LeftShelf_Vase2_T4", (sh_x, 1.40, t4), (0.0, 0.0, -15.0), 0.72, t4),
        ("metal_jug", "LeftShelf_MetalJug_T5", (sh_x, 0.92, t5), (0.0, 0.0, 110.0), 0.76, t5),
        ("wooden_bowl_02", "LeftShelf_Bowl2_T5", (sh_x, 1.28, t5), (0.0, 0.0, 35.0), 0.72, t5),
        ("ceramic_vase_03", "LeftShelf_Vase3_T6", (sh_x, 1.08, t6), (0.0, 0.0, 40.0), 0.72, t6),
        ("brass_pan_01", "LeftShelf_Pan_T6", (sh_x, 1.38, t6), (0.0, 0.0, 72.0), 0.58, t6),
        ("pot_enamel_01", "LeftShelf_Pot_T7", (sh_x, 1.14, t7), (0.0, 0.0, -35.0), 0.68, t7),
        # Right counter & wall shelf
        ("electric_stove", "Kitchen_Stove", (1.58, 0.65, counter_top_z), (0.0, 0.0, -90.0), 0.88, counter_top_z),
        ("pot_enamel_01", "Kitchen_Pot_Enamel", (1.54, 0.42, counter_top_z), (0.0, 0.0, 30.0), 0.95, counter_top_z),
        ("brass_pan_01", "Kitchen_Pan", (1.58, 1.02, counter_top_z), (0.0, 0.0, -145.0), 0.95, counter_top_z),
        ("wooden_cutting_board", "Kitchen_CuttingBoard", (1.54, 0.12, counter_top_z), (0.0, 0.0, 12.0), 0.95, counter_top_z),
        ("metal_jug", "Kitchen_MetalJug", (1.56, -0.14, counter_top_z), (0.0, 0.0, -40.0), 0.95, counter_top_z),
        ("wooden_bowl_02", "Kitchen_Bowl_Shelf", (1.76, 0.28, wall_shelf_top_z), (0.0, 0.0, 15.0), 0.95, wall_shelf_top_z),
        ("jug_01", "Kitchen_Jug_Shelf", (1.76, 0.68, wall_shelf_top_z), (0.0, 0.0, -30.0), 0.95, wall_shelf_top_z),
        ("tea_set_01", "Kitchen_TeaSet_Shelf", (1.74, 1.06, wall_shelf_top_z), (0.0, 0.0, -85.0), 0.90, wall_shelf_top_z),
        # Wall clock strictly at 02:00!
        ("wall_clock", "Kitchen_WallClock", (0.88, 3.50, 1.92), (0.0, 0.0, 0.0), 1.44, None),
    ]

    placed = 0
    for asset_id, name, loc, rot_deg, scale, snap_z in placements:
        obj = _import_gltf_prop(_gltf(asset_id), name, loc, rot_deg, scale=scale, snap_to_z=snap_z)
        if obj is not None:
            placed += 1
            if name == "Kitchen_WallClock":
                _configure_wall_clock_0200(obj)
        elif asset_id == "cardboard_box_01" and name == "Kardus_DeadEnd_Right":
            box_mat = props.make_material("Mat_Cardboard_Fallback", (0.48, 0.35, 0.20, 1.0), roughness=0.88)
            props._make_beveled_box(name, (0.44, 0.40, 0.36), 0.006, box_mat, location=(loc[0], loc[1], 0.18))
            placed += 1

    log("EP001", f"Populated dense kosan kitchen with {placed}/{len(placements)} Poly Haven CC0 props.")
    return placed


# =============================================================================
# KEYFRAME & SECONDARY MOTION HELPERS
# =============================================================================

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _kf_loc_rot(obj: bpy.types.Object, frame: int, loc=None, rot_deg=None, scale=None) -> None:
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert(data_path="location", frame=frame)
    if rot_deg is not None:
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ")
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert(data_path="scale", frame=frame)


def _kf_fov(cam_data: bpy.types.Camera, frame: int, fov_deg: float) -> None:
    cam_data.lens_unit = "MILLIMETERS"
    sensor_mm = cam_data.sensor_height if cam_data.sensor_fit == "VERTICAL" else cam_data.sensor_width
    fov_rad = math.radians(max(12.0, min(150.0, fov_deg)))
    cam_data.lens = (sensor_mm * 0.5) / math.tan(fov_rad * 0.5)
    cam_data.keyframe_insert(data_path="lens", frame=frame)


def _kf_dof(cam_data: bpy.types.Camera, frame: int, dist_m: float, fstop: float = 3.2) -> None:
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = max(0.05, dist_m)
    cam_data.dof.aperture_fstop = fstop
    cam_data.dof.keyframe_insert(data_path="focus_distance", frame=frame)
    cam_data.dof.keyframe_insert(data_path="aperture_fstop", frame=frame)


def _kf_hide(obj: bpy.types.Object, frame: int, hidden: bool) -> None:
    for t in [obj] + list(obj.children_recursive):
        t.hide_render = hidden
        t.hide_viewport = hidden
        t.keyframe_insert(data_path="hide_render", frame=frame)
        t.keyframe_insert(data_path="hide_viewport", frame=frame)


def _kf_light(light_data: bpy.types.Light, frame: int, energy: float) -> None:
    light_data.energy = energy
    light_data.keyframe_insert(data_path="energy", frame=frame)


def _set_neon_emission(neon_mat: bpy.types.Material, frame: int, strength: float) -> None:
    for node in neon_mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED" and "Emission Strength" in node.inputs:
            node.inputs["Emission Strength"].default_value = strength
            node.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=frame)


def _set_antennae_independent(
    ant_rig: Dict[str, bpy.types.Object],
    frame: int,
    t_sec: float,
    pitch_deg: float,
    spread_deg: float,
    jitter: float = 0.0,
    wind_bend_deg: float = 0.0,
) -> None:
    """Animate left & right cockroach antennae independently (twitch -> stiff -> wind-bent -> frantic run)."""
    # Independent frequencies & phases so the two antennae feel genuinely alive!
    jl_p = jitter * (0.65 * math.sin(t_sec * 18.0 + 0.3) + 0.35 * math.cos(t_sec * 31.0))
    jl_s = jitter * (0.70 * math.cos(t_sec * 14.5 + 1.1) + 0.30 * math.sin(t_sec * 27.0))
    jr_p = jitter * (0.65 * math.cos(t_sec * 21.0 + 2.2) + 0.35 * math.sin(t_sec * 35.0))
    jr_s = jitter * (0.70 * math.sin(t_sec * 16.0 + 0.7) + 0.30 * math.cos(t_sec * 29.0))
    _kf_loc_rot(ant_rig["ant_l"], frame, rot_deg=(pitch_deg + wind_bend_deg + jl_p, 0.0, spread_deg + jl_s))
    _kf_loc_rot(ant_rig["ant_r"], frame, rot_deg=(pitch_deg + wind_bend_deg * 0.85 + jr_p, 0.0, -spread_deg - jr_s))


# =============================================================================
# STORYBOARD HERO BEAT PICKERS (REQUIRED INTERFACE FOR GENERIC RUNNER)
# =============================================================================

def pick_scene01a_frame(scene_meta: Dict[str, Any], fps: int) -> int:
    f0 = int(scene_meta["start_frame"])
    f1 = int(scene_meta["end_frame"])
    return max(f0, min(f1, f0 + int(round(0.50 * fps))))


def pick_storyboard_frame(scene_meta: Dict[str, Any], fps: int) -> int:
    sid = int(scene_meta["scene_id"])
    f0 = int(scene_meta["start_frame"])
    f1 = int(scene_meta["end_frame"])
    span = max(1, f1 - f0)
    if sid == 4:
        return max(f0, min(f1, f0 + int(round(0.68 * fps))))
    frac_map = {
        1: 0.55,  # 01B: Neon flash! Mas Dimas at wall switch turning shocked, wearing BOTH green sandals!
        2: 0.65,  # Boss Terakhir: Mas Dimas stepped forward, R barefoot, L wearing sandal, backswing swat grip!
        3: 0.55,  # Cheat Code Aktif: bullet-time descending flat green sandal + cyan wind + reactive antennae
        5: 0.72,  # Tinggal Sejengkal: fridge 5.5cm gap + Mas Dimas's LEFT foot (wearing green sandal!) stomping!
        6: 0.88,  # Terkepung: undistorted wide frame — shod L foot blocking gap + backswing swat sandal above!
        7: 0.72,  # Mode Terbang: translucent amber veined wings fluttering + erratic ascent toward Mas Dimas
        8: 0.72,  # Maaf Ya Bang: upper-third safe-zone shocked glasses face in shadow + falling green sandal + amber wings!
    }
    return max(f0, min(f1, f0 + int(round(frac_map.get(sid, 0.50) * span))))


def get_storyboard_extra_frames(manifest: Dict[str, Any], fps: int) -> List[int]:
    """Return all extra frames needed for fast storyboard baking (01A + Scene 8 pre-drop anchor)."""
    frames: List[int] = [1]
    for s_meta in manifest["scenes"]:
        sid = int(s_meta["scene_id"])
        if sid == 1:
            frames.append(pick_scene01a_frame(s_meta, fps))
        frames.append(pick_storyboard_frame(s_meta, fps))
        if sid == 8:
            f0 = int(s_meta["start_frame"])
            f_pre = f0 + int(round(float(s_meta.get("cut_to_black_sec", 4.5)) * 0.52 * fps))
            frames.append(max(f0, f_pre))
    return frames


# =============================================================================
# MAIN EPISODE BUILDER ENTRYPOINT (`build_episode_scene`)
# =============================================================================

def build_episode_scene(
    scene: bpy.types.Scene,
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    assets_dir: Path,
    human: Dict[str, Any],
    mode: str = "storyboard",
    bake_frames: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Assemble EP001 kosan kitchen, Mas Dimas, pair of Swallow sandals, POV camera & bake keyframes."""
    fps = int(manifest.get("fps", 24))
    pov_cfg = spec["pov_config"]
    cam_h = float(pov_cfg.get("camera_height_m", 0.015))
    base_fov = float(pov_cfg.get("base_fov_deg", 95.0))
    total_frames = int(manifest["total_frames"])
    is_still = mode == "storyboard"

    bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT" if bake_frames is None else "LINEAR"

    # 1. Build kitchen room, lighting & 29 Poly Haven CC0 props (+ 02:00 wall clock)
    env = props.build_kitchen_tile_floor(assets_dir)
    lights = setup_world_and_lights(scene, assets_dir)
    populate_dense_kosan_kitchen(assets_dir)

    # Reposition left-wall Broco switch to bare wall past shelf edge (y=2.22) so it sits cleanly inside 01A & 01B!
    sw1 = bpy.data.objects.get("Wall_LightSwitch_1")
    if sw1 is not None:
        sw1.location = (-1.305, 2.22, 1.18)

    # 2. Build stylized Indonesian props + PAIR of green Swallow flip-flops (Left + Right for 100% continuity!)
    props.build_indomie_bowl_spill((0.0, 0.22, 0.0))
    props.build_fridge_under_gap((-0.14, 2.95, 0.0))
    sandal_right = props.build_sandal_jepit_swallow((0.0, 0.0, 0.0))
    sandal_right["root"].name = "Sandal_Right_Root"
    sandal_left = props.build_sandal_jepit_swallow((0.0, 0.0, 0.0))
    sandal_left["root"].name = "Sandal_Left_Root"

    wind = props.build_wind_lines((0.0, 0.65, 0.18))
    dust = props.build_dust_puff((0.06, 0.72, 0.014))
    shadow_roach = props.build_cockroach_shadow_caster((0.0, 0.055, 0.018))

    # 3. Setup Micro-POV Camera (1.5cm height, Macro DOF, Antennae + Front Leg Tips + Veined Amber Wings)
    cam_data = bpy.data.cameras.new("MicroPOV_Camera")
    cam_data.clip_start = 0.005
    cam_data.clip_end = 40.0
    cam_data.sensor_fit = "VERTICAL"
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 3.2
    cam_data.dof.focus_distance = 0.25
    cam_obj = bpy.data.objects.new("MicroPOV_Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    ant_rig = props.build_cockroach_antennae_rig(cam_obj)
    speed_rig = props.build_speed_lines_rig(cam_obj)

    # Tame wing & antennae specular/glossy so Scene 8 wings stay rich translucent AMBER-BROWN (identical to Scene 7!)
    for mat_name, col, rough, alpha in [
        ("Mat_Cockroach_Wing", (0.24, 0.095, 0.018, 1.0), 0.50, 0.48),
        ("Mat_Cockroach_WingVein", (0.06, 0.022, 0.005, 1.0), 0.56, 0.72),
        ("Mat_Cockroach_Antenna", (0.035, 0.011, 0.003, 1.0), 0.55, 1.0),
        ("Mat_Cockroach_AntennaSeg", (0.030, 0.010, 0.003, 1.0), 0.55, 1.0),
    ]:
        m = bpy.data.materials.get(mat_name)
        if m and m.use_nodes:
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf:
                bsdf.inputs["Base Color"].default_value = col
                bsdf.inputs["Roughness"].default_value = rough
                if "Coat Weight" in bsdf.inputs:
                    bsdf.inputs["Coat Weight"].default_value = 0.02
                if "Specular IOR Level" in bsdf.inputs:
                    bsdf.inputs["Specular IOR Level"].default_value = 0.05
                if "Transmission Weight" in bsdf.inputs:
                    bsdf.inputs["Transmission Weight"].default_value = 0.0
                if "Alpha" in bsdf.inputs:
                    bsdf.inputs["Alpha"].default_value = alpha

    # Cut-to-black shutter right in front of lens for Scene 8 ending
    black_mat = props.make_material("Mat_CutToBlack", (0.0, 0.0, 0.0, 1.0), roughness=1.0)
    black_shutter = props._make_beveled_box(
        "CutToBlack_Shutter",
        (0.40, 0.40, 0.002),
        0.0,
        black_mat,
        parent=cam_obj,
        location=(0.0, 0.0, -0.020),
    )

    tmap: Dict[int, Dict[str, Any]] = {int(s["scene_id"]): s for s in manifest["scenes"]}
    smap: Dict[int, Dict[str, Any]] = {int(s["scene_id"]): s for s in spec["scenes"]}

    def _scene_for_frame(fr: int) -> Tuple[int, Dict[str, Any], float, float]:
        for sid in sorted(tmap.keys()):
            s = tmap[sid]
            if int(s["start_frame"]) <= fr <= int(s["end_frame"]):
                span = max(1, int(s["end_frame"]) - int(s["start_frame"]))
                u = (fr - int(s["start_frame"])) / float(span)
                local_sec = (fr - int(s["start_frame"])) / float(fps)
                return sid, s, u, local_sec
        last_sid = max(tmap.keys())
        s = tmap[last_sid]
        return last_sid, s, 1.0, float(s["scene_duration_sec"])

    frames_to_bake = sorted(set(bake_frames)) if bake_frames is not None else list(range(1, total_frames + 1))
    log("EP001", f"Baking {len(frames_to_bake)} frames (Mas Dimas + pair sandal continuity + 5-archetype POV camera)...")
    t_bake = _time.monotonic()

    drop_anchor_pos: Optional[Vector] = None
    drop_anchor_quat: Optional[Quaternion] = None
    sandal_grip_distances: Dict[int, float] = {}

    for idx_f, fr in enumerate(frames_to_bake):
        scene.frame_set(fr)
        t_global = (fr - 1) / float(fps)
        sid, s_meta, u, local_sec = _scene_for_frame(fr)
        sc_spec = smap.get(sid, {})
        arm = human["arm"]
        mh.reset_pose(human)

        # Camera archetype & modifiers from spec!
        archetype = sc_spec.get("camera_archetype", pov_cfg.get("camera_archetype", "insect_ground"))
        modifiers = list(sc_spec.get("motion_modifiers", []))
        cam_motion_intensity = 0.85
        cam_snap_time: Optional[float] = None
        cam_impact_times: List[float] = []
        cam_fov_rush_prog = 0.0
        cam_fov_rush_target = 112.0

        # Default VFX visibility per frame
        show_wind = False
        show_dust = False
        show_speed = False
        show_wings = False
        show_black = False
        show_shadow_roach = False
        show_front_legs = sid in (1, 4, 5)

        # Default lighting
        e_night = 0.8
        e_neon = 118.0
        neon_y = 2.15
        e_rim = 195.0
        rim_loc = (0.0, 2.86, 2.08)
        rim_rot = (-42.0, 0.0, 0.0)
        e_fg = 10.0
        e_face_fill = 0.0
        e_cyan = 0.0
        e_roach_spot = 0.0
        roach_spot_col = (0.52, 0.76, 1.0)
        e_puddle_spec = 0.0
        e_neon_emit = 14.0
        w_strength = 0.07

        # Default Mas Dimas state & sandal continuity:
        #   - Left foot ALWAYS wears `sandal_left` (left_sandal_on_foot = True across ALL 8 scenes!)
        #   - Right sandal: "foot" in Scene 1A & 1B | "hand" in Scene 2–7 | "drop" in Scene 8!
        h_loc = (0.04, 1.38, 0.0)
        h_yaw = 0.0
        h_hip_drop = 0.06
        h_stance_scale = 0.72
        h_stagger_y = 0.07
        l_foot_ov = None
        torso_lean = 12.0
        torso_tw = 0.0
        head_yaw, head_pitch = 0.0, 18.0
        expr1, expr2, expr_k, jaw_ex = "glare", None, 0.0, 0.0

        right_sandal_mode = "hand"  # "foot" | "hand" | "drop"
        r_hand_curls = mh.GRIP_CURLS
        l_hand_curls = None
        right_hand_target: Optional[Vector] = Vector((-0.34, 1.18, 1.44))
        left_hand_target: Optional[Vector] = None
        r_pole_mode = "backswing"  # "backswing" | "reach_side" | "slam" | "panic"
        sandal_aim_sole: Optional[Vector] = Vector((0.16, -0.70, -0.69)).normalized()
        sandal_blade_hint: Optional[Vector] = Vector((-0.65, -0.52, 0.55))

        # Default camera
        cam_loc = (0.0, 0.0, cam_h)
        cam_rot = (90.0, 0.0, 0.0)
        cam_fov = base_fov
        dof_dist = 1.0
        dof_fstop = 3.4

        # Default antennae & wings
        ant_pitch, ant_spread, ant_jit, ant_wind = 16.0, 10.0, 4.0, 0.0
        wing_flap = 0.0

        # =====================================================================
        # SCENE 1: JAM 2 PAGI — 01A & 01B Continuity: Switch on Left Wall, BOTH Sandals on Feet!
        # =====================================================================
        if sid == 1:
            t_flash = 1.05
            show_shadow_roach = True
            right_sandal_mode = "foot"  # BOTH feet wear green Swallow sandals in 01A & 01B! ZERO sandal in hand!
            cam_snap_time = t_flash

            if local_sec < t_flash:
                # 01A (0.0–1.05s): Half-dark 2 AM blue + puddle specular glint + crisp cockroach shadow;
                # Mas Dimas stands near left wall switch reaching hand to flip it!
                e_night = 24.0
                e_neon = 0.0
                e_rim = 18.0
                e_fg = 0.0
                e_roach_spot = 4.2
                roach_spot_col = (0.54, 0.78, 1.0)
                e_puddle_spec = 2.6  # Subtle golden specular sheen on Indomie broth without white blowout!
                e_neon_emit = 0.06
                w_strength = 0.12

                cam_loc = (0.0, -0.03 + 0.02 * (local_sec / t_flash), cam_h + 0.002)
                cam_rot = (80.5, 0.0, 1.5)
                cam_fov = 96.0
                dof_dist = 0.22
                dof_fstop = 3.8
                cam_motion_intensity = 0.25
                ant_pitch, ant_spread, ant_jit = -6.0, 10.0, 3.2

                # Mas Dimas positioned near bare left-wall Broco switch (-1.305, 2.22, 1.18), reaching right hand to flip it!
                h_loc = (-0.60, 2.22, 0.0)
                h_yaw = -56.0
                h_hip_drop = 0.03
                torso_lean = 10.0
                head_yaw, head_pitch = -12.0, 4.0
                expr1 = "neutral"
                r_hand_curls = mh.POINT_SWITCH_CURLS
                r_pole_mode = "reach_side"
                right_hand_target = Vector((-1.25, 2.22, 1.18))  # Touching Broco light switch on bare left wall!
            else:
                # 01B (1.05s+): Neon flashes ON! Camera snap_jerk up!
                # Mas Dimas just clicked the switch, hand pulling back slightly, head snapping shocked at floor!
                # BOTH green Swallow flip-flops are STILL on his feet — NO sandal in hand!
                dt = local_sec - t_flash
                flash_boost = max(0.0, 1.0 - dt / 0.35)
                e_night = 0.8
                e_neon = 128.0 + 65.0 * flash_boost
                e_rim = 215.0
                e_fg = 13.0
                e_roach_spot = 5.5
                roach_spot_col = (0.94, 0.96, 1.0)
                e_puddle_spec = 1.6
                e_neon_emit = 15.0 + 6.0 * flash_boost
                w_strength = 0.08

                jolt = _smooth(min(1.0, dt / 0.22))
                cam_loc = (0.0, -0.02, cam_h + 0.006 * jolt)
                cam_rot = (_lerp(81.5, 98.5, jolt), 2.0 * math.sin(jolt * math.pi), 6.5 * jolt)
                cam_fov = 95.0
                dof_dist = _lerp(0.24, 1.55, jolt)
                dof_fstop = 4.0
                cam_motion_intensity = 0.35
                ant_pitch, ant_spread, ant_jit = 22.0, 12.0, 1.6  # Stiff frozen startled antennae!

                turn_u = _smooth(min(1.0, dt / 0.65))
                h_loc = (_lerp(-0.60, -0.50, turn_u), 2.22, 0.0)
                h_yaw = _lerp(-56.0, -24.0, turn_u)
                h_hip_drop = 0.05
                torso_lean = _lerp(10.0, 14.0, turn_u)
                torso_tw = _lerp(0.0, 18.0, turn_u)  # Upper body twists cleanly toward camera so JADI APA reads!
                head_yaw = _lerp(-8.0, 22.0, turn_u)
                head_pitch = _lerp(4.0, 22.0, turn_u)
                expr1, expr2, expr_k = "neutral", "shock", turn_u
                r_hand_curls = mh.OPEN_CURLS
                r_pole_mode = "reach_side"
                # Right hand hovering right near the Broco switch he just clicked (EMPTY HAND!)
                right_hand_target = Vector((_lerp(-1.25, -1.08, turn_u), 2.21, _lerp(1.18, 1.15, turn_u)))

        # =====================================================================
        # SCENE 2: BOSS TERAKHIR — Stepped forward! R barefoot, L wearing sandal, BACKSWING SWAT GRIP!
        # =====================================================================
        elif sid == 2:
            e_neon = 114.0
            e_rim = 260.0
            e_fg = 10.0
            w_strength = 0.06

            h_loc = (0.04, 1.40, 0.0)
            h_yaw = 6.0
            h_hip_drop = 0.11
            h_stance_scale = 0.72
            h_stagger_y = 0.09
            torso_lean = 22.0
            torso_tw = -12.0  # Slight cocked backswing shoulder coil!
            head_yaw = 10.0
            head_pitch = 24.0
            expr1 = "angry"
            right_sandal_mode = "hand"  # R foot barefoot, L foot wears green sandal!
            r_pole_mode = "backswing"

            # Cocked athletic backswing (elbow bent out/back, flat green sole aimed forward-down toward camera!)
            su = _smooth(u)
            right_hand_target = Vector((_lerp(-0.36, -0.40, su), _lerp(1.28, 1.24, su), _lerp(1.42, 1.54, su)))
            sandal_aim_sole = Vector((0.20, -0.68, -0.71)).normalized()
            sandal_blade_hint = Vector((-0.68, -0.50, 0.54))

            step_u = _smooth(min(1.0, u * 1.15))
            cam_loc = (_lerp(0.0, -0.02, step_u), _lerp(0.06, 0.12, step_u), cam_h + 0.003)
            cam_rot = (_lerp(116.0, 126.0, step_u), 2.0 * math.sin(u * math.pi * 2.0), _lerp(2.0, 5.0, step_u))
            cam_fov = _lerp(88.0, 68.0, step_u)
            dof_dist = 1.38
            dof_fstop = 3.6
            cam_motion_intensity = 0.25
            ant_pitch, ant_spread, ant_jit = 20.0, 10.0, 5.5

        # =====================================================================
        # SCENE 3: CHEAT CODE AKTIF — Bullet-time downward swat + cyan wind + reactive antennae
        # =====================================================================
        elif sid == 3:
            e_neon = 104.0
            e_rim = 175.0
            e_fg = 10.0
            e_cyan = _lerp(14.0, 34.0, _smooth(u))
            w_strength = 0.06
            show_wind = True

            su = _smooth(u)
            h_loc = (0.04, 1.32, 0.0)
            h_yaw = 4.0
            h_hip_drop = _lerp(0.10, 0.20, su)
            h_stance_scale = 0.72
            h_stagger_y = 0.10
            torso_lean = _lerp(20.0, 34.0, su)
            torso_tw = _lerp(-14.0, 8.0, su)  # Torso follows through into the swat!
            head_pitch = 26.0
            expr1 = "angry"
            right_sandal_mode = "hand"
            r_pole_mode = "backswing"

            # Downward swat arc: flat green sole clearly angled forward-down toward cockroach!
            right_hand_target = Vector((
                _lerp(-0.38, -0.10, su),
                _lerp(1.18, 0.68, su),
                _lerp(1.48, 0.54, su),
            ))
            sandal_aim_sole = Vector((0.12, _lerp(-0.56, -0.30, su), _lerp(-0.82, -0.95, su))).normalized()
            sandal_blade_hint = Vector((-0.55, -0.78, 0.28))

            cam_loc = (_lerp(0.0, 0.02, u), _lerp(0.04, 0.08, u), cam_h + 0.004)
            cam_rot = (_lerp(116.0, 113.0, u), _lerp(7.0, 11.0, u), _lerp(3.0, 1.5, u))
            cam_fov = _lerp(84.0, 92.0, u)
            dof_dist = _lerp(0.95, 0.62, u)
            dof_fstop = 3.2
            cam_motion_intensity = 0.30
            ant_pitch, ant_spread, ant_jit, ant_wind = 10.0, 16.0, 8.5, -14.0 * su  # Wind bends antennae!

            _kf_loc_rot(
                wind["root"],
                fr,
                loc=(_lerp(-0.08, -0.02, u), _lerp(0.76, 0.42, u), _lerp(0.56, 0.20, u)),
                rot_deg=(_lerp(22.0, 12.0, u), 0.0, _lerp(6.0, 2.0, u)),
                scale=(_lerp(0.65, 1.05, u), _lerp(0.65, 1.18, u), _lerp(0.65, 1.05, u)),
            )

        # =====================================================================
        # SCENE 4: 300 KM/JAM — Sandal SLAMS floor beside camera + impact_bump + fov_rush!
        # =====================================================================
        elif sid == 4:
            e_neon = 122.0
            e_rim = 145.0
            e_fg = 16.0
            w_strength = 0.08
            t_slam = 0.50
            t_hold_impact = 1.05
            cam_impact_times = [t_slam]
            right_sandal_mode = "hand"
            r_pole_mode = "slam"

            if local_sec <= t_slam:
                su = _smooth(local_sec / max(0.05, t_slam))
                h_loc = (_lerp(0.06, 0.30, su), _lerp(1.22, 1.06, su), 0.0)
                h_yaw = _lerp(0.0, -28.0, su)
                h_hip_drop = _lerp(0.20, 0.56, su)
                torso_lean = _lerp(32.0, 58.0, su)
                right_hand_target = Vector((_lerp(-0.02, 0.12, su), _lerp(0.70, 0.78, su), _lerp(0.45, 0.055, su)))
                sandal_aim_sole = Vector((0.0, -0.15, -0.99)).normalized()
                sandal_blade_hint = Vector((-0.42, -0.90, 0.04))
                cam_loc = (_lerp(-0.04, -0.18, su), _lerp(0.24, 0.32, su), cam_h + 0.005)
                cam_rot = (90.5, _lerp(-2.0, -11.0, su), _lerp(0.0, -9.5, su))
                cam_fov = 96.0
                cam_fov_rush_prog = su * 0.55
                dof_dist = 0.48
                cam_motion_intensity = 0.75
            elif local_sec <= t_hold_impact:
                dt_imp = local_sec - t_slam
                du = min(1.0, dt_imp / 0.35)
                show_dust = True
                show_speed = True
                _kf_loc_rot(
                    dust["root"],
                    fr,
                    loc=(0.06, 0.72, 0.012 + 0.006 * du),
                    scale=(_lerp(0.60, 1.40, du), _lerp(0.60, 1.40, du), _lerp(0.55, 1.05, du)),
                )
                h_loc = (0.30, 1.06, 0.0)
                h_yaw = -28.0
                h_hip_drop = 0.56
                torso_lean = 58.0
                right_hand_target = Vector((0.12, 0.78, 0.055))
                sandal_aim_sole = Vector((0.0, 0.0, -1.0))
                sandal_blade_hint = Vector((-0.46, -0.89, 0.0))

                dash_u = dt_imp / max(0.05, t_hold_impact - t_slam)
                cam_loc = (-0.18, _lerp(0.32, 0.52, dash_u), cam_h + 0.006)
                cam_rot = (90.5, -11.0, -9.5)
                cam_fov = 95.0
                cam_fov_rush_prog = _lerp(0.65, 0.85, dash_u)
                dof_dist = 0.44
                cam_motion_intensity = 1.05
            else:
                dt = local_sec - t_hold_impact
                sprint_u = min(1.0, dt / max(0.2, s_meta["scene_duration_sec"] - t_hold_impact))
                show_speed = True
                rec_u = _smooth(min(1.0, sprint_u * 1.3))
                h_loc = (_lerp(0.30, 0.14, rec_u), _lerp(1.06, 1.85, rec_u), 0.0)
                h_yaw = _lerp(-28.0, 155.0, rec_u)
                h_hip_drop = _lerp(0.50, 0.04, rec_u)
                torso_lean = _lerp(48.0, 12.0, rec_u)
                fwd_h = Vector((math.sin(math.radians(h_yaw)), -math.cos(math.radians(h_yaw)), 0.0))
                left_h = Vector((math.cos(math.radians(h_yaw)), math.sin(math.radians(h_yaw)), 0.0))
                right_hand_target = Vector(h_loc) + fwd_h * 0.32 - left_h * 0.24 + Vector((0.0, 0.0, _lerp(0.25, 1.25, rec_u)))
                sandal_aim_sole = (fwd_h * 0.65 + Vector((0.0, 0.0, -0.76))).normalized()
                sandal_blade_hint = Vector((0.0, 0.0, 1.0))

                cam_loc = (-0.16 + 0.03 * sprint_u, _lerp(0.56, 1.86, sprint_u), cam_h + 0.003)
                cam_rot = (91.0, -6.0 * (1.0 - sprint_u), 0.0)
                cam_fov = 95.0
                cam_fov_rush_prog = min(1.0, 0.85 + 0.15 * sprint_u)
                dof_dist = 0.85
                cam_motion_intensity = 1.25
            dof_fstop = 4.0
            expr1 = "angry"
            ant_pitch, ant_spread, ant_jit = -10.0, 18.0, 12.0

        # =====================================================================
        # SCENE 5: TINGGAL SEJENGKAL — LEFT FOOT WEARING GREEN SANDAL STOMPS DOWN!
        # =====================================================================
        elif sid == 5:
            e_neon = 114.0
            e_rim = 148.0
            e_fg = 11.0
            w_strength = 0.07
            dur5 = float(s_meta["scene_duration_sec"])
            t_stomp_start = dur5 * 0.34
            t_stomp_land = dur5 * 0.62  # Lands cleanly BEFORE hero frame (0.72) so shod left foot slams gap!
            cam_impact_times = [t_stomp_land]

            show_speed = local_sec < t_stomp_land
            # Stand slightly left of gap (-0.24) so shod LEFT foot sits naturally under left hip at x=-0.08 (ZERO crossed legs!)
            h_loc = (-0.24, 2.50, 0.0)
            h_yaw = -8.0
            torso_lean = 16.0
            expr1 = "angry"
            right_sandal_mode = "hand"
            r_pole_mode = "backswing"
            right_hand_target = Vector((-0.56, 2.20, 1.48))
            sandal_aim_sole = Vector((0.14, -0.52, -0.84)).normalized()
            sandal_blade_hint = Vector((-0.62, -0.52, 0.58))

            # Left foot (WEARING GREEN SWALLOW SANDAL!) lifts high & stomps down squarely blocking the 5.5cm fridge gap!
            if local_sec < t_stomp_start:
                l_foot_ov = (-0.08, 2.58, 0.40, -14.0)
            elif local_sec < t_stomp_land:
                st_u = _smooth((local_sec - t_stomp_start) / max(0.05, t_stomp_land - t_stomp_start))
                l_foot_ov = (-0.08, _lerp(2.58, 2.38, st_u), _lerp(0.40, 0.0, st_u), _lerp(-14.0, 0.0, st_u))
            else:
                l_foot_ov = (-0.08, 2.38, 0.0, 0.0)
                e_neon = 98.0

            cy = _lerp(1.82, 2.02, min(1.0, u * 1.05))
            cam_loc = (-0.14, cy, cam_h + 0.002)
            pitch_up = 89.5 + (5.5 * _smooth((local_sec - t_stomp_start) / max(0.1, dur5 - t_stomp_start)))
            cam_rot = (pitch_up, 0.4, -4.0)
            cam_fov = _lerp(100.0, 88.0, u)
            dof_dist = _lerp(0.85, 0.42, u)
            dof_fstop = 3.8
            cam_motion_intensity = 1.05 if local_sec < t_stomp_land else 0.25
            ant_pitch = -8.0 if local_sec < t_stomp_land else 20.0
            ant_spread, ant_jit = 14.0, 9.0

        # =====================================================================
        # SCENE 6: TERKEPUNG! — Shod LEFT foot blocking gap + barefoot R (UNCROSSED!) + BACKSWING SWAT SANDAL!
        # =====================================================================
        elif sid == 6:
            e_neon = 118.0
            neon_y = 2.75
            e_rim = 190.0
            e_fg = 10.0
            w_strength = 0.07
            # Natural wide athletic stance (-0.24): barefoot R foot on viewer-left (~ -0.36), shod L foot on viewer-right (~ -0.06) blocking gap!
            h_loc = (-0.24, 2.50, 0.0)
            h_yaw = -8.0
            h_hip_drop = 0.08
            h_stance_scale = 0.85
            l_foot_ov = (-0.06, 2.38, 0.0, 0.0)  # Shod LEFT foot squarely blocking fridge gap (ZERO crossed legs!)
            torso_lean = 18.0
            torso_tw = -8.0
            head_yaw = 10.0
            head_pitch = 24.0
            expr1 = "angry"
            right_sandal_mode = "hand"
            r_pole_mode = "backswing"

            # Cocked backswing overhead inside frame: flat green striking sole aimed down toward camera!
            drop_u = _smooth(max(0.0, (u - 0.65) / 0.35))
            right_hand_target = Vector((-0.56, 2.18, _lerp(1.52, 1.38, drop_u)))
            sandal_aim_sole = Vector((0.20, -0.58, -0.79)).normalized()
            sandal_blade_hint = Vector((-0.68, -0.48, 0.56))

            if u < 0.18:
                bu = _smooth(u / 0.18)
                cam_loc = (-0.14, _lerp(2.00, 1.58, bu), cam_h + 0.004 * bu)
                cam_rot = (_lerp(95.0, 102.0, bu), -2.5 * bu, 0.0)
                dof_dist = 0.72
                cam_fov = _lerp(88.0, 82.0, bu)
            elif u < 0.44:
                lu = _smooth(min(1.0, (u - 0.18) / 0.14))
                cam_loc = (-0.14, 1.58, cam_h + 0.004)
                cam_rot = (93.0, 3.5 * lu, _lerp(0.0, 72.0, lu))
                dof_dist = 0.85
                cam_fov = 82.0
            elif u < 0.70:
                ru = _smooth(min(1.0, (u - 0.44) / 0.14))
                cam_loc = (-0.14, 1.58, cam_h + 0.004)
                cam_rot = (93.0, -3.5 * ru, _lerp(72.0, -68.0, ru))
                dof_dist = 0.85
                cam_fov = 82.0
            else:
                uu = _smooth(min(1.0, (u - 0.70) / 0.16))
                cam_loc = (-0.18, _lerp(1.58, 1.44, uu), cam_h + 0.005)
                cam_rot = (_lerp(93.0, 126.0, uu), 2.0 * math.sin(uu * math.pi), _lerp(-68.0, 4.0, uu))
                dof_dist = 1.20
                cam_fov = _lerp(82.0, 86.0, uu)
            dof_fstop = 4.0
            cam_motion_intensity = 0.40
            ant_pitch, ant_spread, ant_jit = 22.0, 16.0, 12.0

        # =====================================================================
        # SCENE 7: MODE TERBANG — Translucent veined amber wings + aerial_erratic takeoff!
        # =====================================================================
        elif sid == 7:
            e_neon = 120.0
            neon_y = 2.92
            e_rim = 165.0
            rim_loc = (0.0, 2.82, 2.15)
            rim_rot = (-28.0, 0.0, 0.0)
            e_fg = 0.0
            e_face_fill = 0.0
            w_strength = 0.045
            t_wings = 1.35

            h_loc = (0.02, 2.48, 0.0)
            h_yaw = 0.0
            h_hip_drop = 0.06
            torso_lean = 10.0
            torso_tw = -8.0
            head_pitch = _lerp(18.0, 2.0, _smooth(u))
            expr1, expr2, expr_k = "angry", "shock", _smooth(max(0.0, (u - 0.40) / 0.60))
            right_sandal_mode = "hand"
            r_pole_mode = "backswing"
            right_hand_target = Vector((-0.36, 2.22, _lerp(1.48, 1.36, _smooth(u))))
            sandal_aim_sole = Vector((0.20, -0.72, -0.66)).normalized()
            sandal_blade_hint = Vector((-0.66, -0.45, 0.60))

            if local_sec < t_wings:
                u0 = _smooth(local_sec / max(0.1, t_wings))
                cam_loc = (_lerp(-0.08, -0.05, u0), _lerp(1.52, 1.48, u0), cam_h + 0.015 * u0)
                cam_rot = (_lerp(128.0, 114.0, u0), 3.5 * math.sin(fr * 1.4), 0.0)
                cam_fov = _lerp(82.0, 96.0, u0)
                dof_dist = 1.05
                cam_motion_intensity = 0.45
            else:
                show_wings = True
                uf = (local_sec - t_wings) / max(0.1, float(s_meta["scene_duration_sec"]) - t_wings)
                cx = -0.05 + 0.22 * math.sin(uf * math.pi * 2.5)
                cy = _lerp(1.48, 1.28, uf)
                cz = _lerp(0.04, 1.46, uf ** 1.12)
                cam_loc = (cx, cy, cz)
                cam_rot = (
                    _lerp(114.0, 95.0, uf),
                    11.0 * math.sin(uf * math.pi * 3.0),
                    -8.0 * math.cos(uf * math.pi * 2.5),
                )
                cam_fov = _lerp(100.0, 96.0, uf)
                dof_dist = 1.15
                cam_motion_intensity = 0.90
                wing_flap = 24.0 * math.sin(t_global * 42.0)  # Rapid wing flutter!
            dof_fstop = 3.2
            ant_pitch, ant_spread, ant_jit = 12.0, 22.0, 11.5

        # =====================================================================
        # SCENE 8: MAAF YA BANG — Upper-Third Safe-Zone Glasses Face + Dark Shadow + Falling Sandal + Amber Wings!
        # =====================================================================
        elif sid == 8:
            # Tight behind-head halo rim light (never shines on foreground wings or chest!) + deep shadow on face!
            e_neon = 42.0
            neon_y = 3.18
            e_neon_emit = 0.35
            e_rim = 145.0
            rim_loc = (0.0, 2.78, 2.02)
            rim_rot = (-38.0, 0.0, 0.0)
            e_fg = 0.0
            e_face_fill = 0.16  # Tiny whisper so eyes/glasses/mouth stay razor-clear inside dramatic shadow!
            e_night = 0.0
            w_strength = 0.012

            dur8 = float(s_meta["scene_duration_sec"])
            t_black = float(s_meta.get("cut_to_black_sec", dur8 - 0.12))
            t_drop = t_black * 0.56  # Right before hero frame (0.72) so falling green sandal is MID-AIR IN FRAME!

            show_wings = True
            show_speed = False
            show_black = local_sec >= t_black

            h_loc = (0.0, 2.48, 0.0)
            h_yaw = 0.0
            h_hip_drop = 0.02
            recoil_u = _smooth(max(0.0, (local_sec - t_drop) / max(0.25, t_black - t_drop)))
            torso_lean = _lerp(8.0, 3.0, recoil_u)
            head_pitch = _lerp(6.0, 4.0, recoil_u)
            expr1, expr2, expr_k = "shock", "panic", recoil_u
            jaw_ex = 0.28 * recoil_u

            if local_sec < t_drop:
                right_sandal_mode = "hand"
                r_pole_mode = "backswing"
                right_hand_target = Vector((-0.24, 2.16, 1.40))
                left_hand_target = Vector((0.26, 2.22, 1.24))
                sandal_aim_sole = Vector((0.15, -0.78, -0.61)).normalized()
                sandal_blade_hint = Vector((-0.55, -0.35, 0.76))
            else:
                # Throws both hands up in terror INSIDE 9:16 frame & releases green Swallow sandal mid-air!
                right_sandal_mode = "drop"
                r_hand_curls = mh.OPEN_CURLS
                l_hand_curls = mh.OPEN_CURLS
                r_pole_mode = "panic"
                right_hand_target = Vector((-0.24, 2.16, _lerp(1.42, 1.56, recoil_u)))
                left_hand_target = Vector((0.28, 2.20, _lerp(1.30, 1.52, recoil_u)))

            # Camera positioned so Mas Dimas's shocked glasses face sits cleanly in UPPER-THIRD safe zone
            # (100% clear of MarginV=380 subtitles!), with Crimson JADI APA tee + falling green sandal + amber wings!
            dive_u = min(1.0, local_sec / max(0.1, t_black))
            ease = dive_u ** 1.30
            cx = _lerp(0.04, 0.0, ease)
            cy = _lerp(1.24, 1.66, ease)
            cz = _lerp(1.42, 1.36, ease)
            cam_loc = (cx, cy, cz)
            cam_rot = (_lerp(94.0, 96.0, ease), 2.5 * (1.0 - 0.5 * dive_u), 0.0)
            cam_fov = _lerp(94.0, 82.0, ease)
            dof_fstop = 2.8
            cam_motion_intensity = 0.65
            ant_pitch, ant_spread, ant_jit = -28.0, 34.0, 14.0
            wing_flap = 28.0 * math.sin(t_global * 48.0)

        # ---- APPLY CAMERA ARCHETYPE + BEAT MODIFIERS + FLOOR CLAMP ----
        cam_loc_final, cam_rot_final, cam_fov_final = cam_lib.evaluate_camera_pose(
            archetype_name=archetype,
            base_loc=cam_loc,
            base_rot_deg=cam_rot,
            base_fov_deg=cam_fov,
            t_sec=t_global,
            local_sec=local_sec,
            fps=fps,
            modifiers=modifiers,
            motion_intensity=cam_motion_intensity,
            min_z_override=0.012 if archetype == "insect_ground" else None,
            impact_times_sec=cam_impact_times,
            snap_time_sec=cam_snap_time,
            fov_rush_progress=cam_fov_rush_prog,
            fov_rush_target=cam_fov_rush_target,
            is_still_storyboard=is_still,
        )

        # ---- APPLY MAS DIMAS POSE (NEVER A-POSE!) ----
        left_shod_lift = 0.016  # Left foot ALWAYS wears left green Swallow flip-flop!
        right_shod_lift = 0.016 if right_sandal_mode == "foot" else 0.0  # Barefoot (nyeker) from Scene 2 onward!
        mh.place_and_feet(
            human,
            h_loc,
            h_yaw,
            fr,
            hip_drop=h_hip_drop,
            left_foot_override=l_foot_ov,
            stance_scale=h_stance_scale,
            stagger_y=h_stagger_y,
            left_sole_lift=left_shod_lift,
            right_sole_lift=right_shod_lift,
        )
        mh.lean(arm, torso_lean)
        mh.torso_twist(arm, torso_tw)
        mh.head_turn(arm, head_yaw, head_pitch)
        mh.D.pose_arms(arm, yaw_deg=h_yaw + torso_tw, elbow=16.0)
        mh.D.relaxed_hands(arm)
        mh.set_hand_curl(arm, "R", r_hand_curls, wrist_pitch=-12.0 if right_sandal_mode == "hand" else -4.0, twist=32.0)
        if l_hand_curls is not None:
            mh.set_hand_curl(arm, "L", l_hand_curls, wrist_pitch=-6.0, twist=20.0)

        fwd_v, left_v = mh.body_frame(arm)
        if right_hand_target is not None:
            if r_pole_mode == "backswing":
                # Realistic swat backswing: elbow bends outward-right & slightly back-up!
                r_pole = -fwd_v * 0.60 - left_v * 0.95 + Vector((0.0, 0.0, 0.20))
            elif r_pole_mode == "reach_side":
                r_pole = -fwd_v * 0.45 - left_v * 0.70 + Vector((0.0, 0.0, -0.55))
            elif r_pole_mode == "slam":
                r_pole = -fwd_v * 0.25 - left_v * 0.90 + Vector((0.0, 0.0, 0.35))
            else:
                r_pole = -fwd_v * 0.35 - left_v * 0.85 + Vector((0.0, 0.0, -0.55))
            mh.reach(arm, "R", right_hand_target, r_pole)
        if left_hand_target is not None:
            l_pole = -fwd_v * 0.35 + left_v * 0.85 + Vector((0.0, 0.0, -0.55))
            mh.reach(arm, "L", left_hand_target, l_pole)

        mh.key_pose(human, fr)
        mh.set_face(human, t_global, fps, expr1, expr2, expr_k, jaw_extra=jaw_ex, frame=fr)

        # ---- SANDAL CONTINUITY LOCK ----
        # 1. LEFT sandal: ALWAYS worn snugly on Mas Dimas's LEFT foot across ALL 8 scenes!
        mh.snap_sandal_to_foot(human, sandal_left["root"], "L", fr, floor_clamp=True)

        # 2. RIGHT sandal: worn on RIGHT foot (Scene 1A & 1B) -> gripped in RIGHT hand (Scene 2-7) -> dropped (Scene 8)!
        if right_sandal_mode == "foot":
            mh.snap_sandal_to_foot(human, sandal_right["root"], "R", fr, floor_clamp=True)
        elif right_sandal_mode == "hand":
            pos_s = mh.snap_sandal_to_right_hand(
                human,
                sandal_right["root"],
                fr,
                aim_sole_dir=sandal_aim_sole,
                blade_dir_hint=sandal_blade_hint,
            )
            w_now = mh.wp(arm, arm.pose.bones["wrist.R"].head)
            sandal_grip_distances[sid] = max(sandal_grip_distances.get(sid, 0.0), (pos_s - w_now).length)
            if sid == 8:
                drop_anchor_pos = sandal_right["root"].location.copy()
                drop_anchor_quat = sandal_right["root"].rotation_quaternion.copy()
        else:
            # Scene 8 post-drop gravity tumble RIGHT INSIDE THE 9:16 FRAME below Mas Dimas's panicked right hand!
            dt_drop = max(0.0, local_sec - (float(s_meta.get("cut_to_black_sec", 4.5)) * 0.56))
            if drop_anchor_pos is None:
                drop_anchor_pos = Vector((-0.20, 2.12, 1.38))
                drop_anchor_quat = Euler((math.radians(108.0), math.radians(18.0), math.radians(-24.0))).to_quaternion()
            inward_u = min(1.0, dt_drop / 0.85)
            fall_pos = Vector((
                _lerp(drop_anchor_pos.x, -0.15, inward_u),
                drop_anchor_pos.y - 0.06 * dt_drop,
                max(0.02, drop_anchor_pos.z - 0.16 * dt_drop - 0.5 * 0.24 * (dt_drop ** 2)),
            ))
            spin_q = Euler((dt_drop * 1.1 + 0.5, dt_drop * 0.8, dt_drop * 0.6 - 0.35)).to_quaternion()
            sandal_right["root"].rotation_mode = "QUATERNION"
            sandal_right["root"].location = fall_pos
            sandal_right["root"].rotation_quaternion = spin_q @ drop_anchor_quat
            sandal_right["root"].keyframe_insert("location", frame=fr)
            sandal_right["root"].keyframe_insert("rotation_quaternion", frame=fr)

        # In Scene 8, dynamically focus Macro DOF squarely onto Mas Dimas's glasses & terrified eyes!
        if sid == 8:
            face_pt = mh.eye_mid(human)
            dof_dist = max(0.15, (face_pt - Vector(cam_loc_final)).length)

        # ---- CAMERA, MACRO DOF, INDEPENDENT ANTENNAE, FLUTTERING AMBER WINGS, VFX, LIGHTS ----
        _kf_loc_rot(cam_obj, fr, loc=cam_loc_final, rot_deg=cam_rot_final)
        _kf_fov(cam_data, fr, cam_fov_final)
        _kf_dof(cam_data, fr, dof_dist, fstop=dof_fstop)

        _set_antennae_independent(ant_rig, fr, t_global, ant_pitch, ant_spread, jitter=ant_jit, wind_bend_deg=ant_wind)
        if show_wings:
            # Pull wings slightly inward in narrower Scene 08 FOV so translucent amber-brown wings match Scene 07!
            wx = 0.019 if sid == 8 else 0.028
            wy = -0.028 if sid == 8 else -0.034
            wz = -0.050 if sid == 8 else -0.048
            _kf_loc_rot(ant_rig["wing_l_pivot"], fr, loc=(-wx, wy, wz), rot_deg=(-8.0, wing_flap, 12.0))
            _kf_loc_rot(ant_rig["wing_r_pivot"], fr, loc=(wx, wy, wz), rot_deg=(-8.0, -wing_flap, -12.0))

        _kf_hide(wind["root"], fr, not show_wind)
        _kf_hide(dust["root"], fr, not show_dust)
        _kf_hide(speed_rig["root"], fr, not show_speed)
        _kf_hide(ant_rig["wing_l"], fr, not show_wings)
        _kf_hide(ant_rig["wing_r"], fr, not show_wings)
        _kf_hide(ant_rig["leg_l"], fr, not show_front_legs)
        _kf_hide(ant_rig["leg_r"], fr, not show_front_legs)
        _kf_hide(shadow_roach["root"], fr, not show_shadow_roach)
        _kf_hide(black_shutter, fr, not show_black)

        _kf_loc_rot(lights["neon_obj"], fr, loc=(0.0, neon_y, 2.56))
        _kf_loc_rot(lights["rim_obj"], fr, loc=rim_loc, rot_deg=rim_rot)
        _kf_light(lights["night_light"], fr, e_night)
        _kf_light(lights["neon_light"], fr, e_neon)
        _kf_light(lights["rim_light"], fr, e_rim)
        _kf_light(lights["fg_light"], fr, e_fg)
        _kf_light(lights["face_fill_light"], fr, e_face_fill)
        _kf_light(lights["cyan_light"], fr, e_cyan)
        _kf_light(lights["roach_spot_light"], fr, e_roach_spot)
        lights["roach_spot_light"].color = roach_spot_col
        lights["roach_spot_light"].keyframe_insert(data_path="color", frame=fr)
        _kf_light(lights["puddle_spec_light"], fr, e_puddle_spec)
        _set_neon_emission(env["neon_mat"], fr, e_neon_emit)
        lights["world_bg"].inputs["Strength"].default_value = w_strength
        lights["world_bg"].inputs["Strength"].keyframe_insert("default_value", frame=fr)

        if (idx_f + 1) % 240 == 0:
            log("EP001", f"Baked {idx_f + 1}/{len(frames_to_bake)} frames ({_time.monotonic() - t_bake:.1f}s)")

    scene.frame_start = 1
    scene.frame_end = total_frames
    log("EP001", f"Finished baking {len(frames_to_bake)} frames in {_time.monotonic() - t_bake:.1f}s")

    return {
        "tmap": tmap,
        "cam_obj": cam_obj,
        "sandal_right": sandal_right,
        "sandal_left": sandal_left,
        "sandal_grip_distances": sandal_grip_distances,
    }
