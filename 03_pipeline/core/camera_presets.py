#!/usr/bin/env python3
"""Universal 5-Archetype POV Camera Library & Beat Modifiers (`Jadi Apa` Studio Core).

DESIGN RULE (EXPLICIT OVERRIDE OF ZACK-BLENDER-PACK):
Zack-Blender-Pack's third-person shorts forbid camera shake ("dolly only").
Our channel (`Jadi Apa` / `Jadi Apa 3D`) is **3D Micro-POV**: the viewer IS the insect,
cell, droplet, object, or human. Organic, subject-authentic POV motion + motion blur
(`shutter = 0.40`) is essential for immersion and retention!

5 Reusable POV Archetypes (selectable via `epXXX_spec.json` -> `camera_archetype`):
1. `insect_ground`      — Micro height (1.2–2.0 cm), rapid skitter shake, macro DOF, strict floor clamp `z >= min_z`.
2. `aerial_erratic`     — Unstable banking, dynamic roll/yaw wobble, rapid flutter micro-vibration.
3. `fluid_float`        — Zero-G organic drift & slow buoyancy roll (inside body / blood / liquid POV).
4. `static_object_pov`  — Camera locked to an object; subtle settle or hand-pickup vibration/tilt.
5. `human_first_person` — Eye height (~1.60 m), natural walk bob & gentle chest breathing sway.

Reusable Beat Modifiers (`motion_modifiers` list in `epXXX_spec.json`):
- `snap_jerk`          — Sudden startle upward jolt + damped overshoot (e.g., neon light flash).
- `bullet_time`        — Slow-motion damped micro-drift with tightened cinematic tilt.
- `whip_pan`           — Fast eased rotational snap with slight counter-roll.
- `impact_bump`        — Sharp 4–6 frame shockwave vertical+roll jolt when heavy object hits nearby.
- `fov_rush`           — Adrenaline FOV widening (e.g., 95° -> 112°) during high-speed sprints.
- `handheld_breath`    — Subtle living breathing micro-sway so static POV shots never feel dead/CG.
- `erratic_wobble`     — High-energy multi-frequency yaw/roll instability (panic flight).
- `rapid_wing_flutter` — High-frequency micro-buzz layered onto flight shots.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


@dataclass
class CameraArchetypeSpec:
    name: str
    default_height_m: float
    min_z_m: float
    default_fov_deg: float
    default_fstop: float
    clip_start_m: float
    pos_amp: Tuple[float, float, float]
    rot_amp_deg: Tuple[float, float, float]
    freq_hz: float
    motion_blur_shutter: float = 0.40


ARCHETYPES: Dict[str, CameraArchetypeSpec] = {
    "insect_ground": CameraArchetypeSpec(
        name="insect_ground",
        default_height_m=0.015,
        min_z_m=0.012,
        default_fov_deg=95.0,
        default_fstop=3.4,
        clip_start_m=0.005,
        pos_amp=(0.0045, 0.0010, 0.0020),
        rot_amp_deg=(0.95, 1.80, 1.10),
        freq_hz=6.8,
        motion_blur_shutter=0.40,
    ),
    "aerial_erratic": CameraArchetypeSpec(
        name="aerial_erratic",
        default_height_m=0.45,
        min_z_m=0.025,
        default_fov_deg=98.0,
        default_fstop=3.0,
        clip_start_m=0.005,
        pos_amp=(0.014, 0.008, 0.011),
        rot_amp_deg=(3.2, 7.5, 4.8),
        freq_hz=3.4,
        motion_blur_shutter=0.40,
    ),
    "fluid_float": CameraArchetypeSpec(
        name="fluid_float",
        default_height_m=0.50,
        min_z_m=-100.0,
        default_fov_deg=88.0,
        default_fstop=2.8,
        clip_start_m=0.005,
        pos_amp=(0.018, 0.014, 0.016),
        rot_amp_deg=(2.8, 5.2, 3.0),
        freq_hz=0.55,
        motion_blur_shutter=0.35,
    ),
    "static_object_pov": CameraArchetypeSpec(
        name="static_object_pov",
        default_height_m=0.10,
        min_z_m=0.008,
        default_fov_deg=82.0,
        default_fstop=3.6,
        clip_start_m=0.005,
        pos_amp=(0.0008, 0.0008, 0.0008),
        rot_amp_deg=(0.35, 0.45, 0.30),
        freq_hz=1.4,
        motion_blur_shutter=0.35,
    ),
    "human_first_person": CameraArchetypeSpec(
        name="human_first_person",
        default_height_m=1.60,
        min_z_m=0.25,
        default_fov_deg=74.0,
        default_fstop=4.0,
        clip_start_m=0.02,
        pos_amp=(0.012, 0.004, 0.020),
        rot_amp_deg=(0.85, 1.15, 0.65),
        freq_hz=1.85,
        motion_blur_shutter=0.40,
    ),
}


def get_archetype(name: Optional[str]) -> CameraArchetypeSpec:
    if name and name in ARCHETYPES:
        return ARCHETYPES[name]
    return ARCHETYPES["insect_ground"]


def _harm(t: float, f1: float, phase: float = 0.0) -> float:
    """Deterministic multi-harmonic organic wave in [-1, 1] (no random jitter jumps across nodes)."""
    return (
        0.62 * math.sin(2.0 * math.pi * f1 * t + phase)
        + 0.28 * math.sin(2.0 * math.pi * (f1 * 1.73) * t + phase * 1.9 + 1.1)
        + 0.10 * math.cos(2.0 * math.pi * (f1 * 2.91) * t - phase * 0.7 + 2.4)
    )


def impact_bump_offset(
    local_sec: float,
    impact_sec: float,
    fps: int = 24,
    duration_frames: int = 5,
    intensity: float = 1.0,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Sharp 4–6 frame shockwave vertical + roll jolt when a heavy object slams nearby."""
    dt = local_sec - impact_sec
    dur = max(1, duration_frames) / float(max(1, fps))
    if dt < 0.0 or dt > dur:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    u = dt / dur
    env = math.exp(-3.4 * u) * math.sin(u * math.pi * 2.2)
    dz = 0.0055 * intensity * env
    dx = 0.0030 * intensity * math.exp(-2.8 * u) * math.cos(u * math.pi * 3.0)
    d_pitch = 3.8 * intensity * env
    d_roll = 5.2 * intensity * math.exp(-2.6 * u) * math.sin(u * math.pi * 2.6 + 0.4)
    return (dx, 0.0, dz), (d_pitch, d_roll, 0.0)


def snap_jerk_offset(
    local_sec: float,
    trigger_sec: float,
    duration_sec: float = 0.24,
    intensity: float = 1.0,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Startled upward snap with fast damped overshoot (e.g., sudden light flash)."""
    dt = local_sec - trigger_sec
    if dt < 0.0 or dt > duration_sec:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    u = dt / max(1e-4, duration_sec)
    overshoot = math.sin(u * math.pi) * math.exp(-2.2 * u)
    dz = 0.0045 * intensity * overshoot
    d_pitch = 4.2 * intensity * overshoot
    d_roll = 2.6 * intensity * math.sin(u * math.pi * 2.0) * (1.0 - u)
    return (0.0, 0.0, dz), (d_pitch, d_roll, -1.4 * intensity * overshoot)


def evaluate_camera_pose(
    archetype_name: str,
    base_loc: Sequence[float],
    base_rot_deg: Sequence[float],
    base_fov_deg: float,
    t_sec: float,
    local_sec: float,
    fps: int = 24,
    modifiers: Optional[Iterable[str]] = None,
    motion_intensity: float = 1.0,
    min_z_override: Optional[float] = None,
    impact_times_sec: Optional[Sequence[float]] = None,
    snap_time_sec: Optional[float] = None,
    fov_rush_progress: float = 0.0,
    fov_rush_target: float = 112.0,
    is_still_storyboard: bool = False,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float]:
    """Combine base keyframed trajectory with POV archetype organic motion + beat modifiers.

    Always enforces strict floor clamp `z >= min_z` (e.g., `z >= 0.012m` for `insect_ground`)
    so the micro-POV camera can NEVER dip under the floor plane!
    """
    spec = get_archetype(archetype_name)
    mods = set(modifiers or ())

    # Keep hero stills clean & framed while preserving subtle living tilt (full shake in video!)
    scale = 0.35 if is_still_storyboard else 1.0
    amp = max(0.0, motion_intensity) * scale

    dx = dy = dz = 0.0
    dp = dr = dyaw = 0.0
    fov = float(base_fov_deg)

    # 1. Archetype baseline organic motion
    freq = spec.freq_hz
    if "bullet_time" in mods:
        freq *= 0.22
        amp *= 0.35

    if amp > 1e-4:
        dx += spec.pos_amp[0] * amp * _harm(t_sec, freq, 0.2)
        dy += spec.pos_amp[1] * amp * _harm(t_sec, freq * 0.85, 1.3)
        if spec.name == "insect_ground":
            # Rapid asymmetric footstep hop (never negative below floor!)
            dz += spec.pos_amp[2] * amp * abs(math.sin(2.0 * math.pi * freq * t_sec))
        else:
            dz += spec.pos_amp[2] * amp * _harm(t_sec, freq * 0.72, 2.1)

        dp += spec.rot_amp_deg[0] * amp * _harm(t_sec, freq * 0.92, 0.7)
        dr += spec.rot_amp_deg[1] * amp * _harm(t_sec, freq * 1.05, 1.8)
        dyaw += spec.rot_amp_deg[2] * amp * _harm(t_sec, freq * 0.78, 2.7)

    # 2. Beat Modifiers
    if "handheld_breath" in mods:
        b = 0.5 if is_still_storyboard else 1.0
        dp += 0.75 * b * math.sin(2.0 * math.pi * 0.38 * t_sec)
        dr += 0.90 * b * math.cos(2.0 * math.pi * 0.29 * t_sec + 0.6)
        dz += 0.0012 * b * math.sin(2.0 * math.pi * 0.38 * t_sec)

    if "erratic_wobble" in mods:
        ew = 0.40 if is_still_storyboard else 1.0
        dp += 2.8 * ew * _harm(t_sec, 2.6, 0.4)
        dr += 5.5 * ew * _harm(t_sec, 3.1, 1.7)
        dyaw += 3.8 * ew * _harm(t_sec, 2.1, 2.9)

    if "rapid_wing_flutter" in mods and not is_still_storyboard:
        dp += 0.85 * math.sin(2.0 * math.pi * 11.5 * t_sec)
        dr += 1.10 * math.cos(2.0 * math.pi * 11.5 * t_sec + 0.5)

    if "snap_jerk" in mods and snap_time_sec is not None:
        (sj_x, sj_y, sj_z), (sj_p, sj_r, sj_yw) = snap_jerk_offset(local_sec, snap_time_sec)
        dx += sj_x
        dy += sj_y
        dz += sj_z
        dp += sj_p
        dr += sj_r
        dyaw += sj_yw

    if "impact_bump" in mods and impact_times_sec:
        for t_imp in impact_times_sec:
            (ib_x, ib_y, ib_z), (ib_p, ib_r, ib_yw) = impact_bump_offset(local_sec, t_imp, fps=fps, duration_frames=5)
            dx += ib_x
            dy += ib_y
            dz += ib_z
            dp += ib_p
            dr += ib_r
            dyaw += ib_yw

    if "fov_rush" in mods and fov_rush_progress > 0.0:
        u = max(0.0, min(1.0, fov_rush_progress))
        fov = fov + (fov_rush_target - fov) * u

    # 3. Assemble & strictly clamp Z >= min_z!
    min_z = spec.min_z_m if min_z_override is None else min_z_override
    out_loc = (
        float(base_loc[0]) + dx,
        float(base_loc[1]) + dy,
        max(min_z, float(base_loc[2]) + dz),
    )
    out_rot = (
        float(base_rot_deg[0]) + dp,
        float(base_rot_deg[1]) + dr,
        float(base_rot_deg[2]) + dyaw,
    )
    return out_loc, out_rot, max(16.0, min(145.0, fov))


def configure_motion_blur(scene: Any, mode: str, shutter: float = 0.40) -> None:
    """Enable smooth cinematic motion blur (shutter=0.4) for all moving renders (motion_check/preview/final)."""
    use_mb = mode != "storyboard"
    scene.render.use_motion_blur = use_mb
    scene.render.motion_blur_shutter = shutter
