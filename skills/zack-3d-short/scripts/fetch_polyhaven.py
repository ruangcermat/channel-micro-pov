# Download Poly Haven (CC0) models as 1k glTF and textures as 1k jpg into assets/
import json, os, sys, urllib.request
UA = {"User-Agent": "doc-render-script"}
def get(url): return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()
def save(url, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path): open(path, "wb").write(get(url))
models, textures = sys.argv[1].split(","), (sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else [])
for m in models:
    f = json.loads(get(f"https://api.polyhaven.com/files/{m}"))
    if "gltf" not in f: print("skip (no gltf)", m, list(f)); continue
    g = f["gltf"]["1k"]["gltf"]
    save(g["url"], f"assets/{m}/{m}.gltf")
    for rel, inc in g.get("include", {}).items(): save(inc["url"], f"assets/{m}/{rel}")
    print("model", m)
for t in textures:
    f = json.loads(get(f"https://api.polyhaven.com/files/{t}"))
    for kind in ("Diffuse", "nor_gl", "Rough", "AO"):
        if kind in f and "1k" in f[kind]:
            v = f[kind]["1k"].get("jpg") or f[kind]["1k"].get("png")
            save(v["url"], f"assets/tex_{t}/{t}_{kind}." + v["url"].rsplit(".", 1)[1])
    print("texture", t)
