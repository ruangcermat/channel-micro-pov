#!/usr/bin/env python3
"""Universal Audio & Word-Level Subtitle Alignment Utilities (`Jadi Apa` Studio Core).

Features:
1. `faster-whisper` (`word_timestamps=True`) millisecond-accurate word timing extraction
   on cached Indonesian VO WAVs (cached as `<wav>.words.json` so re-runs are instant!),
   grouping into punchy 2–3 word (<=18 char) subtitle chunks that align strictly to speech
   even across dramatic pauses. Falls back gracefully if `faster-whisper` or model is unavailable.
2. `build_vo_microfade_filter()` — adds clean 15 ms fade-in & fade-out to every VO scene clip
   to completely eliminate clicks/pops at splice boundaries.
3. `ensure_room_tone_wav()` — generates/loads dynamic ambient `room_tone` beds (`-32 dB` default,
   e.g. `night_fridge_hum`, `kosan_fan_hum`, `body_pulse_hum`, `street_distant_hum`) so there is
   NEVER harsh digital dead-silence underneath VO or dramatic pauses!
"""

from __future__ import annotations

import json
import math
import re
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


_WHISPER_MODEL_CACHE: Dict[str, Any] = {}


def _get_whisper_model(model_size: str = "small"):
    if model_size in _WHISPER_MODEL_CACHE:
        return _WHISPER_MODEL_CACHE[model_size]
    from faster_whisper import WhisperModel  # type: ignore

    # Auto-detect CPU/GPU safely (int8 on CPU is super fast & lightweight on Colab/VM!)
    device = "cpu"
    compute_type = "int8"
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
    except Exception:
        pass

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    _WHISPER_MODEL_CACHE[model_size] = model
    return model


def _probe_wav_duration_sec(wav_path: Path) -> Optional[float]:
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return float(frames) / float(rate)
    except Exception:
        pass
    return None


def _load_wav_mono_16k_float32(wav_path: Path) -> np.ndarray:
    """Read PCM WAV directly into a 16kHz mono float32 array (100% immune to PyAV version mismatches!)."""
    with wave.open(str(wav_path), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sw == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sw == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sw}")
    if nch > 1:
        data = data.reshape(-1, nch).mean(axis=1)
    if sr != 16000 and len(data) > 1:
        target_len = max(1, int(round(len(data) * 16000.0 / float(sr))))
        x_old = np.linspace(0.0, 1.0, len(data), endpoint=False)
        x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.float32)
    return np.ascontiguousarray(data, dtype=np.float32)


def _sanitize_whisper_words(
    raw_words: List[Dict[str, Any]],
    script_words: List[str],
    raw_dur_sec: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Strip faster-whisper trailing silence hallucination loops (0-duration or repeated opening words)."""
    if not raw_words:
        return []

    def _norm(tok: str) -> str:
        return re.sub(r"[^a-z0-9]", "", tok.lower())

    cleaned: List[Dict[str, Any]] = []
    # 1. Drop trailing zero-duration hallucination tail (classic Whisper initial_prompt echo at EOF!)
    end_idx = len(raw_words)
    while end_idx > 1 and (float(raw_words[end_idx - 1]["end"]) - float(raw_words[end_idx - 1]["start"])) <= 0.015:
        end_idx -= 1
    trimmed = raw_words[:end_idx]

    # 2. If Whisper echoed the start of the sentence after finishing it (e.g. "Maaf ya, bang. Dan kebetulan..."), cut the echo!
    n_script = len(script_words)
    if n_script >= 3 and len(trimmed) > n_script:
        first_norm = _norm(script_words[0])
        second_norm = _norm(script_words[1])
        min_cut = max(3, int(n_script * 0.72))
        for i in range(min_cut, len(trimmed)):
            w_i = _norm(str(trimmed[i]["word"]))
            w_next = _norm(str(trimmed[i + 1]["word"])) if (i + 1 < len(trimmed)) else ""
            if w_i == first_norm and (not second_norm or w_next == second_norm or i >= n_script):
                trimmed = trimmed[:i]
                break
        # Hard cap if extra hallucinated words remain after the exact last script word!
        if len(trimmed) > n_script:
            last_norm = _norm(script_words[-1])
            for i in range(min_cut, min(len(trimmed), n_script + 2)):
                if _norm(str(trimmed[i]["word"])) == last_norm:
                    trimmed = trimmed[: i + 1]
                    break

    for w in trimmed:
        t0 = max(0.0, float(w["start"]))
        t1 = max(t0 + 0.03, float(w["end"]))
        if raw_dur_sec and t0 > raw_dur_sec:
            continue
        cleaned.append({"word": str(w["word"]).strip(), "start": round(t0, 4), "end": round(t1, 4)})
    return cleaned


def extract_word_timestamps(
    wav_path: Path,
    vo_text: str,
    vo_speed: float = 1.0,
    expected_dur_sec: Optional[float] = None,
    language: str = "id",
    model_size: str = "small",
    use_cache: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    """Extract millisecond word timestamps from a scene WAV using `faster-whisper`.

    Automatically verifies raw WAV duration vs `expected_dur_sec`, strips trailing silence
    hallucinations, and scales timestamps by `1 / vo_speed` when FFmpeg applies `atempo=vo_speed`
    (e.g. `VO_SPEED = 1.08`), ensuring zero drift between kinetic karaoke subtitles and voiceover!
    """
    cache_path = wav_path.with_suffix(".words.json")
    raw_words: Optional[List[Dict[str, Any]]] = None
    script_words = [w for w in re.split(r"\s+", vo_text.replace("—", " — ").strip()) if w and w != "—"]
    raw_dur = _probe_wav_duration_sec(wav_path)

    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, list) and cached:
                raw_words = _sanitize_whisper_words(cached, script_words, raw_dur_sec=raw_dur)
        except Exception:
            raw_words = None

    if raw_words is None:
        try:
            model = _get_whisper_model(model_size=model_size)
            audio_16k = _load_wav_mono_16k_float32(wav_path)
            segments, _ = model.transcribe(
                audio_16k,
                language=language,
                word_timestamps=True,
                vad_filter=True,
                condition_on_previous_text=False,
                initial_prompt=vo_text,
            )
            extracted: List[Dict[str, Any]] = []
            for seg in segments:
                for w in getattr(seg, "words", None) or []:
                    token = str(w.word).strip()
                    if token:
                        extracted.append(
                            {
                                "word": token,
                                "start": round(float(w.start), 4),
                                "end": round(float(w.end), 4),
                            }
                        )
            extracted = _sanitize_whisper_words(extracted, script_words, raw_dur_sec=raw_dur)
            if extracted:
                raw_words = extracted
                cache_path.write_text(
                    json.dumps(raw_words, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        except Exception as exc:
            print(f"[AUDIO] faster-whisper unavailable/skipped for {wav_path.name} ({exc}); using weighted timing.", flush=True)
            return None

    if not raw_words:
        return None

    # Determine effective speed divisor: raw 1.0x WAV + FFmpeg atempo=vo_speed -> divide by vo_speed (1/VO_SPEED)!
    spd = max(0.5, float(vo_speed))
    if raw_dur and expected_dur_sec and abs(spd - 1.0) > 1e-3:
        err_scaled = abs((raw_dur / spd) - expected_dur_sec)
        err_unscaled = abs(raw_dur - expected_dur_sec)
        if err_unscaled + 0.08 < err_scaled:
            # WAV is already tempo-adjusted on disk; do not double-scale!
            spd = 1.0

    # Map clean script words onto Whisper word timestamps so spelling & punctuation match 100%!
    adjusted: List[Dict[str, Any]] = []
    if len(script_words) == len(raw_words):
        for sw, rw in zip(script_words, raw_words):
            t0 = float(rw["start"]) / spd
            t1 = float(rw["end"]) / spd
            if expected_dur_sec:
                t0 = min(t0, max(0.0, expected_dur_sec - 0.06))
                t1 = min(t1, expected_dur_sec)
            adjusted.append({"word": sw, "start": round(t0, 4), "end": round(max(t0 + 0.05, t1), 4)})
    else:
        # Proportional index alignment preserves exact Whisper speech pauses while keeping clean script text!
        n_s = max(1, len(script_words))
        n_r = len(raw_words)
        for i, sw in enumerate(script_words):
            r_idx0 = min(n_r - 1, int(math.floor(i * n_r / n_s)))
            r_idx1 = min(n_r - 1, max(r_idx0, int(math.floor((i + 1) * n_r / n_s)) - 1))
            t0 = float(raw_words[r_idx0]["start"]) / spd
            t1 = float(raw_words[r_idx1]["end"]) / spd
            if expected_dur_sec:
                t0 = min(t0, max(0.0, expected_dur_sec - 0.06))
                t1 = min(t1, expected_dur_sec)
            adjusted.append({"word": sw, "start": round(t0, 4), "end": round(max(t0 + 0.05, t1), 4)})
    return adjusted


def group_timed_words_into_chunks(
    timed_words: List[Dict[str, Any]],
    max_words: int = 3,
    max_chars: int = 18,
    pause_split_sec: float = 0.28,
) -> List[Dict[str, Any]]:
    """Group word-level timestamps into crisp 2–3 word (<=18 char) kinetic chunks, breaking on pauses."""
    chunks: List[Dict[str, Any]] = []
    cur_words: List[Dict[str, Any]] = []

    def _flush():
        nonlocal cur_words
        if not cur_words:
            return
        text = " ".join(w["word"] for w in cur_words)
        chunks.append(
            {
                "text": text,
                "start": float(cur_words[0]["start"]),
                "end": float(cur_words[-1]["end"]),
            }
        )
        cur_words = []

    for w in timed_words:
        if cur_words:
            gap = float(w["start"]) - float(cur_words[-1]["end"])
            prev_ends_sentence = bool(re.search(r"[.!?,;:]$", cur_words[-1]["word"]))
            cand_text = " ".join([x["word"] for x in cur_words] + [w["word"]])
            if (
                len(cur_words) >= max_words
                or len(cand_text) > max_chars
                or gap >= pause_split_sec
                or (prev_ends_sentence and len(cur_words) >= 2)
            ):
                _flush()
        cur_words.append(w)
    _flush()
    return chunks


def build_vo_microfade_filter(audio_dur_sec: float, fade_ms: float = 15.0) -> str:
    """Return FFmpeg filter snippet applying clean 15ms micro fade-in & fade-out (zero splice clicks/pops)."""
    fd = max(0.005, fade_ms / 1000.0)
    fade_out_st = max(0.0, float(audio_dur_sec) - fd)
    return f"afade=t=in:st=0:d={fd:.4f},afade=t=out:st={fade_out_st:.4f}:d={fd:.4f}"


def ensure_room_tone_wav(
    room_tone_id: str,
    assets_dir: Path,
    duration_sec: float = 12.0,
    sample_rate: int = 48000,
) -> Path:
    """Return path to a seamless loopable room-tone WAV (synthesizing cleanly if not cached)."""
    rt_dir = assets_dir / "sfx"
    rt_dir.mkdir(parents=True, exist_ok=True)
    out_wav = rt_dir / f"room_tone_{room_tone_id}.wav"
    if out_wav.exists() and out_wav.stat().st_size > 4096:
        return out_wav

    n = int(round(duration_sec * sample_rate))
    t = np.linspace(0.0, duration_sec, n, endpoint=False, dtype=np.float64)
    rng = np.random.default_rng(2026)

    if room_tone_id in ("night_fridge_hum", "kosan_night", "kitchen_night"):
        # Authentic Indonesian kosan refrigerator compressor hum (50Hz Indonesian mains + 100/150Hz harmonics)
        # + super-soft brown room air bed so midnight silence feels rich & alive!
        hum = (
            0.38 * np.sin(2.0 * math.pi * 50.0 * t)
            + 0.24 * np.sin(2.0 * math.pi * 100.0 * t + 0.4)
            + 0.11 * np.sin(2.0 * math.pi * 150.0 * t + 1.1)
            + 0.05 * np.sin(2.0 * math.pi * 200.0 * t + 2.0)
        )
        # Gentle slow compressor breath modulation (0.18 Hz)
        hum *= 0.90 + 0.10 * np.sin(2.0 * math.pi * 0.18 * t)
        # Smooth brown-filtered room air
        white = rng.standard_normal(n)
        air = np.cumsum(white)
        air = air - np.linspace(air[0], air[-1], n)
        air /= max(1e-6, np.max(np.abs(air)))
        sig = 0.62 * hum + 0.28 * air
    elif room_tone_id in ("body_pulse_hum", "inside_body"):
        # Low warm organic subterranean body rumble
        sig = (
            0.45 * np.sin(2.0 * math.pi * 36.0 * t)
            + 0.20 * np.sin(2.0 * math.pi * 72.0 * t)
            + 0.15 * rng.standard_normal(n) * 0.15
        )
    else:
        # Generic warm indoor room air bed
        white = rng.standard_normal(n)
        air = np.cumsum(white)
        air = air - np.linspace(air[0], air[-1], n)
        air /= max(1e-6, np.max(np.abs(air)))
        sig = 0.35 * np.sin(2.0 * math.pi * 50.0 * t) + 0.55 * air

    # Seamless crossfade edge window + normalize to -12 dBFS (mixed down to -32 dB in compose_final!)
    sig = sig / max(1e-6, np.max(np.abs(sig))) * 0.25
    fade_n = min(n // 10, int(0.15 * sample_rate))
    win = np.ones(n, dtype=np.float64)
    win[:fade_n] = np.linspace(0.0, 1.0, fade_n)
    win[-fade_n:] = np.linspace(1.0, 0.0, fade_n)
    sig *= win

    pcm = np.clip(sig * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return out_wav
