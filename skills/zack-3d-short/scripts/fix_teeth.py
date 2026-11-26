import bpy
for o in bpy.data.objects:
    if "teeth" in o.name.lower():
        for sl in o.material_slots:
            m = sl.material; nt = m.node_tree
            b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); tx = next((x for x in nt.nodes if x.type == "TEX_IMAGE"), None)
            for l in list(b.inputs["Base Color"].links): nt.links.remove(l)
            if tx: nt.links.new(tx.outputs["Color"], b.inputs["Base Color"]); print("TEETH", m.name)
bpy.ops.wm.save_mainfile()
