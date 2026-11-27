#!/usr/bin/env python3
"""Adaptive Multi-Keyframe Fast Storyboard Sheet Builder (`Jadi Apa` Studio v3.0).

Automatically groups ANY number of rendered transition keyframes (`storyboard_keyframes.json`)
into crisp multi-sheet PNGs (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, ...) with
up to 8–9 panels per sheet (4x2 for <=8/sheet or 3x3 for 9/sheet), complete with:
  - Top panel badge (`01A · 00:00.5`)
  - Optional simulated 9:16 karaoke subtitle safe-zone overlay (e.g. ending `"MAAF YA, BANG."`
    at `MarginV=380` + delayed top badge check!) so facial clearance is visually proven BEFORE final render!
  - Readable metadata card below each panel (`Scene & Waktu`, `Aksi & Kamera`, `VO`, `SFX / BGM`).
"""

from __future__ import annotations

import argparse
import json
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


def _fmt_mmss_dec(sec: float) -> str:
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m:02d}:{s:04.1f}"


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


def _draw_simulated_subtitle_overlay(
    im: Image.Image,
    subtitle_text: str,
    top_badge_text: Optional[str] = None,
) -> Image.Image:
    """Draw exact 9:16 ASS MarginV=380 subtitle & safe-zone box onto a panel for Gate 1 visual verification!"""
    out = im.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = out.size

    # Scale exact 1080x1920 ASS coordinates to panel size
    sx = w / 1080.0
    sy = h / 1920.0

    # Subtle dashed-feel safe-zone guide rectangle for bottom TikTok/Shorts UI (MarginV=380 -> y=1540..1920)
    margin_v_px = int(round(380.0 * sy))
    sub_bottom_y = h - margin_v_px
    margin_lr_px = int(round(95.0 * sx))

    # Faint translucent box showing exact subtitle safe-zone band (above bottom UI!)
    box_h = int(round(92.0 * sy))
    box_y0 = sub_bottom_y - box_h
    box_y1 = sub_bottom_y + int(round(12.0 * sy))
    draw.rounded_rectangle(
        [(margin_lr_px, box_y0), (w - margin_lr_px, box_y1)],
        radius=max(4, int(round(12.0 * sx))),
        fill=(0, 0, 0, 125),
        outline=(250, 204, 21, 220),
        width=max(1, int(round(3.0 * sx))),
    )

    # Render simulated karaoke text (56pt on 1080x1920) with thick black stroke
    f_sub = _load_font(max(14, int(round(56.0 * sy))), bold=True)
    text_upper = subtitle_text.upper()
    tb = draw.textbbox((0, 0), text_upper, font=f_sub)
    tw = tb[2] - tb[0]
    th = tb[3] - tb[1]
    tx = (w - tw) // 2
    ty = box_y0 + (box_y1 - box_y0 - th) // 2 - int(round(4.0 * sy))
    stroke_w = max(2, int(round(5.0 * sx)))
    draw.text(
        (tx, ty),
        text_upper,
        font=f_sub,
        fill=(255, 234, 0, 255),
        stroke_width=stroke_w,
        stroke_fill=(0, 0, 0, 255),
    )

    # Tiny safe-zone label right below the subtitle box
    f_lbl = _load_font(max(10, int(round(22.0 * sy))), bold=True)
    lbl_text = "SIMULASI SUBTITLE (MarginV=380 · AMAN UI BAWAH)"
    lb = draw.textbbox((0, 0), lbl_text, font=f_lbl)
    lw = lb[2] - lb[0]
    draw.text(((w - lw) // 2, box_y1 + int(round(10.0 * sy))), lbl_text, font=f_lbl, fill=(250, 204, 21, 235))

    # Optional delayed top badge simulation (MarginV=260 from top)
    if top_badge_text:
        f_top = _load_font(max(12, int(round(42.0 * sy))), bold=True)
        bt = top_badge_text.upper()
        bb = draw.textbbox((0, 0), bt, font=f_top)
        btw = bb[2] - bb[0]
        bth = bb[3] - bb[1]
        by = int(round(260.0 * sy))
        pad_x = int(round(18.0 * sx))
        pad_y = int(round(8.0 * sy))
        draw.rounded_rectangle(
            [(w // 2 - btw // 2 - pad_x, by - pad_y), (w // 2 + btw // 2 + pad_x, by + bth + pad_y)],
            radius=max(3, int(round(8.0 * sx))),
            fill=(0, 0, 0, 175),
        )
        draw.text((w // 2 - btw // 2, by - int(round(2.0 * sy))), bt, font=f_top, fill=(255, 234, 0, 255))

    return Image.alpha_composite(out, overlay).convert("RGB")


def _partition_sheets(panels: List[Dict[str, Any]], max_per_sheet: int = 8) -> List[List[Dict[str, Any]]]:
    """Split arbitrary keyframe count cleanly into balanced sheets (<= max_per_sheet panels each)."""
    n = len(panels)
    if n == 0:
        return []
    if n <= 9 and max_per_sheet >= 9:
        return [panels]
    if n <= max_per_sheet:
        return [panels]
    # Balance panels across minimum number of sheets (max 8 or 9 per sheet)
    num_sheets = (n + max_per_sheet - 1) // max_per_sheet
    base = n // num_sheets
    rem = n % num_sheets
    sheets: List[List[Dict[str, Any]]] = []
    idx = 0
    for i in range(num_sheets):
        sz = base + (1 if i < rem else 0)
        sheets.append(panels[idx : idx + sz])
        idx += sz
    return sheets


def _render_single_sheet(
    spec: Dict[str, Any],
    manifest: Dict[str, Any],
    sheet_panels: List[Dict[str, Any]],
    sheet_idx: int,
    total_sheets: int,
    total_panels: int,
    out_path: Path,
) -> Path:
    count = len(sheet_panels)
    cols = 4 if count in (4, 7, 8) else (3 if count >= 3 else count)
    rows = (count + cols - 1) // cols

    panel_w = 360
    panel_h = 640
    card_h = 228
    cell_w = panel_w
    cell_h = panel_h + card_h
    gap_x = 22
    gap_y = 26
    margin_x = 30
    margin_top = 104
    margin_bot = 32

    canvas_w = margin_x * 2 + cols * cell_w + (cols - 1) * gap_x
    canvas_h = margin_top + rows * cell_h + (rows - 1) * gap_y + margin_bot

    canvas = Image.new("RGB", (canvas_w, canvas_h), (10, 14, 24))
    draw = ImageDraw.Draw(canvas)

    f_header = _load_font(25, bold=True)
    f_sub = _load_font(14, bold=False)
    f_badge = _load_font(15, bold=True)
    f_card_title = _load_font(14, bold=True)
    f_card_title_sm = _load_font(12, bold=True)
    f_label = _load_font(12, bold=True)
    f_body = _load_font(13, bold=False)
    f_small = _load_font(12, bold=False)

    # Top Studio Header Banner
    draw.rectangle([(0, 0), (canvas_w, margin_top - 14)], fill=(15, 23, 42))
    draw.rectangle([(0, margin_top - 17), (canvas_w, margin_top - 14)], fill=(250, 204, 21))

    channel = spec.get("channel", "Jadi Apa")
    mascot = spec.get("mascot", "Mas Dimas")
    ep_id = spec.get("episode_id", "EP001")
    ep_title = spec.get("title", "3D Micro-POV Storyboard")
    total_dur = float(manifest.get("total_duration_sec", 0.0))
    fps = int(manifest.get("fps", 24))
    vo_speed = float(manifest.get("vo_speed", 1.0))

    sheet_tag = f"SHEET {sheet_idx}/{total_sheets}" if total_sheets > 1 else "STORYBOARD SHEET"
    banner_title = f"{channel.upper()} — {ep_id} ADAPTIVE MULTI-KEYFRAME {sheet_tag}: {ep_title}"
    banner_font = f_header
    for sz in (25, 22, 20, 18, 16):
        cand = _load_font(sz, bold=True)
        bb_h = draw.textbbox((0, 0), banner_title, font=cand)
        banner_font = cand
        if (bb_h[2] - bb_h[0]) <= (canvas_w - margin_x * 2):
            break
    draw.text(
        (margin_x, 18),
        banner_title,
        fill=(248, 250, 252),
        font=banner_font,
    )
    draw.text(
        (margin_x, 54),
        f"Maskot: {mascot} (Semi-Matte 0.60, 100% Nyeker)  |  Panel {count} dari {total_panels} Keyframe  |  "
        f"Durasi: {total_dur:.2f}s ({int(manifest.get('total_frames', 0))} fr @ {fps}fps, VO {vo_speed:.2f}x)  |  AgX + Macro DOF + post.py",
        fill=(148, 163, 184),
        font=f_sub,
    )

    for idx, p in enumerate(sheet_panels):
        col = idx % cols
        row = idx // cols
        x0 = margin_x + col * (cell_w + gap_x)
        y0 = margin_top + row * (cell_h + gap_y)
        accent = tuple(p.get("accent", (250, 204, 21)))

        draw.rectangle(
            [(x0 - 2, y0 - 2), (x0 + cell_w + 2, y0 + cell_h + 2)],
            fill=(17, 24, 39),
            outline=(51, 65, 85),
            width=2,
        )

        img_path = Path(p["image_path"])
        if img_path.exists():
            im = Image.open(img_path).convert("RGB")
            if im.size != (panel_w, panel_h):
                im = im.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
            sub_ov = p.get("subtitle_overlay")
            if sub_ov:
                im = _draw_simulated_subtitle_overlay(im, str(sub_ov), top_badge_text=p.get("top_badge_overlay"))
            canvas.paste(im, (x0, y0))
        else:
            draw.rectangle([(x0, y0), (x0 + panel_w, y0 + panel_h)], fill=(30, 41, 59))
            draw.text((x0 + 18, y0 + panel_h // 2), f"MISSING: {img_path.name}", fill=(248, 113, 113), font=f_badge)

        # Top-left Panel Badge Pill
        t_str = _fmt_mmss_dec(float(p.get("time_sec", 0.0)))
        badge_text = f"{p['code']} · {t_str}"
        bb = draw.textbbox((0, 0), badge_text, font=f_badge)
        bw = (bb[2] - bb[0]) + 18
        bh = (bb[3] - bb[1]) + 12
        draw.rounded_rectangle(
            [(x0 + 10, y0 + 10), (x0 + 10 + bw, y0 + 10 + bh)],
            radius=5,
            fill=(10, 14, 24),
            outline=accent,
            width=2,
        )
        draw.text((x0 + 19, y0 + 14), badge_text, fill=accent, font=f_badge)

        # Bottom Metadata Card
        cy = y0 + panel_h
        draw.rectangle([(x0, cy), (x0 + cell_w, cy + card_h)], fill=(15, 23, 42))
        draw.rectangle([(x0, cy), (x0 + cell_w, cy + 4)], fill=accent)

        pad = 12
        max_tw = cell_w - pad * 2
        cur_y = cy + 10

        header_line = f"{p['code']} | {t_str} · {p['title']}"
        title_font = f_card_title
        for sz in (14, 13, 12, 11, 10):
            cand = _load_font(sz, bold=True)
            hb = draw.textbbox((0, 0), header_line, font=cand)
            title_font = cand
            if (hb[2] - hb[0]) <= max_tw:
                break
        draw.text((x0 + pad, cur_y), header_line, fill=accent, font=title_font)
        cur_y += 22

        draw.line([(x0 + pad, cur_y), (x0 + cell_w - pad, cur_y)], fill=(30, 41, 59), width=1)
        cur_y += 6

        draw.text((x0 + pad, cur_y), "AKSI & KAMERA", fill=(148, 163, 184), font=f_label)
        cur_y += 15
        for line in _wrap_pixel_lines(draw, str(p.get("action", "")), f_body, max_tw, max_lines=3):
            draw.text((x0 + pad, cur_y), line, fill=(226, 232, 240), font=f_body)
            cur_y += 17
        cur_y += 5

        draw.text((x0 + pad, cur_y), "VO", fill=(250, 204, 21), font=f_label)
        cur_y += 15
        vo_quote = f"\"{p.get('vo', '')}\""
        for line in _wrap_pixel_lines(draw, vo_quote, f_body, max_tw, max_lines=2):
            draw.text((x0 + pad, cur_y), line, fill=(248, 250, 252), font=f_body)
            cur_y += 17
        cur_y += 5

        draw.text((x0 + pad, cur_y), "SFX / BGM", fill=(56, 189, 248), font=f_label)
        cur_y += 15
        for line in _wrap_pixel_lines(draw, str(p.get("sfx_bgm", "")), f_small, max_tw, max_lines=2):
            draw.text((x0 + pad, cur_y), line, fill=(186, 230, 253), font=f_small)
            cur_y += 15

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG", optimize=True)
    print(f"[STORYBOARD] Adaptive sheet {sheet_idx}/{total_sheets} ({count} panels, {canvas_w}x{canvas_h}) -> {out_path}")
    return out_path


def build_storyboard_sheets(
    spec_path: Path,
    timing_path: Path,
    scenes_dir: Path,
    out_dir_or_file: Path,
    max_per_sheet: int = 8,
) -> List[Path]:
    """Assemble adaptive multi-keyframe storyboard sheets (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, ...)."""
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    manifest = json.loads(timing_path.read_text(encoding="utf-8"))

    kf_json = scenes_dir / "storyboard_keyframes.json"
    if not kf_json.exists():
        raise FileNotFoundError(
            f"storyboard_keyframes.json not found at {kf_json}. Run build_and_render.py --mode storyboard first."
        )
    panels = json.loads(kf_json.read_text(encoding="utf-8"))

    out_dir = out_dir_or_file.parent if out_dir_or_file.suffix.lower() == ".png" else out_dir_or_file
    sheets = _partition_sheets(panels, max_per_sheet=max_per_sheet)
    written: List[Path] = []
    for idx, sp in enumerate(sheets, start=1):
        sheet_out = out_dir / f"storyboard_sheet_{idx}.png"
        _render_single_sheet(spec, manifest, sp, idx, len(sheets), len(panels), sheet_out)
        written.append(sheet_out)

    # Remove any stale extra sheet files from prior runs
    for extra_idx in range(len(sheets) + 1, 12):
        stale = out_dir / f"storyboard_sheet_{extra_idx}.png"
        if stale.exists():
            stale.unlink()

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Build adaptive multi-keyframe studio storyboard sheets")
    parser.add_argument("--spec", type=str, required=True)
    parser.add_argument("--timing", type=str, required=True)
    parser.add_argument("--scenes-dir", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--max-per-sheet", type=int, default=8)
    args = parser.parse_args()

    build_storyboard_sheets(
        Path(args.spec).resolve(),
        Path(args.timing).resolve(),
        Path(args.scenes_dir).resolve(),
        Path(args.out).resolve(),
        max_per_sheet=max(1, min(9, int(args.max_per_sheet))),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
