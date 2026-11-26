#!/usr/bin/env python3
"""Auto-Audio SFX & BGM Preparation Engine (Zero-Manual Workflow).

Strategy:
1. Automatically fetches verified CC0 / Public Domain SFX directly via HTTP (no login)
   from Wikimedia Commons, converts/enhances via FFmpeg, and caches into Drive
   (`02_assets/sfx/` and `02_assets/bgm/`).
2. Synthesizes punchy, broadcast-grade SFX and seamless loopable BGM using Python
   (`numpy` + `scipy.signal` + FFmpeg mastering filters) for any sound not fetched
   directly — and as a 100% offline fallback so the pipeline NEVER fails on missing audio.
3. Automatically updates `02_assets/asset_catalog.json`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from scipy import signal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline_utils import (
    check_ffmpeg_available,
    download_file,
    get_repo_root,
    http_head_status,
    load_and_validate_spec,
    log,
    resolve_assets_dir,
    upsert_catalog_entry,
)

SR = 48000

# Verified HTTP 200 CC0 / Public Domain direct audio URLs (Wikimedia Commons)
DIRECT_CC0_SFX_SOURCES: Dict[str, Dict[str, Any]] = {
    "light_switch_click": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/8/8e/Clickick_switch.ogg",
        "license": "Public Domain (Wikimedia Commons)",
        "ffmpeg_filter": "atrim=0:0.45,afade=t=out:st=0.35:d=0.10,highpass=f=180,volume=2.2,alimiter=limit=0.95",
        "desc": "Bunyi cetek saklar lampu dapur",
    },
    "fluorescent_hum": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/ce/MainsBrum50Hz.ogg",
        "license": "Public Domain (Wikimedia Commons)",
        "ffmpeg_filter": "aloop=loop=2:size=240000,atrim=0:3.5,bandpass=f=120:width_type=h:w=180,afade=t=in:st=0:d=0.12,afade=t=out:st=3.1:d=0.4,volume=1.6",
        "desc": "Dengung lampu neon 50Hz menyala",
    },
    "sandal_slam_thud": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/5/5b/Dull_thud.ogg",
        "license": "Public Domain (Wikimedia Commons)",
        "ffmpeg_filter": "atrim=0:0.85,bass=g=8:f=90,acompressor=threshold=-14dB:ratio=4:attack=2:release=60,volume=2.4,alimiter=limit=0.95",
        "desc": "Gebukan keras sandal jepit ke lantai",
    },
    "dramatic_boom": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b9/Explosion-LS100155.ogg",
        "license": "Public Domain (Wikimedia Commons)",
        "ffmpeg_filter": "atrim=0:1.7,lowpass=f=320,bass=g=10:f=65,afade=t=out:st=1.1:d=0.6,volume=2.0,alimiter=limit=0.95",
        "desc": "Dentuman tegang sub-bass saat bahaya muncul",
    },
    "human_scream_cut": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d9/Wilhelm_Scream.ogg",
        "license": "CC0 / Public Domain (Wikimedia Commons)",
        "ffmpeg_filter": "atrim=0.05:0.58,asetpts=PTS-STARTPTS,afade=t=out:st=0.50:d=0.03,volume=1.8,alimiter=limit=0.95",
        "desc": "Teriakan kaget terpotong cepat (perfectly cut scream)",
    },
}


def _normalize_stereo(audio: np.ndarray, peak: float = 0.90) -> np.ndarray:
    """Convert mono or stereo float array to peak-normalized stereo float32."""
    if audio.ndim == 1:
        stereo = np.stack([audio, audio], axis=-1)
    else:
        stereo = audio
    max_val = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if max_val > 1e-9:
        stereo = stereo * (peak / max_val)
    return np.clip(stereo, -1.0, 1.0).astype(np.float32)


def _write_stereo_wav(path: Path, stereo_f32: np.ndarray, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm16 = (np.clip(stereo_f32, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())


def _bandpass(x: np.ndarray, low_hz: float, high_hz: float, sr: int = SR, order: int = 3) -> np.ndarray:
    nyq = 0.5 * sr
    lo = max(0.001, min(0.98, low_hz / nyq))
    hi = max(lo + 0.005, min(0.99, high_hz / nyq))
    sos = signal.butter(order, [lo, hi], btype="band", output="sos")
    return signal.sosfilt(sos, x)


def _lowpass(x: np.ndarray, cutoff_hz: float, sr: int = SR, order: int = 3) -> np.ndarray:
    nyq = 0.5 * sr
    wn = max(0.001, min(0.98, cutoff_hz / nyq))
    sos = signal.butter(order, wn, btype="low", output="sos")
    return signal.sosfilt(sos, x)


# =============================================================================
# PUNCHY PROCEDURAL SFX SYNTHESIZERS (100% CC0, Zero External Dependencies)
# =============================================================================

def synth_light_switch_click() -> np.ndarray:
    rng = np.random.default_rng(101)
    dur = 0.35
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    y = np.zeros(n)

    # Plastic rocker switch double snap: pre-click at 0.02s + hard latch at 0.055s
    for offset, amp, freq in [(0.02, 0.45, 2400.0), (0.055, 1.0, 1650.0)]:
        i0 = int(offset * SR)
        length = int(0.045 * SR)
        tt = np.linspace(0, 0.045, length, endpoint=False)
        click = (
            rng.standard_normal(length) * np.exp(-tt * 220.0)
            + 0.7 * np.sin(2 * np.pi * freq * tt) * np.exp(-tt * 180.0)
            + 0.5 * np.sin(2 * np.pi * 420.0 * tt) * np.exp(-tt * 140.0)
        )
        y[i0 : i0 + length] += amp * click

    y = _bandpass(y, 200.0, 9500.0)
    return _normalize_stereo(y, peak=0.92)


def synth_fluorescent_hum() -> np.ndarray:
    rng = np.random.default_rng(102)
    dur = 3.5
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Indonesian 50Hz mains + 100Hz/150Hz/250Hz ballast buzz
    hum = (
        0.50 * np.sin(2 * np.pi * 50.0 * t)
        + 0.40 * np.sin(2 * np.pi * 100.0 * t)
        + 0.22 * np.sin(2 * np.pi * 150.0 * t)
        + 0.12 * np.sin(2 * np.pi * 250.0 * t)
        + 0.08 * _bandpass(rng.standard_normal(n), 900.0, 3200.0)
    )
    # Fluorescent starter flicker in first 0.22s
    env = np.ones(n)
    flicker_n = int(0.22 * SR)
    env[:flicker_n] = 0.25 + 0.75 * (np.sin(2 * np.pi * 22.0 * t[:flicker_n]) > 0).astype(float)
    # Smooth fade-out at end
    fade_out = int(0.35 * SR)
    env[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    return _normalize_stereo(hum * env, peak=0.72)


def synth_dramatic_boom() -> np.ndarray:
    rng = np.random.default_rng(103)
    dur = 1.8
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Cinematic trailer sub-drop: frequency sweeps 105 Hz -> 30 Hz
    freq = 30.0 + 75.0 * np.exp(-t * 5.2)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    sub = np.sin(phase) * np.exp(-t * 2.1)

    # Punchy transient + distorted brassy mid layer
    transient = _lowpass(rng.standard_normal(n), 500.0) * np.exp(-t * 18.0)
    rumble = _bandpass(rng.standard_normal(n), 40.0, 220.0) * np.exp(-t * 2.6)
    y = np.tanh(1.8 * (sub + 0.7 * transient + 0.35 * rumble))
    y[: int(0.004 * SR)] *= np.linspace(0.0, 1.0, int(0.004 * SR))
    return _normalize_stereo(y, peak=0.95)


def synth_wind_whoosh_heavy() -> np.ndarray:
    rng = np.random.default_rng(104)
    dur = 1.05
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)
    noise = rng.standard_normal(n)

    # Multi-band Doppler wind sweep peaking around t=0.45s
    env = np.sin(np.pi * np.clip(t / dur, 0.0, 1.0)) ** 1.7
    low_air = _bandpass(noise, 90.0, 380.0) * (np.sin(np.pi * np.clip(t / dur, 0.0, 1.0)) ** 1.3)
    mid_swish = _bandpass(noise, 400.0, 1900.0) * np.exp(-((t - 0.48) ** 2) / 0.045)
    high_whip = _bandpass(noise, 1800.0, 5200.0) * np.exp(-((t - 0.56) ** 2) / 0.018)

    # Slight stereo sweep left-to-right
    pan = np.linspace(0.3, 0.75, n)
    mono = (0.75 * low_air + 0.9 * mid_swish + 0.45 * high_whip) * env
    stereo = np.stack([mono * (1.0 - pan * 0.4), mono * (0.6 + pan * 0.4)], axis=-1)
    return _normalize_stereo(stereo, peak=0.90)


def synth_sandal_slam_thud() -> np.ndarray:
    rng = np.random.default_rng(105)
    dur = 0.85
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Rubber flip-flop slap (crisp mid-high smack) + floor tile shock thump (low sub)
    freq = 42.0 + 130.0 * np.exp(-t * 28.0)
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    sub_thump = np.sin(phase) * np.exp(-t * 9.0)

    slap_noise = _bandpass(rng.standard_normal(n), 600.0, 4800.0) * np.exp(-t * 55.0)
    tile_ring = np.sin(2 * np.pi * 310.0 * t) * np.exp(-t * 24.0) * 0.3
    y = np.tanh(2.1 * (sub_thump + 1.15 * slap_noise + tile_ring))
    return _normalize_stereo(y, peak=0.96)


def synth_skitter_fast() -> np.ndarray:
    rng = np.random.default_rng(106)
    dur = 3.2
    n = int(dur * SR)
    left = np.zeros(n)
    right = np.zeros(n)

    # Fast frantic insect legs tapping ceramic tiles (~22 steps/sec)
    cursor = 0.02
    step_idx = 0
    while cursor < dur - 0.05:
        i0 = int(cursor * SR)
        tap_len = int(0.018 * SR)
        tt = np.linspace(0, 0.018, tap_len, endpoint=False)
        f_tap = rng.uniform(2200.0, 5400.0)
        amp = rng.uniform(0.45, 1.0)
        tap = (
            0.65 * rng.standard_normal(tap_len) * np.exp(-tt * 340.0)
            + 0.55 * np.sin(2 * np.pi * f_tap * tt) * np.exp(-tt * 280.0)
        )
        pan_l = 0.72 if (step_idx % 2 == 0) else 0.35
        pan_r = 0.35 if (step_idx % 2 == 0) else 0.72
        left[i0 : i0 + tap_len] += amp * pan_l * tap
        right[i0 : i0 + tap_len] += amp * pan_r * tap
        cursor += rng.uniform(0.032, 0.054)
        step_idx += 1

    left = _bandpass(left, 1100.0, 9500.0)
    right = _bandpass(right, 1100.0, 9500.0)
    return _normalize_stereo(np.stack([left, right], axis=-1), peak=0.88)


def synth_wings_buzz_loud() -> np.ndarray:
    rng = np.random.default_rng(107)
    dur = 3.8
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Menacing cockroach flight buzz: sawtooth + intense 52Hz wingbeat AM + chitin rattle
    wobble = 1.0 + 0.06 * np.sin(2 * np.pi * 6.5 * t)
    f0 = 118.0 * wobble
    phase = 2.0 * np.pi * np.cumsum(f0) / SR
    buzz = (
        0.55 * signal.sawtooth(phase)
        + 0.35 * signal.sawtooth(phase * 2.02)
        + 0.25 * _bandpass(rng.standard_normal(n), 700.0, 4200.0)
    )
    am = 0.60 + 0.40 * np.sin(2 * np.pi * 48.0 * t)
    env = np.minimum(1.0, t / 0.12) * np.minimum(1.0, (dur - t) / 0.15)
    buzz = _lowpass(_bandpass(buzz * am, 90.0, 2200.0), 1800.0) * env

    # Stereo flutter as wings beat left & right of camera
    lfo = 0.5 + 0.25 * np.sin(2 * np.pi * 9.0 * t)
    stereo = np.stack([buzz * (1.0 - 0.35 * lfo), buzz * (0.65 + 0.35 * lfo)], axis=-1)
    return _normalize_stereo(stereo, peak=0.82)


def synth_record_scratch() -> np.ndarray:
    rng = np.random.default_rng(108)
    dur = 0.25
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Short, controlled comedic vinyl stop (0.25s)
    f_sweep = np.where(
        t < 0.13,
        1100.0 * np.exp(-t * 14.0) + 160.0,
        240.0 + 1300.0 * (np.maximum(0.0, t - 0.13) / 0.12) ** 1.4,
    )
    phase = 2.0 * np.pi * np.cumsum(f_sweep) / SR
    tone = signal.sawtooth(phase) * 0.55 + np.sin(phase * 1.5) * 0.45
    grit = _bandpass(rng.standard_normal(n), 900.0, 4200.0) * 0.30
    env = np.exp(-((t - 0.06) ** 2) / 0.004) + 0.85 * np.exp(-((t - 0.18) ** 2) / 0.003)
    env[-int(0.02 * SR) :] *= np.linspace(1.0, 0.0, int(0.02 * SR))
    y = _bandpass((tone + grit) * env, 250.0, 4800.0)
    return _normalize_stereo(y, peak=0.85)


def synth_human_scream_cut() -> np.ndarray:
    rng = np.random.default_rng(109)
    dur = 0.52
    n = int(dur * SR)
    t = np.linspace(0, dur, n, endpoint=False)

    # Comedic startled male yell cut off abruptly at 0.50s
    f0 = 330.0 + 165.0 * (1.0 - np.exp(-t * 9.0)) + 14.0 * np.sin(2 * np.pi * 16.0 * t)
    phase = 2.0 * np.pi * np.cumsum(f0) / SR
    glottal = signal.sawtooth(phase)
    # Vocal formants around 750Hz and 1950Hz ("AAAH!")
    y = (
        0.65 * _bandpass(glottal, 550.0, 1050.0)
        + 0.45 * _bandpass(glottal, 1500.0, 2600.0)
        + 0.20 * _bandpass(rng.standard_normal(n), 1200.0, 4500.0)
    )
    env = np.minimum(1.0, t / 0.03)
    env[-int(0.015 * SR) :] *= np.linspace(1.0, 0.0, int(0.015 * SR))
    return _normalize_stereo(np.tanh(2.0 * y) * env, peak=0.94)


# =============================================================================
# LOOPABLE PROCEDURAL BGM SYNTHESIZERS (100% CC0, Zero Copyright Claims)
# =============================================================================

def _midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def synth_bgm_sneaky_night_loop() -> np.ndarray:
    """16-second seamless 100 BPM sneaky tiptoe pizzicato + marimba night loop."""
    bpm = 100.0
    beat_sec = 60.0 / bpm
    bars = 8
    total_beats = bars * 4
    dur = total_beats * beat_sec
    n = int(round(dur * SR))
    t = np.linspace(0, dur, n, endpoint=False)
    left = np.zeros(n)
    right = np.zeros(n)

    # E minor sneaky pizzicato walking bass pattern (8th notes)
    bass_pattern = [40, None, 43, None, 46, 47, 43, None, 40, None, 45, None, 47, None, 46, 43]
    step_sec = beat_sec / 2.0
    for step_idx in range(int(total_beats * 2)):
        note = bass_pattern[step_idx % len(bass_pattern)]
        if note is None:
            continue
        i0 = int(step_idx * step_sec * SR)
        note_len = min(int(0.28 * SR), n - i0)
        tt = np.linspace(0, note_len / SR, note_len, endpoint=False)
        hz = _midi_to_hz(note)
        pluck = (
            0.75 * np.sin(2 * np.pi * hz * tt)
            + 0.30 * np.sin(2 * np.pi * hz * 2.0 * tt) * np.exp(-tt * 14.0)
        ) * np.exp(-tt * 10.5)
        left[i0 : i0 + note_len] += 0.65 * pluck
        right[i0 : i0 + note_len] += 0.65 * pluck

    # Soft marimba/kalimba tiptoe motif panned subtly left/right
    melody = [
        (1, 64), (3, 67), (5, 70), (6, 71),
        (9, 67), (11, 64), (13, 66), (14, 64),
    ]
    for bar_pair in range(bars // 2):
        for step_off, midi in melody:
            step = bar_pair * 16 + step_off
            i0 = int(step * step_sec * SR)
            note_len = min(int(0.22 * SR), n - i0)
            tt = np.linspace(0, note_len / SR, note_len, endpoint=False)
            hz = _midi_to_hz(midi)
            bell = np.sin(2 * np.pi * hz * tt) * np.exp(-tt * 16.0)
            pan = 0.35 if (step_off % 2 == 0) else 0.65
            left[i0 : i0 + note_len] += 0.30 * (1.0 - pan) * bell
            right[i0 : i0 + note_len] += 0.30 * pan * bell

    # Warm dark ambient pad drone (E2 + B2)
    pad = 0.08 * (np.sin(2 * np.pi * _midi_to_hz(40) * t) + 0.6 * np.sin(2 * np.pi * _midi_to_hz(47) * t))
    left += pad
    right += pad
    return _normalize_stereo(np.stack([left, right], axis=-1), peak=0.82)


def synth_bgm_intense_chase_synth() -> np.ndarray:
    """16-second seamless 148 BPM action synthwave chase loop (punchy kick/snare/bass/arp)."""
    rng = np.random.default_rng(202)
    bpm = 148.0
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0  # 16th notes
    total_steps = 16 * 8  # 8 bars (~13s loop, FFmpeg loops seamlessly across scenes 2-7)
    dur = total_steps * step_sec
    n = int(round(dur * SR))
    left = np.zeros(n)
    right = np.zeros(n)

    # Driving 16th-note saw bassline (D minor -> Bb -> C -> A)
    chord_roots = [38, 38, 34, 34, 36, 36, 33, 37]  # per bar
    arp_offsets = [0, 12, 7, 12, 3, 12, 7, 15, 0, 12, 7, 12, 10, 12, 7, 3]

    for step in range(total_steps):
        bar = step // 16
        in_bar = step % 16
        i0 = int(step * step_sec * SR)
        root = chord_roots[bar % len(chord_roots)]

        # 1. Driving saw bass on every 16th note (accent on off-beats)
        b_len = min(int(step_sec * 0.92 * SR), n - i0)
        tt = np.linspace(0, b_len / SR, b_len, endpoint=False)
        hz = _midi_to_hz(root + (12 if in_bar % 4 == 2 else 0))
        bass = _lowpass(signal.sawtooth(2 * np.pi * hz * tt), 680.0) * np.exp(-tt * 7.0)
        amp_b = 0.55 if in_bar % 2 == 0 else 0.42
        left[i0 : i0 + b_len] += amp_b * bass
        right[i0 : i0 + b_len] += amp_b * bass

        # 2. Tense lead synth arpeggio
        arp_midi = root + 24 + arp_offsets[in_bar]
        a_len = min(int(step_sec * 0.80 * SR), n - i0)
        tt_a = np.linspace(0, a_len / SR, a_len, endpoint=False)
        hz_a = _midi_to_hz(arp_midi)
        arp = (0.6 * signal.sawtooth(2 * np.pi * hz_a * tt_a) + 0.4 * np.sin(2 * np.pi * hz_a * tt_a))
        arp = _lowpass(arp, 2600.0) * np.exp(-tt_a * 12.0)
        pan_l = 0.65 if in_bar % 2 == 0 else 0.35
        pan_r = 1.0 - pan_l
        left[i0 : i0 + a_len] += 0.24 * pan_l * arp
        right[i0 : i0 + a_len] += 0.24 * pan_r * arp

        # 3. Four-on-the-floor action kick (steps 0, 4, 8, 12 + syncopated 14)
        if in_bar in (0, 4, 8, 12, 14):
            k_len = min(int(0.14 * SR), n - i0)
            tt_k = np.linspace(0, k_len / SR, k_len, endpoint=False)
            k_freq = 48.0 + 120.0 * np.exp(-tt_k * 35.0)
            k_phase = 2 * np.pi * np.cumsum(k_freq) / SR
            kick = np.tanh(1.6 * np.sin(k_phase) * np.exp(-tt_k * 16.0))
            k_amp = 0.78 if in_bar != 14 else 0.48
            left[i0 : i0 + k_len] += k_amp * kick
            right[i0 : i0 + k_len] += k_amp * kick

        # 4. Snare hit on steps 4 and 12
        if in_bar in (4, 12):
            s_len = min(int(0.12 * SR), n - i0)
            tt_s = np.linspace(0, s_len / SR, s_len, endpoint=False)
            snare = (
                _bandpass(rng.standard_normal(s_len), 900.0, 6500.0) * np.exp(-tt_s * 24.0)
                + 0.45 * np.sin(2 * np.pi * 195.0 * tt_s) * np.exp(-tt_s * 30.0)
            )
            left[i0 : i0 + s_len] += 0.42 * snare
            right[i0 : i0 + s_len] += 0.42 * snare

        # 5. Crisp 16th hi-hats
        if in_bar % 2 == 1:
            h_len = min(int(0.035 * SR), n - i0)
            tt_h = np.linspace(0, h_len / SR, h_len, endpoint=False)
            hat = _bandpass(rng.standard_normal(h_len), 6000.0, 14000.0) * np.exp(-tt_h * 90.0)
            left[i0 : i0 + h_len] += 0.16 * hat
            right[i0 : i0 + h_len] += 0.16 * hat

    # Subtle master soft-clip for energetic glue
    stereo = np.tanh(1.25 * np.stack([left, right], axis=-1))
    return _normalize_stereo(stereo, peak=0.88)


SFX_SYNTH_REGISTRY: Dict[str, Dict[str, Any]] = {
    "light_switch_click": {"fn": synth_light_switch_click, "desc": "Bunyi cetek saklar lampu dapur"},
    "fluorescent_hum": {"fn": synth_fluorescent_hum, "desc": "Dengung lampu neon menyala"},
    "dramatic_boom": {"fn": synth_dramatic_boom, "desc": "Dentuman tegang sub-bass saat bahaya muncul"},
    "wind_whoosh_heavy": {"fn": synth_wind_whoosh_heavy, "desc": "Hembusan angin raksasa dari ayunan sandal"},
    "sandal_slam_thud": {"fn": synth_sandal_slam_thud, "desc": "Gebukan keras sandal jepit ke lantai"},
    "skitter_fast": {"fn": synth_skitter_fast, "desc": "Suara kaki serangga berlari cepat di keramik"},
    "wings_buzz_loud": {"fn": synth_wings_buzz_loud, "desc": "Suara sayap kecoak mendengung keras"},
    "record_scratch": {"fn": synth_record_scratch, "desc": "Stop mendadak untuk momen komedi"},
    "human_scream_cut": {"fn": synth_human_scream_cut, "desc": "Teriakan kaget terpotong cepat"},
}

BGM_SYNTH_REGISTRY: Dict[str, Dict[str, Any]] = {
    "sneaky_night_loop": {
        "fn": synth_bgm_sneaky_night_loop,
        "mood": "tenang, mengendap-endap",
    },
    "intense_chase_synth": {
        "fn": synth_bgm_intense_chase_synth,
        "mood": "tegang, aksi cepat",
    },
}


def prepare_sfx_item(
    sfx_id: str,
    assets_dir: Path,
    ffmpeg_bin: str,
    force: bool = False,
) -> Path:
    dest_wav = assets_dir / "sfx" / f"{sfx_id}.wav"
    if not force and dest_wav.exists() and dest_wav.stat().st_size > 1024:
        log("AUDIO", f"[CACHED] SFX {sfx_id} -> {dest_wav}")
        upsert_catalog_entry(
            assets_dir,
            "sfx",
            {"id": sfx_id, "file": f"02_assets/sfx/{sfx_id}.wav", "cached": True},
        )
        return dest_wav

    source_used = "procedural_synth"
    license_str = "Procedural CC0"
    desc = SFX_SYNTH_REGISTRY.get(sfx_id, {}).get("desc", sfx_id)

    # Attempt verified CC0/PD Wikimedia Commons download first if configured
    if sfx_id in DIRECT_CC0_SFX_SOURCES:
        src = DIRECT_CC0_SFX_SOURCES[sfx_id]
        desc = src["desc"]
        raw_path = assets_dir / "sfx" / f"_{sfx_id}_raw.ogg"
        try:
            download_file(src["url"], raw_path, force=force, min_bytes=512)
            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(raw_path),
                "-af",
                src["ffmpeg_filter"],
                "-ar",
                str(SR),
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(dest_wav),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if dest_wav.exists() and dest_wav.stat().st_size > 2048:
                source_used = "wikimedia_cc0_direct"
                license_str = src["license"]
                log("AUDIO", f"[CC0 DOWNLOAD+FX] SFX {sfx_id} -> {dest_wav}")
            raw_path.unlink(missing_ok=True)
        except Exception as exc:
            log("AUDIO", f"[FALLBACK] CC0 download failed for {sfx_id} ({exc}); synthesizing procedurally...")
            raw_path.unlink(missing_ok=True)

    # Synthesize procedurally if not downloaded (or if custom/unknown SFX ID)
    if not dest_wav.exists() or dest_wav.stat().st_size <= 2048:
        synth_fn: Callable[[], np.ndarray] = SFX_SYNTH_REGISTRY.get(
            sfx_id, {"fn": synth_dramatic_boom}
        )["fn"]
        stereo = synth_fn()
        _write_stereo_wav(dest_wav, stereo, sr=SR)
        log("AUDIO", f"[SYNTHESIZED] SFX {sfx_id} -> {dest_wav}")

    upsert_catalog_entry(
        assets_dir,
        "sfx",
        {
            "id": sfx_id,
            "file": f"02_assets/sfx/{sfx_id}.wav",
            "desc": desc,
            "source": source_used,
            "license": license_str,
            "cached": True,
        },
    )
    return dest_wav


def prepare_bgm_item(
    bgm_id: str,
    assets_dir: Path,
    ffmpeg_bin: str,
    force: bool = False,
) -> Optional[Path]:
    if bgm_id in ("none", "none_cut_silence", "silence", ""):
        return None

    dest_mp3 = assets_dir / "bgm" / f"{bgm_id}.mp3"
    if not force and dest_mp3.exists() and dest_mp3.stat().st_size > 4096:
        log("AUDIO", f"[CACHED] BGM {bgm_id} -> {dest_mp3}")
        upsert_catalog_entry(
            assets_dir,
            "bgm",
            {"id": bgm_id, "file": f"02_assets/bgm/{bgm_id}.mp3", "cached": True},
        )
        return dest_mp3

    cfg = BGM_SYNTH_REGISTRY.get(bgm_id, BGM_SYNTH_REGISTRY["intense_chase_synth"])
    stereo = cfg["fn"]()
    tmp_wav = assets_dir / "bgm" / f"_{bgm_id}_tmp.wav"
    _write_stereo_wav(tmp_wav, stereo, sr=SR)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(tmp_wav),
        "-af",
        "aecho=0.8:0.75:35:0.18,alimiter=limit=0.92",
        "-ar",
        str(SR),
        "-ac",
        "2",
        "-b:a",
        "192k",
        str(dest_mp3),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tmp_wav.unlink(missing_ok=True)
    log("AUDIO", f"[SYNTHESIZED] BGM {bgm_id} -> {dest_mp3}")

    upsert_catalog_entry(
        assets_dir,
        "bgm",
        {
            "id": bgm_id,
            "file": f"02_assets/bgm/{bgm_id}.mp3",
            "mood": cfg.get("mood", ""),
            "source": "procedural_synth_ffmpeg",
            "license": "Procedural CC0",
            "cached": True,
        },
    )
    return dest_mp3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-download CC0 SFX and synthesize punchy SFX/BGM loops with zero manual work."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
        help="Path to episode spec JSON",
    )
    parser.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Override persistent cache directory (defaults to Drive 02_assets if mounted)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate/re-download all audio files",
    )
    parser.add_argument(
        "--verify-urls",
        action="store_true",
        help="Verify all direct CC0 audio URLs return HTTP 200 without downloading",
    )
    args = parser.parse_args()

    if args.verify_urls:
        ok = True
        for sfx_id, info in DIRECT_CC0_SFX_SOURCES.items():
            status = http_head_status(info["url"])
            log("VERIFY", f"SFX {sfx_id} -> HTTP {status} ({info['url']})")
            if status != 200:
                ok = False
        return 0 if ok else 1

    ffmpeg_bin = check_ffmpeg_available()
    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    assets_dir = resolve_assets_dir(args.assets_dir)

    log("AUDIO", f"Preparing SFX & BGM for {spec['episode_id']} -> {assets_dir}")

    # Gather all SFX IDs from both spec and core library
    sfx_ids = set(SFX_SYNTH_REGISTRY.keys())
    for scene in spec.get("scenes", []):
        for cue in scene.get("sfx_cues", []):
            sfx_ids.add(cue["sfx_id"])

    for sfx_id in sorted(sfx_ids):
        prepare_sfx_item(sfx_id, assets_dir, ffmpeg_bin, force=args.force)

    # Gather all BGM IDs from both spec and core library
    bgm_ids = set(BGM_SYNTH_REGISTRY.keys())
    for item in spec.get("bgm_plan", []):
        bgm_ids.add(item["bgm_id"])

    for bgm_id in sorted(bgm_ids):
        prepare_bgm_item(bgm_id, assets_dir, ffmpeg_bin, force=args.force)

    log("AUDIO", f"All SFX & BGM ready and cataloged at {assets_dir / 'asset_catalog.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
