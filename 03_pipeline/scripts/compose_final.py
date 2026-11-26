#!/usr/bin/env python3
"""Dynamic ASS Subtitle Generator & FFmpeg Multi-Track Final Composer.

Responsibilities:
1. Auto-generates kinetic `.ass` subtitles from `timing_manifest.json`:
   - 2–4 words per pop-up chunk weighted by character duration
   - Bold sans-serif white/yellow highlight with thick black outline
   - Safe bottom-center position (y ~ 25% from bottom, avoiding TikTok/Shorts UI!)
   - Stylized top-safe `on_screen_text` badge per scene
2. Concatenates per-scene rendered clips (`scene_01.mp4 .. scene_0N.mp4`).
3. Mixes multi-track audio via FFmpeg:
   - VO track (-6 dB dominant reference, aligned strictly to timing_manifest.json)
   - SFX cues placed at exact `scene.start_sec + cue.offset_sec` (-10 dB)
   - BGM stitched per `bgm_plan` (including hard silence cuts like `none_cut_silence`)
     at -22 dB with `sidechaincompress` auto-ducking triggered by VO!
   - Master broadcast loudness normalization: -14 LUFS (AAC 192kbps, 48kHz stereo)
4. Burns subtitles into H.264 `yuv420p` and exports `final_ep001.mp4` (or `preview_ep001.mp4`).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

# High-impact Indonesian punch words highlighted in kinetic yellow
EMPHASIS_WORDS = {
    "KECOAK", "INDOMIE", "MI", "SANDAL", "JEPIT", "IJO", "RAKSASA", "CHEAT", "CODE",
    "PANTATMU", "ANGIN", "TIGA", "RATUS", "KILOMETER", "KULKAS", "SEJENGKAL",
    "NUTUP", "BUNTU", "TERKEPUNG", "SAYAP", "NYETIR", "TERBANG", "MUKANYA",
    "MAAF", "BANG", "DARURAT", "MENDADAK", "NYALA", "GELAP",
}


def _fmt_ass_time(seconds: float) -> str:
    sec = max(0.0, seconds)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60.0
    cs = int(round((s - int(s)) * 100.0))
    si = int(s)
    if cs >= 100:
        cs = 0
        si += 1
    return f"{h}:{m:02d}:{si:02d}.{cs:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def split_into_short_chunks(text: str, min_words: int = 2, max_words: int = 4) -> List[str]:
    """Split VO sentence into punchy 2-4 word subtitle chunks respecting punctuation."""
    # Split lightly on em-dash / sentence breaks first so timing feels natural
    raw_clauses = [c.strip() for c in re.split(r"(?<=[.!?—])\s+|—", text.strip()) if c.strip()]
    chunks: List[str] = []

    for clause in raw_clauses:
        words = clause.split()
        idx = 0
        n = len(words)
        while idx < n:
            rem = n - idx
            if rem <= max_words:
                take = rem
            elif rem == max_words + 1:
                take = 3  # Avoid orphan 1-word trailing chunk (e.g. 5 -> 3 + 2)
            else:
                take = 3 if rem % 3 == 0 else max_words
            chunk = " ".join(words[idx : idx + take])
            chunks.append(chunk)
            idx += take

    # Merge any accidental 1-word chunk with neighbor when possible
    merged: List[str] = []
    for ch in chunks:
        if merged and len(ch.split()) == 1 and len(merged[-1].split()) < max_words:
            merged[-1] = merged[-1] + " " + ch
        else:
            merged.append(ch)
    return merged or [text.strip()]


def _stylize_chunk_words(chunk: str, chunk_idx: int) -> str:
    """Apply crisp white + kinetic yellow emphasis to key words in ASS markup."""
    words = chunk.split()
    styled = []
    has_highlight = False
    for w in words:
        clean_upper = re.sub(r"[^A-Z0-9]", "", w.upper())
        if clean_upper in EMPHASIS_WORDS:
            styled.append(r"{\c&H0000EAFF&}" + _escape_ass(w.upper()) + r"{\c&H00FFFFFF&}")
            has_highlight = True
        else:
            styled.append(_escape_ass(w.upper()))
    # If no keyword matched on alternate chunks, highlight the last word for rhythmic visual pop
    if not has_highlight and words and (chunk_idx % 2 == 1):
        styled[-1] = r"{\c&H0000EAFF&}" + _escape_ass(words[-1].upper()) + r"{\c&H00FFFFFF&}"
    return " ".join(styled)


def generate_ass_subtitles(
    manifest: Dict[str, Any],
    out_ass: Path,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """Create stylized vertical 9:16 ASS subtitle file with safe 25% bottom margin."""
    scale = height / 1920.0
    sub_font_size = max(28, int(round(74 * scale)))
    badge_font_size = max(24, int(round(56 * scale)))
    outline_px = max(3, int(round(7 * scale)))
    shadow_px = max(2, int(round(3 * scale)))
    margin_v_bottom = int(round(height * 0.25))  # Safe 25% from bottom (above TikTok/Shorts UI)
    margin_v_top = int(round(height * 0.14))     # Safe top zone (below status bar)
    margin_lr = int(round(width * 0.07))

    header = f"""[Script Info]
Title: {manifest.get('episode_id', 'EP')} Dynamic Subtitles
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainSub,DejaVu Sans,{sub_font_size},&H00FFFFFF,&H0000EAFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,{outline_px},{shadow_px},2,{margin_lr},{margin_lr},{margin_v_bottom},1
Style: TopBadge,DejaVu Sans,{badge_font_size},&H0000EAFF,&H00FFFFFF,&H00000000,&HB0000000,-1,0,0,0,100,100,2,0,3,{max(2, outline_px - 2)},0,8,{margin_lr},{margin_lr},{margin_v_top},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: List[str] = []
    global_chunk_idx = 0

    for scene in manifest["scenes"]:
        s_start = float(scene["start_sec"])
        vo_dur = max(0.4, float(scene["audio_duration_sec"]))
        s_end = float(scene["end_sec"])
        vo_text = scene.get("vo_text", "").strip()
        badge = scene.get("on_screen_text", "").strip()

        # Optional punchy top badge (shown cleanly for first 1.6s of scene, or until cut-to-black)
        if badge:
            b_end = min(s_end - 0.15, s_start + 1.8)
            if b_end > s_start + 0.25:
                pop = r"{\fad(80,140)\t(0,90,\fscx108\fscy108)\t(90,170,\fscx100\fscy100)}"
                events.append(
                    f"Dialogue: 0,{_fmt_ass_time(s_start)},{_fmt_ass_time(b_end)},TopBadge,,0,0,0,,{pop}{_escape_ass(badge)}"
                )

        if not vo_text:
            continue

        chunks = split_into_short_chunks(vo_text, min_words=2, max_words=4)
        weights = [max(4, len(ch.replace(" ", ""))) for ch in chunks]
        total_w = float(sum(weights))

        cur = s_start
        for idx, (ch, w) in enumerate(zip(chunks, weights)):
            dur = vo_dur * (w / total_w)
            nxt = min(s_end - 0.05, cur + dur)
            if idx == len(chunks) - 1:
                nxt = min(s_end - 0.05, s_start + vo_dur)
            styled = _stylize_chunk_words(ch, global_chunk_idx)
            anim = r"{\t(0,75,\fscx109\fscy109)\t(75,150,\fscx100\fscy100)}"
            events.append(
                f"Dialogue: 1,{_fmt_ass_time(cur)},{_fmt_ass_time(max(cur + 0.12, nxt))},MainSub,,0,0,0,,{anim}{styled}"
            )
            cur = nxt
            global_chunk_idx += 1

    out_ass.parent.mkdir(parents=True, exist_ok=True)
    out_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    log("SUBS", f"Generated ASS subtitles ({len(events)} events, bottom margin {margin_v_bottom}px = 25%) -> {out_ass}")
    return out_ass


def probe_video_resolution(video_path: Path) -> Tuple[int, int]:
    """Read (width, height) of an MP4 clip via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    w_s, h_s = res.stdout.strip().split("x")
    return int(w_s), int(h_s)


def concatenate_scene_videos(
    manifest: Dict[str, Any],
    scenes_dir: Path,
    concat_mp4: Path,
    ffmpeg_bin: str,
) -> Path:
    """Concatenate scene_01.mp4 .. scene_0N.mp4 cleanly in timeline order."""
    concat_list = scenes_dir / "concat_list.txt"
    lines: List[str] = []
    for scene in manifest["scenes"]:
        sid = int(scene["scene_id"])
        clip = scenes_dir / f"scene_{sid:02d}.mp4"
        if not clip.exists():
            raise FileNotFoundError(
                f"Missing rendered clip for scene {sid}: {clip}. Run build_and_render.py first."
            )
        safe_path = str(clip.resolve()).replace("'", "'\\''")
        lines.append(f"file '{safe_path}'")

    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        str(concat_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    log("COMPOSE", f"Concatenated {len(lines)} scene video clips -> {concat_mp4}")
    return concat_mp4


def mix_audio_and_compose(
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    concat_mp4: Path,
    ass_path: Path,
    assets_dir: Path,
    output_mp4: Path,
    ffmpeg_bin: str,
) -> Path:
    """Mix VO (-6 dB) + SFX (-10 dB) + auto-ducked BGM (-22 dB) + -14 LUFS + burn ASS subtitles."""
    total_dur = float(manifest["total_duration_sec"])
    scene_map: Dict[int, Dict[str, Any]] = {int(s["scene_id"]): s for s in manifest["scenes"]}
    spec_scene_map: Dict[int, Dict[str, Any]] = {int(s["scene_id"]): s for s in spec["scenes"]}

    inputs: List[str] = ["-i", str(concat_mp4)]  # Input 0: concatenated silent video
    next_idx = 1
    filter_parts: List[str] = []

    # 1. VO TRACK (each scene WAV placed precisely at timing_manifest start_sec)
    vo_labels: List[str] = []
    for s in manifest["scenes"]:
        wav = Path(s["wav_path"])
        if not wav.exists():
            raise FileNotFoundError(f"VO WAV missing: {wav}")
        inputs.extend(["-i", str(wav)])
        delay_ms = int(round(float(s["start_sec"]) * 1000.0))
        lbl = f"vo{s['scene_id']}"
        filter_parts.append(
            f"[{next_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={delay_ms}|{delay_ms},apad=whole_dur={total_dur:.4f}[{lbl}]"
        )
        vo_labels.append(f"[{lbl}]")
        next_idx += 1

    filter_parts.append(
        f"{''.join(vo_labels)}amix=inputs={len(vo_labels)}:duration=first:normalize=0,"
        f"volume=-6dB,asplit=2[vo_mix][vo_sc]"
    )

    # 2. SFX TRACK (every cue placed at exact scene.start_sec + cue.offset_sec at -10 dB)
    sfx_labels: List[str] = []
    sfx_counter = 0
    for sid in sorted(scene_map.keys()):
        s_start = float(scene_map[sid]["start_sec"])
        for cue in spec_scene_map[sid].get("sfx_cues", []):
            sfx_id = cue["sfx_id"]
            sfx_file = assets_dir / "sfx" / f"{sfx_id}.wav"
            if not sfx_file.exists():
                log("WARN", f"SFX file not found ({sfx_file}); skipping cue {sfx_id}")
                continue
            inputs.extend(["-i", str(sfx_file)])
            abs_ms = max(0, int(round((s_start + float(cue["offset_sec"])) * 1000.0)))
            lbl = f"sfx{sfx_counter}"
            # Trim SFX cleanly so it doesn't extend past total video duration
            max_play = max(0.15, total_dur - (abs_ms / 1000.0))
            filter_parts.append(
                f"[{next_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"atrim=0:{max_play:.4f},adelay={abs_ms}|{abs_ms},apad=whole_dur={total_dur:.4f}[{lbl}]"
            )
            sfx_labels.append(f"[{lbl}]")
            sfx_counter += 1
            next_idx += 1

    if sfx_labels:
        filter_parts.append(
            f"{''.join(sfx_labels)}amix=inputs={len(sfx_labels)}:duration=first:normalize=0,"
            f"volume=-10dB[sfx_bus]"
        )
    else:
        filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.4f}[sfx_bus]")

    # 3. BGM TRACK (stitched per bgm_plan, hard silence on none_cut_silence, -22 dB + VO sidechain ducking!)
    bgm_labels: List[str] = []
    bgm_counter = 0
    for item in spec.get("bgm_plan", []):
        bgm_id = item.get("bgm_id", "")
        if bgm_id in ("none", "none_cut_silence", "silence", ""):
            continue
        start_sid = int(item["start_scene"])
        end_sid = int(item["end_scene"])
        if start_sid not in scene_map or end_sid not in scene_map:
            continue

        bgm_file = assets_dir / "bgm" / f"{bgm_id}.mp3"
        if not bgm_file.exists():
            alt_wav = assets_dir / "bgm" / f"{bgm_id}.wav"
            bgm_file = alt_wav if alt_wav.exists() else bgm_file
        if not bgm_file.exists():
            log("WARN", f"BGM file missing ({bgm_file}); skipping {bgm_id}")
            continue

        seg_start = float(scene_map[start_sid]["start_sec"])
        seg_end = float(scene_map[end_sid]["end_sec"])
        seg_dur = max(0.2, seg_end - seg_start)
        delay_ms = int(round(seg_start * 1000.0))

        # Loop BGM infinitely via -stream_loop -1, then trim to exact segment duration
        inputs.extend(["-stream_loop", "-1", "-i", str(bgm_file)])
        lbl = f"bgm{bgm_counter}"
        fade_out_st = max(0.0, seg_dur - 0.12)
        filter_parts.append(
            f"[{next_idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"atrim=0:{seg_dur:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.08,afade=t=out:st={fade_out_st:.4f}:d=0.10,"
            f"adelay={delay_ms}|{delay_ms},apad=whole_dur={total_dur:.4f}[{lbl}]"
        )
        bgm_labels.append(f"[{lbl}]")
        bgm_counter += 1
        next_idx += 1

    if bgm_labels:
        filter_parts.append(
            f"{''.join(bgm_labels)}amix=inputs={len(bgm_labels)}:duration=first:normalize=0,"
            f"volume=-22dB[bgm_raw]"
        )
        # Auto-duck BGM smoothly whenever VO speaks!
        filter_parts.append(
            "[bgm_raw][vo_sc]sidechaincompress=threshold=0.015:ratio=6:attack=25:release=260:makeup=1[bgm_ducked]"
        )
    else:
        filter_parts.append("[vo_sc]anullsink")
        filter_parts.append(f"anullsrc=r=48000:cl=stereo:d={total_dur:.4f}[bgm_ducked]")

    # 4. MASTER MIX + -14 LUFS LOUDNESS NORMALIZATION
    filter_parts.append(
        "[vo_mix][sfx_bus][bgm_ducked]amix=inputs=3:duration=first:normalize=0,"
        f"atrim=0:{total_dur:.4f},loudnorm=I=-14:TP=-1.5:LRA=11[a_master]"
    )

    # 5. VIDEO BURN-IN SUBTITLES (.ass)
    # Escape path characters for FFmpeg ass filter
    ass_escaped = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    filter_parts.append(f"[0:v]ass='{ass_escaped}'[v_sub]")

    filter_complex = ";\n".join(filter_parts)

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v_sub]",
        "-map",
        "[a_master]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-t",
        f"{total_dur:.4f}",
        str(output_mp4),
    ]

    log("COMPOSE", f"Mixing VO + {sfx_counter} SFX + {bgm_counter} BGM + ASS subtitles -> {output_mp4}...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log("ERROR", f"FFmpeg failed:\n{proc.stderr[-2500:]}")
        raise RuntimeError("FFmpeg final composition failed")

    size_mb = output_mp4.stat().st_size / (1024 * 1024)
    log("COMPOSE", f"SUCCESS! Exported {output_mp4} ({size_mb:.2f} MB, {total_dur:.2f}s, -14 LUFS)")
    return output_mp4


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate dynamic .ass subtitles and compose final -14 LUFS vertical MP4."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
    )
    parser.add_argument("--timing", type=str, default=None, help="Path to timing_manifest.json")
    parser.add_argument("--assets-dir", type=str, default=None, help="Override 02_assets directory")
    parser.add_argument("--work-dir", type=str, default=None, help="Override episode working directory")
    parser.add_argument("--mode", choices=["preview", "final"], default="final")
    parser.add_argument("--output", type=str, default=None, help="Override final output .mp4 path")
    parser.add_argument(
        "--dry-run-video",
        action="store_true",
        help="Generate synthetic color-card scene MP4s via FFmpeg if Blender hasn't rendered yet (for pipeline verification)",
    )
    args = parser.parse_args()

    ffmpeg_bin = check_ffmpeg_available()
    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    assets_dir = resolve_assets_dir(args.assets_dir)
    work_dir = resolve_episode_work_dir(spec_path, args.work_dir)
    timing_path = Path(args.timing).resolve() if args.timing else (work_dir / "timing_manifest.json")

    if not timing_path.exists():
        log("ERROR", f"timing_manifest.json missing at {timing_path}. Run generate_tts.py first.")
        return 1
    manifest = load_json(timing_path)

    scenes_dir = work_dir / "raw_render" / f"scenes_{args.mode}"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # Optional dry-run video generator so full audio/subtitle/FFmpeg pipeline can be verified without Blender
    if args.dry_run_video:
        w, h = (540, 960) if args.mode == "preview" else (1080, 1920)
        fps = int(manifest.get("fps", 30))
        colors = ["#0c1933", "#1e2a38", "#073440", "#2f3542", "#1b2631", "#3b1d1d", "#2c2214", "#121212"]
        for s in manifest["scenes"]:
            sid = int(s["scene_id"])
            clip = scenes_dir / f"scene_{sid:02d}.mp4"
            dur = float(s["scene_duration_sec"])
            color = colors[(sid - 1) % len(colors)]
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s={w}x{h}:r={fps}:d={dur:.4f}",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-t",
                    f"{dur:.4f}",
                    str(clip),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        log("COMPOSE", f"[DRY-RUN] Generated {len(manifest['scenes'])} placeholder scene MP4 clips ({w}x{h})")

    concat_mp4 = work_dir / "raw_render" / f"concat_{args.mode}.mp4"
    concatenate_scene_videos(manifest, scenes_dir, concat_mp4, ffmpeg_bin)

    w, h = probe_video_resolution(concat_mp4)
    ass_path = work_dir / f"subtitles_{args.mode}.ass"
    generate_ass_subtitles(manifest, ass_path, width=w, height=h)

    ep_slug = spec["episode_id"].lower()
    default_out_name = f"final_{ep_slug}.mp4" if args.mode == "final" else f"preview_{ep_slug}.mp4"
    output_mp4 = Path(args.output).resolve() if args.output else (work_dir / default_out_name)

    mix_audio_and_compose(spec, manifest, concat_mp4, ass_path, assets_dir, output_mp4, ffmpeg_bin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
