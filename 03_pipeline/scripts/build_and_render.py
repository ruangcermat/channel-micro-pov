#!/usr/bin/env python3
"""Blender Headless 3D Scene Builder & Cycles GPU Render Engine (channel-micro-pov).

Usage (via Blender Linux headless):
  blender --background --python 03_pipeline/scripts/build_and_render.py -- \\
      --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json \\
      --mode preview [--scene 4]

Features:
- Cycles GPU acceleration (auto-detects OptiX -> CUDA on Colab T4, safe CPU fallback)
  with OpenImageDenoise (OIDN).
- Reads Audio-First `timing_manifest.json` so every scene's animation matches actual VO duration.
- Loads cached Poly Haven CC0 textures, HDRI, and GLTF kitchen furniture (`modern_wooden_cabinet`,
  `cardboard_box_01`, `Shelf_01`, `wooden_bowl_01`).
- Builds stylized Indonesian props via `procedural_props.py` (Swallow flip-flop, Indomie spill,
  cockroach antennae/wings foreground rig, rigged giant human silhouette, 5.5cm fridge under-gap).
- Full 8-scene dynamic POV choreography: neon flash, low-angle boss tilt, cyan bullet-time,
  300 km/h sprint with camera shake + 112° FOV, foot stomp shadow, whip-pan left/right/up,
  wobbly wing takeoff, dive toward face + Cut to Black.
- Renders per-scene MP4 clips (`raw_render/scenes/scene_0X.mp4`) and supports `--scene N`
  for instant single-scene revision renders.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Euler, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline_utils import (
    check_ffmpeg_available,
    get_repo_root,
    load_and_validate_spec,
    load_json,
    log,
    resolve_assets_dir,
    resolve_episode_work_dir,
)
import procedural_props as props


# =============================================================================
# RENDER ENGINE & GPU CONFIGURATION (CYCLES + OPTIX/CUDA + OIDN)
# =============================================================================

def configure_cycles_render(scene: bpy.types.Scene, mode: str, fps: int) -> None:
    scene.render.engine = "CYCLES"
    scene.render.fps = fps
    scene.render.fps_base = 1.0

    # 1. Auto-detect NVIDIA GPU (OPTIX -> CUDA); fallback safely to CPU
    has_gpu = False
    device_used = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for compute_type in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = compute_type
                prefs.get_devices()
                gpu_devices = [d for d in prefs.devices if d.type == compute_type]
                if gpu_devices:
                    for d in prefs.devices:
                        d.use = d.type == compute_type
                    scene.cycles.device = "GPU"
                    has_gpu = True
                    device_used = f"GPU ({compute_type}: {gpu_devices[0].name})"
                    break
            except Exception:
                continue
        if not has_gpu:
            scene.cycles.device = "CPU"
    except Exception:
        scene.cycles.device = "CPU"

    # 2. Configure resolution & samples based on mode and hardware availability
    if mode == "storyboard" or not has_gpu:
        if mode != "storyboard" and not has_gpu:
            log("BLENDER", f"No GPU detected — automatically falling back to Cycles CPU (360x640, 8 samples, OIDN) for mode '{mode}'.")
        scene.render.resolution_x = 360
        scene.render.resolution_y = 640
        scene.cycles.samples = 8
        scene.cycles.adaptive_threshold = 0.08
        scene.cycles.max_bounces = 3
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 2
        scene.cycles.transparent_max_bounces = 4
        est_sec_per_frame = "0.4-0.8s (GPU)" if has_gpu else "6-12s (CPU)"
    elif mode == "preview":
        scene.render.resolution_x = 540
        scene.render.resolution_y = 960
        scene.cycles.samples = 16
        scene.cycles.adaptive_threshold = 0.06
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 2
        scene.cycles.transparent_max_bounces = 4
        est_sec_per_frame = "0.6-1.2s (T4 OptiX/CUDA)"
    else:
        scene.render.resolution_x = 1080
        scene.render.resolution_y = 1920
        scene.cycles.samples = 24
        scene.cycles.adaptive_threshold = 0.06
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 2
        scene.cycles.transmission_bounces = 2
        scene.cycles.transparent_max_bounces = 4
        est_sec_per_frame = "1.8-3.5s (T4 OptiX/CUDA)"

    scene.render.resolution_percentage = 100
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(scene.cycles, "denoising_input_passes"):
        scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"

    # Motion blur for moving video renders; disable in storyboard for crisp still frames
    scene.render.use_motion_blur = mode != "storyboard"
    scene.render.motion_blur_shutter = 0.35

    # Output crisp PNG frames per scene (robust against Colab disconnects)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15

    # AgX Medium High Contrast color management with controlled -0.55 exposure (no white blowout)
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
        try:
            scene.view_settings.look = "Medium High Contrast"
        except Exception:
            pass
    scene.view_settings.exposure = -0.55

    log(
        "BLENDER",
        f"Cycles configured | Mode: {mode} ({scene.render.resolution_x}x{scene.render.resolution_y}, "
        f"{scene.cycles.samples} samples, {fps}fps) | Device: {device_used} | OIDN: ON | Est: {est_sec_per_frame}/frame",
    )


# =============================================================================
# WORLD HDRI & LIGHTING RIG ("JAM 2 PAGI" HIGH-CONTRAST CINEMATIC)
# =============================================================================

def setup_world_and_lights(scene: bpy.types.Scene, assets_dir: Path) -> Dict[str, Any]:
    """Configure very dim night-blue HDRI + crisp overhead/back neon + boss rim light."""
    world = bpy.data.worlds.new("MicroPOV_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    hdri_path = assets_dir / "hdri" / "small_empty_room_3_1k.hdr"
    if not hdri_path.exists():
        alt = assets_dir / "hdri" / "abandoned_tiled_room_1k.hdr"
        if alt.exists():
            hdri_path = alt

    if hdri_path.exists():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri_path), check_existing=True)
        # Deep 2 AM night-blue tint so ambient fill stays moody & dark
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 0.85
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = (0.16, 0.28, 0.55, 1.0)
        nt.links.new(env.outputs["Color"], sock_a)
        nt.links.new(sock_out, bg.inputs["Color"])
        world_tint = sock_b
        log("BLENDER", f"Loaded cached Poly Haven HDRI (night tint): {hdri_path.name}")
    else:
        bg.inputs["Color"].default_value = (0.02, 0.04, 0.12, 1.0)
        world_tint = bg.inputs["Color"]

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

    # 1. Dim blue 2 AM window/fridge rim light (Scene 1 pre-switch 0-1.0s)
    night_obj, night_data = _add_area_light(
        "Light_Night_Blue", (0.95, 0.85, 1.45), (math.radians(52), math.radians(40), 0.0), 0.7, 1.1, 7.5, (0.14, 0.35, 1.0)
    )

    # 2. Overhead TL Fluorescent Neon positioned behind human's plane (y=2.15) for sharp shadows & dark boss face!
    neon_obj, neon_data = _add_area_light(
        "Light_Neon_Main", (0.0, 2.15, 2.55), (math.radians(10), 0.0, 0.0), 0.14, 0.95, 0.0, (0.92, 0.96, 1.0)
    )

    # 3. Dramatic Boss Backlight behind human head (rim silhouette)
    rim_obj, rim_data = _add_area_light(
        "Light_Boss_Backlight", (0.0, 2.60, 2.10), (math.radians(-48), 0.0, 0.0), 0.75, 0.75, 0.0, (0.85, 0.94, 1.0)
    )

    # 4. Cyan Cheat-Code Accent Light (Scene 3 bullet time)
    cyan_data = bpy.data.lights.new(name="Light_Cyan_Accent", type="POINT")
    cyan_data.energy = 0.0
    cyan_data.color = (0.05, 0.92, 1.0)
    cyan_data.shadow_soft_size = 0.12
    cyan_obj = bpy.data.objects.new("Light_Cyan_Accent", cyan_data)
    cyan_obj.location = (0.0, 0.60, 0.22)
    scene.collection.objects.link(cyan_obj)

    # 5. Subtle floor bounce (very low 1.2W so shadows stay deep & contrasty)
    fill_obj, fill_data = _add_area_light(
        "Light_Floor_Fill", (0.4, -0.4, 0.9), (math.radians(55), 0.0, math.radians(-20)), 0.8, 0.8, 1.2, (0.85, 0.90, 1.0)
    )

    return {
        "world_bg": bg,
        "world_tint": world_tint,
        "night_light": night_data,
        "neon_light": neon_data,
        "rim_light": rim_data,
        "cyan_light": cyan_data,
        "fill_light": fill_data,
    }


# =============================================================================
# IMPORT CACHED POLY HAVEN CC0 GLTF KITCHEN PROPS
# =============================================================================

def import_gltf_prop(
    gltf_path: Path,
    name: str,
    location: Tuple[float, float, float],
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: float = 1.0,
) -> Optional[bpy.types.Object]:
    """Import a cached CC0 .gltf/.glb into an anchor Empty safely."""
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
    log("BLENDER", f"Placed CC0 GLTF prop {name} ({gltf_path.name})")
    return anchor


def populate_cached_kitchen_furniture(assets_dir: Path) -> None:
    """Place downloaded Poly Haven CC0 furniture around the kosan kitchen set."""
    models_dir = assets_dir / "models_3d"
    # Cardboard box blocking right side near fridge (Scene 6: "kanan buntu/kardus"!)
    box_gltf = models_dir / "cardboard_box_01" / "cardboard_box_01_1k.gltf"
    if not import_gltf_prop(box_gltf, "Kardus_DeadEnd_Right", (0.58, 2.48, 0.0), (0.0, 0.0, -18.0), scale=1.05):
        # Procedural fallback cardboard box if offline
        box_mat = props.make_material("Mat_Cardboard_Fallback", (0.58, 0.42, 0.24, 1.0), roughness=0.88)
        props._make_beveled_box("Kardus_DeadEnd_Right", (0.45, 0.42, 0.38), 0.006, box_mat, location=(0.58, 2.48, 0.19))

    # Wooden kitchen cabinet along right wall
    cab_gltf = models_dir / "modern_wooden_cabinet" / "modern_wooden_cabinet_1k.gltf"
    import_gltf_prop(cab_gltf, "Kitchen_Cabinet_Right", (1.28, 1.65, 0.0), (0.0, 0.0, -90.0), scale=0.95)

    # Kitchen shelf along left wall behind start
    shelf_gltf = models_dir / "Shelf_01" / "Shelf_01_1k.gltf"
    import_gltf_prop(shelf_gltf, "Kitchen_Shelf_Left", (-0.64, 0.95, 0.0), (0.0, 0.0, 90.0), scale=0.85)

    # Bowl prop on floor near spill
    bowl_gltf = models_dir / "wooden_bowl_01" / "wooden_bowl_01_1k.gltf"
    import_gltf_prop(bowl_gltf, "Extra_Kitchen_Bowl", (0.52, 0.72, 0.0), (0.0, 0.0, 25.0), scale=0.35)


# =============================================================================
# KEYFRAME HELPERS
# =============================================================================

def _kf_loc_rot(obj: bpy.types.Object, frame: int, loc=None, rot_deg=None, scale=None) -> None:
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert(data_path="location", frame=frame)
    if rot_deg is not None:
        obj.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), "XYZ")
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert(data_path="scale", frame=frame)


def _kf_fov(cam_data: bpy.types.Camera, frame: int, fov_deg: float) -> None:
    """Convert vertical FOV degrees to focal length (mm) and keyframe animatable `lens`."""
    cam_data.lens_unit = "MILLIMETERS"
    sensor_mm = cam_data.sensor_height if cam_data.sensor_fit == "VERTICAL" else cam_data.sensor_width
    fov_rad = math.radians(max(10.0, min(160.0, fov_deg)))
    cam_data.lens = (sensor_mm * 0.5) / math.tan(fov_rad * 0.5)
    cam_data.keyframe_insert(data_path="lens", frame=frame)


def _kf_hide(obj: bpy.types.Object, frame: int, hidden: bool) -> None:
    """Recursively keyframe visibility on an object and all its child meshes."""
    targets = [obj] + list(obj.children_recursive)
    for t in targets:
        t.hide_render = hidden
        t.hide_viewport = hidden
        t.keyframe_insert(data_path="hide_render", frame=frame)
        t.keyframe_insert(data_path="hide_viewport", frame=frame)


def _kf_light(light_data: bpy.types.Light, frame: int, energy: float) -> None:
    light_data.energy = energy
    light_data.keyframe_insert(data_path="energy", frame=frame)


def _set_neon_emission(neon_mat: bpy.types.Material, frame: int, strength: float) -> None:
    for node in neon_mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            if "Emission Strength" in node.inputs:
                node.inputs["Emission Strength"].default_value = strength
                node.inputs["Emission Strength"].keyframe_insert(data_path="default_value", frame=frame)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def _set_antennae_pose(
    ant_rig: Dict[str, bpy.types.Object],
    frame: int,
    pitch_deg: float,
    spread_deg: float,
    jitter: float = 0.0,
) -> None:
    """Keyframe expressive cockroach antennae rotation."""
    j1 = jitter * math.sin(frame * 1.9)
    j2 = jitter * math.cos(frame * 2.3)
    _kf_loc_rot(ant_rig["ant_l"], frame, rot_deg=(pitch_deg + j1, 0.0, spread_deg + j2))
    _kf_loc_rot(ant_rig["ant_r"], frame, rot_deg=(pitch_deg - j2, 0.0, -spread_deg - j1))


# =============================================================================
# FULL EP001 8-SCENE AUDIO-FIRST CHOREOGRAPHY
# =============================================================================

def build_ep001_animation(
    scene: bpy.types.Scene,
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    assets_dir: Path,
) -> Dict[int, Dict[str, Any]]:
    """Build complete EP001 3D world and keyframe all 8 scenes to exact Audio-First timing."""
    fps = int(manifest["fps"])
    pov_cfg = spec["pov_config"]
    cam_h = float(pov_cfg.get("camera_height_m", 0.015))
    base_fov = float(pov_cfg.get("base_fov_deg", 95.0))

    # 1. Build environment, lights & cached CC0 furniture
    env = props.build_kitchen_tile_floor(assets_dir)
    lights = setup_world_and_lights(scene, assets_dir)
    populate_cached_kitchen_furniture(assets_dir)

    # 2. Build stylized Indonesian props
    props.build_indomie_bowl_spill((0.0, 0.22, 0.0))
    fridge = props.build_fridge_under_gap((-0.12, 2.95, 0.0))
    human = props.build_human_silhouette_giant((0.02, 1.32, 0.0))
    sandal = props.build_sandal_jepit_swallow((0.0, 0.0, 0.0))
    wind = props.build_wind_lines((0.0, 0.65, 0.14))
    dust = props.build_dust_puff((0.0, 0.45, 0.01))

    # 3. Setup POV Camera with Macro DOF + Foreground Cockroach Antennae/Wings + Speed Lines
    cam_data = bpy.data.cameras.new("MicroPOV_Camera")
    cam_data.clip_start = 0.005  # Critical for 1.5cm cockroach macro scale!
    cam_data.clip_end = 40.0
    cam_data.sensor_fit = "VERTICAL"
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 3.2
    cam_data.dof.focus_distance = 0.25
    cam_obj = bpy.data.objects.new("MicroPOV_Camera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    def _kf_dof(frame: int, dist_m: float) -> None:
        cam_data.dof.focus_distance = max(0.05, dist_m)
        cam_data.dof.keyframe_insert(data_path="focus_distance", frame=frame)

    # Parent Sandal Jepit directly to Human Right Hand Socket via CHILD_OF constraint
    # so sandal is genuinely gripped in Scenes 1, 2, 3, 6, 7 and never floats in mid-air!
    from mathutils import Matrix
    sandal_grip = sandal["root"].constraints.new("CHILD_OF")
    sandal_grip.name = "Grip_In_RightHand"
    sandal_grip.target = human["sandal_socket"]
    sandal_grip.inverse_matrix = Matrix.Identity(4)
    sandal_grip.influence = 1.0

    def _kf_grip(frame: int, influence: float) -> None:
        sandal_grip.influence = influence
        sandal_grip.keyframe_insert(data_path="influence", frame=frame)

    ant_rig = props.build_cockroach_antennae_rig(cam_obj)
    speed_rig = props.build_speed_lines_rig(cam_obj)

    # Cut-to-black shutter plane right in front of lens for Scene 8's hard blackout ending
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

    def f_at(sid: int, local_sec: float) -> int:
        s = tmap[sid]
        return max(s["start_frame"], min(s["end_frame"], s["start_frame"] + int(round(local_sec * fps))))

    def f_frac(sid: int, frac: float) -> int:
        s = tmap[sid]
        return s["start_frame"] + int(round(frac * (s["frame_count"] - 1)))

    # Initial visibility state (Frame 1)
    _kf_hide(wind["root"], 1, True)
    _kf_hide(dust["root"], 1, True)
    _kf_hide(speed_rig["root"], 1, True)
    _kf_hide(ant_rig["wing_l"], 1, True)
    _kf_hide(ant_rig["wing_r"], 1, True)
    _kf_hide(black_shutter, 1, True)

    # =========================================================================
    # SCENE 1: JAM 2 PAGI — Gelap biru (0-1.0s) -> Flash neon overhead -> Antennae kaku!
    # =========================================================================
    if 1 in tmap:
        s1 = tmap[1]
        f0, f_end = s1["start_frame"], s1["end_frame"]
        f_flash = f_at(1, 1.05)

        _kf_loc_rot(cam_obj, f0, (0.0, -0.02, cam_h), (82.0, 0.0, 0.0))
        _kf_fov(cam_data, f0, base_fov)
        _kf_dof(f0, 0.22)  # Focus on Indomie spill
        _kf_loc_rot(cam_obj, f_flash - 2, (0.0, 0.0, cam_h), (83.0, 0.0, 0.0))

        # Startled jolt upward when blinding neon clicks ON!
        _kf_loc_rot(cam_obj, f_flash + 4, (0.0, -0.01, cam_h + 0.008), (104.0, 3.0, -2.0))
        _kf_loc_rot(cam_obj, f_end, (0.0, -0.01, cam_h + 0.006), (108.0, 0.0, 0.0))
        _kf_fov(cam_data, f_end, base_fov)
        _kf_dof(f_end, 1.20)

        # Dramatic 2 AM blue darkness -> sharp overhead neon flash
        _kf_light(lights["night_light"], f0, 7.5)
        _kf_light(lights["neon_light"], f0, 0.0)
        _kf_light(lights["neon_light"], f_flash - 1, 0.0)
        _set_neon_emission(env["neon_mat"], f0, 0.05)
        _set_neon_emission(env["neon_mat"], f_flash - 1, 0.05)
        lights["world_bg"].inputs["Strength"].default_value = 0.05
        lights["world_bg"].inputs["Strength"].keyframe_insert("default_value", frame=f0)
        lights["world_bg"].inputs["Strength"].keyframe_insert("default_value", frame=f_flash - 1)

        _kf_light(lights["night_light"], f_flash + 1, 0.8)
        _kf_light(lights["neon_light"], f_flash + 1, 185.0)
        _kf_light(lights["neon_light"], f_flash + 7, 110.0)
        _set_neon_emission(env["neon_mat"], f_flash + 1, 16.0)
        lights["world_bg"].inputs["Strength"].default_value = 0.08
        lights["world_bg"].inputs["Strength"].keyframe_insert("default_value", frame=f_flash + 1)

        # Human stands ahead gripping sandal in right hand (no floating!)
        _kf_grip(f0, 1.0)
        _kf_loc_rot(sandal["root"], f0, (0.0, 0.02, -0.02), (90.0, 0.0, 0.0))
        _kf_loc_rot(human["root"], f0, (0.02, 1.32, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["left_leg"], f0, (0.11, 0.0, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (18.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f_end, (-0.23, 0.0, 1.39), (88.0, 0.0, 6.0))

        for fr in range(f0, f_flash, 4):
            _set_antennae_pose(ant_rig, fr, -8.0, 6.0, jitter=4.0)
        _set_antennae_pose(ant_rig, f_flash + 2, 26.0, -8.0, jitter=1.0)
        _set_antennae_pose(ant_rig, f_end, 24.0, -6.0, jitter=1.5)

    # =========================================================================
    # SCENE 2: BOSS TERAKHIR — Low-angle extreme tilt up + backlit silhouette
    # =========================================================================
    if 2 in tmap:
        s2 = tmap[2]
        f0, f_end = s2["start_frame"], s2["end_frame"]
        f_mid1 = f_frac(2, 0.35)
        f_mid2 = f_frac(2, 0.68)

        _kf_loc_rot(cam_obj, f0, (0.0, 0.08, cam_h), (126.0, 0.0, 6.0))
        _kf_fov(cam_data, f0, 92.0)
        _kf_dof(f0, 1.55)

        _kf_loc_rot(cam_obj, f_mid1, (-0.01, 0.12, cam_h), (138.0, -2.5, 10.0))
        _kf_fov(cam_data, f_mid1, 72.0)

        _kf_loc_rot(cam_obj, f_mid2, (-0.02, 0.14, cam_h), (144.0, 2.0, 12.0))
        _kf_fov(cam_data, f_mid2, 56.0)

        _kf_loc_rot(cam_obj, f_end, (-0.02, 0.15, cam_h), (146.0, 0.0, 11.0))
        _kf_fov(cam_data, f_end, 54.0)
        _kf_dof(f_end, 1.65)

        # Backlight boss silhouette glow (keeps human face dark & dramatic!)
        _kf_light(lights["rim_light"], f0, 320.0)
        _kf_light(lights["neon_light"], f0, 115.0)

        _kf_grip(f0, 1.0)
        _kf_loc_rot(sandal["root"], f0, (0.0, 0.02, -0.02), (90.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (148.0, 0.0, 8.0))
        _kf_loc_rot(human["right_arm"], f_end, (-0.23, 0.0, 1.39), (168.0, 0.0, 6.0))

        for fr in range(f0, f_end + 1, 5):
            _set_antennae_pose(ant_rig, fr, 22.0, -4.0, jitter=5.0)

    # =========================================================================
    # SCENE 3: CHEAT CODE AKTIF — Bullet-time slow-mo + subtle cyan wind lines
    # =========================================================================
    if 3 in tmap:
        s3 = tmap[3]
        f0, f_end = s3["start_frame"], s3["end_frame"]
        f_wind_start = f_frac(3, 0.25)

        _kf_loc_rot(cam_obj, f0, (0.0, 0.16, cam_h), (124.0, 9.0, 6.0))
        _kf_fov(cam_data, f0, 82.0)
        _kf_dof(f0, 0.95)
        _kf_loc_rot(cam_obj, f_end, (0.03, 0.20, cam_h), (118.0, 13.0, 2.0))
        _kf_fov(cam_data, f_end, 94.0)
        _kf_dof(f_end, 0.65)

        _kf_light(lights["cyan_light"], f0, 10.0)
        _kf_light(lights["cyan_light"], f_wind_start, 28.0)
        _kf_light(lights["cyan_light"], f_end, 34.0)
        _kf_light(lights["rim_light"], f0, 160.0)

        _kf_hide(wind["root"], f0, False)
        _kf_loc_rot(wind["root"], f0, (-0.10, 0.78, 0.62), (24.0, 0.0, 8.0), scale=(0.6, 0.6, 0.6))
        _kf_loc_rot(wind["root"], f_end, (-0.02, 0.36, 0.16), (12.0, 0.0, 2.0), scale=(1.1, 1.25, 1.1))

        # Slow-motion downward swing with sandal locked in right hand
        _kf_grip(f0, 1.0)
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (165.0, 0.0, 6.0))
        _kf_loc_rot(human["right_arm"], f_end, (-0.23, 0.0, 1.39), (92.0, 0.0, 4.0))

        for fr in range(f0, f_end + 1, 3):
            _set_antennae_pose(ant_rig, fr, 14.0, 10.0, jitter=8.5)

    # =========================================================================
    # SCENE 4: 300 KM/JAM — Sandal slams floor + dust puff + 112° FOV hyper-sprint!
    # =========================================================================
    if 4 in tmap:
        s4 = tmap[4]
        f0, f_end = s4["start_frame"], s4["end_frame"]
        f_slam = f_at(4, 0.42)

        _kf_hide(wind["root"], f0, True)
        _kf_light(lights["cyan_light"], f0, 0.0)
        _kf_light(lights["neon_light"], f0, 130.0)

        # Release grip right as sandal slams onto floor in world space
        _kf_grip(f0, 0.0)
        _kf_loc_rot(sandal["root"], f0, (-0.04, 0.44, 0.45), (176.0, 2.0, 0.0))
        _kf_loc_rot(sandal["root"], f_slam, (0.0, 0.34, 0.017), (180.0, 0.0, 0.0))
        _kf_loc_rot(sandal["root"], f_end, (0.0, 0.34, 0.017), (180.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f_slam, (-0.23, 0.0, 1.39), (22.0, 0.0, 0.0))

        _kf_hide(dust["root"], f0, True)
        _kf_hide(dust["root"], f_slam, False)
        _kf_loc_rot(dust["root"], f_slam, (0.0, 0.36, 0.015), scale=(0.25, 0.25, 0.25))
        _kf_loc_rot(dust["root"], min(f_end, f_slam + 12), (0.0, 0.36, 0.025), scale=(2.2, 2.2, 1.4))
        _kf_hide(dust["root"], min(f_end, f_slam + 18), True)

        _kf_hide(speed_rig["root"], f0, True)
        _kf_hide(speed_rig["root"], f_slam + 2, False)

        _kf_fov(cam_data, f0, 98.0)
        _kf_fov(cam_data, f_slam + 5, 112.0)
        _kf_fov(cam_data, f_end, 112.0)
        _kf_dof(f0, 0.85)

        for fr in range(f0, f_end + 1, 2):
            if fr < f_slam:
                cy = _lerp(0.24, 0.42, (fr - f0) / max(1, f_slam - f0))
                cx = -0.02
                shake_r = 1.5
            else:
                su = (fr - f_slam) / max(1, (f_end - f_slam))
                cy = _lerp(0.45, 1.85, su)
                cx = -0.14 * math.sin(min(1.0, su * 1.4) * math.pi * 0.5) + 0.012 * math.sin(fr * 1.6)
                shake_r = 2.6
            cz = cam_h + 0.003 * abs(math.sin(fr * 1.8))
            pitch = 91.5 + 1.4 * math.sin(fr * 2.1)
            roll = shake_r * math.sin(fr * 1.5)
            yaw = 2.0 * math.cos(fr * 1.3)
            _kf_loc_rot(cam_obj, fr, (cx, cy, cz), (pitch, roll, yaw))
            _set_antennae_pose(ant_rig, fr, -14.0, 20.0, jitter=11.0)

        _kf_loc_rot(human["root"], f_end, (0.04, 1.75, 0.0), (0.0, 0.0, 170.0))

    # =========================================================================
    # SCENE 5: TINGGAL SEJENGKAL — Sprint toward dark fridge under-gap -> FOOT STOMPS!
    # =========================================================================
    if 5 in tmap:
        s5 = tmap[5]
        f0, f_end = s5["start_frame"], s5["end_frame"]
        f_stomp_start = f_at(5, max(1.6, s5["scene_duration_sec"] - 1.10))
        f_stomp_land = f_at(5, max(2.0, s5["scene_duration_sec"] - 0.50))

        _kf_hide(speed_rig["root"], f0, False)
        _kf_hide(speed_rig["root"], f_stomp_land, True)
        _kf_fov(cam_data, f0, 106.0)
        _kf_fov(cam_data, f_end, 96.0)
        _kf_dof(f0, 0.90)
        _kf_dof(f_end, 0.55)

        _kf_loc_rot(human["root"], f0, (0.14, 2.38, 0.0), (0.0, 0.0, 25.0))
        _kf_loc_rot(human["left_leg"], f0, (-0.22, 0.25, 0.42), (-18.0, 0.0, 0.0))
        _kf_loc_rot(human["left_leg"], f_stomp_start, (-0.22, 0.16, 0.36), (-12.0, 0.0, 0.0))
        _kf_loc_rot(human["left_leg"], f_stomp_land, (-0.24, 0.04, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["left_leg"], f_end, (-0.24, 0.04, 0.0), (0.0, 0.0, 0.0))

        for fr in range(f0, f_end + 1, 2):
            u = (fr - f0) / max(1, (f_end - f0))
            cy = _lerp(1.86, 2.24, min(1.0, u * 1.05))
            cx = -0.12 + 0.008 * math.sin(fr * 1.7)
            cz = cam_h + 0.0025 * abs(math.sin(fr * 2.0))
            pitch = 88.5 + (6.0 * max(0.0, (fr - f_stomp_start) / max(1, f_end - f_stomp_start)))
            roll = 1.8 * math.sin(fr * 1.6) if fr < f_stomp_land else 0.5
            _kf_loc_rot(cam_obj, fr, (cx, cy, cz), (pitch, roll, 0.0))
            _set_antennae_pose(ant_rig, fr, -8.0 if fr < f_stomp_land else 22.0, 14.0, jitter=9.0)

        _kf_light(lights["neon_light"], f0, 120.0)
        _kf_light(lights["neon_light"], f_stomp_land, 95.0)

    # =========================================================================
    # SCENE 6: TERKEPUNG! — Hard brake + Whip-pan Left, Right, Up (sandal in hand!)
    # =========================================================================
    if 6 in tmap:
        s6 = tmap[6]
        f0, f_end = s6["start_frame"], s6["end_frame"]
        f_brake = f_frac(6, 0.14)
        f_left_in = f_frac(6, 0.28)
        f_left_hold = f_frac(6, 0.42)
        f_right_in = f_frac(6, 0.54)
        f_right_hold = f_frac(6, 0.68)
        f_up_in = f_frac(6, 0.80)

        _kf_hide(speed_rig["root"], f0, True)
        _kf_fov(cam_data, f0, 96.0)
        _kf_fov(cam_data, f_up_in, 102.0)
        _kf_dof(f0, 0.45)
        _kf_dof(f_up_in, 0.75)
        _kf_light(lights["neon_light"], f0, 125.0)

        # Sandal locked back in right hand overhead!
        _kf_grip(f0, 1.0)
        _kf_loc_rot(sandal["root"], f0, (0.0, 0.02, -0.02), (90.0, 0.0, 0.0))
        _kf_loc_rot(human["root"], f0, (0.14, 2.38, 0.0), (0.0, 0.0, 22.0))
        _kf_loc_rot(human["left_leg"], f0, (-0.24, 0.04, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (154.0, 0.0, 5.0))
        _kf_loc_rot(human["right_arm"], f_end, (-0.23, 0.0, 1.39), (138.0, 0.0, 4.0))

        _kf_loc_rot(cam_obj, f0, (-0.12, 2.24, cam_h), (95.0, 0.0, 0.0))
        _kf_loc_rot(cam_obj, f_brake, (-0.12, 2.18, cam_h + 0.004), (98.0, -4.0, 0.0))
        _kf_loc_rot(cam_obj, f_left_in, (-0.12, 2.18, cam_h), (93.0, 5.0, 78.0))
        _kf_loc_rot(cam_obj, f_left_hold, (-0.12, 2.18, cam_h), (93.0, 3.0, 80.0))
        _kf_loc_rot(cam_obj, f_right_in, (-0.12, 2.18, cam_h), (93.0, -5.0, -76.0))
        _kf_loc_rot(cam_obj, f_right_hold, (-0.12, 2.18, cam_h), (93.0, -3.0, -74.0))
        _kf_loc_rot(cam_obj, f_up_in, (-0.12, 2.18, cam_h), (162.0, 4.0, -8.0))
        _kf_loc_rot(cam_obj, f_end, (-0.12, 2.18, cam_h), (168.0, -3.0, -4.0))

        for fr in range(f0, f_end + 1, 3):
            _set_antennae_pose(ant_rig, fr, 26.0, 18.0, jitter=14.0)

    # =========================================================================
    # SCENE 7: MODE TERBANG — Translucent amber wings at bottom corners + wobbly takeoff
    # =========================================================================
    if 7 in tmap:
        s7 = tmap[7]
        f0, f_end = s7["start_frame"], s7["end_frame"]
        f_wings = f_at(7, 1.35)

        _kf_hide(ant_rig["wing_l"], f0, True)
        _kf_hide(ant_rig["wing_r"], f0, True)
        _kf_hide(ant_rig["wing_l"], f_wings, False)
        _kf_hide(ant_rig["wing_r"], f_wings, False)

        # Sandal gripped in hand; backlight behind human keeps his face in deep dark shadow!
        _kf_grip(f0, 1.0)
        _kf_loc_rot(sandal["root"], f0, (0.0, 0.02, -0.02), (90.0, 0.0, 0.0))
        _kf_loc_rot(human["root"], f0, (0.04, 2.48, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["left_leg"], f0, (0.11, 0.0, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (105.0, 0.0, 12.0))
        _kf_light(lights["neon_light"], f0, 145.0)
        _kf_light(lights["rim_light"], f0, 360.0)

        _kf_fov(cam_data, f0, 98.0)
        _kf_fov(cam_data, f_wings, 106.0)
        _kf_fov(cam_data, f_end, 102.0)
        _kf_dof(f0, 1.15)
        _kf_dof(f_end, 1.10)

        for fr in range(f0, f_end + 1, 2):
            if fr < f_wings:
                u0 = (fr - f0) / max(1, f_wings - f0)
                cx = _lerp(-0.12, -0.05, u0)
                cy = _lerp(2.14, 1.75, u0)
                cz = cam_h + 0.015 * u0
                pitch = _lerp(135.0, 118.0, u0)
                roll = 4.0 * math.sin(fr * 1.4)
                yaw = 0.0
            else:
                uf = (fr - f_wings) / max(1, f_end - f_wings)
                cx = -0.05 + 0.24 * math.sin(uf * math.pi * 2.5)
                cy = _lerp(1.75, 1.25, uf)
                cz = _lerp(0.04, 1.46, uf ** 1.15)
                pitch = _lerp(116.0, 96.0, uf) + 5.0 * math.sin(fr * 0.7)
                roll = 14.0 * math.sin(uf * math.pi * 3.0) + 3.0 * math.cos(fr * 1.8)
                yaw = -12.0 * math.cos(uf * math.pi * 2.5)
                flap = 18.0 * math.sin(fr * 2.8)
                _kf_loc_rot(ant_rig["wing_l_pivot"], fr, rot_deg=(-8.0, flap, 10.0))
                _kf_loc_rot(ant_rig["wing_r_pivot"], fr, rot_deg=(-8.0, -flap, -10.0))

            _kf_loc_rot(cam_obj, fr, (cx, cy, cz), (pitch, roll, yaw))
            _set_antennae_pose(ant_rig, fr, 12.0, 22.0, jitter=12.0)

    # =========================================================================
    # SCENE 8: MAAF YA BANG — Dive to dark shadowed face -> drop sandal -> CUT TO BLACK 0.35s after scream!
    # =========================================================================
    if 8 in tmap:
        s8 = tmap[8]
        f0, f_end = s8["start_frame"], s8["end_frame"]
        f_drop = f_frac(8, 0.45)
        # Cut to black right at end (0.35s after scream starts, synced via cut_to_black_sec)
        f_black = max(f0 + 1, f_end - max(1, int(round(0.08 * fps))))

        _kf_hide(ant_rig["wing_l"], f0, False)
        _kf_hide(ant_rig["wing_r"], f0, False)
        _kf_hide(speed_rig["root"], f0, False)

        _kf_loc_rot(human["root"], f0, (0.0, 2.48, 0.0), (0.0, 0.0, 0.0))
        _kf_loc_rot(human["head"], f0, (0.0, 0.0, 1.46), (-8.0, 0.0, 0.0))
        _kf_loc_rot(human["head"], f_black, (0.0, 0.02, 1.46), (12.0, 0.0, 0.0))

        _kf_loc_rot(human["eye_l"], f0, scale=(1.0, 1.0, 1.0))
        _kf_loc_rot(human["eye_r"], f0, scale=(1.0, 1.0, 1.0))
        _kf_loc_rot(human["eye_l"], f_drop, scale=(1.50, 1.2, 1.50))
        _kf_loc_rot(human["eye_r"], f_drop, scale=(1.50, 1.2, 1.50))
        _kf_loc_rot(human["mouth"], f0, scale=(1.0, 1.0, 1.0))
        _kf_loc_rot(human["mouth"], f_drop, scale=(1.40, 1.0, 2.8))

        # Gripped at start of Scene 8, then released as he recoils & drops sandal in panic
        _kf_grip(f0, 1.0)
        _kf_grip(f_drop - 1, 1.0)
        _kf_grip(f_drop, 0.0)
        _kf_loc_rot(human["right_arm"], f0, (-0.23, 0.0, 1.39), (95.0, 0.0, 12.0))
        _kf_loc_rot(human["right_arm"], f_drop + 8, (-0.23, 0.0, 1.39), (135.0, -35.0, 45.0))
        _kf_loc_rot(sandal["root"], f_drop, (-0.30, 2.12, 1.36), (135.0, 35.0, -25.0))
        _kf_loc_rot(sandal["root"], f_black, (-0.42, 2.02, 0.18), (340.0, 190.0, 85.0))

        _kf_fov(cam_data, f0, 96.0)
        _kf_fov(cam_data, f_black, 108.0)
        _kf_dof(f0, 0.90)
        _kf_dof(f_black, 0.25)

        for fr in range(f0, f_black + 1, 2):
            u = (fr - f0) / max(1, (f_black - f0))
            ease = u ** 1.45
            cx = _lerp(0.05, 0.0, ease) + 0.014 * (1.0 - u) * math.sin(fr * 1.9)
            cy = _lerp(1.25, 2.24, ease)
            cz = _lerp(1.48, 1.64, ease) + 0.010 * (1.0 - u) * math.cos(fr * 2.1)
            pitch = _lerp(96.0, 91.0, ease)
            roll = 4.5 * math.sin(fr * 2.2) * (1.0 - 0.5 * u)
            _kf_loc_rot(cam_obj, fr, (cx, cy, cz), (pitch, roll, 0.0))
            _set_antennae_pose(ant_rig, fr, -10.0, 24.0, jitter=15.0)
            flap = 22.0 * math.sin(fr * 3.1)
            _kf_loc_rot(ant_rig["wing_l_pivot"], fr, rot_deg=(-8.0, flap, 12.0))
            _kf_loc_rot(ant_rig["wing_r_pivot"], fr, rot_deg=(-8.0, -flap, -12.0))

        # HARD CUT TO BLACK 0.35s after scream starts!
        _kf_hide(black_shutter, f_black - 1, True)
        _kf_hide(black_shutter, f_black, False)
        _kf_hide(black_shutter, f_end, False)

    scene.frame_start = 1
    scene.frame_end = int(manifest["total_frames"])
    return tmap


# =============================================================================
# PER-SCENE RENDER (WITH AUTO-RESUME PER FRAME) + MP4 ENCODING
# =============================================================================

def render_scene_clip(
    scene: bpy.types.Scene,
    scene_meta: Dict[str, Any],
    scenes_out_dir: Path,
    ffmpeg_bin: str,
    fps: int,
) -> Path:
    import time as _time

    sid = int(scene_meta["scene_id"])
    f_start = int(scene_meta["start_frame"])
    f_end = int(scene_meta["end_frame"])
    total_scene_frames = f_end - f_start + 1

    frames_dir = scenes_out_dir / f"scene_{sid:02d}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    skipped = 0
    rendered = 0
    first_frame_time: Optional[float] = None

    log("RENDER", f"Scene {sid:02d} | Frames {f_start}..{f_end} ({total_scene_frames} frames, auto-resume active)...")
    for fr in range(f_start, f_end + 1):
        frame_file = frames_dir / f"frame_{fr:04d}.png"
        if frame_file.exists() and frame_file.stat().st_size > 10_240:
            skipped += 1
            continue

        t0 = _time.monotonic()
        scene.frame_set(fr)
        scene.render.filepath = str(frame_file)
        bpy.ops.render.render(write_still=True)
        dt = _time.monotonic() - t0
        rendered += 1
        if first_frame_time is None:
            first_frame_time = dt
            rem = max(0, (f_end - fr))
            log("RENDER", f"Scene {sid:02d} | Frame {fr} took {dt:.2f}s (est. remaining ~{rem * dt:.1f}s)")

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
) -> Path:
    """Render 1 middle keyframe still for a scene and wrap it as a still MP4 matching VO duration."""
    sid = int(scene_meta["scene_id"])
    f_start = int(scene_meta["start_frame"])
    f_end = int(scene_meta["end_frame"])
    mid_frame = (f_start + f_end) // 2
    dur = float(scene_meta["scene_duration_sec"])

    out_png = scenes_out_dir / f"scene_{sid:02d}.png"
    scene.frame_set(mid_frame)
    scene.render.filepath = str(out_png)

    log("STORYBOARD", f"Rendering Scene {sid:02d} keyframe (frame {mid_frame}) -> {out_png.name}")
    bpy.ops.render.render(write_still=True)

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
    log("STORYBOARD", f"Scene {sid:02d} animatic clip ready ({dur:.2f}s) -> {out_mp4.name}")
    return out_png


def build_storyboard_contact_sheet(
    scene_ids: List[int],
    scenes_out_dir: Path,
    grid_out_path: Path,
    ffmpeg_bin: str,
) -> Path:
    """Combine rendered scene keyframes into a 2x4 contact sheet grid with Scene 01..08 labels."""
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    font_opt = f"fontfile={font_path}:" if font_path.exists() else ""

    inputs: List[str] = []
    filters: List[str] = []
    valid_labels: List[str] = []

    for idx, sid in enumerate(sorted(scene_ids)):
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
    parser = argparse.ArgumentParser(description="Blender Headless 3D Micro-POV Builder & Renderer")
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
    )
    parser.add_argument("--timing", type=str, default=None, help="Path to timing_manifest.json")
    parser.add_argument("--assets-dir", type=str, default=None, help="Override 02_assets cache directory")
    parser.add_argument("--work-dir", type=str, default=None, help="Override episode working directory")
    parser.add_argument("--mode", choices=["storyboard", "preview", "final"], default="preview")
    parser.add_argument(
        "--scene",
        type=int,
        default=None,
        help="Render ONLY a single scene_id (for fast partial revision)",
    )
    parser.add_argument("--save-blend", action="store_true", help="Save assembled .blend file before rendering")
    parser.add_argument("--no-render", action="store_true", help="Build .blend scene only without rendering frames")
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

    # Start from a completely clean Blender scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    configure_cycles_render(scene, args.mode, fps)

    tmap = build_ep001_animation(scene, spec, manifest, assets_dir)

    if args.save_blend or args.no_render:
        blend_path = work_dir / f"{spec['episode_id'].lower()}_{args.mode}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        log("BLENDER", f"Saved Blender project -> {blend_path}")

    if args.no_render:
        log("BLENDER", "--no-render active; scene assembly verified cleanly.")
        return 0

    scenes_out_dir = work_dir / "raw_render" / f"scenes_{args.mode}"
    scenes_out_dir.mkdir(parents=True, exist_ok=True)

    target_ids = [args.scene] if args.scene is not None else sorted(tmap.keys())
    for sid in target_ids:
        if sid not in tmap:
            log("ERROR", f"Scene {sid} not found in timing_manifest.json (available: {sorted(tmap.keys())})")
            return 1
        if args.mode == "storyboard":
            render_storyboard_keyframe(scene, tmap[sid], scenes_out_dir, ffmpeg_bin, fps)
        else:
            render_scene_clip(scene, tmap[sid], scenes_out_dir, ffmpeg_bin, fps)

    if args.mode == "storyboard":
        grid_ids = sorted(tmap.keys()) if len(target_ids) > 1 or args.scene is None else target_ids
        build_storyboard_contact_sheet(grid_ids, scenes_out_dir, work_dir / "storyboard_grid.png", ffmpeg_bin)

    log("RENDER", f"Completed rendering {len(target_ids)} scene(s) in mode '{args.mode}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
