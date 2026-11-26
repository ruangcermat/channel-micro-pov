# "Real camera" pass from the tutorial: softer lens, glow on bright spots, vignette, film grain.
# Usage: python post.py in.png out.png   (same look will be done with ffmpeg for video frames)
import sys, numpy as np
from PIL import Image, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB"); w, h = im.size; s = w / 1080
a = np.asarray(im).astype(np.float32) / 255

# 1. softer lens: blend in a tiny blur
soft = np.asarray(im.filter(ImageFilter.GaussianBlur(0.7 * s))).astype(np.float32) / 255
a = a * 0.65 + soft * 0.35

# 2. glow: blur only what is bright and add it back
lum = a @ np.array([0.2126, 0.7152, 0.0722])
bright = np.clip((lum - 0.72) / 0.28, 0, 1)[..., None] * a
g = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(18 * s))
a = 1 - (1 - a) * (1 - np.asarray(g).astype(np.float32) / 255 * 0.45)      # screen blend

# 3. vignette
yy, xx = np.mgrid[0:h, 0:w]
d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)
a *= (1 - 0.28 * np.clip((d - 0.35) / 0.65, 0, 1) ** 1.6)[..., None]

# 4. film grain (luma noise, slightly stronger in the shadows)
rng = np.random.default_rng(7)
n = rng.normal(0, 1, (h, w)).astype(np.float32)
n = np.asarray(Image.fromarray(((n * 0.25 + 0.5).clip(0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6 * s))).astype(np.float32) / 255 - 0.5
a += (n * 0.045 * (1.2 - lum.clip(0, 1)))[..., None]

Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8)).save(dst)
print("post ->", dst)
