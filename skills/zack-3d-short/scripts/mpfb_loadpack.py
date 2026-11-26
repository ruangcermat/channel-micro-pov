import bpy, sys, addon_utils
mod = "bl_ext.blender_org.mpfb"
addon_utils.enable(mod, default_set=True, persistent=True)
bpy.ops.wm.save_userpref()
r = bpy.ops.mpfb.load_pack(filepath=sys.argv[-1])
print("LOADPACK", r)
