# Repaint MakeHuman male_casualsuit02 (long-sleeve tee + jeans) into Doc's outfit:
# navy zip hoodie (zip, drawstrings, black tee V, pocket seams), near-black jeans.
# Also flattens the collar-rib normal map so no seam line shows on the chest.
import numpy as np, os
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_dilation

D = os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\extensions\.user\blender_org\mpfb\data\clothes\male_casualsuit02")
HERE = os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE, "tex"), exist_ok=True)

im = Image.open(os.path.join(D, "male_casualsuit02_diffuse.png")).convert("RGB"); W, H = im.size; k = W / 512
a = np.asarray(im).astype(np.float32) / 255; r, g, b = a[..., 0], a[..., 1], a[..., 2]
L = 0.3 * r + 0.59 * g + 0.11 * b; yy, xx = np.mgrid[0:H, 0:W] / k
orange = binary_dilation(r > b + 0.15, iterations=6)
ring = (np.hypot(xx - 286, yy - 87) > 24) & (np.hypot(xx - 286, yy - 87) < 32)      # grey logo circle
collar = (yy < 36) & (((xx > 235) & (xx < 340)) | ((xx > 30) & (xx < 150)))
jeans = (yy > 210) & ~((xx > 375) & (yy > 290)); fabric = ~jeans
bad = orange | collar | ring
med = np.median(L[fabric & ~bad]); Lf = np.where(bad, med, L)
out = a.copy(); navy = np.array([0.105, 0.130, 0.225])
out[fabric] = np.clip(navy * (Lf / med)[fabric][:, None] ** 0.6, 0, 1)
out[jeans] = np.clip(np.stack([L * 0.16, L * 0.18, L * 0.25], -1)[jeans], 0, 1)
img = Image.fromarray((out * 255).astype(np.uint8))
patch = img.crop((int(50 * k), int(80 * k), int(130 * k), int(160 * k)))          # plain fleece from the back
img.paste(patch, (int(246 * k), int(48 * k)))

S = 2; big = img.resize((W * S, H * S)); d = ImageDraw.Draw(big); K = k * S; C = 287 * K
d.polygon([(C - 18 * K, 8 * K), (C + 18 * K, 8 * K), (C, 52 * K)], fill=(16, 16, 18))          # black tee V
d.line([(C, 50 * K), (C, 203 * K)], fill=(28, 31, 44), width=int(4 * K))                     # zip tape
d.line([(C, 50 * K), (C, 203 * K)], fill=(125, 130, 140), width=int(1.1 * K))                # zip teeth
d.rounded_rectangle([C - 2 * K, 50 * K, C + 2 * K, 57 * K], radius=int(1 * K), fill=(150, 152, 160))
for s in (-1, 1):
    d.line([(C + s * 10 * K, 14 * K), (C + s * 12 * K, 92 * K)], fill=(185, 186, 182), width=int(1.5 * K))
    d.rounded_rectangle([C + s * 12 * K - 1.2 * K, 89 * K, C + s * 12 * K + 1.2 * K, 96 * K], radius=int(0.6 * K), fill=(120, 122, 128))
    d.line([(C + s * 4 * K, 150 * K), (C + s * 38 * K, 150 * K), (C + s * 48 * K, 195 * K)], fill=(18, 22, 40), width=int(1.2 * K))
img = big.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.5))
img.save(os.path.join(HERE, "tex", "male_casualsuit02_hoodie.png"))

nm = Image.open(os.path.join(D, "male_casualsuit02_normal.png")).convert("RGB"); NW, NH = nm.size; nk = NW / 512
n = np.asarray(nm).copy(); ny, nx = np.mgrid[0:NH, 0:NW] / nk
m = ((ny < 40) & (((nx > 230) & (nx < 345)) | ((nx > 25) & (nx < 155)))) | ((nx > 246) & (nx < 330) & (ny > 48) & (ny < 128))
n[m] = (128, 128, 255); Image.fromarray(n).save(os.path.join(HERE, "tex", "male_casualsuit02_normal_flat.png"))
print("painted")
