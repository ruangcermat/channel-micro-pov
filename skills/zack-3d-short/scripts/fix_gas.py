# hide near-zero gas puffs in the baked file (they crash Cycles)
import bpy
sc = bpy.context.scene; n = 0
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    for g in [o for o in bpy.data.objects if o.name.startswith("GasPuff")]:
        if g.scale.x < 0.002 and not g.hide_render:
            g.hide_render = True; g.keyframe_insert("hide_render", frame=f); n += 1
print("HIDDEN", n); bpy.ops.wm.save_mainfile()
