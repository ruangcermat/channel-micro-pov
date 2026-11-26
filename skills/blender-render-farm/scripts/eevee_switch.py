# Switch a baked Cycles scene to EEVEE (fast, real-time renderer) so a long shot renders on a normal PC.
# ~2-6 s/frame instead of 30-60 s. Softer realism: no true path-traced bounce, approximate SSS/volumes.
# Usage: blender -b scene.blend -P eevee_switch.py -- out.blend [samples=32]
import bpy, sys
a = sys.argv[sys.argv.index("--") + 1:]; out = a[0]; smp = int(a[1]) if len(a) > 1 else 32
sc = bpy.context.scene
ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
sc.render.engine = next(e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if e in ids)
ee = sc.eevee
for k, v in (("taa_render_samples", smp), ("use_shadows", True), ("use_raytracing", True),
             ("ray_tracing_method", "SCREEN"), ("use_volumetric_shadows", True), ("volumetric_tile_size", "4"),
             ("shadow_ray_count", 2), ("shadow_step_count", 8)):
    try: setattr(ee, k, v)
    except Exception as e: print("skip", k, e)
bpy.ops.wm.save_as_mainfile(filepath=out)
print("ENGINE", sc.render.engine, "samples", smp, "->", out)
