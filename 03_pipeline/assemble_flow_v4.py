#!/usr/bin/env python3
"""Mobile-First v4.0 Google Flow Auto-Assembler & Master Exporter (`Jadi Apa`).

Pulls `vo_master.wav`, `vo_timing_manifest.json`, `subtitles.ass`, and `raw_clips/shot_*.mp4`
from Google Drive `04_episodes/<ep_id>/`, then:
  1. Trims excess tail duration from every Flow clip cleanly to match each VO segment duration
     100% accurately via FFmpeg (ZERO freeze-frame padding!).
  2. Mixes 3 balanced audio layers normalized to broadcast `-14 LUFS`:
     - Layer 1: `vo_master.wav` at `-6 dB` (dominant reference & sidechain trigger)
     - Layer 2: Native foley from Flow clips at `-10 dB` with smooth sidechain auto-ducking under VO
     - Layer 3: CC0 BGM at `-22 dB` with smooth sidechain auto-ducking under VO
  3. Applies a light cinematic post-look (`eq` + subtle `vignette`) and burns clean bottom-only
     karaoke `subtitles.ass` (stripping any legacy `TopBadge` events so ZERO double text occurs!).
  4. Exports 1 master vertical video `final_<ep_id>.mp4` (`1080x1920`, `libx264`, `-crf 18`,
     `-pix_fmt yuv420p`, `+faststart`, AAC `192k` 48kHz stereo) directly to Drive `04_episodes/<ep_id>/`,
     and cleans up temporary `/tmp/` files automatically.

Usage:
  python3 03_pipeline/assemble_flow_v4.py --ep ep001_kecoak_dapur
  python3 03_pipeline/assemble_flow_v4.py --ep ep001_kecoak_dapur --no-drive --work-dir /tmp/test_flow_v4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent

DEFAULT_DRIVE_EPISODES_FOLDER_ID = "1RS6RuYzydBZodpaTVPKL97EAa2_jOGON"
DEFAULT_DRIVE_ASSETS_FOLDER_ID = "1dcthq7su13Kp92Uk8v-bEicGsvvNV2IX"


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def check_ffmpeg_tools() -> Tuple[str, str]:
    ff = shutil.which("ffmpeg")
    fp = shutil.which("ffprobe")
    if not ff or not fp:
        raise RuntimeError("ffmpeg dan ffprobe wajib tersedia di PATH!")
    return ff, fp


# =============================================================================
# GOOGLE DRIVE CLI HELPERS (`gdrive`)
# =============================================================================

def _gdrive_json(args: List[str]) -> Any:
    cmd = ["gdrive", "--json", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gdrive command failed ({' '.join(cmd)}):\n{proc.stderr or proc.stdout}")
    out = proc.stdout.strip()
    return json.loads(out) if out else {}


def _find_child(parent_id: str, name: str, is_folder: bool) -> Optional[str]:
    items = _gdrive_json(["readonly", "ls", parent_id])
    if not isinstance(items, list):
        return None
    for item in items:
        mime = item.get("mimeType", "")
        want_dir = mime == "application/vnd.google-apps.folder"
        if item.get("name") == name and want_dir == is_folder:
            return str(item["id"])
    return None


def _download_drive_file(file_id: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["gdrive", "readonly", "download", file_id, "--out", str(dest)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Gagal mengunduh Drive file {file_id} -> {dest}:\n{proc.stderr or proc.stdout}")
    return dest


def upload_or_update_drive_file(local_path: Path, parent_id: str) -> str:
    existing_id = _find_child(parent_id, local_path.name, is_folder=False)
    if existing_id:
        _gdrive_json(["mutate", "update", existing_id, str(local_path)])
        log("DRIVE", f"Updated {local_path.name} in-place (ID: {existing_id})")
        return existing_id
    res = _gdrive_json(["mutate", "upload", str(local_path), "--parent", parent_id])
    fid = str(res.get("id", "")) if isinstance(res, dict) else ""
    log("DRIVE", f"Uploaded {local_path.name} (ID: {fid})")
    return fid


def pull_episode_from_drive(
    ep_id: str,
    work_dir: Path,
    episodes_folder_id: str,
) -> str:
    """Download `vo_master.wav`, `vo_timing_manifest.json`, `subtitles.ass`, & `raw_clips/shot_*` from Drive."""
    ep_folder_id = _find_child(episodes_folder_id, ep_id, is_folder=True)
    if not ep_folder_id:
        raise FileNotFoundError(f"Folder Drive `04_episodes/{ep_id}/` tidak ditemukan di parent {episodes_folder_id}!")

    ep_items = _gdrive_json(["readonly", "ls", ep_folder_id])
    by_name = {item["name"]: item for item in ep_items if isinstance(item, dict)}

    for req_name in ("vo_master.wav", "vo_timing_manifest.json", "subtitles.ass"):
        item = by_name.get(req_name)
        if not item:
            raise FileNotFoundError(
                f"File wajib `{req_name}` belum ada di Drive `04_episodes/{ep_id}/`! "
                f"Jalankan `03_pipeline/generate_vo_v4.py --ep {ep_id}` terlebih dahulu."
            )
        _download_drive_file(str(item["id"]), work_dir / req_name)
        log("DRIVE", f"Pulled {req_name}")

    raw_clips_item = by_name.get("raw_clips")
    if not raw_clips_item or raw_clips_item.get("mimeType") != "application/vnd.google-apps.folder":
        raise FileNotFoundError(
            f"Folder `raw_clips/` tidak ditemukan di Drive `04_episodes/{ep_id}/`! "
            f"Unggah klip `shot_01.mp4 .. shot_NN.mp4` dari HP terlebih dahulu."
        )

    clips_dir = work_dir / "raw_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_items = _gdrive_json(["readonly", "ls", str(raw_clips_item["id"])])
    downloaded = 0
    for c in clip_items:
        if c.get("mimeType") == "application/vnd.google-apps.folder":
            continue
        cname = str(c.get("name", ""))
        if re.match(r"^shot_\d+\.(mp4|mov|mkv|webm)$", cname, flags=re.IGNORECASE):
            _download_drive_file(str(c["id"]), clips_dir / cname)
            downloaded += 1
    log("DRIVE", f"Pulled {downloaded} raw Google Flow clip(s) from Drive `04_episodes/{ep_id}/raw_clips/`")
    return ep_folder_id


# =============================================================================
# CLIP PROBING, STRICT TRIMMING (ZERO FREEZE FRAME!), & BGM RESOLUTION
# =============================================================================

def probe_media(media_path: Path, ffprobe_bin: str) -> Dict[str, Any]:
    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json",
        str(media_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    dur = float(info.get("format", {}).get("duration", 0.0) or 0.0)
    return {
        "duration_sec": dur,
        "has_audio": has_audio,
        "width": int(v_stream.get("width", 0) or 0),
        "height": int(v_stream.get("height", 0) or 0),
    }


def _find_clip_for_shot(clips_dir: Path, shot_id: int, preferred_name: str) -> Optional[Path]:
    cand = clips_dir / preferred_name
    if cand.exists():
        return cand
    for ext in (".mp4", ".MP4", ".mov", ".MOV", ".mkv", ".webm"):
        for stem in (f"shot_{shot_id:02d}", f"shot_{shot_id}"):
            p = clips_dir / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def trim_and_normalize_shot(
    raw_clip: Path,
    out_clip: Path,
    target_dur: float,
    fps: int,
    ffmpeg_bin: str,
    ffprobe_bin: str,
) -> Path:
    """Normalize clip to 1080x1920 @ `fps` + 48kHz stereo foley and trim strictly to `target_dur` (NO freeze frame!)."""
    meta = probe_media(raw_clip, ffprobe_bin)
    clip_dur = meta["duration_sec"]
    has_audio = meta["has_audio"]

    pts_filter = ""
    if clip_dur > 0.0 and clip_dur < target_dur - 0.05:
        ratio = target_dur / clip_dur
        if ratio > 1.25:
            raise RuntimeError(
                f"Klip `{raw_clip.name}` terlalu pendek ({clip_dur:.2f}s) untuk segmen VO {target_dur:.2f}s "
                f"(>25% lebih pendek — dilarang freeze frame!). Generate ulang klip minimal {int(target_dur) + 1}s di Flow."
            )
        log(
            "TRIM_WARN",
            f"{raw_clip.name} sedikit lebih pendek ({clip_dur:.2f}s < {target_dur:.2f}s); "
            f"menyesuaikan tempo gerak lembut {ratio:.3f}x (TANPA freeze frame).",
        )
        pts_filter = f"setpts={ratio:.6f}*PTS,"

    vf = (
        f"{pts_filter}scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,fps={fps},format=yuv420p"
    )
    fade_out_st = max(0.0, target_dur - 0.02)

    out_clip.parent.mkdir(parents=True, exist_ok=True)
    if has_audio:
        atempo_audio = ""
        if clip_dur > 0.0 and clip_dur < target_dur - 0.05:
            inv_ratio = max(0.5, min(2.0, clip_dur / target_dur))
            atempo_audio = f"atempo={inv_ratio:.5f},"
        af = (
            f"{atempo_audio}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=0:{target_dur:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.015,afade=t=out:st={fade_out_st:.4f}:d=0.018"
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(raw_clip),
            "-vf", vf,
            "-af", af,
            "-t", f"{target_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
            str(out_clip),
        ]
    else:
        # Clip has no native audio stream -> attach clean 48kHz stereo silence so concat never breaks
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(raw_clip),
            "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={target_dur:.4f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-vf", vf,
            "-t", f"{target_dur:.4f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
            str(out_clip),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg trim gagal untuk {raw_clip.name}:\n{proc.stderr[-1500:]}")
    log(
        "TRIM",
        f"{raw_clip.name} ({clip_dur:.2f}s -> trimmed cleanly to {target_dur:.2f}s, foley={'ON' if has_audio else 'SILENT'})",
    )
    return out_clip


def resolve_bgm_file(
    bgm_arg: Optional[str],
    manifest: Dict[str, Any],
    work_dir: Path,
    use_drive: bool,
    drive_assets_folder_id: str,
) -> Optional[Path]:
    """Locate a CC0 BGM file locally or pull it from Google Drive `02_assets/bgm/`."""
    bgm_ref = (bgm_arg or str(manifest.get("bgm_id") or "")).strip()
    if not bgm_ref or bgm_ref.lower() in ("none", "silence", "none_cut_silence"):
        return None

    direct = Path(bgm_ref)
    if direct.exists():
        return direct.resolve()

    local_dirs = [
        REPO_ROOT / "02_assets" / "bgm",
        Path("/tmp/ep001_assets/bgm"),
        work_dir / "bgm",
    ]
    for d in local_dirs:
        for ext in ("", ".mp3", ".wav"):
            cand = d / f"{bgm_ref}{ext}"
            if cand.exists():
                return cand.resolve()

    if use_drive:
        try:
            bgm_folder_id = _find_child(drive_assets_folder_id, "bgm", is_folder=True)
            if bgm_folder_id:
                for ext in ("", ".mp3", ".wav"):
                    fid = _find_child(bgm_folder_id, f"{bgm_ref}{ext}", is_folder=False)
                    if fid:
                        dest = work_dir / "bgm" / f"{bgm_ref}{ext or '.mp3'}"
                        _download_drive_file(fid, dest)
                        log("DRIVE", f"Pulled BGM CC0 -> {dest.name}")
                        return dest
        except Exception as exc:
            log("WARN", f"BGM '{bgm_ref}' tidak dapat ditarik dari Drive ({exc}); lanjut tanpa BGM.")
    return None


def sanitize_ass_strip_top_badges(ass_path: Path, out_ass: Path) -> Path:
    """Enforce v4.0 rule (g): strip any legacy `TopBadge` dialogue lines so ZERO double text ever renders."""
    lines = ass_path.read_text(encoding="utf-8").splitlines()
    clean = [ln for ln in lines if not (ln.startswith("Dialogue:") and ",TopBadge," in ln)]
    removed = len(lines) - len(clean)
    if removed:
        log("SUBS", f"Stripped {removed} legacy TopBadge event(s) to guarantee ZERO double text.")
    out_ass.write_text("\n".join(clean) + "\n", encoding="utf-8")
    return out_ass


# =============================================================================
# 3-LAYER AUDIO MIX (-14 LUFS) + SUBTITLE BURN-IN + FINAL EXPORT
# =============================================================================

def compose_master_video(
    concat_video: Path,
    vo_master_wav: Path,
    ass_path: Path,
    bgm_file: Optional[Path],
    output_mp4: Path,
    total_dur: float,
    ffmpeg_bin: str,
    vo_db: float = -6.0,
    foley_db: float = -10.0,
    bgm_db: float = -22.0,
    apply_post_look: bool = True,
) -> Path:
    """Mix VO (-6dB) + ducked native Flow foley (-10dB) + ducked CC0 BGM (-22dB) -> -14 LUFS + burn ASS."""
    inputs: List[str] = [
        "-i", str(concat_video),   # 0: concatenated Flow video + native foley audio
        "-i", str(vo_master_wav),  # 1: master VO
    ]
    filter_parts: List[str] = []

    # Layer 1: Dominant VO (-6 dB) split into mix bus + 2 sidechain ducking triggers
    filter_parts.append(
        f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"atrim=0:{total_dur:.4f},asetpts=PTS-STARTPTS,volume={vo_db:.1f}dB,"
        f"asplit=3[vo_mix][vo_sc_foley][vo_sc_bgm]"
    )

    # Layer 2: Native Flow foley (-10 dB) with sidechain ducking under VO
    filter_parts.append(
        f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"atrim=0:{total_dur:.4f},asetpts=PTS-STARTPTS,volume={foley_db:.1f}dB[foley_raw]"
    )
    filter_parts.append(
        "[foley_raw][vo_sc_foley]sidechaincompress=threshold=0.015:ratio=4.5:attack=20:release=220:makeup=1[foley_ducked]"
    )

    # Layer 3: CC0 BGM (-22 dB) looped + sidechain ducking under VO
    if bgm_file and bgm_file.exists():
        inputs.extend(["-stream_loop", "-1", "-i", str(bgm_file)])
        fade_out = max(0.0, total_dur - 0.20)
        filter_parts.append(
            f"[2:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=0:{total_dur:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.10,afade=t=out:st={fade_out:.4f}:d=0.18,"
            f"volume={bgm_db:.1f}dB[bgm_raw]"
        )
        filter_parts.append(
            "[bgm_raw][vo_sc_bgm]sidechaincompress=threshold=0.015:ratio=6:attack=25:release=260:makeup=1[bgm_ducked]"
        )
    else:
        filter_parts.append("[vo_sc_bgm]anullsink")
        filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.4f}[bgm_ducked]")

    # Master 3-layer mix + broadcast -14 LUFS loudness normalization
    filter_parts.append(
        "[vo_mix][foley_ducked][bgm_ducked]amix=inputs=3:duration=first:normalize=0,"
        f"atrim=0:{total_dur:.4f},loudnorm=I=-14:TP=-1.5:LRA=11[a_master]"
    )

    # Video chain: light cinema grade + subtle vignette BEFORE crisp bottom karaoke ASS subtitles!
    ass_escaped = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    if apply_post_look:
        filter_parts.append(
            f"[0:v]eq=contrast=1.03:saturation=1.05:gamma=0.99,"
            f"vignette=angle=PI/5.6:mode=backward,ass='{ass_escaped}'[v_out]"
        )
    else:
        filter_parts.append(f"[0:v]ass='{ass_escaped}'[v_out]")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin, "-y",
        *inputs,
        "-filter_complex", ";\n".join(filter_parts),
        "-map", "[v_out]",
        "-map", "[a_master]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-t", f"{total_dur:.4f}",
        str(output_mp4),
    ]

    bgm_tag = bgm_file.name if bgm_file else "NONE"
    log("COMPOSE_V4", f"Mixing VO ({vo_db:.0f}dB) + ducked Flow Foley ({foley_db:.0f}dB) + BGM ({bgm_tag}, {bgm_db:.0f}dB) -> -14 LUFS + ASS...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg final assembly gagal:\n{proc.stderr[-2500:]}")

    size_mb = output_mp4.stat().st_size / (1024 * 1024)
    log("COMPOSE_V4", f"SUCCESS! Exported {output_mp4} ({size_mb:.2f} MB, {total_dur:.2f}s, 1080x1920, -14 LUFS)")
    return output_mp4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mobile-First v4.0 Google Flow Auto-Assembler (trim clips cleanly + 3-layer -14 LUFS + karaoke ASS -> Drive)."
    )
    parser.add_argument("--ep", type=str, required=True, help="Episode slug (e.g. ep001_kecoak_dapur)")
    parser.add_argument("--work-dir", type=str, default=None, help="Local temp working dir (default /tmp/flow_v4_assemble/<ep>)")
    parser.add_argument("--bgm", type=str, default=None, help="Optional BGM path or ID (overrides manifest bgm_id)")
    parser.add_argument("--fps", type=int, default=24, help="Output framerate (default 24)")
    parser.add_argument("--vo-db", type=float, default=-6.0)
    parser.add_argument("--foley-db", type=float, default=-10.0)
    parser.add_argument("--bgm-db", type=float, default=-22.0)
    parser.add_argument("--no-post", action="store_true", help="Disable light FFmpeg grade+vignette post-look")
    parser.add_argument("--no-drive", action="store_true", help="Read/write locally in --work-dir without Google Drive")
    parser.add_argument("--keep-temp", action="store_true", help="Keep local /tmp working folder after export")
    parser.add_argument(
        "--drive-episodes-folder",
        type=str,
        default=os.environ.get("MICRO_POV_DRIVE_EPISODES_ID", DEFAULT_DRIVE_EPISODES_FOLDER_ID),
    )
    parser.add_argument(
        "--drive-assets-folder",
        type=str,
        default=os.environ.get("MICRO_POV_DRIVE_ASSETS_ID", DEFAULT_DRIVE_ASSETS_FOLDER_ID),
    )
    args = parser.parse_args()

    ffmpeg_bin, ffprobe_bin = check_ffmpeg_tools()
    ep_id = args.ep.strip()
    work_dir = Path(args.work_dir).resolve() if args.work_dir else (Path("/tmp/flow_v4_assemble") / ep_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    ep_drive_id: Optional[str] = None
    if not args.no_drive:
        ep_drive_id = pull_episode_from_drive(ep_id, work_dir, args.drive_episodes_folder)

    manifest_path = work_dir / "vo_timing_manifest.json"
    vo_master_wav = work_dir / "vo_master.wav"
    ass_raw_path = work_dir / "subtitles.ass"
    clips_dir = work_dir / "raw_clips"

    for req in (manifest_path, vo_master_wav, ass_raw_path):
        if not req.exists():
            raise FileNotFoundError(f"File wajib tidak ditemukan: {req}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    segments = manifest.get("segments") or []
    if not segments:
        raise ValueError(f"`segments` kosong di {manifest_path}!")

    # Verify ALL required Flow clips exist before starting FFmpeg!
    matched_clips: List[Tuple[Dict[str, Any], Path]] = []
    missing: List[str] = []
    for seg in segments:
        sid = int(seg["shot_id"])
        pref = str(seg.get("shot_filename") or f"shot_{sid:02d}.mp4")
        clip_p = _find_clip_for_shot(clips_dir, sid, pref)
        if clip_p is None:
            missing.append(pref)
        else:
            matched_clips.append((seg, clip_p))
    if missing:
        raise FileNotFoundError(
            f"Klip Google Flow belum lengkap di {clips_dir}! Kurang: {', '.join(missing)}"
        )

    # Trim & normalize every Flow clip cleanly (NO freeze frames!)
    trimmed_dir = work_dir / "_trimmed_shots"
    trimmed_clips: List[Path] = []
    for seg, raw_clip in matched_clips:
        sid = int(seg["shot_id"])
        target_dur = float(seg["duration_sec"])
        out_shot = trimmed_dir / f"shot_{sid:02d}_norm.mkv"
        trim_and_normalize_shot(
            raw_clip,
            out_shot,
            target_dur=target_dur,
            fps=args.fps,
            ffmpeg_bin=ffmpeg_bin,
            ffprobe_bin=ffprobe_bin,
        )
        trimmed_clips.append(out_shot)

    # Concatenate all trimmed clips seamlessly
    concat_txt = work_dir / "_shots_concat.txt"
    concat_txt.write_text(
        "\n".join(f"file '{str(p.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for p in trimmed_clips) + "\n",
        encoding="utf-8",
    )
    concat_video = work_dir / "_concat_flow.mkv"
    subprocess.run(
        [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c", "copy",
            str(concat_video),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    clean_ass = sanitize_ass_strip_top_badges(ass_raw_path, work_dir / "_subtitles_clean.ass")
    bgm_file = resolve_bgm_file(
        args.bgm,
        manifest,
        work_dir,
        use_drive=not args.no_drive,
        drive_assets_folder_id=args.drive_assets_folder,
    )

    total_dur = float(manifest["total_duration_sec"])
    out_mp4 = work_dir / f"final_{ep_id}.mp4"
    compose_master_video(
        concat_video=concat_video,
        vo_master_wav=vo_master_wav,
        ass_path=clean_ass,
        bgm_file=bgm_file,
        output_mp4=out_mp4,
        total_dur=total_dur,
        ffmpeg_bin=ffmpeg_bin,
        vo_db=args.vo_db,
        foley_db=args.foley_db,
        bgm_db=args.bgm_db,
        apply_post_look=not args.no_post,
    )

    if not args.no_drive and ep_drive_id:
        fid = upload_or_update_drive_file(out_mp4, ep_drive_id)
        log("EXPORT", f"Uploaded ONLY final MP4 -> Drive `04_episodes/{ep_id}/{out_mp4.name}` (ID: {fid})")
        if not args.keep_temp and str(work_dir).startswith("/tmp/") and work_dir.exists():
            shutil.rmtree(work_dir)
            log("CLEANUP", f"Auto-deleted local temp workspace: {work_dir}")
    else:
        log("EXPORT", f"Local export ready: {out_mp4}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
