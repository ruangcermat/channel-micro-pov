#!/usr/bin/env python3
"""Audio-First Voiceover Generator using Gemini 3.8 Flash TTS.

STRICT ARCHITECTURE RULES:
1. Uses `gemini-3.8-flash-tts` as primary model and `gemini-3.8-flash-lite-tts` as fallback.
2. Reads `GEMINI_API_KEY` from environment variable or Google Colab Secrets.
3. NEVER concatenates `vo_delivery` or `voice_persona` into `vo_text`.
   - `text` contains ONLY clean verbatim `vo_text`.
   - Acting instructions (`voice_persona` + `vo_delivery`) are sent strictly via
     `speech_metadata` (`style`), so instructions are NEVER spoken aloud verbatim.
4. Measures actual generated WAV duration for each scene and writes `timing_manifest.json`
   as the single source of truth for 3D Blender animation frame lengths (Audio-First!).
"""

from __future__ import annotations

import argparse
import base64
import math
import os
import struct
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline_utils import (
    get_repo_root,
    load_and_validate_spec,
    log,
    resolve_episode_work_dir,
    save_json,
)

DEFAULT_PRIMARY_MODEL = "gemini-3.8-flash-tts"
DEFAULT_FALLBACK_MODEL = "gemini-3.8-flash-lite-tts"
DEFAULT_VOICE = "Puck"
DEFAULT_FPS = 24
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_PAD_SEC = 0.06
DEFAULT_VO_SPEED = 1.08


def get_gemini_api_key() -> Optional[str]:
    """Read GEMINI_API_KEY from environment or Google Colab userdata secrets."""
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_name)
        if val and val.strip():
            return val.strip()

    try:
        from google.colab import userdata  # type: ignore

        for secret_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            try:
                val = userdata.get(secret_name)
                if val and val.strip():
                    return val.strip()
            except Exception:
                continue
    except ImportError:
        pass
    return None


def save_wav_bytes(
    dest_path: Path,
    audio_bytes: bytes,
    channels: int = 1,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    sample_width: int = 2,
) -> None:
    """Save either a complete RIFF WAV container or raw 16-bit PCM bytes to a .wav file."""
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
    """Return exact duration of a WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError(f"Invalid WAV sample rate in {wav_path}")
        return frames / float(rate)


def build_style_prompt(tts_config: Dict[str, Any], scene: Dict[str, Any]) -> str:
    """Compose clean turn-level style metadata (NEVER placed into text)."""
    language = tts_config.get("language", "id-ID")
    persona = tts_config.get(
        "voice_persona",
        "Teman nongkrong Indonesia yang ekspresif, ritme cepat, artikulasi jelas",
    )
    delivery = scene.get("vo_delivery", "").strip()
    parts = [
        f"Language/Accent: natural spoken Indonesian ({language}).",
        f"Persona: {persona}.",
    ]
    if delivery:
        parts.append(f"Delivery for this line: {delivery}.")
    return " ".join(parts)


def _decode_audio_payload(data: Any) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return base64.b64decode(data)
    raise TypeError(f"Unsupported audio payload type: {type(data)}")


def _wrap_print(prefix: str, text: str, width: int = 100) -> None:
    """Print long error/payload messages wrapped cleanly across lines."""
    import textwrap

    for raw_line in text.splitlines() or [""]:
        wrapped = textwrap.wrap(raw_line, width=width, break_long_words=True, break_on_hyphens=False)
        if not wrapped:
            print(f"[{prefix}]", flush=True)
        else:
            for line in wrapped:
                print(f"[{prefix}] {line}", flush=True)


def _extract_audio_from_response(response: Any, model_id: str) -> bytes:
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None and getattr(inline_data, "data", None):
                mime = getattr(inline_data, "mime_type", "") or ""
                raw_bytes = _decode_audio_payload(inline_data.data)
                if raw_bytes[:4] == b"RIFF":
                    log("TTS", f"Received WAV (RIFF) audio ({len(raw_bytes)} bytes, mime={mime or 'audio/wav'})")
                else:
                    log("TTS", f"Received raw PCM audio ({len(raw_bytes)} bytes, mime={mime or 'audio/l16'}); wrapping with 24kHz mono WAV header")
                return raw_bytes
    raise RuntimeError(f"Model {model_id} returned no inline audio data: {repr(response)}")


def synthesize_with_gemini(
    client: Any,
    model_id: str,
    vo_text: str,
    style_prompt: str,
    voice_name: str,
) -> bytes:
    """Call Gemini 3.8 TTS (v1beta) via client.models.generate_content.

    Strict separation:
    - contents[].parts[].text contains ONLY verbatim vo_text
    - contents[].parts[].speech_metadata contains ONLY {"style": style_prompt}
    - config.speech_config.voice_config uses {"voice": voice_name} with fallback to
      {"prebuilt_voice_config": {"voice_name": voice_name}} only if SDK rejects "voice".
    """
    clean_text = vo_text.strip()
    if not clean_text:
        raise ValueError("vo_text is empty")

    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": clean_text,
                    "speech_metadata": {
                        "style": style_prompt,
                    },
                }
            ],
        }
    ]

    primary_config = {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "voice": voice_name,
            }
        },
    }
    fallback_config = {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {
                    "voice_name": voice_name,
                }
            }
        },
    }

    payload_primary = {"model": model_id, "contents": contents, "config": primary_config}
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=contents,
            config=primary_config,
        )
        return _extract_audio_from_response(response, model_id)
    except Exception as exc:
        err_str = str(exc)
        _wrap_print("TTS_ERR", f"Primary voice_config.{{\"voice\"}} failed on {model_id}: {err_str}")
        _wrap_print("TTS_PAYLOAD", f"repr(payload) = {repr(payload_primary)}")

        # Fallback to prebuilt_voice_config ONLY if SDK/schema rejected the "voice" key
        voice_key_rejected = any(
            marker in err_str.lower()
            for marker in ("voice", "prebuilt_voice_config", "extra inputs", "validation", "unknown field", "unexpected keyword")
        )
        if not voice_key_rejected:
            raise

        payload_fallback = {"model": model_id, "contents": contents, "config": fallback_config}
        log("TTS", f"Retrying {model_id} with prebuilt_voice_config fallback...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=fallback_config,
            )
            return _extract_audio_from_response(response, model_id)
        except Exception as exc2:
            _wrap_print("TTS_ERR", f"Fallback prebuilt_voice_config failed on {model_id}: {exc2}")
            _wrap_print("TTS_PAYLOAD", f"repr(payload) = {repr(payload_fallback)}")
            raise


def synthesize_scene_with_fallback(
    client: Any,
    primary_model: str,
    fallback_model: str,
    vo_text: str,
    style_prompt: str,
    voice_name: str,
    retries: int = 2,
) -> Tuple[bytes, str]:
    """Try primary model (gemini-3.8-flash-tts), falling back to gemini-3.8-flash-lite-tts."""
    models = [primary_model]
    if fallback_model and fallback_model != primary_model:
        models.append(fallback_model)

    last_err: Optional[Exception] = None
    for model_id in models:
        for attempt in range(1, retries + 1):
            try:
                audio_bytes = synthesize_with_gemini(
                    client=client,
                    model_id=model_id,
                    vo_text=vo_text,
                    style_prompt=style_prompt,
                    voice_name=voice_name,
                )
                return audio_bytes, model_id
            except Exception as exc:
                last_err = exc
                _wrap_print("TTS", f"Attempt {attempt}/{retries} failed on {model_id}: {exc}")
                if attempt < retries:
                    time.sleep(2.0 * attempt)
        log("TTS", f"Switching from {model_id} to fallback model...")

    raise RuntimeError(f"All Gemini TTS models failed: {last_err}")


def generate_dry_run_wav(dest_path: Path, duration_sec: float, scene_id: int) -> None:
    """Create a clean low-volume placeholder speech-cadence WAV for offline dry-run testing."""
    sr = DEFAULT_SAMPLE_RATE
    n_samples = max(int(duration_sec * sr), sr // 2)
    base_freq = 190.0 + (scene_id * 17.0)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sr
        # Gentle syllable-like amplitude modulation so sidechain ducking can be verified
        syllable_env = 0.5 + 0.5 * math.sin(2.0 * math.pi * 4.2 * t)
        fade = min(1.0, t / 0.04, max(0.0, (duration_sec - t) / 0.08))
        val = (
            0.18
            * fade
            * syllable_env
            * (0.7 * math.sin(2.0 * math.pi * base_freq * t) + 0.3 * math.sin(2.0 * math.pi * (base_freq * 2.0) * t))
        )
        sample = max(-32767, min(32767, int(val * 32767)))
        buf.extend(struct.pack("<h", sample))

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(bytes(buf))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Audio-First VO WAVs with Gemini 3.8 TTS and export timing_manifest.json."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
        help="Path to episode spec JSON",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default=None,
        help="Episode output/working directory (defaults to Drive episode dir if mounted)",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        help=f"Gemini prebuilt voice name or custom voice ID (default: {DEFAULT_VOICE})",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help="Target animation frame rate for frame counts (default: 24)",
    )
    parser.add_argument(
        "--pad-sec",
        type=float,
        default=DEFAULT_PAD_SEC,
        help="Breathing padding appended after each scene VO audio (default: 0.06s)",
    )
    parser.add_argument(
        "--vo-speed",
        type=float,
        default=DEFAULT_VO_SPEED,
        help="Playback tempo multiplier for VO via FFmpeg atempo (default: 1.08, reuses cached WAVs)",
    )
    parser.add_argument(
        "--scene",
        type=int,
        default=None,
        help="Regenerate VO only for a single scene_id (still rebuilds full timing_manifest.json)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing scene_XX.wav files if already generated",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate offline placeholder WAVs using est_duration_sec (no API calls)",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    work_dir = resolve_episode_work_dir(spec_path, args.work_dir)
    vo_dir = work_dir / "raw_render" / "vo"
    vo_dir.mkdir(parents=True, exist_ok=True)

    tts_cfg = spec.get("tts_config", {})
    primary_model = tts_cfg.get("model", DEFAULT_PRIMARY_MODEL)
    fallback_model = tts_cfg.get("fallback_model", DEFAULT_FALLBACK_MODEL)
    voice_name = args.voice or tts_cfg.get("voice_name", DEFAULT_VOICE)
    vo_speed = max(0.5, min(2.0, float(args.vo_speed)))

    client = None
    if not args.dry_run:
        api_key = get_gemini_api_key()
        if not api_key:
            log(
                "ERROR",
                "GEMINI_API_KEY tidak ditemukan di environment variable maupun Colab Secrets! "
                "Set GEMINI_API_KEY terlebih dahulu atau jalankan dengan --dry-run untuk uji offline.",
            )
            return 1
        try:
            from google import genai
        except ImportError as exc:
            log("ERROR", f"google-genai SDK belum terinstall (`pip install 'google-genai>=2.24.0'`): {exc}")
            return 1
        client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    log("TTS", f"Episode: {spec['episode_id']} | Primary: {primary_model} | Fallback: {fallback_model} | Voice: {voice_name} | VO Speed: {vo_speed}x")
    log("TTS", f"VO output dir: {vo_dir}")

    scenes_manifest: List[Dict[str, Any]] = []
    cursor_sec = 0.0
    cursor_frame = 1

    for scene in spec["scenes"]:
        sid = int(scene["scene_id"])
        wav_path = vo_dir / f"scene_{sid:02d}.wav"
        vo_text = scene["vo_text"].strip()
        style_prompt = build_style_prompt(tts_cfg, scene)
        used_model = "cached"

        should_generate = True
        if args.scene is not None and sid != args.scene:
            should_generate = not wav_path.exists()
        elif args.skip_existing and wav_path.exists() and wav_path.stat().st_size > 1024:
            should_generate = False

        if should_generate:
            if args.dry_run:
                est_dur = float(scene.get("est_duration_sec", 4.0))
                target_audio = max(1.0, (est_dur - args.pad_sec) * vo_speed)
                generate_dry_run_wav(wav_path, target_audio, sid)
                used_model = "dry_run_placeholder"
                log("TTS", f"[DRY-RUN] Scene {sid:02d} -> {wav_path.name} (raw {target_audio:.2f}s)")
            else:
                log("TTS", f"Generating Scene {sid:02d}: text='{vo_text[:55]}...' | style='{style_prompt[:60]}...'")
                audio_bytes, used_model = synthesize_scene_with_fallback(
                    client=client,
                    primary_model=primary_model,
                    fallback_model=fallback_model,
                    vo_text=vo_text,
                    style_prompt=style_prompt,
                    voice_name=voice_name,
                )
                save_wav_bytes(wav_path, audio_bytes)
                log("TTS", f"[OK:{used_model}] Scene {sid:02d} saved -> {wav_path.name}")
        else:
            log("TTS", f"[CACHED] Scene {sid:02d} reusing {wav_path.name}")

        raw_audio_dur = measure_wav_duration(wav_path)
        audio_dur = raw_audio_dur / vo_speed

        # Scene 6: 0.15s pre-VO pause so record_scratch at 0.0s doesn't overlap "kaki"
        vo_delay_sec = 0.15 if sid == 6 else 0.0

        # Scene 8: human_scream_cut triggers dynamically at audio_dur + 0.05s, cut to black 0.35s later
        scream_offset_sec: Optional[float] = None
        cut_to_black_sec: Optional[float] = None
        if sid == len(spec["scenes"]):
            scream_offset_sec = round(vo_delay_sec + audio_dur + 0.05, 4)
            cut_to_black_sec = round(scream_offset_sec + 0.35, 4)
            scene_dur = cut_to_black_sec
        else:
            max_sfx_offset = max(
                (float(c["offset_sec"]) for c in scene.get("sfx_cues", []) if c["sfx_id"] != "human_scream_cut"),
                default=0.0,
            )
            scene_dur = max(vo_delay_sec + audio_dur + args.pad_sec, max_sfx_offset + 0.20)

        frame_count = max(1, int(round(scene_dur * args.fps)))
        exact_scene_dur = frame_count / float(args.fps)
        start_frame = cursor_frame
        end_frame = cursor_frame + frame_count - 1

        entry: Dict[str, Any] = {
            "scene_id": sid,
            "wav_path": str(wav_path),
            "vo_text": vo_text,
            "vo_delivery": scene.get("vo_delivery", ""),
            "style_metadata_sent": style_prompt,
            "on_screen_text": scene.get("on_screen_text", ""),
            "model_used": used_model,
            "raw_audio_duration_sec": round(raw_audio_dur, 4),
            "audio_duration_sec": round(audio_dur, 4),
            "vo_delay_sec": vo_delay_sec,
            "vo_speed": vo_speed,
            "scene_duration_sec": round(exact_scene_dur, 4),
            "start_sec": round(cursor_sec, 4),
            "end_sec": round(cursor_sec + exact_scene_dur, 4),
            "start_frame": start_frame,
            "end_frame": end_frame,
            "frame_count": frame_count,
            "est_duration_sec": float(scene.get("est_duration_sec", 4.0)),
        }
        if scream_offset_sec is not None:
            entry["scream_offset_sec"] = scream_offset_sec
            entry["cut_to_black_sec"] = cut_to_black_sec

        scenes_manifest.append(entry)

        cursor_sec += exact_scene_dur
        cursor_frame = end_frame + 1

    manifest = {
        "episode_id": spec["episode_id"],
        "title": spec["title"],
        "fps": args.fps,
        "vo_speed": vo_speed,
        "pad_sec": args.pad_sec,
        "voice_name": voice_name,
        "primary_model": primary_model,
        "fallback_model": fallback_model,
        "total_duration_sec": round(cursor_sec, 4),
        "total_frames": cursor_frame - 1,
        "audio_first_verified": True,
        "scenes": scenes_manifest,
    }

    manifest_path = work_dir / "timing_manifest.json"
    save_json(manifest_path, manifest)
    log(
        "TTS",
        f"Timing manifest written: {manifest_path} | Total: {manifest['total_duration_sec']:.2f}s ({manifest['total_frames']} frames @ {args.fps}fps)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
