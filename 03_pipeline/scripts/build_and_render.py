#!/usr/bin/env python3
"""Blender 5.2+ Headless 3D Micro-POV Scene Builder & Render Engine (Zack-Blender-Pack Architecture).

Usage (Blender 5.2.2 Linux headless):
  blender --background --python 03_pipeline/scripts/build_and_render.py -- \\
      --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json \\
      --mode storyboard --engine CYCLES [--scene 4] [--save-blend]

Key Upgrades (Zack-Blender-Pack + 3D Micro-POV):
- Real MPFB2 human rig loaded from `family_ready.blend` (`mpfb_human.py`): ENHANCED_SSS matte skin,
  Displace 0.006 kosan outfit, fix_teeth.py, calibrated Leg IK, world-space `reach()`, ARKit
  expressions (BOOST=1.6) + `jaw` bone rotation, and zero `$md-*` zeroing.
- Anti-floating Sandal Jepit: positioned & rotated directly from `wrist.R` world palm frame on
  every frame of Scenes 1-7 and released with gravity drop in Scene 8.
- Dense Indonesian kosan kitchen with 15 real Poly Haven CC0 GLTF props + PBR tile & plaster walls.
- High-contrast "Jam 2 Pagi" lighting + AgX Medium High Contrast + Macro DOF + `post.py` camera look.
- Supports `--engine CYCLES` (multi-GPU OptiX/CUDA + OIDN + CPU fallback) and `--engine EEVEE`
  (`eevee_switch.py` fast render) + 24fps auto-resume per frame + automated TROUBLESHOOTING.md QC.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline_utils import (
    apply_post_camera_look,
    check_ffmpeg_available,
    get_repo_root,
    load_and_validate_spec,
    load_json,
    log,
    resolve_assets_dir,
    resolve_episode_work_dir,
    resolve_family_ready_blend,
)
import mpfb_human as mh
import procedural_props as props


# =============================================================================
# RENDER ENGINE CONFIGURATION (CYCLES MULTI-GPU + OIDN / EEVEE SWITCH)
# =============================================================================

def configure_render_engine(
    scene: bpy.types.Scene,
    engine_choice: str,
    mode: str,
    fps: int,
) -> Dict[str, Any]:
    """Configure Cycles (OptiX/CUDA multi-GPU + OIDN) or EEVEE (`eevee_switch.py`) + AgX."""
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    engine_upper = engine_choice.upper()

    # Resolution & sample presets
    if mode == "storyboard":
        res_x, res_y = 360, 640
        cyc_samples, eevee_samples = 10, 16
        max_bounces = 3
    elif mode == "preview":
        res_x, res_y = 540, 960
        cyc_samples, eevee_samples = 16, 24
        max_bounces = 4
    else:
        res_x, res_y = 1080, 1920
        cyc_samples, eevee_samples = 24, 32
        max_bounces = 4

    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15

    # Motion blur for video renders; crisp stills in storyboard
    scene.render.use_motion_blur = mode != "storyboard"
    scene.render.motion_blur_shutter = 0.35

    # AgX Medium High Contrast with controlled exposure (no white highlight blowout)
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
        try:
            scene.view_settings.look = "Medium High Contrast"
        except Exception:
            pass
    scene.view_settings.exposure = -0.45

    # Detect NVIDIA GPU backend (enables ALL T4 GPUs on Kaggle 2xT4!)
    has_gpu = False
    device_used = "CPU"
    gpu_backend: Optional[str] = None
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for compute_type in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = compute_type
                prefs.refresh_devices()
                gpu_devices = [d for d in prefs.devices if d.type == compute_type]
                if gpu_devices:
                    for d in prefs.devices:
                        d.use = d.type == compute_type
                    has_gpu = True
                    gpu_backend = compute_type
                    names = ", ".join(d.name for d in gpu_devices)
                    device_used = f"GPU x{len(gpu_devices)} ({compute_type}: {names})"
                    break
            except Exception:
                continue
    except Exception:
        pass

    active_engine = engine_upper
    if engine_upper == "EEVEE":
        # Adopt skills/blender-render-farm/scripts/eevee_switch.py
        ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
        eevee_id = next((e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if e in ids), None)
        if eevee_id and has_gpu:
            scene.render.engine = eevee_id
            ee = scene.eevee
            for k, v in (
                ("taa_render_samples", eevee_samples),
                ("use_shadows", True),
                ("use_raytracing", True),
                ("ray_tracing_method", "SCREEN"),
                ("use_volumetric_shadows", True),
                ("volumetric_tile_size", "4"),
                ("shadow_ray_count", 2),
                ("shadow_step_count", 8),
            ):
                try:
                    setattr(ee, k, v)
                except Exception:
                    pass
            log(
                "BLENDER",
                f"EEVEE configured ({eevee_id}) | Mode: {mode} ({res_x}x{res_y}, {eevee_samples} samples, {fps}fps) | {device_used}",
            )
            return {"engine": eevee_id, "has_gpu": has_gpu, "backend": gpu_backend}
        else:
            log(
                "BLENDER",
                "EEVEE requested without GPU/EGL display — safely falling back to Cycles CPU + OIDN.",
            )
            active_engine = "CYCLES"

    # CYCLES configuration
    scene.render.engine = "CYCLES"
    if has_gpu:
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
        if mode != "storyboard":
            # Keep CPU test renders reasonable while preserving aspect ratio
            log("BLENDER", f"No GPU detected — rendering mode '{mode}' on Cycles CPU + OIDN.")

    scene.cycles.samples = cyc_samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.06 if mode != "storyboard" else 0.08
    scene.cycles.max_bounces = max_bounces
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 6
    scene.cycles.use_denoising = True
    # Always use OpenImageDenoise (Kaggle/Colab T4 driver fails with OptiX denoiser!)
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(scene.cycles, "denoising_input_passes"):
        scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    try:
        scene.cycles.denoising_use_gpu = has_gpu
    except Exception:
        pass

    log(
        "BLENDER",
        f"Cycles configured | Mode: {mode} ({res_x}x{res_y}, {cyc_samples} samples, {fps}fps) | "
        f"Device: {device_used} | OIDN: ON | AgX: ON",
    )
    return {"engine": "CYCLES", "has_gpu": has_gpu, "backend": gpu_backend}


# =============================================================================
# WORLD HDRI & LIGHTING RIG ("JAM 2 PAGI" CINEMATIC BACKLIT SHADOWS)
# =============================================================================

def setup_world_and_lights(scene: bpy.types.Scene, assets_dir: Path) -> Dict[str, Any]:
    """Configure dim night-blue ambient (0.05-0.10) + overhead neon + dramatic boss backlight."""
    world = bpy.data.worlds.new("MicroPOV_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    hdri_path = assets_dir / "hdri" / "small_empty_room_3_1k.hdr"
    if hdri_path.exists():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri_path), check_existing=True)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 0.88
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = (0.14, 0.25, 0.52, 1.0)
        nt.links.new(env.outputs["Color"], sock_a)
        nt.links.new(sock_out, bg.inputs["Color"])
        log("BLENDER", f"Loaded cached Poly Haven HDRI (2 AM night-blue tint): {hdri_path.name}")
    else:
        bg.inputs["Color"].default_value = (0.02, 0.04, 0.12, 1.0)

    bg.inputs["Strength"].default_value = 0.06

    def _add_area_light(name: str, loc, rot, size, size_y, energy, color):
        ld = bpy.data.lights.new(name=name, type="AREA")
        ld.shape = "RECTANGLE"
        ld.size = size
        ld.size_y = size_y
        ld.energy = energy
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = rot
        scene.collection.objects.link(lo)
        return lo, ld

    # 1. Dim blue 2 AM moonlight/fridge glow (Scene 1 pre-switch 0-1.0s)
    _, night_data = _add_area_light(
        "Light_Night_Blue",
        (0.95, 0.75, 1.35),
        (math.radians(52), math.radians(38), 0.0),
        0.7,
        1.1,
        9.0,
        (0.14, 0.36, 1.0),
    )

    # 2. Overhead TL Fluorescent Neon behind-above human (y=2.25) so front of human face falls
    #    in deep dramatic shadow ("bayangan paling gelap di dapur ini ada tepat di mukanya"!)
    neon_obj, neon_data = _add_area_light(
        "Light_Neon_Main",
        (0.0, 2.25, 2.56),
        (math.radians(8), 0.0, 0.0),
        0.16,
        1.05,
        0.0,
        (0.92, 0.96, 1.0),
    )

    # 3. Dramatic Boss Backlight behind human head (crisp silhouette rim light)
    rim_obj, rim_data = _add_area_light(
        "Light_Boss_Backlight",
        (0.0, 2.95, 2.15),
        (math.radians(-46), 0.0, 0.0),
        0.80,
        0.80,
        0.0,
        (0.84, 0.93, 1.0),
    )

    # 4. Controlled foreground floor pool (keeps Indomie spill, tile floor & sandal vivid
    #    while keeping human face moody & shadowed!)
    fg_obj, fg_data = _add_area_light(
        "Light_Foreground_Pool",
        (0.25, 0.35, 1.65),
        (math.radians(-6), math.radians(8), 0.0),
        0.55,
        0.55,
        0.0,
        (0.96, 0.94, 0.88),
    )

    # 5. Subtle warm bounce fill from tile floor onto human face in Scene 8 ONLY
    #    (just enough to read wide eyes + shock mouth in shadow without ruining dark silhouette!)
    face_fill_obj, face_fill_data = _add_area_light(
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
    }


# =============================================================================
# DENSE KOSAN KITCHEN SET — 15 REAL POLY HAVEN CC0 PROPS (ZERO FLOATING!)
# =============================================================================

def _snap_group_bottom_to_z(objs: List[bpy.types.Object], anchor: bpy.types.Object, target_z: float) -> None:
    """Adjust anchor.location.z so the lowest world vertex of imported meshes sits flush on target_z."""
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


def import_gltf_prop(
    gltf_path: Path,
    name: str,
    location: Tuple[float, float, float],
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
    snap_to_z: Optional[float] = None,
) -> Optional[bpy.types.Object]:
    """Import a cached Poly Haven CC0 .gltf/.glb under an anchor Empty with flush surface snapping."""
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


def populate_dense_kosan_kitchen(assets_dir: Path) -> int:
    """Fill the Indonesian kosan kitchen with 15 real Poly Haven CC0 props (kitchen_set.py style).

    All props stay strictly outside the cockroach's central sprint corridor (x in [-0.36, 0.36])
    so the camera never collides with furniture while every camera angle looks dense & real!
    """
    models_dir = assets_dir / "models_3d"

    def _gltf(asset_id: str) -> Path:
        p = models_dir / asset_id / f"{asset_id}_1k.gltf"
        if p.exists():
            return p
        p2 = models_dir / asset_id / f"{asset_id}.gltf"
        return p2

    counter_top_z = 0.828
    shelf_top_z = 1.495

    placements = [
        # (asset_id, name, loc, rot_deg, scale, snap_z)
        # 1. Cardboard box blocking right side near fridge (Scene 6: "kanan buntu/kardus"!)
        ("cardboard_box_01", "Kardus_DeadEnd_Right", (0.56, 2.48, 0.0), (0.0, 0.0, -18.0), 1.05, 0.0),
        # 2. Wooden kitchen cabinet along right-back wall
        ("modern_wooden_cabinet", "Kitchen_Cabinet_Right", (1.28, 2.08, 0.0), (0.0, 0.0, -90.0), 0.92, 0.0),
        # 3. Left wall shelf
        ("Shelf_01", "Kitchen_Shelf_Left", (-0.68, 1.15, 0.0), (0.0, 0.0, 90.0), 0.85, 0.0),
        # 4. Kosan wooden chair on left foreground-mid
        ("WoodenChair_01", "Kitchen_Chair_Left", (-0.64, 0.26, 0.0), (0.0, 0.0, 58.0), 0.92, 0.0),
        # 5. Wicker basket near right cabinet/kardus
        ("wicker_basket_02", "Kitchen_Basket_Right", (0.64, 1.98, 0.0), (0.0, 0.0, 22.0), 0.95, 0.0),
        # 6. Electric stove on kosan counter
        ("electric_stove", "Kitchen_Stove", (1.30, 0.65, counter_top_z), (0.0, 0.0, -90.0), 0.88, counter_top_z),
        # 7. Enamel cooking pot on counter/stove area
        ("pot_enamel_01", "Kitchen_Pot_Enamel", (1.26, 0.42, counter_top_z), (0.0, 0.0, 30.0), 0.95, counter_top_z),
        # 8. Frying pan on counter
        ("brass_pan_01", "Kitchen_Pan", (1.30, 1.02, counter_top_z), (0.0, 0.0, -145.0), 0.95, counter_top_z),
        # 9. Wooden cutting board on counter
        ("wooden_cutting_board", "Kitchen_CuttingBoard", (1.26, 0.12, counter_top_z), (0.0, 0.0, 12.0), 0.95, counter_top_z),
        # 10. Metal kettle/jug on counter
        ("metal_jug", "Kitchen_MetalJug", (1.28, -0.14, counter_top_z), (0.0, 0.0, -40.0), 0.95, counter_top_z),
        # 11. Wooden bowl on floor right of Indomie spill
        ("wooden_bowl_01", "Kitchen_Bowl_Floor", (0.58, 0.72, 0.0), (0.0, 0.0, 25.0), 0.95, 0.0),
        # 12. Second bowl on upper floating shelf
        ("wooden_bowl_02", "Kitchen_Bowl_Shelf", (1.48, 0.28, shelf_top_z), (0.0, 0.0, 15.0), 0.95, shelf_top_z),
        # 13. Jug/bottle on upper wall shelf
        ("jug_01", "Kitchen_Jug_Shelf", (1.48, 0.68, shelf_top_z), (0.0, 0.0, -30.0), 0.95, shelf_top_z),
        # 14. Tea set on upper wall shelf
        ("tea_set_01", "Kitchen_TeaSet_Shelf", (1.46, 1.06, shelf_top_z), (0.0, 0.0, -85.0), 0.90, shelf_top_z),
        # 15. Wall clock on back wall above fridge/right side (facing -Y into kitchen!)
        ("wall_clock", "Kitchen_WallClock", (0.64, 3.51, 1.94), (0.0, 0.0, 0.0), 1.05, None),
    ]

    placed = 0
    for asset_id, name, loc, rot_deg, scale, snap_z in placements:
        obj = import_gltf_prop(_gltf(asset_id), name, loc, rot_deg, scale=scale, snap_to_z=snap_z)
        if obj is not None:
            placed += 1
        elif asset_id == "cardboard_box_01":
            box_mat = props.make_material("Mat_Cardboard_Fallback", (0.48, 0.35, 0.20, 1.0), roughness=0.88)
            props._make_beveled_box(name, (0.44, 0.40, 0.36), 0.006, box_mat, location=(loc[0], loc[1], 0.18))
            placed += 1

    log("BLENDER", f"Populated dense kosan kitchen with {placed}/{len(placements)} Poly Haven CC0 props.")
    return placed


# =============================================================================
# KEYFRAME & CAMERA HELPERS
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


def _set_antennae_pose(
    ant_rig: Dict[str, bpy.types.Object],
    frame: int,
    pitch_deg: float,
    spread_deg: float,
    jitter: float = 0.0,
) -> None:
    j1 = jitter * math.sin(frame * 1.9)
    j2 = jitter * math.cos(frame * 2.3)
    _kf_loc_rot(ant_rig["ant_l"], frame, rot_deg=(pitch_deg + j1, 0.0, spread_deg + j2))
    _kf_loc_rot(ant_rig["ant_r"], frame, rot_deg=(pitch_deg - j2, 0.0, -spread_deg - j1))


# =============================================================================
# FULL EP001 8-SCENE PER-FRAME CHOREOGRAPHY (REAL MPFB2 + MICRO-POV)
# =============================================================================

def pick_storyboard_frame(scene_meta: Dict[str, Any], fps: int) -> int:
    """Pick the most informative hero beat frame for each scene in storyboard mode."""
    sid = int(scene_meta["scene_id"])
    f0 = int(scene_meta["start_frame"])
    f1 = int(scene_meta["end_frame"])
    span = max(1, f1 - f0)
    # Tailored hero beat per scene so storyboard_grid.png showcases 8 distinct cinematic shots!
    frac_map = {
        1: 0.55,  # Post neon flash: glossy Indomie spill + towering human + raised sandal
        2: 0.65,  # Boss Terakhir: low-angle backlit silhouette + broad green Swallow sandal
        3: 0.55,  # Cheat Code Aktif: bullet-time descending sandal + subtle cyan wind ribbons
        4: 0.42,  # 300 KM/JAM: post-slam hyper-sprint down tile floor toward fridge
        5: 0.72,  # Tinggal Sejengkal: fridge 5.5cm gap dead ahead + giant foot descending!
        6: 0.88,  # Terkepung: dramatic whip-pan UP at towering giant + sandal about to drop!
        7: 0.72,  # Mode Terbang: amber veined wings at bottom corners + ascent toward dark face
        8: 0.72,  # Maaf Ya Bang: panicked dark-shadowed MPFB2 face close-up + falling sandal
    }
    frac = frac_map.get(sid, 0.50)
    return max(f0, min(f1, f0 + int(round(frac * span))))


def build_ep001_animation(
    scene: bpy.types.Scene,
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    assets_dir: Path,
    human: Dict[str, Any],
    bake_frames: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Assemble kosan kitchen, props, POV camera & bake all 8 EP001 scenes to Audio-First timing."""
    fps = int(manifest.get("fps", 24))
    pov_cfg = spec["pov_config"]
    cam_h = float(pov_cfg.get("camera_height_m", 0.015))
    base_fov = float(pov_cfg.get("base_fov_deg", 95.0))
    total_frames = int(manifest["total_frames"])

    # Use CONSTANT interpolation when baking per-frame (exact Zack kitchen_shots.py rule)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT" if bake_frames is None else "LINEAR"

    # 1. Build kitchen room, lighting & 15 Poly Haven CC0 props
    env = props.build_kitchen_tile_floor(assets_dir)
    lights = setup_world_and_lights(scene, assets_dir)
    populate_dense_kosan_kitchen(assets_dir)

    # 2. Build stylized Indonesian props
    props.build_indomie_bowl_spill((0.0, 0.22, 0.0))
    props.build_fridge_under_gap((-0.14, 2.95, 0.0))
    sandal = props.build_sandal_jepit_swallow((0.0, 0.0, 0.0))
    wind = props.build_wind_lines((0.0, 0.65, 0.18))
    dust = props.build_dust_puff((0.0, 0.45, 0.01))

    # 3. Setup Micro-POV Camera (1.5cm height, Macro DOF, Antennae + Translucent Veined Wings)
    cam_data = bpy.data.cameras.new("MicroPOV_Camera")
    cam_data.clip_start = 0.005  # Essential for 1.5cm macro cockroach POV!
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

    # Map scene_id -> timing metadata
    tmap: Dict[int, Dict[str, Any]] = {int(s["scene_id"]): s for s in manifest["scenes"]}

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
    log("BAKE", f"Baking {len(frames_to_bake)} frames (MPFB2 rig + wrist-anchored sandal + Macro DOF)...")
    t_bake = _time.monotonic()

    # Keep track of Scene 8 sandal drop start state
    drop_anchor_pos: Optional[Vector] = None
    drop_anchor_quat: Optional[Quaternion] = None
    sandal_grip_distances: Dict[int, float] = {}

    for idx_f, fr in enumerate(frames_to_bake):
        scene.frame_set(fr)
        t_global = (fr - 1) / float(fps)
        sid, s_meta, u, local_sec = _scene_for_frame(fr)
        arm = human["arm"]
        mh.reset_pose(human)

        # Default VFX visibility per frame
        show_wind = False
        show_dust = False
        show_speed = False
        show_wings = False
        show_black = False

        # Default lighting ("Jam 2 Pagi" backlit neon strictly behind human plane)
        e_night = 0.8
        e_neon = 115.0
        neon_y = 2.15
        e_rim = 210.0
        e_fg = 10.0
        e_face_fill = 0.0
        e_cyan = 0.0
        e_neon_emit = 14.0
        w_strength = 0.07

        # Default human state
        h_loc = (0.02, 1.38, 0.0)
        h_yaw = 0.0
        h_hip_drop = 0.0
        l_foot_ov = None
        expr1, expr2, expr_k, jaw_ex = "glare", None, 0.0, 0.0
        grip_sandal = True
        right_hand_target = Vector((-0.24, 1.15, 1.25))
        left_hand_target: Optional[Vector] = None
        torso_lean = 6.0
        head_yaw, head_pitch = 0.0, 14.0
        sandal_extra_pitch = 0.0
        sandal_extra_roll = 0.0

        # Default camera
        cam_loc = (0.0, 0.0, cam_h)
        cam_rot = (90.0, 0.0, 0.0)
        cam_fov = base_fov
        dof_dist = 1.0
        dof_fstop = 3.2

        # Default antennae & wings
        ant_pitch, ant_spread, ant_jit = 16.0, 8.0, 4.0
        wing_flap = 0.0

        # =====================================================================
        # SCENE 1: JAM 2 PAGI — Dark blue -> neon flash @1.05s -> startled tilt
        # =====================================================================
        if sid == 1:
            t_flash = 1.05
            if local_sec < t_flash:
                e_night = 9.5
                e_neon = 0.0
                e_rim = 0.0
                e_fg = 0.0
                e_neon_emit = 0.04
                w_strength = 0.05
                cam_loc = (0.0, -0.02 + 0.02 * (local_sec / t_flash), cam_h)
                cam_rot = (82.0, 0.0, 0.0)
                cam_fov = base_fov
                dof_dist = 0.22
                dof_fstop = 2.8
                ant_pitch, ant_spread, ant_jit = -8.0, 6.0, 3.5
                right_hand_target = Vector((-0.24, 1.18, 1.02))
                torso_lean = 4.0
                head_pitch = 16.0
            else:
                dt = local_sec - t_flash
                flash_boost = max(0.0, 1.0 - dt / 0.35)
                e_night = 0.8
                e_neon = 118.0 + 70.0 * flash_boost
                e_rim = 220.0
                e_fg = 12.0
                e_neon_emit = 15.0 + 6.0 * flash_boost
                w_strength = 0.07
                jolt = _smooth(min(1.0, dt / 0.22))
                cam_loc = (0.0, -0.01, cam_h + 0.006 * jolt)
                cam_rot = (_lerp(83.0, 102.0, jolt), 2.5 * math.sin(jolt * math.pi), -1.5 * math.sin(jolt * math.pi))
                cam_fov = base_fov
                dof_dist = _lerp(0.24, 1.15, jolt)
                dof_fstop = 3.2
                ant_pitch, ant_spread, ant_jit = 24.0, -6.0, 1.5
                lift_u = _smooth(min(1.0, dt / max(0.5, s_meta["scene_duration_sec"] - t_flash)))
                right_hand_target = Vector((-0.26, _lerp(1.16, 1.08, lift_u), _lerp(1.06, 1.62, lift_u)))
                torso_lean = _lerp(5.0, 10.0, lift_u)
                head_pitch = 20.0
                expr1, expr2, expr_k = "neutral", "glare", lift_u

        # =====================================================================
        # SCENE 2: BOSS TERAKHIR — Low-angle silhouette + raised Swallow sandal
        # =====================================================================
        elif sid == 2:
            e_neon = 110.0
            e_rim = 280.0
            e_fg = 8.0
            w_strength = 0.06
            h_loc = (0.02, 1.38, 0.0)
            torso_lean = 12.0
            head_pitch = 22.0
            expr1 = "glare"
            # Right arm lifts Swallow flip-flop high overhead with broad sole turned toward camera!
            right_hand_target = Vector((-0.30, 1.12, _lerp(1.66, 1.88, _smooth(u))))
            sandal_extra_pitch = 20.0
            sandal_extra_roll = 68.0

            # Staggered dramatic push-in (low angle!)
            step_u = _smooth(min(1.0, u * 1.15))
            cam_loc = (_lerp(0.0, -0.02, step_u), _lerp(0.10, 0.18, step_u), cam_h)
            cam_rot = (_lerp(122.0, 136.0, step_u), 2.2 * math.sin(u * math.pi * 2.0), _lerp(5.0, 10.0, step_u))
            cam_fov = _lerp(88.0, 56.0, step_u)
            dof_dist = 1.48
            dof_fstop = 3.2
            ant_pitch, ant_spread, ant_jit = 22.0, -4.0, 5.0

        # =====================================================================
        # SCENE 3: CHEAT CODE AKTIF — Bullet-time slow-mo + subtle cyan wind
        # =====================================================================
        elif sid == 3:
            e_neon = 100.0
            e_rim = 165.0
            e_fg = 8.0
            e_cyan = _lerp(12.0, 32.0, _smooth(u))
            w_strength = 0.06
            show_wind = True

            h_loc = (0.02, 1.32, 0.0)
            h_hip_drop = _lerp(0.02, 0.10, _smooth(u))
            torso_lean = _lerp(14.0, 26.0, _smooth(u))
            head_pitch = 24.0
            expr1 = "angry"
            # Slow-motion downward swing of right arm WITH sandal locked in wrist.R!
            su = _smooth(u)
            right_hand_target = Vector((
                _lerp(-0.28, -0.08, su),
                _lerp(1.08, 0.66, su),
                _lerp(1.76, 0.62, su),
            ))
            sandal_extra_pitch = _lerp(20.0, 55.0, su)

            cam_loc = (_lerp(0.0, 0.03, u), _lerp(0.18, 0.22, u), cam_h)
            cam_rot = (_lerp(120.0, 114.0, u), _lerp(9.0, 13.0, u), _lerp(5.0, 2.0, u))
            cam_fov = _lerp(82.0, 94.0, u)
            dof_dist = _lerp(0.95, 0.58, u)
            dof_fstop = 2.8
            ant_pitch, ant_spread, ant_jit = 14.0, 10.0, 8.0

            _kf_loc_rot(
                wind["root"],
                fr,
                loc=(_lerp(-0.08, -0.02, u), _lerp(0.76, 0.38, u), _lerp(0.58, 0.16, u)),
                rot_deg=(_lerp(22.0, 12.0, u), 0.0, _lerp(6.0, 2.0, u)),
                scale=(_lerp(0.65, 1.05, u), _lerp(0.65, 1.18, u), _lerp(0.65, 1.05, u)),
            )

        # =====================================================================
        # SCENE 4: 300 KM/JAM — Sandal slams floor (still gripped!) + hyper-sprint
        # =====================================================================
        elif sid == 4:
            e_neon = 122.0
            e_rim = 145.0
            e_fg = 14.0
            w_strength = 0.08
            t_slam = 0.42

            if local_sec <= t_slam:
                su = _smooth(local_sec / max(0.05, t_slam))
                h_loc = (0.02, 1.08, 0.0)
                h_hip_drop = _lerp(0.12, 0.28, su)
                torso_lean = _lerp(28.0, 42.0, su)
                right_hand_target = Vector((_lerp(-0.06, -0.02, su), _lerp(0.62, 0.42, su), _lerp(0.52, 0.12, su)))
                sandal_extra_pitch = 72.0
                cam_loc = (-0.02, _lerp(0.24, 0.46, su), cam_h)
                cam_rot = (92.0, 1.5 * math.sin(fr * 1.5), 0.0)
                cam_fov = 98.0
                dof_dist = 0.75
            else:
                dt = local_sec - t_slam
                sprint_u = min(1.0, dt / max(0.2, s_meta["scene_duration_sec"] - t_slam))
                # Dust burst right after slam
                if dt < 0.75:
                    show_dust = True
                    du = min(1.0, dt / 0.50)
                    _kf_loc_rot(
                        dust["root"],
                        fr,
                        loc=(0.0, 0.38, 0.015 + 0.01 * du),
                        scale=(_lerp(0.3, 2.1, du), _lerp(0.3, 2.1, du), _lerp(0.3, 1.3, du)),
                    )
                show_speed = True
                # Human recovers & starts turning to chase cockroach toward fridge
                rec_u = _smooth(min(1.0, sprint_u * 1.3))
                h_loc = (_lerp(0.02, 0.14, rec_u), _lerp(1.08, 1.85, rec_u), 0.0)
                h_yaw = _lerp(0.0, 155.0, rec_u)
                h_hip_drop = _lerp(0.26, 0.02, rec_u)
                torso_lean = _lerp(36.0, 10.0, rec_u)
                fwd_h, left_h = Vector((math.sin(math.radians(h_yaw)), -math.cos(math.radians(h_yaw)), 0.0)), Vector((math.cos(math.radians(h_yaw)), math.sin(math.radians(h_yaw)), 0.0))
                right_hand_target = Vector(h_loc) + fwd_h * 0.32 - left_h * 0.24 + Vector((0.0, 0.0, _lerp(0.25, 1.25, rec_u)))

                cx = -0.18 * math.sin(min(1.0, sprint_u * 1.4) * math.pi * 0.5) + 0.010 * math.sin(fr * 1.6)
                cy = _lerp(0.48, 1.86, sprint_u)
                cz = cam_h + 0.0028 * abs(math.sin(fr * 1.8))
                cam_loc = (cx, cy, cz)
                cam_rot = (91.5 + 1.2 * math.sin(fr * 2.1), 2.4 * math.sin(fr * 1.5), 1.8 * math.cos(fr * 1.3))
                cam_fov = _lerp(100.0, 112.0, min(1.0, sprint_u * 3.0))
                dof_dist = 0.90
            dof_fstop = 4.0
            expr1 = "angry"
            ant_pitch, ant_spread, ant_jit = -14.0, 20.0, 10.5

        # =====================================================================
        # SCENE 5: TINGGAL SEJENGKAL — Sprint to fridge gap -> GIANT FOOT STOMPS!
        # =====================================================================
        elif sid == 5:
            e_neon = 112.0
            e_rim = 145.0
            e_fg = 10.0
            w_strength = 0.07
            dur5 = float(s_meta["scene_duration_sec"])
            t_stomp_start = max(1.0, dur5 - 1.05)
            t_stomp_land = max(1.4, dur5 - 0.42)

            show_speed = local_sec < t_stomp_land
            h_loc = (0.14, 2.46, 0.0)
            h_yaw = 22.0
            torso_lean = 14.0
            expr1 = "angry"
            right_hand_target = Vector((-0.18, 2.18, 1.52))

            # Left leg IK lifts high & stomps straight down in front of fridge under-gap!
            if local_sec < t_stomp_start:
                l_foot_ov = (0.04, 2.60, 0.42, -16.0)
            elif local_sec < t_stomp_land:
                st_u = _smooth((local_sec - t_stomp_start) / max(0.05, t_stomp_land - t_stomp_start))
                l_foot_ov = (_lerp(0.04, -0.09, st_u), _lerp(2.60, 2.42, st_u), _lerp(0.42, 0.0, st_u), _lerp(-16.0, 0.0, st_u))
            else:
                l_foot_ov = (-0.09, 2.42, 0.0, 0.0)
                e_neon = 94.0  # Shadow falls across floor

            cy = _lerp(1.86, 2.16, min(1.0, u * 1.05))
            cx = -0.12 + 0.007 * math.sin(fr * 1.7)
            cz = cam_h + 0.0022 * abs(math.sin(fr * 2.0))
            pitch_up = 89.0 + (7.0 * _smooth((local_sec - t_stomp_start) / max(0.1, dur5 - t_stomp_start)))
            roll_s = 1.6 * math.sin(fr * 1.6) if local_sec < t_stomp_land else 0.4
            cam_loc = (cx, cy, cz)
            cam_rot = (pitch_up, roll_s, 0.0)
            cam_fov = _lerp(106.0, 96.0, u)
            dof_dist = _lerp(0.90, 0.48, u)
            dof_fstop = 3.6
            ant_pitch = -8.0 if local_sec < t_stomp_land else 22.0
            ant_spread, ant_jit = 14.0, 8.5

        # =====================================================================
        # SCENE 6: TERKEPUNG! — Hard brake + Whip-pan Left, Right, Up (sandal!)
        # =====================================================================
        elif sid == 6:
            e_neon = 118.0
            neon_y = 2.75
            e_rim = 180.0
            e_fg = 8.0
            w_strength = 0.07
            h_loc = (0.14, 2.46, 0.0)
            h_yaw = 20.0
            l_foot_ov = (-0.09, 2.42, 0.0, 0.0)
            torso_lean = 16.0
            head_pitch = 22.0
            expr1 = "angry"
            # Right arm holds sandal overhead ready to smash down!
            right_hand_target = Vector((-0.16, 2.14, _lerp(1.68, 1.38, _smooth(max(0.0, (u - 0.65) / 0.35)))))
            sandal_extra_pitch = 35.0
            sandal_extra_roll = 45.0

            # Multi-beat whip-pan camera choreography
            if u < 0.18:
                bu = _smooth(u / 0.18)
                cam_loc = (-0.12, _lerp(2.16, 2.06, bu), cam_h + 0.003 * bu)
                cam_rot = (_lerp(95.0, 100.0, bu), -3.0 * bu, 0.0)
                dof_dist = 0.44
                cam_fov = 100.0
            elif u < 0.44:
                lu = _smooth(min(1.0, (u - 0.18) / 0.14))
                cam_loc = (-0.12, 2.06, cam_h)
                cam_rot = (93.0, 4.0 * lu, _lerp(0.0, 78.0, lu))
                dof_dist = 0.72
                cam_fov = 98.0
            elif u < 0.70:
                ru = _smooth(min(1.0, (u - 0.44) / 0.14))
                cam_loc = (-0.12, 2.06, cam_h)
                cam_rot = (93.0, -4.0 * ru, _lerp(78.0, -72.0, ru))
                dof_dist = 0.72
                cam_fov = 98.0
            else:
                uu = _smooth(min(1.0, (u - 0.70) / 0.16))
                cam_loc = (-0.12, 2.06, cam_h)
                cam_rot = (_lerp(93.0, 152.0, uu), 3.0 * math.sin(uu * math.pi), _lerp(-72.0, -8.0, uu))
                dof_dist = 1.05
                cam_fov = _lerp(98.0, 104.0, uu)
            dof_fstop = 3.6
            ant_pitch, ant_spread, ant_jit = 26.0, 18.0, 13.0

        # =====================================================================
        # SCENE 7: MODE TERBANG — Translucent veined amber wings + wobbly takeoff
        # =====================================================================
        elif sid == 7:
            # Neon strictly BEHIND human (y=2.88 > 2.48) so his face falls in dramatic shadow!
            e_neon = 115.0
            neon_y = 2.88
            e_rim = 145.0
            e_fg = 0.0
            e_face_fill = 0.4
            w_strength = 0.06
            t_wings = 1.35

            h_loc = (0.02, 2.48, 0.0)
            h_yaw = 0.0
            torso_lean = 8.0
            head_pitch = _lerp(18.0, 2.0, _smooth(u))
            expr1, expr2, expr_k = "angry", "shock", _smooth(max(0.0, (u - 0.40) / 0.60))
            right_hand_target = Vector((-0.26, 2.18, _lerp(1.48, 1.32, _smooth(u))))

            if local_sec < t_wings:
                u0 = _smooth(local_sec / max(0.1, t_wings))
                cam_loc = (_lerp(-0.12, -0.05, u0), _lerp(2.04, 1.72, u0), cam_h + 0.015 * u0)
                cam_rot = (_lerp(132.0, 114.0, u0), 3.5 * math.sin(fr * 1.4), 0.0)
                cam_fov = _lerp(98.0, 104.0, u0)
                dof_dist = 1.05
            else:
                show_wings = True
                uf = (local_sec - t_wings) / max(0.1, float(s_meta["scene_duration_sec"]) - t_wings)
                cx = -0.05 + 0.22 * math.sin(uf * math.pi * 2.5)
                cy = _lerp(1.72, 1.28, uf)
                cz = _lerp(0.04, 1.46, uf ** 1.12)
                cam_loc = (cx, cy, cz)
                cam_rot = (
                    _lerp(114.0, 95.0, uf) + 4.5 * math.sin(fr * 0.7),
                    13.0 * math.sin(uf * math.pi * 3.0) + 2.5 * math.cos(fr * 1.8),
                    -10.0 * math.cos(uf * math.pi * 2.5),
                )
                cam_fov = _lerp(105.0, 100.0, uf)
                dof_dist = 1.15
                wing_flap = 18.0 * math.sin(fr * 2.8)
            dof_fstop = 3.2
            ant_pitch, ant_spread, ant_jit = 12.0, 22.0, 11.5

        # =====================================================================
        # SCENE 8: MAAF YA BANG — Dive into dark shadowed face -> panic drop -> BLACK
        # =====================================================================
        elif sid == 8:
            # Neon strictly BEHIND human (y=2.92) + subtle 0.7W bounce = dramatic dark shadowed face!
            e_neon = 110.0
            neon_y = 2.92
            e_rim = 115.0
            e_fg = 0.0
            e_face_fill = 0.75
            w_strength = 0.05

            dur8 = float(s_meta["scene_duration_sec"])
            t_black = float(s_meta.get("cut_to_black_sec", dur8 - 0.12))
            t_drop = t_black * 0.45

            show_wings = True
            show_speed = True
            show_black = local_sec >= t_black

            h_loc = (0.0, 2.48, 0.0)
            h_yaw = 0.0
            recoil_u = _smooth(max(0.0, (local_sec - t_drop) / max(0.25, t_black - t_drop)))
            torso_lean = _lerp(4.0, -14.0, recoil_u)
            head_pitch = _lerp(2.0, -10.0, recoil_u)
            expr1, expr2, expr_k = "shock", "panic", recoil_u
            jaw_ex = 0.25 * recoil_u

            if local_sec < t_drop:
                grip_sandal = True
                right_hand_target = Vector((-0.26, 2.18, 1.38))
                left_hand_target = Vector((0.26, 2.22, 1.15))
            else:
                # Throws both arms out in pure terror & releases the Swallow sandal!
                grip_sandal = False
                right_hand_target = Vector((-0.44, 2.22, _lerp(1.38, 1.62, recoil_u)))
                left_hand_target = Vector((0.44, 2.22, _lerp(1.15, 1.56, recoil_u)))

            dive_u = min(1.0, local_sec / max(0.1, t_black))
            ease = dive_u ** 1.38
            cx = _lerp(0.04, 0.0, ease) + 0.012 * (1.0 - dive_u) * math.sin(fr * 1.9)
            cy = _lerp(1.28, 2.04, ease)
            cz = _lerp(1.46, 1.55, ease) + 0.008 * (1.0 - dive_u) * math.cos(fr * 2.1)
            cam_loc = (cx, cy, cz)
            cam_rot = (_lerp(94.0, 91.0, ease), 4.0 * math.sin(fr * 2.2) * (1.0 - 0.5 * dive_u), 0.0)
            cam_fov = _lerp(92.0, 74.0, ease)
            dof_fstop = 2.8
            ant_pitch, ant_spread, ant_jit = -10.0, 24.0, 14.0
            wing_flap = 22.0 * math.sin(fr * 3.1)

        # ---- APPLY MPFB2 HUMAN POSE (NEVER A-POSE!) ----
        mh.place_and_feet(human, h_loc, h_yaw, fr, hip_drop=h_hip_drop, left_foot_override=l_foot_ov)
        mh.lean(arm, torso_lean)
        mh.head_turn(arm, head_yaw, head_pitch)
        mh.D.pose_arms(arm, yaw_deg=h_yaw, elbow=16.0)
        mh.D.relaxed_hands(arm)
        mh.set_hand_curl(arm, "R", mh.GRIP_CURLS if grip_sandal else mh.OPEN_CURLS, wrist_pitch=-10.0, twist=30.0)
        if not grip_sandal:
            mh.set_hand_curl(arm, "L", mh.OPEN_CURLS, wrist_pitch=-6.0, twist=20.0)

        fwd_v, left_v = mh.body_frame(arm)
        r_pole = -fwd_v * 0.35 - left_v * 0.85 + Vector((0.0, 0.0, -0.55))
        mh.reach(arm, "R", right_hand_target, r_pole)
        if left_hand_target is not None:
            l_pole = -fwd_v * 0.35 + left_v * 0.85 + Vector((0.0, 0.0, -0.55))
            mh.reach(arm, "L", left_hand_target, l_pole)

        mh.key_pose(human, fr)
        mh.set_face(human, t_global, fps, expr1, expr2, expr_k, jaw_extra=jaw_ex, frame=fr)

        # ---- SANDAL JEPIT: ANCHORED DIRECTLY FROM wrist.R EVERY FRAME IN SCENES 1-7! ----
        if grip_sandal:
            pos_s = mh.snap_sandal_to_right_hand(
                human,
                sandal["root"],
                fr,
                extra_pitch_deg=sandal_extra_pitch,
                extra_roll_deg=sandal_extra_roll,
            )
            w_now = mh.wp(arm, arm.pose.bones["wrist.R"].head)
            sandal_grip_distances[sid] = max(sandal_grip_distances.get(sid, 0.0), (pos_s - w_now).length)
            if sid == 8:
                drop_anchor_pos = sandal["root"].location.copy()
                drop_anchor_quat = sandal["root"].rotation_quaternion.copy()
        else:
            # Scene 8 post-drop gravity tumble
            dt_drop = max(0.0, local_sec - (float(s_meta.get("cut_to_black_sec", 4.5)) * 0.45))
            if drop_anchor_pos is None:
                # Fallback if storyboard jumps straight to Scene 8 post-drop frame!
                w_now = mh.wp(arm, arm.pose.bones["wrist.R"].head)
                drop_anchor_pos = w_now + Vector((0.05, -0.08, -0.10))
                drop_anchor_quat = Euler((math.radians(125.0), math.radians(25.0), math.radians(-18.0))).to_quaternion()
            fall_pos = Vector((
                drop_anchor_pos.x - 0.14 * dt_drop,
                drop_anchor_pos.y - 0.10 * dt_drop,
                max(0.02, drop_anchor_pos.z - 0.5 * 5.2 * (dt_drop ** 2)),
            ))
            spin_q = Euler((dt_drop * 4.2, dt_drop * 2.8, dt_drop * 1.9)).to_quaternion()
            sandal["root"].rotation_mode = "QUATERNION"
            sandal["root"].location = fall_pos
            sandal["root"].rotation_quaternion = spin_q @ drop_anchor_quat
            sandal["root"].keyframe_insert("location", frame=fr)
            sandal["root"].keyframe_insert("rotation_quaternion", frame=fr)

        # In Scene 8, dynamically focus Macro DOF directly onto the human's terrified eyes!
        if sid == 8:
            face_pt = mh.eye_mid(human)
            dof_dist = max(0.15, (face_pt - Vector(cam_loc)).length)

        # ---- CAMERA, MACRO DOF, ANTENNAE, WINGS, VFX, LIGHTS ----
        _kf_loc_rot(cam_obj, fr, loc=cam_loc, rot_deg=cam_rot)
        _kf_fov(cam_data, fr, cam_fov)
        _kf_dof(cam_data, fr, dof_dist, fstop=dof_fstop)

        _set_antennae_pose(ant_rig, fr, ant_pitch, ant_spread, jitter=ant_jit)
        if show_wings:
            _kf_loc_rot(ant_rig["wing_l_pivot"], fr, rot_deg=(-8.0, wing_flap, 10.0))
            _kf_loc_rot(ant_rig["wing_r_pivot"], fr, rot_deg=(-8.0, -wing_flap, -10.0))

        _kf_hide(wind["root"], fr, not show_wind)
        _kf_hide(dust["root"], fr, not show_dust)
        _kf_hide(speed_rig["root"], fr, not show_speed)
        _kf_hide(ant_rig["wing_l"], fr, not show_wings)
        _kf_hide(ant_rig["wing_r"], fr, not show_wings)
        _kf_hide(black_shutter, fr, not show_black)

        _kf_loc_rot(lights["neon_obj"], fr, loc=(0.0, neon_y, 2.56))
        _kf_light(lights["night_light"], fr, e_night)
        _kf_light(lights["neon_light"], fr, e_neon)
        _kf_light(lights["rim_light"], fr, e_rim)
        _kf_light(lights["fg_light"], fr, e_fg)
        _kf_light(lights["face_fill_light"], fr, e_face_fill)
        _kf_light(lights["cyan_light"], fr, e_cyan)
        _set_neon_emission(env["neon_mat"], fr, e_neon_emit)
        lights["world_bg"].inputs["Strength"].default_value = w_strength
        lights["world_bg"].inputs["Strength"].keyframe_insert("default_value", frame=fr)

        if (idx_f + 1) % 240 == 0:
            log("BAKE", f"Baked {idx_f + 1}/{len(frames_to_bake)} frames ({_time.monotonic() - t_bake:.1f}s)")

    scene.frame_start = 1
    scene.frame_end = total_frames
    log("BAKE", f"Finished baking {len(frames_to_bake)} frames in {_time.monotonic() - t_bake:.1f}s")

    return {
        "tmap": tmap,
        "cam_obj": cam_obj,
        "sandal": sandal,
        "sandal_grip_distances": sandal_grip_distances,
    }


# =============================================================================
# AUTOMATED QC CHECKLIST (TROUBLESHOOTING.md ANTI-BUG VERIFICATION)
# =============================================================================

def run_qc_checks(
    scene: bpy.types.Scene,
    human: Dict[str, Any],
    build_info: Dict[str, Any],
    fps: int,
) -> Dict[str, Any]:
    """Run TROUBLESHOOTING.md checklist: no pink textures, no unparented body parts,
    `$md-*` body keys intact, sandal anchored to wrist.R, and no camera-inside-object black frames.
    """
    import os

    issues: List[str] = []

    # 1. Missing/unpacked images -> would render pink!
    missing_imgs = [
        i.filepath
        for i in bpy.data.images
        if i.source == "FILE" and not i.packed_file and not os.path.exists(bpy.path.abspath(i.filepath))
    ]
    if missing_imgs:
        issues.append(f"MISSING_TEXTURES: {missing_imgs}")

    # 2. Unparented MPFB2 Human.* meshes -> would float off body!
    unparented = [
        o.name
        for o in bpy.data.objects
        if o.type == "MESH" and o.name.startswith("Human.") and o.parent is None
    ]
    if unparented:
        issues.append(f"UNPARENTED_HUMAN_PARTS: {unparented}")

    # 3. `$md-*` body shape keys must NOT be zeroed!
    body = human["body"]
    md_keys = [k for k in body.data.shape_keys.key_blocks if k.name.startswith("$md-")]
    nonzero_md = [k.name for k in md_keys if abs(k.value) > 1e-4]
    if md_keys and not nonzero_md:
        issues.append("BODY_SHAPE_KEYS_ZEROED: all $md-* keys are 0 (body would vanish!)")

    # 4. Sandal grip distance to wrist.R in Scenes 1-7
    bad_grip = {sid: round(d, 3) for sid, d in build_info["sandal_grip_distances"].items() if sid <= 7 and d > 0.25}
    if bad_grip:
        issues.append(f"FLOATING_SANDAL: {bad_grip}")

    # 5. Camera unobstructed raycast check on all 8 storyboard frames (no black frame inside prop!)
    cam_obj = build_info["cam_obj"]
    dg = bpy.context.evaluated_depsgraph_get()
    blocked_scenes: List[Tuple[int, str, float]] = []
    for sid, s_meta in sorted(build_info["tmap"].items()):
        fr = pick_storyboard_frame(s_meta, fps)
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        origin = cam_obj.matrix_world.translation.copy()
        fwd = (cam_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        hit, hit_loc, _, _, hit_obj, _ = scene.ray_cast(dg, origin + fwd * 0.015, fwd, distance=0.06)
        if hit and hit_obj and not hit_obj.name.startswith(("Cockroach_", "Speed_Line", "CutToBlack")):
            blocked_scenes.append((sid, hit_obj.name, round((hit_loc - origin).length, 4)))
    if blocked_scenes:
        issues.append(f"CAMERA_BLOCKED: {blocked_scenes}")

    report = {
        "passed": len(issues) == 0,
        "missing_textures": missing_imgs,
        "unparented_human_parts": unparented,
        "md_body_keys_preserved": len(nonzero_md),
        "sandal_grip_max_dist_m": {k: round(v, 3) for k, v in sorted(build_info["sandal_grip_distances"].items())},
        "camera_blocked": blocked_scenes,
        "issues": issues,
    }
    if report["passed"]:
        log(
            "QC",
            f"ALL CHECKS PASSED | MISSING=[] | unparented=0 | $md keys={len(nonzero_md)} intact | "
            f"sandal_dist={report['sandal_grip_max_dist_m']} | camera_clear=ALL",
        )
    else:
        log("QC_WARN", f"QC detected issues: {issues}")
    return report


# =============================================================================
# RESILIENT FRAME RENDERER (OPTIX -> CUDA -> CPU FALLBACK + AUTO-RESUME + post.py)
# =============================================================================

def _render_single_frame_resilient(scene: bpy.types.Scene, frame: int, out_png: Path, apply_post: bool) -> float:
    t0 = _time.monotonic()
    scene.frame_set(frame)
    scene.render.filepath = str(out_png)
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as exc:
        log("WARN", f"Frame {frame} render failed ({exc}); trying fallback backend...")
        if scene.render.engine == "CYCLES":
            prefs = bpy.context.preferences.addons["cycles"].preferences
            for backend in ("CUDA", None):
                try:
                    if backend:
                        prefs.compute_device_type = backend
                        prefs.refresh_devices()
                        for d in prefs.devices:
                            d.use = d.type == backend
                        scene.cycles.device = "GPU"
                    else:
                        scene.cycles.device = "CPU"
                    try:
                        scene.cycles.denoising_use_gpu = False
                    except Exception:
                        pass
                    bpy.ops.render.render(write_still=True)
                    log("RENDER", f"Recovered frame {frame} via {backend or 'CPU'}")
                    break
                except Exception:
                    continue
            else:
                raise
        else:
            # EEVEE headless fallback to Cycles CPU
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
            bpy.ops.render.render(write_still=True)

    if apply_post and out_png.exists():
        apply_post_camera_look(out_png, out_png, seed=7 + frame)

    return _time.monotonic() - t0


def render_scene_clip(
    scene: bpy.types.Scene,
    scene_meta: Dict[str, Any],
    scenes_out_dir: Path,
    ffmpeg_bin: str,
    fps: int,
    apply_post: bool = True,
) -> Path:
    sid = int(scene_meta["scene_id"])
    f_start = int(scene_meta["start_frame"])
    f_end = int(scene_meta["end_frame"])
    total_scene_frames = f_end - f_start + 1

    frames_dir = scenes_out_dir / f"scene_{sid:02d}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    skipped = 0
    rendered = 0
    log("RENDER", f"Scene {sid:02d} | Frames {f_start}..{f_end} ({total_scene_frames} frames, auto-resume >10KB, post={apply_post})")

    for fr in range(f_start, f_end + 1):
        frame_file = frames_dir / f"frame_{fr:04d}.png"
        if frame_file.exists() and frame_file.stat().st_size > 10_240:
            skipped += 1
            continue
        dt = _render_single_frame_resilient(scene, fr, frame_file, apply_post=apply_post)
        rendered += 1
        if rendered == 1 or rendered % 24 == 0 or fr == f_end:
            rem = max(0, f_end - fr)
            log("RENDER", f"FRAME {fr}/{f_end} (Scene {sid:02d}) {dt:.1f}s | est. scene rem ~{rem * dt:.0f}s")

    log("RENDER", f"Scene {sid:02d} frames ready (rendered={rendered}, resumed/skipped={skipped})")

    out_mp4 = scenes_out_dir / f"scene_{sid:02d}.mp4"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        str(f_start),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "fast",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    log("RENDER", f"Scene {sid:02d} MP4 ready -> {out_mp4}")
    return out_mp4


def render_storyboard_keyframe(
    scene: bpy.types.Scene,
    scene_meta: Dict[str, Any],
    scenes_out_dir: Path,
    ffmpeg_bin: str,
    fps: int,
    apply_post: bool = True,
) -> Path:
    sid = int(scene_meta["scene_id"])
    hero_frame = pick_storyboard_frame(scene_meta, fps)
    dur = float(scene_meta["scene_duration_sec"])

    out_png = scenes_out_dir / f"scene_{sid:02d}.png"
    log("STORYBOARD", f"Rendering Scene {sid:02d} hero frame {hero_frame} -> {out_png.name}")
    dt = _render_single_frame_resilient(scene, hero_frame, out_png, apply_post=apply_post)
    log("STORYBOARD", f"Scene {sid:02d} rendered in {dt:.1f}s (post.py={'ON' if apply_post else 'OFF'})")

    out_mp4 = scenes_out_dir / f"scene_{sid:02d}.mp4"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-loop",
        "1",
        "-i",
        str(out_png),
        "-t",
        f"{dur:.4f}",
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "20",
        "-preset",
        "ultrafast",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return out_png


def build_storyboard_contact_sheet(
    scene_ids: List[int],
    scenes_out_dir: Path,
    grid_out_path: Path,
    ffmpeg_bin: str,
) -> Path:
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    font_opt = f"fontfile={font_path}:" if font_path.exists() else ""

    inputs: List[str] = []
    filters: List[str] = []
    valid_labels: List[str] = []

    for sid in sorted(scene_ids):
        png_path = scenes_out_dir / f"scene_{sid:02d}.png"
        if not png_path.exists():
            continue
        inputs.extend(["-i", str(png_path)])
        in_idx = len(valid_labels)
        lbl = f"t{in_idx}"
        filters.append(
            f"[{in_idx}:v]drawtext={font_opt}text='Scene {sid:02d}':"
            f"fontsize=26:fontcolor=yellow:box=1:boxcolor=black@0.75:boxborderw=8:x=12:y=12[{lbl}]"
        )
        valid_labels.append(f"[{lbl}]")

    if not valid_labels:
        raise RuntimeError("No storyboard PNGs found to assemble contact sheet.")

    n = len(valid_labels)
    cols = 4 if n > 4 else n
    rows = max(1, (n + cols - 1) // cols)
    filters.append(
        f"{''.join(valid_labels)}concat=n={n}:v=1:a=0,tile={cols}x{rows}:padding=8:margin=8:color=0x111827[grid]"
    )

    grid_out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[grid]",
        "-frames:v",
        "1",
        str(grid_out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    log("STORYBOARD", f"Contact sheet {rows}x{cols} ready -> {grid_out_path}")
    return grid_out_path


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Blender 5.2+ Headless 3D Micro-POV Builder & Renderer")
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
    )
    parser.add_argument("--timing", type=str, default=None, help="Path to timing_manifest.json")
    parser.add_argument("--assets-dir", type=str, default=None, help="Override 02_assets cache directory")
    parser.add_argument("--work-dir", type=str, default=None, help="Override episode working directory")
    parser.add_argument("--family-blend", type=str, default=None, help="Override path to MPFB2 family_ready.blend")
    parser.add_argument("--mode", choices=["storyboard", "preview", "final"], default="storyboard")
    parser.add_argument("--engine", choices=["CYCLES", "EEVEE"], default="CYCLES")
    parser.add_argument("--scene", type=int, default=None, help="Render ONLY a single scene_id")
    parser.add_argument("--save-blend", action="store_true", help="Pack & save assembled .blend file")
    parser.add_argument("--bake-all", action="store_true", help="Force full frame-by-frame bake even in storyboard mode")
    parser.add_argument("--no-post", action="store_true", help="Disable post.py camera look pass")
    parser.add_argument("--no-render", action="store_true", help="Build & QC .blend scene only without rendering")
    return parser.parse_args(extra)


def main() -> int:
    args = parse_args()
    ffmpeg_bin = check_ffmpeg_available()

    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    assets_dir = resolve_assets_dir(args.assets_dir)
    work_dir = resolve_episode_work_dir(spec_path, args.work_dir)
    timing_path = Path(args.timing).resolve() if args.timing else (work_dir / "timing_manifest.json")

    if not timing_path.exists():
        log("ERROR", f"timing_manifest.json not found at {timing_path}. Run generate_tts.py first (Audio-First!).")
        return 1
    manifest = load_json(timing_path)
    fps = int(manifest.get("fps", 24))

    # Locate MPFB2 family_ready.blend (auto-syncs from Google Drive / Kaggle input!)
    family_blend = Path(args.family_blend).resolve() if args.family_blend else resolve_family_ready_blend(assets_dir)
    if family_blend is None or not family_blend.exists():
        log(
            "ERROR",
            "MPFB2 family_ready.blend tidak ditemukan! Pastikan Google Drive ter-mount di "
            "`/content/drive/MyDrive/Skill referensi/Zack Blender Pack/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend` "
            "atau passing `--family-blend <path>`.",
        )
        return 1

    log("BLENDER", f"Opening MPFB2 base rig: {family_blend}")
    human = mh.load_mpfb2_human_base(family_blend, target_height_m=1.68)
    scene = bpy.context.scene
    configure_render_engine(scene, args.engine, args.mode, fps)

    # In fast storyboard mode (without --bake-all or --save-blend), only bake the 8 hero storyboard frames!
    bake_frames: Optional[List[int]] = None
    if args.mode == "storyboard" and not args.bake_all and not args.save_blend:
        bake_frames = [1]
        for s_meta in manifest["scenes"]:
            bake_frames.append(pick_storyboard_frame(s_meta, fps))
            if int(s_meta["scene_id"]) == 8:
                # Also bake pre-drop frame in Scene 8 so sandal drop anchor is exact!
                f0 = int(s_meta["start_frame"])
                f_pre = f0 + int(round(float(s_meta.get("cut_to_black_sec", 4.5)) * 0.40 * fps))
                bake_frames.append(max(f0, f_pre))
    elif args.scene is not None and not args.bake_all and not args.save_blend:
        s_target = next((s for s in manifest["scenes"] if int(s["scene_id"]) == args.scene), None)
        if s_target:
            bake_frames = list(range(int(s_target["start_frame"]), int(s_target["end_frame"]) + 1))

    build_info = build_ep001_animation(scene, spec, manifest, assets_dir, human, bake_frames=bake_frames)
    tmap = build_info["tmap"]

    # Automated TROUBLESHOOTING.md QC verification before saving or rendering!
    run_qc_checks(scene, human, build_info, fps)

    if args.save_blend or args.no_render:
        try:
            bpy.ops.file.pack_all()
        except Exception as exc:
            log("WARN", f"pack_all warning: {exc}")
        blend_path = work_dir / f"{spec['episode_id'].lower()}_{args.mode}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
        log("BLENDER", f"Saved packed Blender 5.2 project -> {blend_path}")

    if args.no_render:
        log("BLENDER", "--no-render active; scene assembly & QC verified cleanly.")
        return 0

    scenes_out_dir = work_dir / "raw_render" / f"scenes_{args.mode}"
    scenes_out_dir.mkdir(parents=True, exist_ok=True)
    apply_post = not args.no_post

    target_ids = [args.scene] if args.scene is not None else sorted(tmap.keys())
    for sid in target_ids:
        if sid not in tmap:
            log("ERROR", f"Scene {sid} not found in timing_manifest.json (available: {sorted(tmap.keys())})")
            return 1
        if args.mode == "storyboard":
            render_storyboard_keyframe(scene, tmap[sid], scenes_out_dir, ffmpeg_bin, fps, apply_post=apply_post)
        else:
            render_scene_clip(scene, tmap[sid], scenes_out_dir, ffmpeg_bin, fps, apply_post=apply_post)

    if args.mode == "storyboard":
        grid_ids = sorted(tmap.keys()) if len(target_ids) > 1 or args.scene is None else target_ids
        build_storyboard_contact_sheet(grid_ids, scenes_out_dir, work_dir / "storyboard_grid.png", ffmpeg_bin)

    log("RENDER", f"Completed rendering {len(target_ids)} scene(s) in mode '{args.mode}' ({args.engine}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
