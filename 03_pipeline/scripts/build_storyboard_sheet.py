#!/usr/bin/env python3
"""Build a studio-grade 9-panel `storyboard_sheet.png` (3x3 layout) with metadata cards.

Panels:
  01A (Remang Jam 2) | 01B (Lampu Nyala) | 02 (Boss Terakhir)
  03 (Cheat Code)    | 04 (300 KM/JAM)   | 05 (Tinggal Sejengkal)
  06 (Terkepung!)    | 07 (Mode Terbang) | 08 (Maaf Ya Bang)

Each panel displays the rendered frame (post.py applied) + a readable card below with:
  - Scene & Waktu
  - Aksi & Kamera
  - VO
  - SFX / BGM
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _fmt_mmss(sec: float) -> str:
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = int(round(sec - m * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m:02d}:{s:02d}"


def _bgm_for_scene(spec: Dict[str, Any], sid: int) -> str:
    for b in spec.get("bgm_plan", []):
        if int(b.get("start_scene", 0)) <= sid <= int(b.get("end_scene", 0)):
            return str(b.get("bgm_id", "none"))
    return "none"


def _wrap_pixel_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int = 3,
) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        test = f"{cur} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while len(last) > 4:
            bbox = draw.textbbox((0, 0), last + "...", font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                lines[-1] = last + "..."
                break
            last = last[:-1].rstrip()
    return lines


def _compact_action_summary(sid: int, sub_tag: Optional[str], scene_spec: Dict[str, Any]) -> str:
    """Concise 1-line Indonesian Aksi & Kamera summary tailored for mobile/studio storyboard reading."""
    overrides = {
        (1, "A"): "Remang biru + specular kuah & bayangan kecoak; Mas Dimas di saklar kiri memakai 2 sandal ijo.",
        (1, "B"): "Lampu nyala + snap_jerk; Mas Dimas baru tekan saklar & kaget (2 sandal di kaki, tangan kosong).",
        (2, None): "Low-angle + handheld_breath; Mas Dimas bungkuk backswing sandal kanan (kaki kanan nyeker, kiri bersandal).",
        (3, None): "Bullet-time miring; sandal kanan mengayun datar ke bawah + angin cyan membengkokkan antena.",
        (4, None): "Sandal kanan menghantam lantai + debu tipis + impact_bump & fov_rush 95°->112° menuju kulkas.",
        (5, None): "Sprint lurus ke kolong kulkas 5,5 cm; kaki KIRI Mas Dimas (bersandal ijo) menghentak menutup jalur.",
        (6, None): "Whip-pan kiri-kanan-atas; kaki kiri bersandal blokir kolong, tangan kanan backswing sandal siap geplak.",
        (7, None): "Sayap amber berurat rapid flutter di tepi lensa; kamera aerial_erratic oleng naik ke arah Mas Dimas.",
        (8, None): "Wajah berkacamata Mas Dimas di upper-third (bayangan gelap + rim tajam), sandal lepas, sayap amber.",
    }
    if (sid, sub_tag) in overrides:
        return overrides[(sid, sub_tag)]
    cam = str(scene_spec.get("camera_motion", "")).strip()
    act = str(scene_spec.get("visual_action", "")).strip()
    return f"{cam} | {act}" if cam else act


def _build_panel_specs(
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    scenes_dir: Path,
) -> List[Dict[str, Any]]:
    smap = {int(s["scene_id"]): s for s in spec.get("scenes", [])}
    tmap = {int(s["scene_id"]): s for s in manifest.get("scenes", [])}

    panels: List[Dict[str, Any]] = []

    # Panel 1: 01A (Remang Jam 2, 0.0-1.05s)
    s1 = smap[1]
    t1 = tmap[1]
    t1_end = float(t1.get("end_sec", 7.3))
    panels.append(
        {
            "code": "01A",
            "title": "REMANG JAM 2",
            "time_range": "00:00–00:01",
            "image_path": scenes_dir / "scene_01a.png",
            "action": _compact_action_summary(1, "A", s1),
            "vo": "Jam dua pagi...",
            "sfx_bgm": "SFX: ambient malam | Room: night_fridge_hum (-32dB) | BGM: sneaky_night_loop",
            "accent": (96, 165, 250),
        }
    )

    # Panel 2: 01B (Lampu Nyala, 1.05s - end of scene 1)
    panels.append(
        {
            "code": "01B",
            "title": "LAMPU NYALA",
            "time_range": f"00:01–{_fmt_mmss(t1_end)}",
            "image_path": scenes_dir / "scene_01b.png" if (scenes_dir / "scene_01b.png").exists() else scenes_dir / "scene_01.png",
            "action": _compact_action_summary(1, "B", s1),
            "vo": "Lampu dapur mendadak nyala. Masalahnya, kamu lagi jadi kecoak yang kepergok nyeruput kuah mi.",
            "sfx_bgm": "SFX: light_switch_click (1.0s), fluorescent_hum (1.1s) | BGM: sneaky_night_loop",
            "accent": (250, 204, 21),
        }
    )

    accents = {
        2: (248, 113, 113),
        3: (34, 211, 238),
        4: (74, 222, 128),
        5: (251, 146, 60),
        6: (244, 63, 94),
        7: (245, 158, 11),
        8: (192, 132, 252),
    }
    for sid in range(2, 9):
        if sid not in smap or sid not in tmap:
            continue
        sc = smap[sid]
        tm = tmap[sid]
        cues = sc.get("sfx_cues", [])
        sfx_str = ", ".join(f"{c['sfx_id']} ({c.get('offset_sec', 0):.1f}s)" for c in cues) if cues else "none"
        bgm_str = _bgm_for_scene(spec, sid)
        panels.append(
            {
                "code": f"{sid:02d}",
                "title": str(sc.get("on_screen_text", f"SCENE {sid:02d}")).upper(),
                "time_range": f"{_fmt_mmss(tm['start_sec'])}–{_fmt_mmss(tm['end_sec'])}",
                "image_path": scenes_dir / f"scene_{sid:02d}.png",
                "action": _compact_action_summary(sid, None, sc),
                "vo": str(sc.get("vo_text", "")),
                "sfx_bgm": f"SFX: {sfx_str} | BGM: {bgm_str}",
                "accent": accents.get(sid, (250, 204, 21)),
            }
        )

    return panels


def build_storyboard_sheet(
    spec_path: Path,
    timing_path: Path,
    scenes_dir: Path,
    out_path: Path,
) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    manifest = json.loads(timing_path.read_text(encoding="utf-8"))
    panels = _build_panel_specs(spec, manifest, scenes_dir)

    cols = 3
    rows = (len(panels) + cols - 1) // cols

    panel_w = 450
    panel_h = 800
    card_h = 268
    cell_w = panel_w
    cell_h = panel_h + card_h
    gap_x = 28
    gap_y = 32
    margin_x = 36
    margin_top = 112
    margin_bot = 40

    canvas_w = margin_x * 2 + cols * cell_w + (cols - 1) * gap_x
    canvas_h = margin_top + rows * cell_h + (rows - 1) * gap_y + margin_bot

    canvas = Image.new("RGB", (canvas_w, canvas_h), (10, 14, 24))
    draw = ImageDraw.Draw(canvas)

    f_header = _load_font(28, bold=True)
    f_sub = _load_font(15, bold=False)
    f_badge = _load_font(18, bold=True)
    f_card_title = _load_font(15, bold=True)
    f_card_title_sm = _load_font(13, bold=True)
    f_label = _load_font(13, bold=True)
    f_body = _load_font(14, bold=False)
    f_small = _load_font(13, bold=False)

    # Top Studio Header Banner
    draw.rectangle([(0, 0), (canvas_w, margin_top - 16)], fill=(15, 23, 42))
    draw.rectangle([(0, margin_top - 19), (canvas_w, margin_top - 16)], fill=(250, 204, 21))

    channel = spec.get("channel", "Jadi Apa")
    mascot = spec.get("mascot", "Mas Dimas")
    ep_id = spec.get("episode_id", "EP001")
    ep_title = spec.get("title", "3D Micro-POV Storyboard")
    total_dur = float(manifest.get("total_duration_sec", 0.0))
    fps = int(manifest.get("fps", 24))
    vo_speed = float(manifest.get("vo_speed", 1.0))

    draw.text((margin_x, 18), f"{channel.upper()} — {ep_id} STORYBOARD SHEET: {ep_title}", fill=(248, 250, 252), font=f_header)
    draw.text(
        (margin_x, 58),
        f"Maskot: {mascot}  |  9 Panel (01A–08)  |  Durasi: {total_dur:.2f}s ({int(manifest.get('total_frames', 0))} fr @ {fps}fps)  |  "
        f"VO: Puck ({vo_speed:.2f}x) + faster-whisper + Room Tone -32dB  |  AgX + Macro DOF + post.py",
        fill=(148, 163, 184),
        font=f_sub,
    )

    for idx, p in enumerate(panels):
        col = idx % cols
        row = idx // cols
        x0 = margin_x + col * (cell_w + gap_x)
        y0 = margin_top + row * (cell_h + gap_y)
        accent = p["accent"]

        # Outer card frame border
        draw.rectangle(
            [(x0 - 2, y0 - 2), (x0 + cell_w + 2, y0 + cell_h + 2)],
            fill=(17, 24, 39),
            outline=(51, 65, 85),
            width=2,
        )

        # Panel Image
        img_path: Path = p["image_path"]
        if img_path.exists():
            im = Image.open(img_path).convert("RGB")
            if im.size != (panel_w, panel_h):
                im = im.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
            canvas.paste(im, (x0, y0))
        else:
            draw.rectangle([(x0, y0), (x0 + panel_w, y0 + panel_h)], fill=(30, 41, 59))
            draw.text((x0 + 24, y0 + panel_h // 2), f"MISSING: {img_path.name}", fill=(248, 113, 113), font=f_badge)

        # Top-left Panel Badge Pill on Image
        badge_text = f"{p['code']} · {p['title']}"
        bb = draw.textbbox((0, 0), badge_text, font=f_badge)
        bw = (bb[2] - bb[0]) + 22
        bh = (bb[3] - bb[1]) + 14
        draw.rounded_rectangle(
            [(x0 + 12, y0 + 12), (x0 + 12 + bw, y0 + 12 + bh)],
            radius=6,
            fill=(10, 14, 24),
            outline=accent,
            width=2,
        )
        draw.text((x0 + 23, y0 + 17), badge_text, fill=accent, font=f_badge)

        # Bottom Metadata Info Card
        cy = y0 + panel_h
        draw.rectangle([(x0, cy), (x0 + cell_w, cy + card_h)], fill=(15, 23, 42))
        draw.rectangle([(x0, cy), (x0 + cell_w, cy + 4)], fill=accent)

        pad = 14
        max_tw = cell_w - pad * 2
        cur_y = cy + 12

        # Row 1: Scene & Waktu (auto-shrink font if title is wide so zero clipping!)
        header_line = f"Scene {p['code']} | {p['time_range']} · {p['title']}"
        hb = draw.textbbox((0, 0), header_line, font=f_card_title)
        title_font = f_card_title if (hb[2] - hb[0]) <= max_tw else f_card_title_sm
        draw.text((x0 + pad, cur_y), header_line, fill=accent, font=title_font)
        cur_y += 26

        # Divider
        draw.line([(x0 + pad, cur_y), (x0 + cell_w - pad, cur_y)], fill=(30, 41, 59), width=1)
        cur_y += 8

        # Row 2: Aksi & Kamera
        draw.text((x0 + pad, cur_y), "AKSI & KAMERA", fill=(148, 163, 184), font=f_label)
        cur_y += 17
        for line in _wrap_pixel_lines(draw, p["action"], f_body, max_tw, max_lines=2):
            draw.text((x0 + pad, cur_y), line, fill=(226, 232, 240), font=f_body)
            cur_y += 19
        cur_y += 6

        # Row 3: VO
        draw.text((x0 + pad, cur_y), "VO", fill=(250, 204, 21), font=f_label)
        cur_y += 17
        vo_quote = f"\"{p['vo']}\""
        for line in _wrap_pixel_lines(draw, vo_quote, f_body, max_tw, max_lines=3):
            draw.text((x0 + pad, cur_y), line, fill=(248, 250, 252), font=f_body)
            cur_y += 19
        cur_y += 6

        # Row 4: SFX / BGM
        draw.text((x0 + pad, cur_y), "SFX / BGM", fill=(56, 189, 248), font=f_label)
        cur_y += 17
        for line in _wrap_pixel_lines(draw, p["sfx_bgm"], f_small, max_tw, max_lines=2):
            draw.text((x0 + pad, cur_y), line, fill=(186, 230, 253), font=f_small)
            cur_y += 17

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG", optimize=True)
    print(f"[STORYBOARD] 9-panel studio sheet ready ({canvas_w}x{canvas_h}) -> {out_path}")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build 9-panel studio storyboard_sheet.png")
    parser.add_argument("--spec", type=str, required=True)
    parser.add_argument("--timing", type=str, required=True)
    parser.add_argument("--scenes-dir", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    build_storyboard_sheet(
        Path(args.spec).resolve(),
        Path(args.timing).resolve(),
        Path(args.scenes_dir).resolve(),
        Path(args.out).resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
