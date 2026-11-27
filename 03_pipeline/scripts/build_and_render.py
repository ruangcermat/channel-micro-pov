#!/usr/bin/env python3
"""Generic 3D Micro-POV Episode Runner (`Jadi Apa` / `Jadi Apa 3D` Studio Engine).

ZERO episode-specific hardcoding! Dynamically loads `<episode_dir>/scene_builder.py` so
producing EP002–EP100+ can NEVER break EP001.

Usage (Blender 5.2.2 Linux headless):
  blender --background --python 03_pipeline/scripts/build_and_render.py -- \\
      --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json \\
      --mode storyboard --engine CYCLES [--scene 4] [--save-blend]

2-Hard-Gate Modes:
- `storyboard`   (Gate 1): Fast hero frames (450x800, 12 samples, post.py) -> `storyboard_sheet.png`
- `motion_check` (Gate 2): Full 24fps (360x640, 8 samples, EEVEE w/ Cycles fallback, motion blur ON)
- `preview`              : Full 24fps (540x960, 16 samples, motion blur ON)
- `final`                : Full 24fps (1080x1920, 24 samples, motion blur ON, Kaggle 2xT4 / Colab T4)
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time as _time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
from mathutils import Vector

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
for _p in (str(SCRIPT_DIR), str(PIPELINE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import lighting_utils as lgt_lib
from core import mpfb_helpers as mh
from core import post as post_lib
from pipeline_utils import (
    check_ffmpeg_available,
    get_repo_root,
    load_and_validate_spec,
    load_json,
    log,
    resolve_assets_dir,
    resolve_episode_work_dir,
    resolve_family_ready_blend,
    resolve_mas_dimas_blend,
)


def load_episode_scene_builder(spec_path: Path):
    """Dynamically import `scene_builder.py` from the episode's own directory."""
    ep_dir = spec_path.resolve().parent
    builder_path = ep_dir / "scene_builder.py"
    if not builder_path.exists():
        raise FileNotFoundError(
            f"Episode scene_builder.py tidak ditemukan di {builder_path}. "
            f"Setiap episode wajib memiliki builder terisolasi sendiri."
        )
    mod_name = f"episode_scene_builder_{ep_dir.name}"
    spec = importlib.util.spec_from_file_location(mod_name, str(builder_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Gagal memuat modul episode: {builder_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# AUTOMATED QC CHECKLIST (TROUBLESHOOTING.md + STUDIO ANTI-BUG VERIFICATION)
# =============================================================================

def run_qc_checks(
    scene: bpy.types.Scene,
    human: Dict[str, Any],
    build_info: Dict[str, Any],
    ep_builder: Any,
    fps: int,
) -> Dict[str, Any]:
    """Run universal TROUBLESHOOTING.md checklist before rendering."""
    issues: List[str] = []

    # 1. Missing/unpacked images -> would render pink!
    missing_imgs = [
        i.filepath
        for i in bpy.data.images
        if i.source == "FILE" and not i.packed_file and not os.path.exists(bpy.path.abspath(i.filepath))
    ]
    if missing_imgs:
        issues.append(f"MISSING_TEXTURES: {missing_imgs}")

    # 2. Shoes must be completely removed (Mas Dimas is barefoot / uses prop sandals!)
    shoes_found = [o.name for o in bpy.data.objects if "shoes" in o.name.lower()]
    if shoes_found:
        issues.append(f"SHOES_NOT_REMOVED: {shoes_found}")

    # 3. Unparented MPFB2 Human.* meshes -> would float off body!
    unparented = [
        o.name
        for o in bpy.data.objects
        if o.type == "MESH" and o.name.startswith("Human.") and o.parent is None
    ]
    if unparented:
        issues.append(f"UNPARENTED_HUMAN_PARTS: {unparented}")

    # 4. `$md-*` body shape keys must NOT be zeroed!
    body = human["body"]
    md_keys = [k for k in body.data.shape_keys.key_blocks if k.name.startswith("$md-")]
    nonzero_md = [k.name for k in md_keys if abs(k.value) > 1e-4]
    if md_keys and not nonzero_md:
        issues.append("BODY_SHAPE_KEYS_ZEROED: all $md-* keys are 0")

    # 5. Hand prop grip distance check (if episode reports sandal_grip_distances)
    grip_map = build_info.get("sandal_grip_distances", {})
    bad_grip = {sid: round(d, 3) for sid, d in grip_map.items() if sid <= 7 and d > 0.25}
    if bad_grip:
        issues.append(f"FLOATING_HAND_PROP: {bad_grip}")

    # 6. Camera unobstructed raycast check across all storyboard hero beats
    cam_obj = build_info["cam_obj"]
    dg = bpy.context.evaluated_depsgraph_get()
    blocked_scenes: List[Tuple[str, str, float]] = []
    check_frames: List[Tuple[str, int]] = []
    for sid, s_meta in sorted(build_info["tmap"].items()):
        if sid == 1 and hasattr(ep_builder, "pick_scene01a_frame"):
            check_frames.append(("01A", ep_builder.pick_scene01a_frame(s_meta, fps)))
            check_frames.append(("01B", ep_builder.pick_storyboard_frame(s_meta, fps)))
        else:
            check_frames.append((f"{sid:02d}", ep_builder.pick_storyboard_frame(s_meta, fps)))

    for label, fr in check_frames:
        scene.frame_set(fr)
        bpy.context.view_layer.update()
        origin = cam_obj.matrix_world.translation.copy()
        fwd = (cam_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        hit, hit_loc, _, _, hit_obj, _ = scene.ray_cast(dg, origin + fwd * 0.015, fwd, distance=0.06)
        if hit and hit_obj and not hit_obj.name.startswith(("Cockroach_", "Speed_Line", "CutToBlack")):
            blocked_scenes.append((label, hit_obj.name, round((hit_loc - origin).length, 4)))
    if blocked_scenes:
        issues.append(f"CAMERA_BLOCKED: {blocked_scenes}")

    report = {
        "passed": len(issues) == 0,
        "missing_textures": missing_imgs,
        "shoes_found": shoes_found,
        "unparented_human_parts": unparented,
        "md_body_keys_preserved": len(nonzero_md),
        "sandal_grip_max_dist_m": {k: round(v, 3) for k, v in sorted(grip_map.items())},
        "camera_blocked": blocked_scenes,
        "issues": issues,
    }
    if report["passed"]:
        log(
            "QC",
            f"ALL CHECKS PASSED | MISSING=[] | shoes=0 | unparented=0 | "
            f"$md keys={len(nonzero_md)} intact | prop_dist={report['sandal_grip_max_dist_m']} | "
            f"camera_clear=ALL ({len(check_frames)} panels)",
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
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 8
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
            bpy.ops.render.render(write_still=True)

    if apply_post and out_png.exists():
        post_lib.apply_camera_look(out_png, out_png, seed=7 + frame)

    return _time.monotonic() - t0


def _compute_scene_frames(f_start: int, f_end: int, frame_step: int = 1, max_frames: int = 0) -> List[int]:
    """Compute exact sorted list of frames to render for a scene."""
    step = max(1, int(frame_step))
    frames = list(range(f_start, f_end + 1, step))
    if not frames:
        frames = [f_start]
    if max_frames > 0:
        frames = frames[:max_frames]
    elif step > 1 and frames[-1] != f_end:
        frames.append(f_end)
    return frames


def render_scene_clip(
    scene: bpy.types.Scene,
    scene_meta: Dict[str, Any],
    scenes_out_dir: Path,
    ffmpeg_bin: str,
    fps: int,
    apply_post: bool = True,
    frame_step: int = 1,
    max_frames: int = 0,
) -> Path:
    sid = int(scene_meta["scene_id"])
    f_start = int(scene_meta["start_frame"])
    f_end = int(scene_meta["end_frame"])
    total_scene_frames = f_end - f_start + 1
    target_frames = _compute_scene_frames(f_start, f_end, frame_step=frame_step, max_frames=max_frames)

    frames_dir = scenes_out_dir / f"scene_{sid:02d}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    skipped = 0
    rendered = 0
    step_tag = f", step={frame_step}" if frame_step > 1 else ""
    max_tag = f", max_frames={max_frames}" if max_frames > 0 else ""
    log(
        "RENDER",
        f"Scene {sid:02d} | Frames {f_start}..{f_end} ({len(target_frames)}/{total_scene_frames} frames{step_tag}{max_tag}, "
        f"auto-resume >10KB, post={apply_post})",
    )

    for idx, fr in enumerate(target_frames):
        frame_file = frames_dir / f"frame_{fr:04d}.png"
        if frame_file.exists() and frame_file.stat().st_size > 10_240:
            skipped += 1
            continue
        dt = _render_single_frame_resilient(scene, fr, frame_file, apply_post=apply_post)
        rendered += 1
        if rendered == 1 or rendered % 12 == 0 or idx == len(target_frames) - 1:
            rem = max(0, len(target_frames) - 1 - idx)
            log("RENDER", f"FRAME {fr}/{f_end} (Scene {sid:02d}, {idx + 1}/{len(target_frames)}) {dt:.1f}s | est. scene rem ~{rem * dt:.0f}s")

    log("RENDER", f"Scene {sid:02d} frames ready (rendered={rendered}, resumed/skipped={skipped})")

    out_mp4 = scenes_out_dir / f"scene_{sid:02d}.mp4"
    if frame_step == 1 and max_frames == 0:
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
    else:
        # Exact-duration stepped playblast or smoke-test MP4 encoded smoothly at native 24fps!
        concat_txt = frames_dir / "frames_concat.txt"
        lines: List[str] = []
        for idx, fr in enumerate(target_frames):
            png_path = (frames_dir / f"frame_{fr:04d}.png").resolve()
            safe_p = str(png_path).replace("'", "'\\''")
            if idx + 1 < len(target_frames):
                span = max(1, target_frames[idx + 1] - fr)
            else:
                span = max(1, (f_end - fr + 1) if max_frames == 0 else 1)
            dur = span / float(fps)
            lines.append(f"file '{safe_p}'")
            lines.append(f"duration {dur:.6f}")
        # FFmpeg concat demuxer quirk: repeat last file entry so final duration is respected!
        last_safe = str((frames_dir / f"frame_{target_frames[-1]:04d}.png").resolve()).replace("'", "'\\''")
        lines.append(f"file '{last_safe}'")
        concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

        exact_dur = (total_scene_frames if max_frames == 0 else len(target_frames)) / float(fps)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-r",
            str(fps),
            "-t",
            f"{exact_dur:.6f}",
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
    ep_builder: Any,
    ffmpeg_bin: str,
    fps: int,
    apply_post: bool = True,
) -> Path:
    sid = int(scene_meta["scene_id"])
    dur = float(scene_meta["scene_duration_sec"])

    if sid == 1 and hasattr(ep_builder, "pick_scene01a_frame"):
        fr_a = ep_builder.pick_scene01a_frame(scene_meta, fps)
        out_a = scenes_out_dir / "scene_01a.png"
        log("STORYBOARD", f"Rendering Scene 01A frame {fr_a} -> {out_a.name}")
        dt_a = _render_single_frame_resilient(scene, fr_a, out_a, apply_post=apply_post)
        log("STORYBOARD", f"Scene 01A rendered in {dt_a:.1f}s (post.py={'ON' if apply_post else 'OFF'})")

        fr_b = ep_builder.pick_storyboard_frame(scene_meta, fps)
        out_b = scenes_out_dir / "scene_01b.png"
        log("STORYBOARD", f"Rendering Scene 01B frame {fr_b} -> {out_b.name}")
        dt_b = _render_single_frame_resilient(scene, fr_b, out_b, apply_post=apply_post)
        log("STORYBOARD", f"Scene 01B rendered in {dt_b:.1f}s (post.py={'ON' if apply_post else 'OFF'})")

        out_png = scenes_out_dir / "scene_01.png"
        shutil.copy2(out_b, out_png)
    else:
        hero_frame = ep_builder.pick_storyboard_frame(scene_meta, fps)
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


def render_adaptive_storyboard_keyframes(
    scene: bpy.types.Scene,
    keyframes: List[Dict[str, Any]],
    scenes_out_dir: Path,
    apply_post: bool = True,
) -> Path:
    """Render an adaptive list of transition keyframes (270x480, 4 samples + OIDN) & write storyboard_keyframes.json."""
    import json as _json

    scenes_out_dir.mkdir(parents=True, exist_ok=True)
    rendered_meta: List[Dict[str, Any]] = []
    total = len(keyframes)
    for idx, kf in enumerate(keyframes, start=1):
        code = str(kf["code"])
        fr = int(kf["frame"])
        safe_slug = code.lower().replace(" ", "_")
        out_png = scenes_out_dir / f"kf_{idx:02d}_{safe_slug}.png"
        log("STORYBOARD", f"[{idx:02d}/{total:02d}] Rendering keyframe {code} (fr={fr}, t={float(kf.get('time_sec', 0.0)):.2f}s) -> {out_png.name}")
        dt = _render_single_frame_resilient(scene, fr, out_png, apply_post=apply_post)
        log("STORYBOARD", f"[{idx:02d}/{total:02d}] Keyframe {code} done in {dt:.1f}s (post.py={'ON' if apply_post else 'OFF'})")
        entry = dict(kf)
        entry["image_path"] = str(out_png.resolve())
        rendered_meta.append(entry)

    kf_json = scenes_out_dir / "storyboard_keyframes.json"
    kf_json.write_text(_json.dumps(rendered_meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log("STORYBOARD", f"Saved {len(rendered_meta)} adaptive keyframe descriptors -> {kf_json}")
    return kf_json


def build_studio_storyboard_sheet(
    spec_path: Path,
    timing_path: Path,
    scenes_out_dir: Path,
    sheet_out_path: Path,
) -> Optional[Path]:
    sheet_script = SCRIPT_DIR / "build_storyboard_sheet.py"
    if not sheet_script.exists():
        log("WARN", f"build_storyboard_sheet.py not found at {sheet_script}")
        return None
    py_bin = shutil.which("python3") or sys.executable
    try:
        subprocess.run(
            [
                py_bin,
                str(sheet_script),
                "--spec",
                str(spec_path),
                "--timing",
                str(timing_path),
                "--scenes-dir",
                str(scenes_out_dir),
                "--out",
                str(sheet_out_path),
                "--max-per-sheet",
                "8",
            ],
            check=True,
        )
        log("STORYBOARD", f"Adaptive multi-keyframe storyboard sheets ready in {sheet_out_path.parent}")
        return sheet_out_path
    except Exception as exc:
        log("WARN", f"Could not generate storyboard sheets via {py_bin}: {exc}")
        return None


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Generic 3D Micro-POV Episode Runner (Jadi Apa Studio)")
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
    )
    parser.add_argument("--timing", type=str, default=None, help="Path to timing_manifest.json")
    parser.add_argument("--assets-dir", type=str, default=None, help="Override 02_assets cache directory")
    parser.add_argument("--work-dir", type=str, default=None, help="Override episode working directory")
    parser.add_argument("--mas-dimas-blend", type=str, default=None, help="Override path to mas_dimas_ready.blend")
    parser.add_argument("--family-blend", type=str, default=None, help="Override fallback path to family_ready.blend")
    parser.add_argument(
        "--mode",
        choices=["storyboard", "motion_check", "preview", "final"],
        default="storyboard",
    )
    parser.add_argument("--engine", choices=["CYCLES", "EEVEE", "AUTO"], default="CYCLES")
    parser.add_argument("--scene", type=int, default=None, help="Render ONLY a single scene_id")
    parser.add_argument("--save-blend", action="store_true", help="Pack & save assembled .blend file")
    parser.add_argument("--bake-all", action="store_true", help="Force full frame-by-frame bake even in storyboard mode")
    parser.add_argument("--no-post", action="store_true", help="Disable post.py camera look pass")
    parser.add_argument("--no-render", action="store_true", help="Build & QC .blend scene only without rendering")
    parser.add_argument("--build-mas-dimas", action="store_true", help="Rebuild mas_dimas_ready.blend & front check PNG")
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Render every K-th frame (default 1 = full 24fps on GPU; >1 for fast CPU stepped playblast held at 24fps)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Limit rendered frames per scene (0 = all; e.g. 2 for 2-frame final smoke test)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=0,
        help="Optional Cycles sample override (0 = use mode preset: 4 storyboard, 8 motion_check, 16 preview, 24 final)",
    )
    return parser.parse_args(extra)


def main() -> int:
    args = parse_args()
    ffmpeg_bin = check_ffmpeg_available()

    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    assets_dir = resolve_assets_dir(args.assets_dir)
    work_dir = resolve_episode_work_dir(spec_path, args.work_dir)
    timing_path = Path(args.timing).resolve() if args.timing else (work_dir / "timing_manifest.json")

    # Resolve permanent mascot Mas Dimas master blend (or build it automatically from family_ready.blend!)
    mas_dimas_blend = Path(args.mas_dimas_blend).resolve() if args.mas_dimas_blend else resolve_mas_dimas_blend(assets_dir)
    if args.build_mas_dimas or mas_dimas_blend is None or not mas_dimas_blend.exists():
        family_blend = Path(args.family_blend).resolve() if args.family_blend else resolve_family_ready_blend(assets_dir)
        if family_blend is None or not family_blend.exists():
            log(
                "ERROR",
                "Baik `mas_dimas_ready.blend` maupun `family_ready.blend` tidak ditemukan! "
                "Pastikan Google Drive ter-mount atau passing `--mas-dimas-blend` / `--family-blend`.",
            )
            return 1
        target_master = assets_dir / "models_3d" / "mas_dimas_ready.blend"
        front_png = work_dir / "mas_dimas_front_check.png" if args.build_mas_dimas else None
        mas_dimas_blend = mh.build_mas_dimas_master(family_blend, target_master, front_check_png=front_png)
        if args.build_mas_dimas:
            log("MAS_DIMAS", f"Master build & front check selesai -> {mas_dimas_blend}")
            return 0

    if not timing_path.exists():
        log("ERROR", f"timing_manifest.json not found at {timing_path}. Run generate_tts.py first (Audio-First!).")
        return 1
    manifest = load_json(timing_path)
    fps = int(manifest.get("fps", 24))

    ep_builder = load_episode_scene_builder(spec_path)
    log("RUNNER", f"Loaded isolated episode builder: {ep_builder.__file__}")
    log("BLENDER", f"Opening permanent mascot Mas Dimas master: {mas_dimas_blend}")

    human = mh.load_mpfb2_human_base(mas_dimas_blend, target_height_m=1.68)
    scene = bpy.context.scene
    lgt_lib.configure_render_engine(scene, args.engine, args.mode, fps, log_fn=log)
    if args.samples and args.samples > 0 and scene.render.engine == "CYCLES":
        scene.cycles.samples = int(args.samples)
        log("BLENDER", f"Sample override active: Cycles samples = {scene.cycles.samples}")

    # Narrow baked frames cleanly for Adaptive Multi-Keyframe Storyboard, single-scene, stepped playblast, or smoke tests!
    bake_frames: Optional[List[int]] = None
    adaptive_kfs: Optional[List[Dict[str, Any]]] = None
    frame_step = max(1, int(args.frame_step))
    max_frames = max(0, int(args.max_frames))
    if args.mode == "storyboard" and hasattr(ep_builder, "get_storyboard_keyframes"):
        all_kfs = ep_builder.get_storyboard_keyframes(spec, manifest, fps)
        adaptive_kfs = (
            [k for k in all_kfs if int(k.get("scene_id", 0)) == args.scene]
            if args.scene is not None
            else all_kfs
        )
        if not args.bake_all and not args.save_blend:
            bf_set = {1}
            for k in all_kfs:
                bf_set.add(int(k["frame"]))
            if hasattr(ep_builder, "get_storyboard_extra_frames"):
                bf_set.update(ep_builder.get_storyboard_extra_frames(manifest, fps))
            bake_frames = sorted(bf_set)
    elif args.mode == "storyboard" and not args.bake_all and not args.save_blend:
        if hasattr(ep_builder, "get_storyboard_extra_frames"):
            bake_frames = ep_builder.get_storyboard_extra_frames(manifest, fps)
        else:
            bake_frames = [1] + [ep_builder.pick_storyboard_frame(s, fps) for s in manifest["scenes"]]
    elif not args.bake_all and not args.save_blend and (args.scene is not None or frame_step > 1 or max_frames > 0):
        chosen_scenes = (
            [s for s in manifest["scenes"] if int(s["scene_id"]) == args.scene]
            if args.scene is not None
            else manifest["scenes"]
        )
        bf_set = set()
        for s in chosen_scenes:
            sf = _compute_scene_frames(
                int(s["start_frame"]),
                int(s["end_frame"]),
                frame_step=frame_step,
                max_frames=max_frames,
            )
            for fr in sf:
                bf_set.add(fr)
                # Bake neighbor frames +/- 1 when motion blur is active so shutter interpolation is smooth!
                if scene.render.use_motion_blur:
                    if fr > int(s["start_frame"]):
                        bf_set.add(fr - 1)
                    if fr < int(s["end_frame"]):
                        bf_set.add(fr + 1)
        # Also include storyboard hero frames for QC raycast accuracy
        if hasattr(ep_builder, "pick_storyboard_frame"):
            for s in manifest["scenes"]:
                bf_set.add(ep_builder.pick_storyboard_frame(s, fps))
        if hasattr(ep_builder, "pick_scene01a_frame") and manifest["scenes"]:
            bf_set.add(ep_builder.pick_scene01a_frame(manifest["scenes"][0], fps))
        bake_frames = sorted(bf_set)

    build_info = ep_builder.build_episode_scene(
        scene,
        spec,
        manifest,
        assets_dir,
        human,
        mode=args.mode,
        bake_frames=bake_frames,
    )
    tmap = build_info["tmap"]

    run_qc_checks(scene, human, build_info, ep_builder, fps)

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
    # Gate 2 motion_check skips heavy post.py by default for max speed unless final/preview/storyboard
    apply_post = (not args.no_post) and (args.mode != "motion_check")

    if args.mode == "storyboard" and adaptive_kfs is not None:
        render_adaptive_storyboard_keyframes(scene, adaptive_kfs, scenes_out_dir, apply_post=apply_post)
        build_studio_storyboard_sheet(spec_path, timing_path, scenes_out_dir, work_dir / "storyboard_sheet_1.png")
        log("RENDER", f"Completed Adaptive Multi-Keyframe Fast Storyboard ({len(adaptive_kfs)} panels).")
        return 0

    target_ids = [args.scene] if args.scene is not None else sorted(tmap.keys())
    for sid in target_ids:
        if sid not in tmap:
            log("ERROR", f"Scene {sid} not found in timing_manifest.json (available: {sorted(tmap.keys())})")
            return 1
        if args.mode == "storyboard":
            render_storyboard_keyframe(scene, tmap[sid], scenes_out_dir, ep_builder, ffmpeg_bin, fps, apply_post=apply_post)
        else:
            render_scene_clip(
                scene,
                tmap[sid],
                scenes_out_dir,
                ffmpeg_bin,
                fps,
                apply_post=apply_post,
                frame_step=frame_step,
                max_frames=max_frames,
            )

    if args.mode == "storyboard":
        grid_ids = sorted(tmap.keys()) if len(target_ids) > 1 or args.scene is None else target_ids
        build_storyboard_contact_sheet(grid_ids, scenes_out_dir, work_dir / "storyboard_grid.png", ffmpeg_bin)
        if args.scene is None:
            build_studio_storyboard_sheet(spec_path, timing_path, scenes_out_dir, work_dir / "storyboard_sheet.png")

    log("RENDER", f"Completed rendering {len(target_ids)} scene(s) in mode '{args.mode}' ({args.engine}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
