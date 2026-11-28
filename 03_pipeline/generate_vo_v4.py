#!/usr/bin/env python3
"""Mobile-First v4.2 Audio-First Voiceover, Timing Manifest & Subtitle Generator (`Jadi Apa`).

Reads `04_episodes/<ep_id>/<ep_id>_vo_spec.json`, synthesizes Indonesian voiceover via
`gemini-3.8-flash-tts` (`Fenrir`, with acting/style directions strictly isolated in
`speech_metadata` — NEVER concatenated into `vo_text`), stitches a unified `vo_master.wav`,
runs `faster-whisper` (`condition_on_previous_text=False`, anti-zero-duration tail filter)
to generate:
  1. `vo_master.wav`            — unified 48kHz stereo master VO
  2. `vo_timing_manifest.json`  — exact segment start/end/duration + recommended Google Flow
                                  Omni Flash 1.2 clip length rounded UP into `3..10` seconds
  3. `subtitles.ass`            — kinetic 9:16 bottom karaoke subtitles (ZERO top yellow badges!)

Finally syncs all outputs directly to Google Drive `04_episodes/<ep_id>/` and ensures the
`raw_clips/` subfolder exists so the user can upload `shot_01.mp4 .. shot_NN.mp4` from mobile.

Usage:
  python3 03_pipeline/generate_vo_v4.py --ep ep001_kecoak_dapur
  python3 03_pipeline/generate_vo_v4.py --spec path/to/ep_vo_spec.json --dry-run --no-drive
"""

from __future__ import annotations

import argparse
import base64
from difflib import SequenceMatcher
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
    _get_whisper_model,
    _load_wav_mono_16k_float32,
    build_vo_microfade_filter,
    extract_word_timestamps,
    group_timed_words_into_chunks,
)

DEFAULT_PRIMARY_MODEL = "gemini-3.8-flash-tts"
DEFAULT_FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
DEFAULT_VOICE = "Fenrir"
DEFAULT_VO_SPEED = 1.02
DEFAULT_PAD_SEC = 0.06
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_DRIVE_EPISODES_FOLDER_ID = "1RS6RuYzydBZodpaTVPKL97EAa2_jOGON"

QC_MIN_WPS = 1.7
QC_MAX_WPS = 2.9
QC_MIN_SIMILARITY = 0.82
QC_MAX_RETRIES = 2
QC_RETRY_STYLE_SUFFIX = "Ucapkan lebih tenang dengan artikulasi sangat jelas per kata, jangan terburu-buru."

POV_WATCH_WORDS = {
    "kamu", "kakimu", "pantatmu", "ukuranmu", "tubuhmu", "kepalamu",
    "sayapmu", "matamu", "tanganmu", "hidupmu", "punggungmu", "jantungmu",
}
NON_POV_MU_WORDS = {"ilmu", "tamu", "ketemu", "semu", "ramu", "jamu", "bertemu", "ditemu"}

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
# GOOGLE DRIVE CLI HELPERS (`gdrive`) — CLEAN OVERWRITE (ZERO DUPLICATES!)
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
    """Clean-overwrite `local_path` in `parent_id` (updates in-place and trashes any duplicate copies)."""
    items = _gdrive_json(["readonly", "ls", parent_id])
    exact_matches: List[Dict[str, Any]] = []
    dup_matches: List[Dict[str, Any]] = []
    dup_pattern = re.compile(
        rf"^{re.escape(local_path.stem)}\s*\(\d+\){re.escape(local_path.suffix)}$",
        flags=re.IGNORECASE,
    )
    if isinstance(items, list):
        for item in items:
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                continue
            name = str(item.get("name", ""))
            if name == local_path.name:
                exact_matches.append(item)
            elif dup_pattern.match(name):
                dup_matches.append(item)

    # Trash any numbered duplicate files (e.g. `vo_master (1).wav`) and extra exact-name duplicates
    for dup in dup_matches:
        _gdrive_json(["mutate", "trash", str(dup["id"])])
        log("DRIVE", f"Trashed duplicate {dup.get('name')} (ID: {dup['id']})")

    if len(exact_matches) > 1:
        for extra in exact_matches[1:]:
            _gdrive_json(["mutate", "trash", str(extra["id"])])
            log("DRIVE", f"Trashed extra copy {extra.get('name')} (ID: {extra['id']})")

    if exact_matches:
        existing_id = str(exact_matches[0]["id"])
        _gdrive_json(["mutate", "update", existing_id, str(local_path)])
        log("DRIVE", f"Clean-overwrote {local_path.name} in-place (ID: {existing_id})")
        return existing_id

    res = _gdrive_json(["mutate", "upload", str(local_path), "--parent", parent_id])
    file_id = str(res.get("id", "")) if isinstance(res, dict) else ""
    log("DRIVE", f"Uploaded {local_path.name} (ID: {file_id})")
    return file_id


# =============================================================================
# AUTOMATED TTS VERBATIM & SPEED QC GATE (`faster-whisper` RAW AUDIT)
# =============================================================================

_ID_UNITS = ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan"]


def _int_to_indonesian(n: int) -> str:
    if n < 0:
        return "minus " + _int_to_indonesian(-n)
    if n < 10:
        return _ID_UNITS[n]
    if n == 10:
        return "sepuluh"
    if n == 11:
        return "sebelas"
    if n < 20:
        return f"{_ID_UNITS[n - 10]} belas"
    if n < 100:
        tens, rem = divmod(n, 10)
        return f"{_ID_UNITS[tens]} puluh" + (f" {_int_to_indonesian(rem)}" if rem else "")
    if n < 200:
        rem = n - 100
        return "seratus" + (f" {_int_to_indonesian(rem)}" if rem else "")
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        return f"{_ID_UNITS[hundreds]} ratus" + (f" {_int_to_indonesian(rem)}" if rem else "")
    if n < 2000:
        rem = n - 1000
        return "seribu" + (f" {_int_to_indonesian(rem)}" if rem else "")
    if n < 10000:
        thousands, rem = divmod(n, 1000)
        return f"{_ID_UNITS[thousands]} ribu" + (f" {_int_to_indonesian(rem)}" if rem else "")
    return str(n)


def _normalize_id_text_for_qc(text: str) -> str:
    """Normalize Indonesian spoken text & Whisper raw output (digits/units -> spoken words) for verbatim QC."""
    s = text.lower().replace("—", " ").replace("-", " ")
    # Expand common unit abbreviations Whisper emits after digits (e.g. "300 km/jam" -> "300 kilometer per jam")
    s = re.sub(r"\bkm\s*/\s*jam\b", "kilometer per jam", s)
    s = re.sub(r"\bkm\b", "kilometer", s)
    s = re.sub(r"\bcm\b", "sentimeter", s)
    s = re.sub(r"\bmm\b", "milimeter", s)
    s = re.sub(r"\bkg\b", "kilogram", s)
    # Replace integers with Indonesian spoken words so Whisper digits match spelled-out vo_text
    s = re.sub(r"\b\d{1,4}\b", lambda m: _int_to_indonesian(int(m.group(0))), s)
    # Normalize common Indonesian informal spelling variants Whisper produces (without masking POV errors!)
    s = re.sub(r"\b(gak|ga|ngga)\b", "nggak", s)
    s = re.sub(r"\bmie\b", "mi", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _extract_required_pov_words(vo_text: str) -> List[str]:
    norm_tokens = _normalize_id_text_for_qc(vo_text).split()
    req: List[str] = []
    seen = set()
    for tok in norm_tokens:
        is_pov = (tok in POV_WATCH_WORDS) or (len(tok) >= 4 and tok.endswith("mu") and tok not in NON_POV_MU_WORDS)
        if is_pov and tok not in seen:
            req.append(tok)
            seen.add(tok)
    return req


def run_segment_tts_qc(
    raw_wav: Path,
    vo_text: str,
    vo_speed: float,
    whisper_model_size: str = "small",
    min_wps: float = QC_MIN_WPS,
    max_wps: float = QC_MAX_WPS,
    min_similarity: float = QC_MIN_SIMILARITY,
) -> Dict[str, Any]:
    """Audit raw TTS segment WAV via unbiased `faster-whisper` (`initial_prompt=None`, `condition_on_previous_text=False`)."""
    raw_dur = measure_wav_duration(raw_wav)
    spd = max(0.5, float(vo_speed))
    effective_speech_dur = raw_dur / spd
    word_count = max(1, len(vo_text.split()))
    words_per_sec = round(word_count / max(0.1, effective_speech_dur), 2)
    speed_ok = (min_wps <= words_per_sec <= max_wps)

    model = _get_whisper_model(model_size=whisper_model_size)
    audio_16k = _load_wav_mono_16k_float32(raw_wav)
    segments, _ = model.transcribe(
        audio_16k,
        language="id",
        word_timestamps=False,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt=None,
    )
    raw_transcript = " ".join(str(seg.text).strip() for seg in segments if str(seg.text).strip()).strip()

    norm_expected = _normalize_id_text_for_qc(vo_text)
    norm_actual = _normalize_id_text_for_qc(raw_transcript)
    similarity = round(SequenceMatcher(None, norm_expected, norm_actual).ratio(), 4)
    similarity_ok = similarity >= min_similarity

    required_pov = _extract_required_pov_words(vo_text)
    actual_tokens = set(norm_actual.split())
    missing_pov: List[str] = []
    for w in required_pov:
        found = w in actual_tokens
        if not found and len(w) >= 4 and w.endswith("mu"):
            # Whisper occasionally writes Indonesian possessive "-mu" separated (e.g. "kaki mu" vs "kakimu")
            spaced = f"{w[:-2]} mu"
            if re.search(rf"\b{re.escape(spaced)}\b", norm_actual):
                found = True
        if not found:
            missing_pov.append(w)
    pov_ok = len(missing_pov) == 0

    reasons: List[str] = []
    if words_per_sec > max_wps:
        reasons.append(f"terlalu ngebut ({words_per_sec:.2f} > {max_wps:.1f} kata/detik)")
    elif words_per_sec < min_wps:
        reasons.append(f"terlalu lambat ({words_per_sec:.2f} < {min_wps:.1f} kata/detik)")
    if not pov_ok:
        reasons.append(f"kata POV hilang/salah baca: {', '.join(missing_pov)}")
    if not similarity_ok:
        reasons.append(f"kesamaan teks rendah ({similarity:.2f} < {min_similarity:.2f})")

    return {
        "passed": bool(speed_ok and similarity_ok and pov_ok),
        "raw_transcript": raw_transcript,
        "words_per_sec": words_per_sec,
        "speed_ok": speed_ok,
        "similarity": similarity,
        "similarity_ok": similarity_ok,
        "required_pov_words": required_pov,
        "missing_pov_words": missing_pov,
        "pov_ok": pov_ok,
        "reasons": reasons,
    }


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
        or "Teman nongkrong Indonesia yang ekspresif, santai, dan jernih artikulasinya"
    ).rstrip(".")
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
        parts.append(f"Delivery for this line: {delivery.rstrip('.')}.")
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
    margin_v = int(manifest.get("subtitle_margin_v") or 380)
    header = f"""[Script Info]
Title: {manifest.get('episode_id', 'EP')} Mobile-First v4.2 Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainSub,DejaVu Sans,56,&H00FFFFFF,&H0000EAFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,5,2,2,95,95,{margin_v},1

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


def _qc_rank_key(qc: Dict[str, Any]) -> Tuple[int, int, int, float]:
    """Ranking key to select the cleanest take if all retries still have minor QC issues."""
    return (
        1 if qc.get("passed") else 0,
        1 if qc.get("pov_ok") else 0,
        1 if qc.get("speed_ok") else 0,
        float(qc.get("similarity", 0.0)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mobile-First v4.2 Audio-First VO (`gemini-3.8-flash-tts`) + Automated Verbatim/Speed QC + `faster-whisper` Timing Manifest + Karaoke ASS."
    )
    parser.add_argument("--ep", type=str, default=None, help="Episode slug (e.g. ep001_kecoak_dapur)")
    parser.add_argument("--spec", type=str, default=None, help="Explicit path to <ep_id>_vo_spec.json")
    parser.add_argument("--out-dir", type=str, default=None, help="Local output directory (default /tmp/flow_v4_vo/<ep>)")
    parser.add_argument("--voice", type=str, default=None, help="Gemini TTS voice override (default Fenrir)")
    parser.add_argument("--vo-speed", type=float, default=None, help="VO playback speed override (default 1.02)")
    parser.add_argument("--pad-sec", type=float, default=DEFAULT_PAD_SEC, help="Default trailing pause per segment (s)")
    parser.add_argument("--primary-model", type=str, default=None)
    parser.add_argument("--fallback-model", type=str, default=None)
    parser.add_argument("--whisper-model", type=str, default="small", help="faster-whisper model size (default small)")
    parser.add_argument("--qc-retries", type=int, default=QC_MAX_RETRIES, help="Max auto-retries when segment fails Verbatim/Speed QC (default 2)")
    parser.add_argument("--no-qc", action="store_true", help="Skip Automated TTS Verbatim & Speed QC Gate")
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
    sub_cfg = spec.get("subtitle_config", {}) if isinstance(spec.get("subtitle_config"), dict) else {}
    voice_name = str(
        args.voice
        or spec.get("voice")
        or tts_cfg.get("voice_name")
        or tts_cfg.get("voice")
        or DEFAULT_VOICE
    )
    if args.vo_speed is not None:
        vo_speed = float(args.vo_speed)
    elif spec.get("vo_speed") is not None:
        vo_speed = float(spec["vo_speed"])
    elif tts_cfg.get("vo_speed") is not None:
        vo_speed = float(tts_cfg["vo_speed"])
    else:
        vo_speed = DEFAULT_VO_SPEED

    primary_model = str(args.primary_model or tts_cfg.get("model") or DEFAULT_PRIMARY_MODEL)
    fallback_model = str(args.fallback_model or tts_cfg.get("fallback_model") or DEFAULT_FALLBACK_MODEL)
    margin_v = int(sub_cfg.get("margin_v") or 380)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (Path("/tmp/flow_v4_vo") / ep_id)
    raw_seg_dir = out_dir / "segments_raw"
    proc_seg_dir = out_dir / "segments_48k"
    raw_seg_dir.mkdir(parents=True, exist_ok=True)
    proc_seg_dir.mkdir(parents=True, exist_ok=True)

    # Clean Overwrite Policy (local): remove stale master artifacts before rebuilding
    for stale_name in ("vo_master.wav", "vo_timing_manifest.json", "subtitles.ass"):
        stale_file = out_dir / stale_name
        if stale_file.exists():
            stale_file.unlink()
            log("CLEAN", f"Removed stale local artifact: {stale_file.name}")

    client = None
    if not args.dry_run:
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY tidak ditemukan di environment! Set GEMINI_API_KEY atau pakai --dry-run.")
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    qc_enabled = (not args.no_qc) and (not args.no_whisper) and (not args.dry_run)
    log(
        "VO_V4",
        f"Episode: {ep_id} | Spec: {spec_path.name} | Segments: {len(raw_segments)} | "
        f"Model: {primary_model} | Voice: {voice_name} ({vo_speed}x) | QC Gate: {'ON' if qc_enabled else 'OFF'}",
    )

    manifest_segments: List[Dict[str, Any]] = []
    processed_wavs: List[Path] = []
    cursor_sec = 0.0
    total_words = 0

    for idx, seg in enumerate(raw_segments, start=1):
        shot_id = int(seg.get("shot_id") or seg.get("scene_id") or seg.get("id") or idx)
        segment_id = str(seg.get("segment_id") or f"seg_{shot_id:02d}")
        shot_label = str(seg.get("shot_label") or "").strip()
        vo_text = str(seg.get("vo_text", "")).strip()
        if not vo_text:
            raise ValueError(f"Segment/shot {shot_id} memiliki `vo_text` kosong!")

        if re.search(r"\d", vo_text):
            log("WARN", f"Shot {shot_id:02d} masih mengandung angka digit di `vo_text` — sebaiknya dieja lisan: {vo_text!r}")

        style_prompt = build_speech_metadata_style(spec, seg)
        if seg.get("post_silence_sec") is not None:
            pause_after = float(seg["post_silence_sec"])
        elif seg.get("pause_after_sec") is not None:
            pause_after = float(seg["pause_after_sec"])
        else:
            pause_after = float(args.pad_sec)
        raw_wav = raw_seg_dir / f"shot_{shot_id:02d}_raw.wav"
        proc_wav = proc_seg_dir / f"shot_{shot_id:02d}_48k.wav"

        model_used = primary_model
        qc_result: Optional[Dict[str, Any]] = None
        qc_attempts = 0
        final_style_used = style_prompt

        if args.skip_existing and raw_wav.exists() and raw_wav.stat().st_size > 1000:
            log("TTS", f"Shot {shot_id:02d}: reusing cached {raw_wav.name}")
            if qc_enabled:
                qc_result = run_segment_tts_qc(
                    raw_wav=raw_wav,
                    vo_text=vo_text,
                    vo_speed=vo_speed,
                    whisper_model_size=args.whisper_model,
                )
                qc_result["attempts"] = 0
                qc_result["source"] = "cached"
        elif args.dry_run:
            generate_dry_run_wav(raw_wav, vo_text, shot_id)
            model_used = "dry_run"
        else:
            max_tries = 1 + (max(0, int(args.qc_retries)) if qc_enabled else 0)
            best_wav_bytes: Optional[bytes] = None
            best_qc: Optional[Dict[str, Any]] = None
            best_model = primary_model
            best_style = style_prompt

            for try_idx in range(1, max_tries + 1):
                qc_attempts = try_idx
                attempt_style = style_prompt if try_idx == 1 else f"{style_prompt} {QC_RETRY_STYLE_SUFFIX}"
                # Delete any previous defective WAV / word cache before writing new take
                raw_wav.unlink(missing_ok=True)
                raw_wav.with_suffix(".words.json").unlink(missing_ok=True)

                audio_bytes, model_used = synthesize_gemini_tts(
                    client=client,
                    primary_model=primary_model,
                    fallback_model=fallback_model,
                    vo_text=vo_text,
                    style_prompt=attempt_style,
                    voice_name=voice_name,
                )
                save_wav_bytes(raw_wav, audio_bytes)
                log(
                    "TTS",
                    f"Shot {shot_id:02d} (try {try_idx}/{max_tries}): synthesized via {model_used} "
                    f"({raw_wav.stat().st_size / 1024:.1f} KB)",
                )

                if not qc_enabled:
                    final_style_used = attempt_style
                    break

                qc_curr = run_segment_tts_qc(
                    raw_wav=raw_wav,
                    vo_text=vo_text,
                    vo_speed=vo_speed,
                    whisper_model_size=args.whisper_model,
                )
                qc_curr["attempts"] = try_idx
                qc_curr["source"] = "synthesized"

                if best_qc is None or _qc_rank_key(qc_curr) > _qc_rank_key(best_qc):
                    best_qc = qc_curr
                    best_wav_bytes = raw_wav.read_bytes()
                    best_model = model_used
                    best_style = attempt_style

                if qc_curr["passed"]:
                    qc_result = qc_curr
                    final_style_used = attempt_style
                    break

                reason_str = "; ".join(qc_curr["reasons"])
                log(
                    "QC_FAIL",
                    f"{segment_id} try {try_idx}/{max_tries} GAGAL QC [{reason_str}] | "
                    f"wps={qc_curr['words_per_sec']:.2f} | sim={qc_curr['similarity']:.2f} | "
                    f"whisper={qc_curr['raw_transcript']!r}",
                )
                # Delete defective segment file before retrying
                raw_wav.unlink(missing_ok=True)
                raw_wav.with_suffix(".words.json").unlink(missing_ok=True)
                if try_idx < max_tries:
                    log("QC_RETRY", f"{segment_id}: menghapus WAV cacat & auto-retry ({try_idx + 1}/{max_tries}) dengan arahan artikulasi tenang...")

            if qc_enabled and qc_result is None and best_wav_bytes is not None and best_qc is not None:
                raw_wav.write_bytes(best_wav_bytes)
                qc_result = best_qc
                model_used = best_model
                final_style_used = best_style
                log(
                    "QC_WARN",
                    f"{segment_id}: masih belum 100% lolos setelah {max_tries} percobaan — memakai take terbaik "
                    f"(wps={qc_result['words_per_sec']:.2f}, sim={qc_result['similarity']:.2f}, reasons={qc_result['reasons']})",
                )

        if qc_result is not None:
            status_tag = "PASS" if qc_result["passed"] else "WARN"
            pov_status = "OK" if qc_result["pov_ok"] else f"MISSING({','.join(qc_result['missing_pov_words'])})"
            log(
                "QC",
                f"{segment_id} [{status_tag}] {qc_result['words_per_sec']:.2f} kata/detik | "
                f"sim={qc_result['similarity']:.2f} | POV={pov_status} | "
                f"asli={vo_text!r} | whisper={qc_result['raw_transcript']!r}",
            )

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
        words_per_sec = round(word_count / max(0.1, speech_dur), 2)

        seg_entry: Dict[str, Any] = {
            "segment_id": segment_id,
            "shot_id": shot_id,
            "shot_filename": f"shot_{shot_id:02d}.mp4",
            "start_sec": start_sec,
            "end_sec": end_sec,
            "duration_sec": seg_dur,
            "speech_duration_sec": speech_dur,
            "post_silence_sec": round(pause_after, 4),
            "pause_after_sec": round(pause_after, 4),
            "words_per_sec": words_per_sec,
            "recommended_flow_clip_sec": rec_flow_sec,
            "recommended_flow_duration_sec": rec_flow_sec,
            "vo_text": vo_text,
            "speech_metadata": {"style": final_style_used},
            "tts_model": model_used,
            "words": timed_words_global,
        }
        if shot_label:
            seg_entry["shot_label"] = shot_label
        if qc_result is not None:
            seg_entry["qc"] = qc_result
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
        "pipeline_version": "4.2-mobile-first-flow",
        "episode_id": str(spec.get("episode_id") or ep_id.split("_")[0].upper()),
        "episode_slug": ep_id,
        "title": str(spec.get("title", ep_id)),
        "voice": voice_name,
        "vo_speed": vo_speed,
        "subtitle_margin_v": margin_v,
        "total_words": total_words,
        "total_duration_sec": master_dur,
        "recommended_total_flow_sec": sum(int(s["recommended_flow_clip_sec"]) for s in manifest_segments),
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
        qc_info = s.get("qc") or {}
        qc_badge = "PASS" if qc_info.get("passed") else ("SKIP" if not qc_info else "WARN")
        log(
            "FLOW_PLAN",
            f"  {s['segment_id']} ({s['shot_filename']}) | VO {s['start_sec']:5.2f}s–{s['end_sec']:5.2f}s "
            f"(speech={s['speech_duration_sec']:4.2f}s + silence={s['post_silence_sec']:4.2f}s = {s['duration_sec']:4.2f}s, "
            f"{s['words_per_sec']:.2f} wps, QC={qc_badge}) -> Flow: {s['recommended_flow_clip_sec']}s",
        )

    if not args.no_drive:
        ep_drive_id = ensure_drive_folder(ep_id, args.drive_episodes_folder)
        raw_clips_drive_id = ensure_drive_folder("raw_clips", ep_drive_id)
        upload_or_update_drive_file(spec_path, ep_drive_id)
        upload_or_update_drive_file(vo_master_wav, ep_drive_id)
        upload_or_update_drive_file(manifest_path, ep_drive_id)
        upload_or_update_drive_file(ass_path, ep_drive_id)
        log(
            "DRIVE",
            f"Synced 4 VO v4.2 artifacts (clean overwrite, 0 duplicates) -> Drive 04_episodes/{ep_id}/ "
            f"(folder ID: {ep_drive_id} | raw_clips ID: {raw_clips_drive_id})",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
