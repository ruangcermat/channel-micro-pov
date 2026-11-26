#!/usr/bin/env python3
"""Universal Lighting, AgX Color Management & Render Engine Presets (`Jadi Apa` Studio Core).

Supports 2-Hard-Gate production modes:
- `storyboard`   (Gate 1): 450×800, 12 Cycles samples, crisp stills + `storyboard_sheet.png`
- `motion_check` (Gate 2): 360×640, 8 samples, EEVEE with automatic Cycles low-sample fallback
                           on headless Linux without EGL, `use_motion_blur=True` (`shutter=0.40`)
- `preview`              : 540×960, 16 samples, 24fps GPU motion preview
- `final`                : 1080×1920, 24 samples, 24fps production master
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import bpy


def configure_render_engine(
    scene: bpy.types.Scene,
    engine_choice: str,
    mode: str,
    fps: int = 24,
    log_fn=None,
) -> Dict[str, Any]:
    """Configure Cycles (multi-GPU OptiX/CUDA + OIDN) or EEVEE (with headless fallback) + AgX."""
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    engine_upper = engine_choice.upper()

    if mode == "storyboard":
        # Fast Draft QC (< 60s total for all 9 panels!): 1/4 of 1080x1920 + 4 samples + OIDN, motion blur OFF
        res_x, res_y = 270, 480
        cyc_samples, eevee_samples = 4, 8
        max_bounces = 2
    elif mode == "motion_check":
        res_x, res_y = 360, 640
        cyc_samples, eevee_samples = 8, 8
        max_bounces = 2
    elif mode == "preview":
        res_x, res_y = 540, 960
        cyc_samples, eevee_samples = 16, 20
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

    # Motion blur ON for all moving video renders (shutter=0.40 for smooth shake & whip-pan!)
    scene.render.use_motion_blur = mode != "storyboard"
    scene.render.motion_blur_shutter = 0.40

    # AgX Medium High Contrast with controlled exposure (anti highlight blowout)
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

    # Gate 2 motion_check prefers EEVEE if GPU/EGL is available, else auto-falls back to Cycles 8-sample!
    want_eevee = engine_upper == "EEVEE" or (mode == "motion_check" and engine_upper == "AUTO")
    if want_eevee:
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
            if log_fn:
                log_fn(
                    "BLENDER",
                    f"EEVEE configured ({eevee_id}) | Mode: {mode} ({res_x}x{res_y}, {eevee_samples} samples, "
                    f"{fps}fps, MB={scene.render.use_motion_blur}) | {device_used}",
                )
            return {"engine": eevee_id, "has_gpu": has_gpu, "backend": gpu_backend}
        elif log_fn:
            log_fn(
                "BLENDER",
                f"EEVEE headless without GPU/EGL — auto-fallback to Cycles low-sample ({cyc_samples} samples) + OIDN.",
            )

    # Motion blur ON for all GPU video renders and all preview/final renders (shutter=0.40);
    # skipped only on CPU-only motion_check fallback to avoid 2-3x slower per-frame mesh deformation BVH rebuilds.
    scene.render.use_motion_blur = (mode != "storyboard") and (has_gpu or mode != "motion_check")
    scene.render.motion_blur_shutter = 0.40

    scene.render.engine = "CYCLES"
    scene.render.use_persistent_data = True
    scene.cycles.device = "GPU" if has_gpu else "CPU"
    scene.cycles.samples = cyc_samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.12 if mode == "storyboard" else (0.10 if mode == "motion_check" else 0.06)
    eff_bounces = 1 if (mode == "motion_check" and not has_gpu) else max_bounces
    scene.cycles.max_bounces = eff_bounces
    scene.cycles.diffuse_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.glossy_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.transmission_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.transparent_max_bounces = 4 if (mode == "motion_check" and not has_gpu) else 6
    scene.cycles.use_denoising = True
    # Always OpenImageDenoise (Kaggle/Colab T4 driver fails with OptiX denoiser!)
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(scene.cycles, "denoising_input_passes"):
        scene.cycles.denoising_input_passes = (
            "RGB_ALBEDO" if (mode == "storyboard" or (mode == "motion_check" and not has_gpu)) else "RGB_ALBEDO_NORMAL"
        )
    try:
        scene.cycles.denoising_use_gpu = has_gpu
    except Exception:
        pass

    if log_fn:
        log_fn(
            "BLENDER",
            f"Cycles configured | Mode: {mode} ({res_x}x{res_y}, {cyc_samples} samples, {fps}fps, "
            f"MB={scene.render.use_motion_blur}) | Device: {device_used} | OIDN: ON | AgX: ON",
        )
    return {"engine": "CYCLES", "has_gpu": has_gpu, "backend": gpu_backend}


def add_area_light(
    scene: bpy.types.Scene,
    name: str,
    loc: Tuple[float, float, float],
    rot_rad: Tuple[float, float, float],
    size: float,
    size_y: float,
    energy: float,
    color: Tuple[float, float, float],
    spread_deg: Optional[float] = None,
) -> Tuple[bpy.types.Object, bpy.types.Light]:
    ld = bpy.data.lights.new(name=name, type="AREA")
    ld.shape = "RECTANGLE"
    ld.size = size
    ld.size_y = size_y
    ld.energy = energy
    ld.color = color
    if spread_deg is not None and hasattr(ld, "spread"):
        ld.spread = math.radians(spread_deg)
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = rot_rad
    scene.collection.objects.link(lo)
    return lo, ld


def setup_hdri_world(
    scene: bpy.types.Scene,
    hdri_path: Optional[Path] = None,
    tint_rgba: Tuple[float, float, float, float] = (0.14, 0.28, 0.58, 1.0),
    tint_mix: float = 0.88,
    strength: float = 0.08,
    world_name: str = "MicroPOV_World",
) -> bpy.types.Node:
    """Create a tinted HDRI world (or clean ambient color fallback) and return the Background node."""
    world = bpy.data.worlds.new(world_name)
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    if hdri_path and hdri_path.exists():
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(hdri_path), check_existing=True)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = tint_mix
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = tint_rgba
        nt.links.new(env.outputs["Color"], sock_a)
        nt.links.new(sock_out, bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (tint_rgba[0] * 0.2, tint_rgba[1] * 0.2, tint_rgba[2] * 0.25, 1.0)

    bg.inputs["Strength"].default_value = strength
    return bg
