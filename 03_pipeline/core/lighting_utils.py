#!/usr/bin/env python3
"""Universal Lighting, AgX Color Management & Render Engine Presets (`Jadi Apa` Studio Core).

Supports Fast Local Cloud Production modes with STRICT engine enforcement (ZERO silent CPU fallback!):
- `EEVEE` (Default fastest):
    * Detects `BLENDER_EEVEE_NEXT` (Blender 4.2–4.5) or `BLENDER_EEVEE` (Blender 5.0+ / <=4.1)
    * `taa_render_samples = 16`, heavy raytracing/screen-space refraction OFF, Principled BSDF SSS stripped
    * NEVER silently falls back to Cycles CPU!
- `CYCLES_GPU` (Strict NVIDIA GPU):
    * Calls `cycles.preferences.get_devices()`, activates `OPTIX` (fallback `CUDA`), enables ALL GPUs & disables CPU
    * `samples = 10`, `adaptive_threshold = 0.05`, `max_bounces = 4` (`diffuse=2, glossy=2, transmission=2, volume=0`),
      `use_persistent_data = True`
    * If 0 GPU devices detected -> RAISES RuntimeError immediately (NEVER silently falls back to CPU!)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy


def optimize_materials_for_eevee(log_fn=None) -> int:
    """Strip heavy Subsurface Scattering (SSS), deduplicate GLTF `.001` materials, & trim fill-light shadows for fast EEVEE."""
    import re as _re

    # 1. Deduplicate identical Poly Haven GLTF `.001/.002` material clones (cuts shader compiles by ~60%!)
    deduped = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not getattr(obj.data, "materials", None):
            continue
        for idx, mat in enumerate(obj.data.materials):
            if mat is None:
                continue
            m_dot = _re.match(r"^(.+)\.\d{3}$", mat.name)
            if not m_dot:
                continue
            base_mat = bpy.data.materials.get(m_dot.group(1))
            if base_mat is not None and base_mat is not mat and not mat.name.startswith("Human."):
                obj.data.materials[idx] = base_mat
                deduped += 1

    # 2. Strip heavy Subsurface Scattering (SSS) & screen-space refraction for fast Principled BSDF
    touched = 0
    seen_trees = set()

    def _walk_tree(nt: bpy.types.NodeTree) -> None:
        nonlocal touched
        if nt is None or nt.as_pointer() in seen_trees:
            return
        seen_trees.add(nt.as_pointer())
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                changed = False
                for inp_name in ("Subsurface Weight", "Subsurface", "Subsurface Scale", "Transmission Weight", "Transmission"):
                    inp = n.inputs.get(inp_name)
                    if inp is not None:
                        if inp.is_linked:
                            for lk in list(inp.links):
                                nt.links.remove(lk)
                            changed = True
                        if hasattr(inp, "default_value") and float(inp.default_value) != 0.0:
                            inp.default_value = 0.0
                            changed = True
                if changed:
                    touched += 1
            elif n.type == "GROUP" and getattr(n, "node_tree", None) is not None:
                _walk_tree(n.node_tree)

    for mat in bpy.data.materials:
        if mat is None:
            continue
        if hasattr(mat, "use_screen_refraction"):
            try:
                mat.use_screen_refraction = False
            except Exception:
                pass
        if mat.use_nodes and mat.node_tree:
            _walk_tree(mat.node_tree)

    # 3. Disable virtual shadow maps on soft fill/bounce lights (keep shadows ON for key/backlight/spot lights!)
    fill_culled = 0
    for lgt in bpy.data.lights:
        lname = lgt.name.lower()
        is_fill = any(tok in lname for tok in ("fill", "fg_", "foreground", "puddle", "cyan", "night", "bedroom"))
        if is_fill and getattr(lgt, "use_shadow", False):
            lgt.use_shadow = False
            fill_culled += 1

    if log_fn:
        log_fn(
            "ENGINE",
            f"EEVEE fast Principled BSDF optimization applied (stripped SSS/refraction on {touched} nodes, "
            f"deduped {deduped} GLTF material slots, culled shadows on {fill_culled} fill lights)",
        )
    return touched


def detect_cycles_gpus() -> Tuple[bool, Optional[str], List[str]]:
    """Explicitly query Cycles GPU devices via `get_devices()`, preferring OPTIX then CUDA (disabling CPU)."""
    has_gpu = False
    gpu_backend: Optional[str] = None
    gpu_names: List[str] = []
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for compute_type in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = compute_type
                if hasattr(prefs, "get_devices"):
                    prefs.get_devices()
                prefs.refresh_devices()
                gpu_devices = [d for d in prefs.devices if d.type == compute_type]
                if gpu_devices:
                    for d in prefs.devices:
                        d.use = d.type == compute_type
                    has_gpu = True
                    gpu_backend = compute_type
                    gpu_names = [d.name for d in gpu_devices]
                    break
            except Exception:
                continue
    except Exception:
        pass
    return has_gpu, gpu_backend, gpu_names


def _resolve_eevee_engine_id() -> str:
    """Return `BLENDER_EEVEE_NEXT` (Blender 4.2–4.5) or `BLENDER_EEVEE` (Blender 5.0+ and <=4.1)."""
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    if bpy.app.version >= (4, 2, 0) and "BLENDER_EEVEE_NEXT" in ids:
        return "BLENDER_EEVEE_NEXT"
    if "BLENDER_EEVEE" in ids:
        return "BLENDER_EEVEE"
    if "BLENDER_EEVEE_NEXT" in ids:
        return "BLENDER_EEVEE_NEXT"
    raise RuntimeError(f"EEVEE render engine tidak ditemukan di Blender {bpy.app.version} (available: {ids})")


def configure_render_engine(
    scene: bpy.types.Scene,
    engine_choice: str,
    mode: str,
    fps: int = 24,
    log_fn=None,
) -> Dict[str, Any]:
    """Configure EEVEE (fast headless) or strict CYCLES_GPU (OPTIX/CUDA) + AgX. NEVER silently drops to CPU!"""
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    engine_upper = engine_choice.upper()

    if mode == "storyboard":
        res_x, res_y = 270, 480
        cyc_samples, eevee_samples = 4, 8
        max_bounces = 2
    elif mode == "motion_check":
        res_x, res_y = 360, 640
        cyc_samples, eevee_samples = 8, 8
        max_bounces = 2
    elif mode == "preview":
        res_x, res_y = 540, 960
        cyc_samples, eevee_samples = 10, 12
        max_bounces = 4
    else:
        res_x, res_y = 1080, 1920
        cyc_samples, eevee_samples = 10, 16
        max_bounces = 4

    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 15

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

    has_gpu, gpu_backend, gpu_names = detect_cycles_gpus()
    gpu_label = ", ".join(gpu_names) if gpu_names else "None (Headless EGL / Software GL)"

    # -------------------------------------------------------------------------
    # OPTION 1: EEVEE (Fastest! NEVER falls back silently to Cycles CPU!)
    # -------------------------------------------------------------------------
    if engine_upper == "EEVEE":
        eevee_id = _resolve_eevee_engine_id()
        scene.render.engine = eevee_id
        scene.render.use_motion_blur = False  # Avoid expensive multi-step velocity passes in headless EEVEE!
        ee = scene.eevee
        for k, v in (
            ("taa_render_samples", eevee_samples),
            ("use_shadows", True),
            ("use_raytracing", False),          # OFF: heavy screen-space raytracing crawls on headless EGL!
            ("use_volumetric_shadows", False),
            ("use_ssr", False),                 # Blender 4.1- compat
            ("use_ssr_refraction", False),      # Blender 4.1- compat
            ("use_gtao", False),
            ("shadow_ray_count", 1),
            ("shadow_step_count", 4),
            ("shadow_resolution_scale", 0.5),
            ("shadow_pool_size", "128"),
            ("volumetric_tile_size", "8"),
        ):
            try:
                setattr(ee, k, v)
            except Exception:
                pass
        banner = f"Active: {eevee_id} | GPU Devices: {gpu_label}"
        if log_fn:
            log_fn("ENGINE", banner)
            log_fn(
                "BLENDER",
                f"EEVEE Fast configured ({eevee_id}) | Mode: {mode} ({res_x}x{res_y}, {eevee_samples} TAA samples, "
                f"raytracing=OFF, shadows=ON, {fps}fps, MB=False) | AgX: ON",
            )
        else:
            print(f"[ENGINE] {banner}", flush=True)
        return {
            "engine": eevee_id,
            "has_gpu": has_gpu,
            "backend": gpu_backend,
            "gpu_names": gpu_names,
            "strict_no_cpu": True,
        }

    # -------------------------------------------------------------------------
    # OPTION 2: CYCLES_GPU / CYCLES_FAST (Strict GPU — HARD FAIL if 0 GPUs!)
    # -------------------------------------------------------------------------
    strict_gpu = engine_upper in ("CYCLES_GPU", "CYCLES_FAST")
    if strict_gpu and not has_gpu:
        msg = (
            f"[ENGINE] Active: NONE (ABORTED) | GPU Devices: 0 NVIDIA GPUs detected!\n"
            f"ERROR: --engine {engine_upper} dipilih tetapi tidak ada GPU NVIDIA (OPTIX/CUDA) yang terdeteksi.\n"
            f"Di Google Colab, buka menu: Runtime -> Ubah jenis runtime -> pilih 'GPU T4', lalu jalankan ulang.\n"
            f"Skrip dihentikan paksa agar TIDAK jatuh diam-diam ke Cycles CPU (14 menit/frame)!"
        )
        if log_fn:
            log_fn("ERROR", msg)
        else:
            print(msg, flush=True)
        raise RuntimeError(msg)

    scene.render.engine = "CYCLES"
    scene.render.use_persistent_data = True
    scene.cycles.device = "GPU" if has_gpu else "CPU"
    scene.cycles.samples = cyc_samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = (
        0.12 if mode == "storyboard" else (0.10 if mode == "motion_check" else 0.05)
    )
    eff_bounces = 1 if (mode == "motion_check" and not has_gpu) else max_bounces
    scene.cycles.max_bounces = eff_bounces
    scene.cycles.diffuse_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.glossy_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.transmission_bounces = 2 if eff_bounces >= 3 else 1
    scene.cycles.volume_bounces = 0
    scene.cycles.transparent_max_bounces = 4
    scene.cycles.use_denoising = True

    use_optix_denoiser = has_gpu and gpu_backend == "OPTIX" and mode != "storyboard"
    denoiser_name = "OPTIX" if use_optix_denoiser else "OPENIMAGEDENOISE"
    try:
        scene.cycles.denoiser = denoiser_name
    except Exception:
        denoiser_name = "OPENIMAGEDENOISE"
        scene.cycles.denoiser = denoiser_name
    if hasattr(scene.cycles, "denoising_input_passes"):
        scene.cycles.denoising_input_passes = (
            "RGB_ALBEDO" if (mode == "storyboard" or (mode == "motion_check" and not has_gpu)) else "RGB_ALBEDO_NORMAL"
        )
    if denoiser_name == "OPENIMAGEDENOISE":
        try:
            scene.cycles.denoising_use_gpu = has_gpu
        except Exception:
            pass

    active_tag = f"CYCLES ({gpu_backend})" if has_gpu else "CYCLES (CPU)"
    banner = f"Active: {active_tag} | GPU Devices: {', '.join(gpu_names) if gpu_names else 'CPU ONLY (legacy mode)'}"
    if log_fn:
        log_fn("ENGINE", banner)
        log_fn(
            "BLENDER",
            f"Cycles configured ({engine_upper}) | Mode: {mode} ({res_x}x{res_y}, {cyc_samples} samples, "
            f"adapt={scene.cycles.adaptive_threshold}, bounces={eff_bounces}/vol=0, {fps}fps, "
            f"MB={scene.render.use_motion_blur}, persistent=True) | Denoiser: {denoiser_name} | AgX: ON",
        )
    else:
        print(f"[ENGINE] {banner}", flush=True)
    return {
        "engine": "CYCLES",
        "has_gpu": has_gpu,
        "backend": gpu_backend,
        "gpu_names": gpu_names,
        "denoiser": denoiser_name,
        "strict_no_cpu": strict_gpu,
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
