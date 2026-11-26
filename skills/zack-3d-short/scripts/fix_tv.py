# TV screen: 3 single images switched by keyed mix factors (image sequences can't be packed for Colab)
import bpy, os
HERE = os.path.dirname(bpy.data.filepath).rsplit(os.sep, 1)[0]
m = bpy.data.materials["TVScreen"]; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
for n in [n for n in nt.nodes if n.type == "TEX_IMAGE"]: nt.nodes.remove(n)
imgs = []
for k in (1, 2, 3):
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(HERE, "tex", f"tvshow_{k:02d}.png")); imgs.append(t)
m1 = nt.nodes.new("ShaderNodeMix"); m1.data_type = "RGBA"; m2 = nt.nodes.new("ShaderNodeMix"); m2.data_type = "RGBA"
nt.links.new(imgs[0].outputs["Color"], m1.inputs["A"]); nt.links.new(imgs[1].outputs["Color"], m1.inputs["B"])
nt.links.new(m1.outputs["Result"], m2.inputs["A"]); nt.links.new(imgs[2].outputs["Color"], m2.inputs["B"])
nt.links.new(m2.outputs["Result"], b.inputs["Base Color"]); nt.links.new(m2.outputs["Result"], b.inputs["Emission Color"])
sc = bpy.context.scene
for f in range(sc.frame_start, sc.frame_end + 1):
    k = (f // 6) % 3                       # new drawing every 6 frames (cartoon pace)
    m1.inputs["Factor"].default_value = 1.0 if k == 1 else 0.0; m2.inputs["Factor"].default_value = 1.0 if k == 2 else 0.0
    m1.inputs["Factor"].keyframe_insert("default_value", frame=f); m2.inputs["Factor"].keyframe_insert("default_value", frame=f)
print("TV FIXED"); bpy.ops.wm.save_mainfile()
