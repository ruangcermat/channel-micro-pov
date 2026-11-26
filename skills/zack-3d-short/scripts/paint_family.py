# Outfit textures for the kitchen short:
#  kid  -> male_casualsuit06 (tee + jeans): red tee, logos removed, big "MR UDO" on the chest
#  mom  -> female_casualsuit01 (tee + jeans): soft sage-green tee, logo removed, darker jeans
# Run: python paint_family.py [kid_text_x kid_text_y kid_text_w]   (texture pixels, 2048 map)
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "extensions", ".user",
                   "blender_org", "mpfb", "data", "clothes")
OUT = os.path.join(HERE, "tex"); os.makedirs(OUT, exist_ok=True)
FONT = "C:/Windows/Fonts/ariblk.ttf"

def recolour(img, box, rgb, keep=0.85):
    """recolour a region to rgb, keeping the fabric shading (luminance)"""
    a = np.asarray(img).astype(np.float32) / 255.0
    x0, y0, x1, y1 = box
    reg = a[y0:y1, x0:x1]
    lum = (0.299 * reg[..., 0] + 0.587 * reg[..., 1] + 0.114 * reg[..., 2])
    shade = lum / max(1e-4, np.percentile(lum, 70))
    shade = 1 - keep + keep * np.clip(shade, 0, 1.3)
    col = np.array(rgb, np.float32)[None, None, :] / 255.0
    bg = reg.mean(axis=2) > 0.78                     # the light-grey empty texture background stays as it is
    new = np.clip(col * shade[..., None], 0, 1)
    if "skipbg" in rgb.__class__.__name__: pass
    reg[:] = np.where(bg[..., None] & (lum[..., None] > 0.8) & False, reg, new)
    a[y0:y1, x0:x1] = reg
    return Image.fromarray((a * 255).astype(np.uint8))

def patch(img, box, src_box):
    """cover a logo with clean fabric copied from src_box (same size), soft edges"""
    x0, y0, x1, y1 = box; w, h = x1 - x0, y1 - y0
    piece = img.crop(src_box).resize((w, h))
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([6, 6, w - 6, h - 6], 30, fill=255)
    img.paste(piece, (x0, y0), m.filter(ImageFilter.GaussianBlur(8)))

UVM = {}
def uv_mask(name, size=2048):
    """rasterise the garment's UV islands from its .obj -> exact cloth area of the texture"""
    if name in UVM: return UVM[name]
    vt, faces = [], []
    for line in open(os.path.join(SRC, name, name + ".obj"), encoding="utf8", errors="ignore"):
        if line.startswith("vt "):
            u, v = map(float, line.split()[1:3]); vt.append((u * size, (1 - v) * size))
        elif line.startswith("f "):
            faces.append([int(t.split("/")[1]) - 1 for t in line.split()[1:] if "/" in t and t.split("/")[1]])
    m = Image.new("L", (size, size), 0); d = ImageDraw.Draw(m)
    for f in faces:
        if len(f) >= 3: d.polygon([vt[i] for i in f], fill=255)
    m = m.filter(ImageFilter.MaxFilter(5))
    UVM[name] = m; return m
CUR = [None]
def fabric_mask(img, box):
    return np.asarray(uv_mask(CUR[0]).crop(box)) > 128

# ---------------------------------------------------------------- kid: red tee, MR UDO
CUR[0] = "male_casualsuit06"
kid = Image.open(os.path.join(SRC, "male_casualsuit06", "male_casualsuit06_diffuse.png")).convert("RGB")
TEE = (0, 0, 2048, 860)                                   # top band of the map = the tee panels
patch(kid, (380, 250, 640, 330), (120, 520, 380, 600))    # small chest logo (front)
patch(kid, (840, 220, 1580, 440), (900, 520, 1640, 740))  # big back logo
mask = fabric_mask(kid, TEE)
red = recolour(kid.crop(TEE), (0, 0, TEE[2], TEE[3]), (178, 28, 30), keep=0.75)
base = kid.crop(TEE); base.paste(red, (0, 0), Image.fromarray((mask * 255).astype(np.uint8)))
kid.paste(base, (0, 0))
tx = int(sys.argv[1]) if len(sys.argv) > 1 else 360
ty = int(sys.argv[2]) if len(sys.argv) > 2 else 345
tw = int(sys.argv[3]) if len(sys.argv) > 3 else 340
txt = Image.new("RGBA", (tw, tw // 2), (0, 0, 0, 0)); d = ImageDraw.Draw(txt)
size = 10
while True:
    f = ImageFont.truetype(FONT, size + 4)
    if d.textlength("MR UDO", font=f) > tw * 0.94: break
    size += 4
f = ImageFont.truetype(FONT, size)
bb = d.textbbox((0, 0), "MR UDO", font=f)
d.text(((tw - (bb[2] - bb[0])) / 2 - bb[0], (tw // 2 - (bb[3] - bb[1])) / 2 - bb[1]), "MR UDO", font=f, fill=(250, 246, 238, 255))
# printed-ink look: a little fabric shading shows through
kid.paste(txt, (tx - tw // 2, ty - tw // 4), txt)
kid.save(os.path.join(OUT, "kid_tee_diffuse.png"))

# ---------------------------------------------------------------- mom: sage-green tee
CUR[0] = "female_casualsuit01"
mom = Image.open(os.path.join(SRC, "female_casualsuit01", "female_casualsuit01_diffuse.png")).convert("RGB")
patch(mom, (1455, 290, 1800, 670), (1110, 290, 1455, 670))   # front logo
TOP = (0, 0, 2048, 860)
mask = fabric_mask(mom, TOP)
grn = recolour(mom.crop(TOP), (0, 0, TOP[2], TOP[3]), (112, 140, 112), keep=0.55)
base = mom.crop(TOP); base.paste(grn, (0, 0), Image.fromarray((mask * 255).astype(np.uint8)))
mom.paste(base, (0, 0))
# sleeve caps (right-hand pieces lower down) recoloured too
SL = (1520, 1150, 2048, 1720)
mask = fabric_mask(mom, SL)
g2 = recolour(mom.crop(SL), (0, 0, SL[2] - SL[0], SL[3] - SL[1]), (112, 140, 112), keep=0.55)
b2 = mom.crop(SL); b2.paste(g2, (0, 0), Image.fromarray((mask * 255).astype(np.uint8))); mom.paste(b2, SL[:2])
mom.save(os.path.join(OUT, "mom_tee_diffuse.png"))
prev = Image.new("RGB", (1600, 800)); prev.paste(kid.resize((800, 800)), (0, 0)); prev.paste(mom.resize((800, 800)), (800, 0))
prev.save(os.path.join(OUT, "family_tex_preview.jpg"))
print("saved")
