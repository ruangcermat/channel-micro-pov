# Render chosen frames of an already-baked .blend, skipping frames already on disk (safe to resume).
# blender -b file.blend -P render_frames.py -- <out_dir> <samples> <width> <f1,f2,...|a-b|@listfile>
import bpy, sys, os, time
a = sys.argv[sys.argv.index("--") + 1:]; out, smp, w, spec = a[0], int(a[1]), int(a[2]), a[3]
if spec.startswith("@"): spec = open(spec[1:]).read().strip()
frames = []
for part in spec.split(","):
    if "-" in part: s, e = map(int, part.split("-")); frames += range(s, e + 1)
    elif part: frames.append(int(part))
sc = bpy.context.scene; r = sc.render; r.resolution_x = w; r.resolution_y = int(w * 16 / 9) // 2 * 2; r.resolution_percentage = 100
if sc.render.engine == "CYCLES": sc.cycles.samples = smp
os.makedirs(out, exist_ok=True)
for f in frames:
    p = os.path.join(os.path.abspath(out), f"k_{f:04d}.png")
    if os.path.exists(p): continue
    t = time.time(); sc.frame_set(f); r.filepath = p; bpy.ops.render.render(write_still=True)
    print(f"FRAME {f} {time.time() - t:.1f}s", flush=True)
