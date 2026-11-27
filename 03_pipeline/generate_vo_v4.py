#!/usr/bin/env python3
"""Mobile-First v4.0 Audio-First Voiceover, Timing Manifest & Subtitle Generator (`Jadi Apa`).

Reads `04_episodes/<ep_id>/<ep_id>_vo_spec.json`, synthesizes Indonesian voiceover via
`gemini-3.8-flash-tts` (`Puck`, with acting/style directions strictly isolated in
`speech_metadata` — NEVER concatenated into `vo_text`), stitches a unified `vo_master.wav`,
runs `faster-whisper` (`condition_on_previous_text=False`, anti-zero-duration tail filter)
to generate:
  1. `vo_master.wav`            — unified 48kHz stereo master VO
  2. `vo_timing_manifest.json`  — exact segment start/end/duration + recommended Google Flow
                                  Omni Flash 1.2 clip length rounded UP into `3..10` seconds
  3. `subtitles.ass`            — kinetic 9:16 bottom karaoke subtitles (ZERO top yellow badges!)

Finally syncs all 3 outputs directly to Google Drive `04_episodes/<ep_id>/` and ensures the
`raw_clips/` subfolder exists so the user can upload `shot_01.mp4 .. shot_NN.mp4` from mobile.

Usage:
  python3 03_pipeline/generate_vo_v4.py --ep ep001_kecoak_dapur
  python3 03_pipeline/generate_vo_v4.py --spec path/to/ep_vo_spec.json --dry-run --no-drive
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PIPELINE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PIPELINE_DIR / "scripts"
REPO_ROOT = PIPELINE_DIR.parent
for _p in (str(PIPELINE_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.audio_utils import (  # noqa: E402
    build_vo_microfade_filter,
    extract_word_timestamps,
    group_timed_words_into_chunks,
)

DEFAULT_PRIMARY_MODEL = "gemini-3.8-flash-tts"
DEFAULT_FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
DEFAULT_VOICE = "Puck"
DEFAULT_VO_SPEED = 1.08
DEFAULT_PAD_SEC = 0.06
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_DRIVE_EPISODES_FOLDER_ID = "1RS6RuYzydBZodpaTVPKL97EAa2_jOGON"

HIGHLIGHT_KEYWORDS = {
    "DUA", "PAGI", "KECOAK", "RAKSASA", "SANDAL", "JEPIT", "IJO", "CHEAT", "CODE",
    "TIGA", "RATUS", "KILOMETER", "KULKAS", "TERKEPUNG", "TEMBOK", "BUNTU",
    "SAYAP", "TERBANG", "MUKANYA", "MAAF", "BANG", "DARAH", "PUTIH", "CHARGER",
    "PANIK", "MELEDAK", "KRAKATAU", "NYAMUK", "CICAK", "SATU", "PERSEN",
}


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def check_ffmpeg() -> str:
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError("ffmpeg tidak ditemukan di PATH!")
    return ff


def get_gemini_api_key() -> Optional[str]:
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_name)
        if val and val.strip():
            return val.strip()
    return None


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


def ensure_drive_folder(name: str, parent_id: str) -> str:
    """Find or create a folder named `name` inside `parent_id` on Google Drive."""
    items = _gdrive_json(["readonly", "ls", parent_id])
    if isinstance(items, list):
        for item in items:
            if item.get("name") == name and item.get("mimeType") == "application/vnd.google-apps.folder":
                return str(item["id"])
    created = _gdrive_json(["mutate", "mkdir", name, "--parent", parent_id])
    folder_id = created.get("id") if isinstance(created, dict) else None
    if not folder_id:
        raise RuntimeError(f"Gagal membuat folder Drive '{name}' di parent {parent_id}: {created}")
    log("DRIVE", f"Created Drive folder '{name}' -> {folder_id}")
    return str(folder_id)


def upload_or_update_drive_file(local_path: Path, parent_id: str) -> str:
    """Upload `local_path` to `parent_id`, updating in-place if a file with the same name already exists."""
    items = _gdrive_json(["readonly", "ls", parent_id])
    existing_id: Optional[str] = None
    if isinstance(items, list):
        for item in items:
            if item.get("name") == local_path.name and item.get("mimeType") != "application/vnd.google-apps.folder":
                existing_id = str(item["id"])
                break

    if existing_id:
        _gdrive_json(["mutate", "update", existing_id, str(local_path)])
        log("DRIVE", f"Updated {local_path.name} in-place (ID: {existing_id})")
        return existing_id

    res = _gdrive_json(["mutate", "upload", str(local_path), "--parent", parent_id])
    file_id = str(res.get("id", "")) if isinstance(res, dict) else ""
    log("DRIVE", f"Uploaded {local_path.name} (ID: {file_id})")
    return file_id


# =============================================================================
# GEMINI 3.8 FLASH TTS (`speech_metadata` STRICTLY SEPARATED FROM `vo_text`)
# =============================================================================

def save_wav_bytes(
    dest_path: Path,
    audio_bytes: bytes,
    channels: int = 1,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    sample_width: int = 2,
) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if audio_bytes[:4] == b"RIFF":
        dest_path.write_bytes(audio_bytes)
    else:
        with wave.open(str(dest_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)


def measure_wav_duration(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError(f"Invalid WAV sample rate in {wav_path}")
        return frames / float(rate)


def build_speech_metadata_style(spec: Dict[str, Any], seg: Dict[str, Any]) -> str:
    """Build clean turn-level `speech_metadata.style` (NEVER concatenated into `vo_text`)."""
    tts_cfg = spec.get("tts_config", {}) if isinstance(spec.get("tts_config"), dict) else {}
    language = str(spec.get("language") or tts_cfg.get("language") or "id-ID")
    persona = str(
        spec.get("voice_persona")
        or tts_cfg.get("voice_persona")
        or "Teman nongkrong Indonesia yang ekspresif, ritme cepat, artikulasi lisan natural dan jernih"
    )
    seg_meta = seg.get("speech_metadata")
    if isinstance(seg_meta, dict):
        delivery = str(seg_meta.get("style") or seg_meta.get("delivery") or "").strip()
    elif isinstance(seg_meta, str):
        delivery = seg_meta.strip()
    else:
        delivery = str(seg.get("vo_delivery") or seg.get("speech_style") or "").strip()

    parts = [
        f"Language/Accent: natural spoken Indonesian ({language}).",
        f"Persona: {persona}.",
    ]
    if delivery:
        parts.append(f"Delivery for this line: {delivery}.")
    return " ".join(parts)


def _extract_audio_bytes(response: Any, model_id: str) -> bytes:
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    return base64.b64decode(data)
    raise RuntimeError(f"Model {model_id} returned no inline audio data: {repr(response)}")


def synthesize_gemini_tts(
    client: Any,
    primary_model: str,
    fallback_model: str,
    vo_text: str,
    style_prompt: str,
    voice_name: str,
    retries: int = 2,
) -> Tuple[bytes, str]:
    """Call `gemini-3.8-flash-tts` with `vo_text` strictly isolated from `speech_metadata`."""
    clean_text = vo_text.strip()
    if not clean_text:
        raise ValueError("vo_text is empty")

    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": clean_text,
                    "speech_metadata": {"style": style_prompt},
                }
            ],
        }
    ]
    primary_cfg = {
        "response_modalities": ["AUDIO"],
        "speech_config": {"voice_config": {"voice": voice_name}},
    }
    fallback_cfg = {
        "response_modalities": ["AUDIO"],
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}},
    }

    models = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models.append(fallback_model)

    last_err: Optional[Exception] = None
    for model_id in models:
        for attempt in range(1, retries + 1):
            try:
                try:
                    resp = client.models.generate_content(model=model_id, contents=contents, config=primary_cfg)
                except Exception as exc:
                    low = str(exc).lower()
                    if any(k in low for k in ("voice", "prebuilt_voice_config", "extra inputs", "unknown field")):
                        resp = client.models.generate_content(model=model_id, contents=contents, config=fallback_cfg)
                    else:
                        raise
                return _extract_audio_bytes(resp, model_id), model_id
            except Exception as exc:
                last_err = exc
                log("TTS_WARN", f"Attempt {attempt}/{retries} failed on {model_id}: {exc}")
                if attempt < retries:
                    time.sleep(2.0 * attempt)
    raise RuntimeError(f"All Gemini TTS models failed: {last_err}")


def generate_dry_run_wav(dest_path: Path, vo_text: str, shot_id: int) -> None:
    """Create a realistic-length offline cadence WAV for pipeline dry-run verification."""
    words = max(1, len(vo_text.split()))
    dur = max(1.8, round(words / 2.25, 2))
    sr = DEFAULT_SAMPLE_RATE
    n = int(round(dur * sr))
    freq = 165.0 + (shot_id % 5) * 18.0
    frames = bytearray()
    for i in range(n):
        t = i / float(sr)
        env = 0.5 * (1.0 + math.sin(2.0 * math.pi * 3.8 * t))
        fade = min(1.0, min(i, n - 1 - i) / (0.04 * sr))
        sample = int(2800.0 * env * fade * math.sin(2.0 * math.pi * freq * t))
        frames.extend(struct.pack("<h", max(-32767, min(32767, sample))))
    save_wav_bytes(dest_path, bytes(frames), channels=1, sample_rate=sr)


# =============================================================================
# SUBTITLE `.ASS` GENERATOR (KARAOKE BOTTOM ONLY — ZERO TOP YELLOW BADGES!)
# =============================================================================

def _fmt_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60.0
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _split_chunks_weighted(text: str, max_words: int = 3, max_chars: int = 18) -> List[str]:
    words = [w for w in re.split(r"\s+", text.replace("—", " — ").strip()) if w and w != "—"]
    chunks: List[str] = []
    cur: List[str] = []
    for w in words:
        cand = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(cand) > max_chars):
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        if cur and re.search(r"[.!?]$", w):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _stylize_karaoke_chunk(chunk: str, chunk_idx: int) -> str:
    words = chunk.upper().split()
    if not words:
        return ""
    hl_idx = -1
    for i, w in enumerate(words):
        if re.sub(r"[^A-Z0-9]", "", w) in HIGHLIGHT_KEYWORDS:
            hl_idx = i
            break
    if hl_idx == -1:
        hl_idx = len(words) - 1 if (chunk_idx % 2 == 0) else 0
    out: List[str] = []
    for i, w in enumerate(words):
        esc = _escape_ass(w)
        if i == hl_idx:
            out.append(r"{\c&H0000EAFF&\fscx108\fscy108}" + esc + r"{\c&H00FFFFFF&\fscx100\fscy100}")
        else:
            out.append(esc)
    return " ".join(out)


def write_clean_karaoke_ass(manifest: Dict[str, Any], out_ass: Path) -> Path:
    """Write 1080x1920 bottom-only kinetic karaoke `.ass` subtitles (ZERO top yellow badges!)."""
    header = f"""[Script Info]
Title: {manifest.get('episode_id', 'EP')} Mobile-First v4.0 Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainSub,DejaVu Sans,56,&H00FFFFFF,&H0000EAFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,5,2,2,95,95,380,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: List[str] = []
    chunk_idx = 0

    for seg in manifest["segments"]:
        s_start = float(seg["start_sec"])
        s_end = float(seg["end_sec"])
        speech_dur = max(0.30, float(seg["speech_duration_sec"]))
        vo_text = str(seg.get("vo_text", "")).strip()
        if not vo_text:
            continue

        words = seg.get("words") or []
        if words:
            rel_words = [
                {
                    "word": w["word"],
                    "start": max(0.0, float(w["start"]) - s_start),
                    "end": max(0.04, float(w["end"]) - s_start),
                }
                for w in words
            ]
            chunks = group_timed_words_into_chunks(rel_words, max_words=3, max_chars=18)
            for idx, ch in enumerate(chunks):
                t0 = max(s_start, s_start + float(ch["start"]))
                t1 = min(s_end - 0.02, s_start + float(ch["end"]) + 0.04)
                if idx + 1 < len(chunks):
                    nxt_t0 = s_start + float(chunks[idx + 1]["start"])
                    t1 = min(t1, max(t0 + 0.10, nxt_t0 - 0.01))
                styled = _stylize_karaoke_chunk(ch["text"], chunk_idx)
                anim = r"{\t(0,70,\fscx106\fscy106)\t(70,140,\fscx100\fscy100)}"
                events.append(
                    f"Dialogue: 1,{_fmt_ass_time(t0)},{_fmt_ass_time(max(t0 + 0.12, t1))},MainSub,,0,0,0,,{anim}{styled}"
                )
                chunk_idx += 1
        else:
            chunks_txt = _split_chunks_weighted(vo_text, max_words=3, max_chars=18)
            weights = [max(4, len(c.replace(" ", ""))) for c in chunks_txt]
            tot_w = float(sum(weights))
            cur = s_start
            for idx, (ch_txt, w_len) in enumerate(zip(chunks_txt, weights)):
                dur = speech_dur * (w_len / tot_w)
                nxt = min(s_end - 0.02, cur + dur)
                if idx == len(chunks_txt) - 1:
                    nxt = min(s_end - 0.02, s_start + speech_dur)
                styled = _stylize_karaoke_chunk(ch_txt, chunk_idx)
                anim = r"{\t(0,70,\fscx106\fscy106)\t(70,140,\fscx100\fscy100)}"
                events.append(
                    f"Dialogue: 1,{_fmt_ass_time(cur)},{_fmt_ass_time(max(cur + 0.12, nxt))},MainSub,,0,0,0,,{anim}{styled}"
                )
                cur = nxt
                chunk_idx += 1

    out_ass.parent.mkdir(parents=True, exist_ok=True)
    out_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    log("SUBS", f"Generated clean bottom-only karaoke ASS ({len(events)} events, TopBadge=0) -> {out_ass}")
    return out_ass


# =============================================================================
# MASTER VO STITCHING & MANIFEST GENERATION
# =============================================================================

def _resolve_spec_path(ep_id: Optional[str], spec_arg: Optional[str]) -> Tuple[str, Path]:
    if spec_arg:
        p = Path(spec_arg).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Spec tidak ditemukan: {p}")
        resolved_ep = ep_id or p.parent.name
        return resolved_ep, p
    if not ep_id:
        raise ValueError("Wajib isi `--ep <ep_id>` atau `--spec <path_vo_spec.json>`!")
    ep_dir = REPO_ROOT / "04_episodes" / ep_id
    candidates = [
        ep_dir / f"{ep_id}_vo_spec.json",
        *sorted(ep_dir.glob("*_vo_spec.json")),
        *sorted(ep_dir.glob("*_spec.json")),
    ]
    for cand in candidates:
        if cand.exists():
            return ep_id, cand.resolve()
    raise FileNotFoundError(
        f"File vo_spec JSON tidak ditemukan di {ep_dir} (diharapkan {ep_dir / f'{ep_id}_vo_spec.json'})."
    )


def _stitch_segment_to_48k_stereo(
    raw_wav: Path,
    out_wav: Path,
    ffmpeg_bin: str,
    vo_speed: float,
    pause_after_sec: float,
) -> Tuple[float, float]:
    """Apply `atempo=vo_speed` + 15ms micro-fade + clean trailing pause -> 48kHz stereo PCM WAV.

    Returns `(speech_dur_sec, total_seg_dur_sec)`.
    """
    raw_dur = measure_wav_duration(raw_wav)
    spd = max(0.5, min(2.0, float(vo_speed)))
    speech_dur = raw_dur / spd
    total_dur = speech_dur + max(0.0, float(pause_after_sec))

    tempo_chain = f",atempo={spd:.4f}" if abs(spd - 1.0) > 1e-3 else ""
    microfade = build_vo_microfade_filter(speech_dur, fade_ms=15.0)
    pad_chain = f",apad=whole_dur={total_dur:.4f}" if pause_after_sec > 1e-4 else ""

    af = f"aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo{tempo_chain},{microfade}{pad_chain}"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg_bin, "-y",
            "-i", str(raw_wav),
            "-af", af,
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    actual_total = measure_wav_duration(out_wav)
    return round(speech_dur, 4), round(actual_total, 4)


def concat_master_wav(seg_wavs: List[Path], out_master_wav: Path, ffmpeg_bin: str) -> Path:
    list_txt = out_master_wav.parent / "_vo_concat.txt"
    lines = []
    for p in seg_wavs:
        safe = str(p.resolve()).replace("'", "'\\''")
        lines.append(f"file '{safe}'")
    list_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    subprocess.run(
        [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_txt),
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
            str(out_master_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    list_txt.unlink(missing_ok=True)
    return out_master_wav


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mobile-First v4.0 Audio-First VO (`gemini-3.8-flash-tts`) + `faster-whisper` Timing Manifest + Karaoke ASS."
    )
    parser.add_argument("--ep", type=str, default=None, help="Episode slug (e.g. ep001_kecoak_dapur)")
    parser.add_argument("--spec", type=str, default=None, help="Explicit path to <ep_id>_vo_spec.json")
    parser.add_argument("--out-dir", type=str, default=None, help="Local output directory (default /tmp/flow_v4_vo/<ep>)")
    parser.add_argument("--voice", type=str, default=None, help="Gemini TTS voice override (default Puck)")
    parser.add_argument("--vo-speed", type=float, default=None, help="VO playback speed override (default 1.08)")
    parser.add_argument("--pad-sec", type=float, default=DEFAULT_PAD_SEC, help="Default trailing pause per segment (s)")
    parser.add_argument("--primary-model", type=str, default=DEFAULT_PRIMARY_MODEL)
    parser.add_argument("--fallback-model", type=str, default=DEFAULT_FALLBACK_MODEL)
    parser.add_argument("--whisper-model", type=str, default="small", help="faster-whisper model size (default small)")
    parser.add_argument("--skip-existing", action="store_true", help="Reuse existing segment WAVs in out-dir")
    parser.add_argument("--no-whisper", action="store_true", help="Disable faster-whisper and use weighted timing")
    parser.add_argument("--dry-run", action="store_true", help="Synthesize offline placeholder WAVs (0 API calls)")
    parser.add_argument("--no-drive", action="store_true", help="Skip uploading outputs to Google Drive")
    parser.add_argument(
        "--drive-episodes-folder",
        type=str,
        default=os.environ.get("MICRO_POV_DRIVE_EPISODES_ID", DEFAULT_DRIVE_EPISODES_FOLDER_ID),
    )
    args = parser.parse_args()

    ffmpeg_bin = check_ffmpeg()
    ep_id, spec_path = _resolve_spec_path(args.ep, args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    raw_segments = spec.get("segments") or spec.get("scenes")
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError(f"Spec {spec_path} harus memiliki array `segments` (atau `scenes`) yang tidak kosong!")

    tts_cfg = spec.get("tts_config", {}) if isinstance(spec.get("tts_config"), dict) else {}
    voice_name = str(args.voice or spec.get("voice") or tts_cfg.get("voice") or DEFAULT_VOICE)
    vo_speed = float(args.vo_speed if args.vo_speed is not None else spec.get("vo_speed", DEFAULT_VO_SPEED))

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (Path("/tmp/flow_v4_vo") / ep_id)
    raw_seg_dir = out_dir / "segments_raw"
    proc_seg_dir = out_dir / "segments_48k"
    raw_seg_dir.mkdir(parents=True, exist_ok=True)
    proc_seg_dir.mkdir(parents=True, exist_ok=True)

    client = None
    if not args.dry_run:
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY tidak ditemukan di environment! Set GEMINI_API_KEY atau pakai --dry-run.")
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    log("VO_V4", f"Episode: {ep_id} | Spec: {spec_path.name} | Segments: {len(raw_segments)} | Voice: {voice_name} ({vo_speed}x)")

    manifest_segments: List[Dict[str, Any]] = []
    processed_wavs: List[Path] = []
    cursor_sec = 0.0
    total_words = 0

    for idx, seg in enumerate(raw_segments, start=1):
        shot_id = int(seg.get("shot_id") or seg.get("scene_id") or seg.get("id") or idx)
        vo_text = str(seg.get("vo_text", "")).strip()
        if not vo_text:
            raise ValueError(f"Segment/shot {shot_id} memiliki `vo_text` kosong!")

        if re.search(r"\d", vo_text):
            log("WARN", f"Shot {shot_id:02d} masih mengandung angka digit di `vo_text` — sebaiknya dieja lisan: {vo_text!r}")

        style_prompt = build_speech_metadata_style(spec, seg)
        pause_after = float(seg.get("pause_after_sec", args.pad_sec))
        raw_wav = raw_seg_dir / f"shot_{shot_id:02d}_raw.wav"
        proc_wav = proc_seg_dir / f"shot_{shot_id:02d}_48k.wav"

        model_used = "cached"
        if args.skip_existing and raw_wav.exists() and raw_wav.stat().st_size > 1000:
            log("TTS", f"Shot {shot_id:02d}: reusing cached {raw_wav.name}")
        elif args.dry_run:
            generate_dry_run_wav(raw_wav, vo_text, shot_id)
            model_used = "dry_run"
        else:
            audio_bytes, model_used = synthesize_gemini_tts(
                client=client,
                primary_model=args.primary_model,
                fallback_model=args.fallback_model,
                vo_text=vo_text,
                style_prompt=style_prompt,
                voice_name=voice_name,
            )
            save_wav_bytes(raw_wav, audio_bytes)
            log("TTS", f"Shot {shot_id:02d}: synthesized via {model_used} ({raw_wav.stat().st_size / 1024:.1f} KB)")

        speech_dur, seg_dur = _stitch_segment_to_48k_stereo(
            raw_wav,
            proc_wav,
            ffmpeg_bin=ffmpeg_bin,
            vo_speed=vo_speed,
            pause_after_sec=pause_after,
        )
        processed_wavs.append(proc_wav)

        # Extract word-level timestamps via faster-whisper (condition_on_previous_text=False + anti-0-dur tail!)
        timed_words_global: List[Dict[str, Any]] = []
        if not args.no_whisper and not args.dry_run:
            rel_words = extract_word_timestamps(
                raw_wav,
                vo_text,
                vo_speed=vo_speed,
                expected_dur_sec=speech_dur,
                language="id",
                model_size=args.whisper_model,
                use_cache=True,
            )
            if rel_words:
                for w in rel_words:
                    timed_words_global.append(
                        {
                            "word": w["word"],
                            "start": round(cursor_sec + float(w["start"]), 4),
                            "end": round(cursor_sec + float(w["end"]), 4),
                        }
                    )

        # Recommend Google Flow Omni Flash 1.2 duration: rounded UP, clamped cleanly into 3..10s!
        ceil_sec = int(math.ceil(seg_dur))
        rec_flow_sec = max(3, min(10, ceil_sec))
        flow_warning: Optional[str] = None
        if seg_dur > 10.0:
            flow_warning = (
                f"Segmen berdurasi {seg_dur:.2f}s (> 10s batas hemat Flow)! "
                f"WAJIB pecah menjadi 2 shot <= 10 detik agar tidak kena tarif 2x lipat & tetap dapat upscale 1080p gratis."
            )
            log("FLOW_WARN", f"Shot {shot_id:02d}: {flow_warning}")

        start_sec = round(cursor_sec, 4)
        end_sec = round(cursor_sec + seg_dur, 4)
        cursor_sec = end_sec
        word_count = len(vo_text.split())
        total_words += word_count

        seg_entry: Dict[str, Any] = {
            "shot_id": shot_id,
            "shot_filename": f"shot_{shot_id:02d}.mp4",
            "start_sec": start_sec,
            "end_sec": end_sec,
            "duration_sec": seg_dur,
            "speech_duration_sec": speech_dur,
            "pause_after_sec": round(pause_after, 4),
            "recommended_flow_duration_sec": rec_flow_sec,
            "vo_text": vo_text,
            "speech_metadata": {"style": style_prompt},
            "tts_model": model_used,
            "words": timed_words_global,
        }
        if seg.get("visual_note"):
            seg_entry["visual_note"] = seg["visual_note"]
        if flow_warning:
            seg_entry["flow_split_warning"] = flow_warning
        manifest_segments.append(seg_entry)

    vo_master_wav = out_dir / "vo_master.wav"
    concat_master_wav(processed_wavs, vo_master_wav, ffmpeg_bin)
    master_dur = round(measure_wav_duration(vo_master_wav), 4)

    bgm_id = spec.get("bgm_id")
    if not bgm_id and isinstance(spec.get("bgm_plan"), list) and spec["bgm_plan"]:
        bgm_id = spec["bgm_plan"][0].get("bgm_id")

    manifest: Dict[str, Any] = {
        "pipeline_version": "4.0-mobile-first-flow",
        "episode_id": str(spec.get("episode_id") or ep_id.split("_")[0].upper()),
        "episode_slug": ep_id,
        "title": str(spec.get("title", ep_id)),
        "voice": voice_name,
        "vo_speed": vo_speed,
        "total_words": total_words,
        "total_duration_sec": master_dur,
        "recommended_total_flow_sec": sum(int(s["recommended_flow_duration_sec"]) for s in manifest_segments),
        "bgm_id": bgm_id or "",
        "vo_master_filename": "vo_master.wav",
        "subtitles_filename": "subtitles.ass",
        "segments": manifest_segments,
    }

    manifest_path = out_dir / "vo_timing_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ass_path = out_dir / "subtitles.ass"
    write_clean_karaoke_ass(manifest, ass_path)

    log("VO_V4", f"Master VO ready : {vo_master_wav} ({master_dur:.2f}s, {total_words} words)")
    log("VO_V4", f"Timing Manifest : {manifest_path}")
    for s in manifest_segments:
        log(
            "FLOW_PLAN",
            f"  {s['shot_filename']} | VO {s['start_sec']:5.2f}s–{s['end_sec']:5.2f}s "
            f"(dur={s['duration_sec']:4.2f}s) -> Flow Omni Flash 1.2: {s['recommended_flow_duration_sec']}s | "
            f"\"{s['vo_text'][:48]}\"",
        )

    if not args.no_drive:
        ep_drive_id = ensure_drive_folder(ep_id, args.drive_episodes_folder)
        raw_clips_drive_id = ensure_drive_folder("raw_clips", ep_drive_id)
        upload_or_update_drive_file(vo_master_wav, ep_drive_id)
        upload_or_update_drive_file(manifest_path, ep_drive_id)
        upload_or_update_drive_file(ass_path, ep_drive_id)
        log(
            "DRIVE",
            f"Synced 3 VO v4.0 artifacts -> Drive 04_episodes/{ep_id}/ (folder ID: {ep_drive_id} | "
            f"raw_clips ID: {raw_clips_drive_id})",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
