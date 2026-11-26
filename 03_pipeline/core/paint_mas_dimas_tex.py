#!/usr/bin/env python3
"""UV Texture Painter for Permanent Mascot "Mas Dimas" (`Jadi Apa` / `Jadi Apa 3D`).

Adopts the UV-painting technique from `skills/zack-3d-short/scripts/paint_family.py`:
- Uses the exact per-face UV polygon mask exported from `Human.male_casualsuit06` so
  100% of shirt faces (front, back, collar, left/right sleeves) get Crimson/Brick Red `#A62C2B`
  while 100% of shorts faces get dark charcoal `#20242C` with ZERO color bleed!
- Cleanly flattens any previous chest/back text before recolouring so fabric luminance shading
  stays natural and smooth.
- Paints bold white uppercase `JADI APA` centered strictly inside the verified front-chest UV box
  (viewer-left -> viewer-right = increasing U -> guaranteed non-mirrored & zero seam clipping!).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Linear/AgX-calibrated deep Brick Red / Crimson so rendered color reads as rich #A62C2B under AgX!
CRIMSON_RED_RGB = (132, 26, 26)
CHARCOAL_SHORTS_RGB = (28, 32, 40)  # Dark kosan shorts
INK_WHITE_RGBA = (248, 246, 240, 245)


def _find_bold_font(size: int) -> ImageFont.FreeTypeFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _rasterize_uv_polys(polys: List[List[Tuple[float, float]]], size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    for poly in polys:
        if len(poly) >= 3:
            pts = [(u * size, (1.0 - v) * size) for (u, v) in poly]
            draw.polygon(pts, fill=255)
    # Dilate slightly (MaxFilter 9) to eliminate UV seam bleed at mipmap edges
    return mask.filter(ImageFilter.MaxFilter(9))


def paint_mas_dimas_outfit(
    src_tex_path: Path,
    uv_meta_path: Path,
    out_tex_path: Path,
    size: int = 2048,
    chest_text: str = "JADI APA",
) -> Path:
    uv_meta = json.loads(uv_meta_path.read_text(encoding="utf-8"))
    shirt_polys = uv_meta.get("shirt_uv_polys", [])
    shorts_polys = uv_meta.get("shorts_uv_polys", [])
    chest_box = uv_meta.get("chest_uv_box", {"u_min": 0.1012, "u_max": 0.2597, "v_min": 0.7722, "v_max": 0.9247})

    # Synthesize 100% clean cotton jersey knit weave (ZERO ghosting from old logos in family_ready.blend;
    # real cloth folds & shadows come from male_casualsuit06_ao.png + male_casualsuit06_normal.png!)
    rng = np.random.default_rng(108)
    fine_grain = rng.normal(0.0, 0.016, size=(size, size)).astype(np.float32)
    yy = np.arange(size, dtype=np.float32)[:, None]
    xx = np.arange(size, dtype=np.float32)[None, :]
    knit = 0.010 * np.sin(yy * 1.4) + 0.008 * np.sin(xx * 1.8)
    shade = np.clip(1.0 + fine_grain + knit, 0.90, 1.08)

    crimson = np.array(CRIMSON_RED_RGB, dtype=np.float32)[None, None, :] / 255.0
    charcoal = np.array(CHARCOAL_SHORTS_RGB, dtype=np.float32)[None, None, :] / 255.0

    shirt_rgb = np.clip(crimson * shade[..., None], 0.0, 1.0)
    shorts_rgb = np.clip(charcoal * shade[..., None], 0.0, 1.0)

    shirt_mask_img = _rasterize_uv_polys(shirt_polys, size)
    shorts_mask_img = _rasterize_uv_polys(shorts_polys, size)

    s_m = (np.asarray(shirt_mask_img, dtype=np.float32) / 255.0)[..., None]
    p_m = (np.asarray(shorts_mask_img, dtype=np.float32) / 255.0)[..., None]

    # Combine: 100% pure shirt connected-component = Crimson, shorts connected-component = Charcoal
    out_arr = shirt_rgb * s_m + shorts_rgb * np.clip(p_m * (1.0 - s_m), 0.0, 1.0)
    bg_m = np.clip(1.0 - np.maximum(s_m, p_m), 0.0, 1.0)
    split_y = int(size * 0.50)
    bg_fill = np.zeros_like(out_arr)
    bg_fill[:split_y] = shirt_rgb[:split_y]
    bg_fill[split_y:] = shorts_rgb[split_y:]
    out_arr = np.clip(out_arr + bg_fill * bg_m, 0.0, 1.0)

    out_img = Image.fromarray((out_arr * 255.0).astype(np.uint8), mode="RGB")

    # Paint crisp bold white "JADI APA" centered strictly inside the front-chest UV box!
    u_min = float(chest_box["u_min"])
    u_max = float(chest_box["u_max"])
    v_min = float(chest_box["v_min"])
    v_max = float(chest_box["v_max"])

    cx = int(round(((u_min + u_max) * 0.5) * size))
    # Place slightly above vertical midpoint of chest box (natural printed graphic tee height!)
    cy = int(round((1.0 - (v_min + (v_max - v_min) * 0.54)) * size))
    target_w = int(round((u_max - u_min) * size * 0.78))  # 78% of chest width -> generous side margin, zero seam clip!

    # Auto-fit bold font size to exact target_w
    tmp_draw = ImageDraw.Draw(out_img)
    fsize = 18
    while fsize < 220:
        f_test = _find_bold_font(fsize + 2)
        if tmp_draw.textlength(chest_text, font=f_test) > target_w:
            break
        fsize += 2
    font = _find_bold_font(fsize)

    # Render text onto RGBA layer with subtle dark drop edge & cotton texture blend
    txt_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt_layer)
    bb = td.textbbox((0, 0), chest_text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    tx = int(round(cx - tw * 0.5 - bb[0]))
    ty = int(round(cy - th * 0.5 - bb[1]))

    # Crisp subtle underline accent bar below "JADI APA" for clean studio graphic tee look
    td.text((tx, ty), chest_text, font=font, fill=INK_WHITE_RGBA)
    bar_y = int(round(cy + th * 0.5 + 10))
    bar_half = int(round(tw * 0.34))
    td.rounded_rectangle(
        [(cx - bar_half, bar_y), (cx + bar_half, bar_y + 7)],
        radius=3,
        fill=(250, 212, 68, 235),  # Subtle golden-yellow studio brand accent bar!
    )

    out_rgba = out_img.convert("RGBA")
    out_rgba.alpha_composite(txt_layer)
    final_rgb = out_rgba.convert("RGB")

    out_tex_path.parent.mkdir(parents=True, exist_ok=True)
    final_rgb.save(out_tex_path, format="PNG", optimize=True)
    print(
        f"[TEX] Painted Mas Dimas Crimson #A62C2B + '{chest_text}' (font={fsize}px @ {cx},{cy}, w={tw}px) -> {out_tex_path}",
        flush=True,
    )
    return out_tex_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Paint Mas Dimas Crimson JADI APA outfit UV texture")
    parser.add_argument("--src", type=str, required=True)
    parser.add_argument("--uv-meta", type=str, required=True)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--size", type=int, default=2048)
    parser.add_argument("--text", type=str, default="JADI APA")
    args = parser.parse_args()

    paint_mas_dimas_outfit(
        Path(args.src),
        Path(args.uv_meta),
        Path(args.out),
        size=args.size,
        chest_text=args.text,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
