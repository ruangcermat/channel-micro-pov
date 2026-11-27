#!/usr/bin/env python3
"""Universal Lighting, AgX Color Management & Colab T4 Cycles CUDA Preset (`Jadi Apa` Studio Core).

Colab T4 Fast Local Pipeline Standard (Zero EEVEE llvmpipe, Zero OptiX Black-Frame, Zero CPU Mix):
- Pure Cycles `CUDA` GPU ONLY: `compute_device_type = 'CUDA'`, `get_devices()`,
  `device.use = (device.type == 'CUDA')` (CPU strictly `False`), `scene.cycles.device = 'GPU'`
- Stable GPU Denoiser: `OPENIMAGEDENOISE` (`RGB_ALBEDO_NORMAL`, `prefilter='FAST'`, `denoising_use_gpu=True`)
  — NEVER `'OPTIX'` denoiser (produces solid black PNG frames on Colab T4 driver!)
- Fast Sampling & Light Paths: `samples=12`, `adaptive_threshold=0.05`, `adaptive_min_samples=4`,
  `max_bounces=4` (`diffuse=2, glossy=2, transmission=2, transparent=4, volume=0`),
  `caustics_reflective=False`, `caustics_refractive=False`, `sample_clamp_indirect=10.0`,
  `use_persistent_data=True`, `use_simplify=True`, `texture_limit_render='1024'`,
  `PNG compression=0` (zero CPU compression bottleneck on fast local `/tmp/` SSD).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy


def detect_cuda_gpus() -> Tuple[bool, List[str]]:
    """Explicitly configure Cycles `CUDA` ONLY via `get_devices()`, disabling CPU (`d.use = d.type == 'CUDA'`)."""
    has_cuda = False
    gpu_names: List[str] = []
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "CUDA"
        if hasattr(prefs, "get_devices"):
            prefs.get_devices()
        prefs.refresh_devices()
        cuda_devices = [d for d in prefs.devices if d.type == "CUDA"]
        if cuda_devices:
            for d in prefs.devices:
                # STRICT: enable ONLY CUDA GPU devices; NEVER mix Colab's 2-core CPU with GPU!
                d.use = d.type == "CUDA"
            has_cuda = True
            gpu_names = [d.name for d in cuda_devices]
    except Exception:
        pass
    return has_cuda, gpu_names


def configure_render_engine(
    scene: bpy.types.Scene,
    engine_choice: str,
    mode: str,
    fps: int = 24,
    log_fn=None,
    allow_cpu: bool = False,
) -> Dict[str, Any]:
    """Configure Pure Cycles CUDA GPU + OIDN GPU (FAST) + 1024px Simplify + Uncompressed PNG + AgX."""
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    engine_upper = engine_choice.upper()

    if mode == "storyboard":
        res_x, res_y = 270, 480
        cyc_samples = 4
        max_bounces = 2
    elif mode == "motion_check":
        res_x, res_y = 360, 640
        cyc_samples = 8
        max_bounces = 2
    elif mode == "preview":
        res_x, res_y = 540, 960
        cyc_samples = 10
        max_bounces = 4
    else:
        # Colab T4 Production Master: 1080x1920 @ 12 adaptive samples + OIDN GPU FAST + 1024px texture limit
        res_x, res_y = 1080, 1920
        cyc_samples = 12
        max_bounces = 4

    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 0  # Zero CPU compression overhead on local /tmp/ SSD!

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

    has_cuda, gpu_names = detect_cuda_gpus()
    strict_cuda = (not allow_cpu) and (engine_upper not in ("CYCLES_CPU", "CPU"))

    if strict_cuda and not has_cuda:
        msg = (
            "PREFLIGHT FAILED: Black frame or no CUDA GPU — "
            "0 perangkat NVIDIA CUDA terdeteksi! Di Google Colab, aktifkan Runtime -> Ubah jenis runtime -> GPU T4."
        )
        if log_fn:
            log_fn("ERROR", msg)
        else:
            print(f"[ERROR] {msg}", flush=True)
        raise RuntimeError(msg)

    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU" if has_cuda else "CPU"
    scene.render.use_persistent_data = True

    # Simplify & texture memory optimization (cuts 4K Poly Haven textures down to crisp 1024px for 9:16 mobile!)
    scene.render.use_simplify = True
    if hasattr(scene.cycles, "texture_limit_render"):
        scene.cycles.texture_limit_render = "1024"
    if hasattr(scene.cycles, "use_tiling"):
        scene.cycles.use_tiling = False

    # Adaptive sampling & clean light path clamping (zero fireflies, zero caustics overhead)
    scene.cycles.samples = cyc_samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.12 if mode == "storyboard" else 0.05
    scene.cycles.adaptive_min_samples = min(cyc_samples, 4)

    eff_bounces = max_bounces
    scene.cycles.max_bounces = eff_bounces
    scene.cycles.diffuse_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.glossy_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.transmission_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.transparent_max_bounces = 4
    scene.cycles.volume_bounces = 0
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.sample_clamp_indirect = 10.0

    # Stable GPU Denoiser: ALWAYS OpenImageDenoise (NEVER OptiX denoiser — produces solid black PNGs on Colab T4!)
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    if hasattr(scene.cycles, "denoising_input_passes"):
        scene.cycles.denoising_input_passes = "RGB_ALBEDO" if mode == "storyboard" else "RGB_ALBEDO_NORMAL"
    if hasattr(scene.cycles, "denoising_prefilter"):
        scene.cycles.denoising_prefilter = "FAST"
    if hasattr(scene.cycles, "denoising_use_gpu"):
        try:
            scene.cycles.denoising_use_gpu = bool(has_cuda)
        except Exception:
            pass

    gpu_label = ", ".join(gpu_names) if gpu_names else "CPU ONLY (--allow-cpu)"
    active_tag = "CYCLES (CUDA GPU ONLY)" if has_cuda else "CYCLES (CPU)"
    banner = f"Active: {active_tag} | GPU Devices: {gpu_label} | Denoiser: OPENIMAGEDENOISE (GPU={has_cuda}, FAST)"
    if log_fn:
        log_fn("ENGINE", banner)
        log_fn(
            "BLENDER",
            f"Cycles T4 Fast configured | Mode: {mode} ({res_x}x{res_y}, samples={cyc_samples}, "
            f"adapt={scene.cycles.adaptive_threshold}/min={scene.cycles.adaptive_min_samples}, "
            f"bounces={eff_bounces}/vol=0/caustics=OFF/clamp=10.0, tex_limit=1024, PNG comp=0, "
            f"persistent=True, MB={scene.render.use_motion_blur}) | AgX: ON",
        )
    else:
        print(f"[ENGINE] {banner}", flush=True)

    return {
        "engine": "CYCLES",
        "has_gpu": has_cuda,
        "backend": "CUDA" if has_cuda else "CPU",
        "gpu_names": gpu_names,
        "denoiser": "OPENIMAGEDENOISE",
        "strict_no_cpu": strict_cuda,
    }


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
