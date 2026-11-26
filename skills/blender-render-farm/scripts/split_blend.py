# Split a big packed .blend into 9 MB parts so it can be uploaded through the browser
# (the Chrome extension's file upload caps at ~10.4 MB per call). Colab/Kaggle notebooks join them back.
# Usage: python split_blend.py scene_packed.blend out_dir [part_mb=9]
import os, sys
src, out = sys.argv[1], sys.argv[2]; mb = float(sys.argv[3]) if len(sys.argv) > 3 else 9
os.makedirs(out, exist_ok=True); size = int(mb * 1_000_000); name = os.path.basename(src)
with open(src, "rb") as f:
    i = 0
    while True:
        b = f.read(size)
        if not b: break
        open(os.path.join(out, f"{name}.part{i}"), "wb").write(b); i += 1
print("wrote", i, "parts of", mb, "MB ->", out, "(join must sort NUMERICALLY: part10 after part9)")
