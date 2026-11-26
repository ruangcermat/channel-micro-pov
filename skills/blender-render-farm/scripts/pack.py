# Pack every texture into the .blend so it renders anywhere (Kaggle has none of our files).
import bpy, os, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.file.make_paths_absolute()
missing = [i.filepath for i in bpy.data.images if i.source == "FILE" and not i.packed_file and not os.path.exists(bpy.path.abspath(i.filepath))]
print("MISSING", missing)
bpy.ops.file.pack_all()
print("PACKED", sum(1 for i in bpy.data.images if i.packed_file), "of", len(bpy.data.images))
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
