# Kitchen set for the onion short. Opens renders/family.blend (mom + kid), removes the studio,
# builds a dense CC0 kitchen (Poly Haven scans + code-built cabinets) and saves renders/kitchen.blend.
# Run: blender -b renders/family.blend -P kitchen_set.py -- <out_png|none> <samples> <width>
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "none"
SAMPLES = int(argv[1]) if len(argv) > 1 else 24
WIDTH = int(argv[2]) if len(argv) > 2 else 540
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(HERE, "assets"); sys.path.insert(0, HERE)
sc = bpy.context.scene; rnd = random.Random(4)

for n in ("Backdrop", "Key", "Fill", "Rim", "RimL"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

# room: x -2.3..2.3, y -2.6..1.8, h 2.6. Counter run on the back wall (y=1.8), fridge back right, door in the right wall.
X0, X1, Y0, Y1, H = -2.3, 2.3, -2.6, 1.8, 2.6
CT = 0.92                     # worktop height

def tex_mat(name, tex, scale, rough=0.6, tint=None, bump=0.3):
    m = bpy.data.materials.new(name); nt = m.node_tree; b = nt.nodes["Principled BSDF"]; L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale,) * 3; L(tc.outputs["UV"], mp.inputs["Vector"])
    d = os.path.join(A, "tex_" + tex)
    def img(kind, nc=False):
        f = next((os.path.join(d, x) for x in os.listdir(d) if f"_{kind}." in x), None)
        if not f: return None
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(f, check_existing=True)
        if nc: n.image.colorspace_settings.name = "Non-Color"
        L(mp.outputs["Vector"], n.inputs["Vector"]); return n
    dif = img("Diffuse")
    if dif and tint:
        mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs["Factor"].default_value = 1
        L(dif.outputs["Color"], mx.inputs["A"]); mx.inputs["B"].default_value = (*tint, 1); L(mx.outputs["Result"], b.inputs["Base Color"])
    elif dif: L(dif.outputs["Color"], b.inputs["Base Color"])
    r = img("Rough", True)
    if r: L(r.outputs["Color"], b.inputs["Roughness"])
    else: b.inputs["Roughness"].default_value = rough
    n = img("nor_gl", True)
    if n:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump
        L(n.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    return m

def plain(name, col, rough=0.5, metal=0.0, emit=0.0, coat=0.0):
    m = bpy.data.materials.new(name); b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = emit
    return m

M_FLOOR = tex_mat("Floor", "wood_floor", 0.45, bump=0.4)
M_WALL = tex_mat("Wall", "painted_plaster_wall", 0.45, tint=(0.97, 0.92, 0.82), bump=0.4)
def subway():
    m = bpy.data.materials.new("Subway"); nt = m.node_tree; b = nt.nodes["Principled BSDF"]; L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord"); br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0; br.inputs["Mortar Size"].default_value = 0.006
    br.inputs["Brick Width"].default_value = 0.15; br.inputs["Row Height"].default_value = 0.075
    br.inputs["Color1"].default_value = (0.92, 0.93, 0.92, 1); br.inputs["Color2"].default_value = (0.86, 0.88, 0.87, 1)
    br.inputs["Mortar"].default_value = (0.55, 0.55, 0.52, 1); br.offset = 0.5
    L(tc.outputs["UV"], br.inputs["Vector"]); L(br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.12; b.inputs["Coat Weight"].default_value = 0.5
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; bp.invert = True
    L(br.outputs["Fac"], bp.inputs["Height"]); L(bp.outputs["Normal"], b.inputs["Normal"])
    return m
M_TILE = subway()
M_TOP = tex_mat("Worktop", "marble_01", 0.7, bump=0.2)
M_CAB = plain("Cabinet", (0.16, 0.27, 0.25), 0.35, coat=0.3)          # sage-teal painted doors
M_CABIN = plain("CabinetBody", (0.86, 0.84, 0.78), 0.5)
M_HANDLE = plain("Brass", (0.75, 0.55, 0.25), 0.25, metal=1.0)
M_STEEL = plain("Steel", (0.75, 0.76, 0.78), 0.22, metal=1.0)
M_FRIDGE = plain("Fridge", (0.90, 0.90, 0.88), 0.25, coat=0.6)
M_TRIM = plain("Trim", (0.93, 0.92, 0.88), 0.4)
M_DARK = plain("Dark", (0.03, 0.03, 0.035), 0.4)
M_SKY = plain("Sky", (0.55, 0.75, 1.0), 1.0, emit=3.0)

def box(name, c, s, mat, bevel=0.25):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)), verts=bm.verts)
    uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i])); u, v = [i for i in range(3) if i != ax]
        for l in f.loops: l[uv].uv = (l.vert.co[u], l.vert.co[v])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat)
    if bevel:
        bv = ob.modifiers.new("b", "BEVEL"); bv.width = min(min(s) * bevel, 0.012); bv.segments = 2
    return ob

def quad(name, pts, mat, uvs=1.0):
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in pts]; f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
    ax = max(range(3), key=lambda i: abs(f.normal[i])); u, v = [i for i in range(3) if i != ax]
    for l in f.loops: l[uv].uv = (l.vert.co[u] * uvs, l.vert.co[v] * uvs)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat); return ob

def cyl(name, c, r, h, mat, verts=24):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=h)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return ob

def place(asset, loc, rot_z=0.0, scale=1.0, name=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, asset, asset + ".gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(name or ("P_" + asset), None); sc.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.location = loc; root.rotation_euler = (0, 0, math.radians(rot_z)); root.scale = (scale,) * 3
    return root

# ---------------------------------------------------------------- shell
WIN = (-1.55, -0.45, 1.15, 2.1)          # window over the sink in the back wall
DOOR = (-0.95, 0.05, 2.15)               # doorway in the right wall: y0, y1, top
quad("Floor", [(X0, Y0, 0), (X1, Y0, 0), (X1, Y1, 0), (X0, Y1, 0)], M_FLOOR)
quad("Ceiling", [(X0, Y0, H), (X0, Y1, H), (X1, Y1, H), (X1, Y0, H)], plain("Ceil", (0.92, 0.91, 0.88), 0.9))
quad("WallL", [(X0, Y0, 0), (X0, Y1, 0), (X0, Y1, H), (X0, Y0, H)], M_WALL)
dy0, dy1, dz = DOOR
quad("WallR1", [(X1, Y1, 0), (X1, dy1, 0), (X1, dy1, H), (X1, Y1, H)], M_WALL)
quad("WallR2", [(X1, dy0, 0), (X1, Y0, 0), (X1, Y0, H), (X1, dy0, H)], M_WALL)
quad("WallR3", [(X1, dy1, dz), (X1, dy0, dz), (X1, dy0, H), (X1, dy1, H)], M_WALL)
quad("WallF", [(X1, Y0, 0), (X0, Y0, 0), (X0, Y0, H), (X1, Y0, H)], M_WALL)
wx0, wx1, wz0, wz1 = WIN
quad("WallB1", [(X0, Y1, 0), (wx0, Y1, 0), (wx0, Y1, H), (X0, Y1, H)], M_WALL)
quad("WallB2", [(wx1, Y1, 0), (X1, Y1, 0), (X1, Y1, H), (wx1, Y1, H)], M_WALL)
quad("WallB3", [(wx0, Y1, 0), (wx1, Y1, 0), (wx1, Y1, wz0), (wx0, Y1, wz0)], M_WALL)
quad("WallB4", [(wx0, Y1, wz1), (wx1, Y1, wz1), (wx1, Y1, H), (wx0, Y1, H)], M_WALL)
for nm, c, s in (("WinT", ((wx0 + wx1) / 2, Y1, wz1), (wx1 - wx0 + 0.1, 0.1, 0.06)), ("WinB", ((wx0 + wx1) / 2, Y1 - 0.03, wz0), (wx1 - wx0 + 0.12, 0.14, 0.04)),
                 ("WinL", (wx0, Y1, (wz0 + wz1) / 2), (0.06, 0.1, wz1 - wz0)), ("WinR", (wx1, Y1, (wz0 + wz1) / 2), (0.06, 0.1, wz1 - wz0)),
                 ("WinM", ((wx0 + wx1) / 2, Y1, (wz0 + wz1) / 2), (0.035, 0.08, wz1 - wz0))):
    box(nm, c, s, M_TRIM)
sky = quad("Sky", [(-30, Y1 + 40, -2), (30, Y1 + 40, -2), (30, Y1 + 40, 30), (-30, Y1 + 40, 30)], M_SKY); sky.visible_shadow = False
# garden outside the window: soft green band + tree blobs
import street; street.build(sc, Vector((0, Y1, 0)), plain, box, quad, cyl, x_span=(-16, 30))
# door frame + hallway glimpse
for nm, c, s in (("DoorL", (X1, dy0 - 0.03, dz / 2), (0.14, 0.06, dz)), ("DoorR", (X1, dy1 + 0.03, dz / 2), (0.14, 0.06, dz)),
                 ("DoorT", (X1, (dy0 + dy1) / 2, dz + 0.03), (0.14, dy1 - dy0 + 0.12, 0.06))):
    box(nm, c, s, M_TRIM)
quad("Hall", [(X1 + 1.2, dy1 + 0.6, 0), (X1 + 1.2, dy0 - 0.6, 0), (X1 + 1.2, dy0 - 0.6, H), (X1 + 1.2, dy1 + 0.6, H)], plain("HallWall", (0.80, 0.70, 0.58), 0.8))
quad("HallFloor", [(X1, dy1 + 0.6, 0.001), (X1, dy0 - 0.6, 0.001), (X1 + 1.2, dy0 - 0.6, 0.001), (X1 + 1.2, dy1 + 0.6, 0.001)], M_FLOOR)
for nm, c, s in (("SkirtL", (X0 + 0.01, (Y0 + Y1) / 2, 0.05), (0.02, Y1 - Y0, 0.1)), ("SkirtF", (0, Y0 + 0.01, 0.05), (X1 - X0, 0.02, 0.1))):
    box(nm, c, s, M_TRIM, 0)

# ---------------------------------------------------------------- counter run on the back wall (x -2.3 .. 0.9) + stove gap
DEP = 0.62
def base_run(x0, x1):
    box("Plinth", ((x0 + x1) / 2, Y1 - DEP / 2 + 0.05, 0.05), (x1 - x0, DEP - 0.1, 0.1), M_DARK, 0)
    box("Carcass", ((x0 + x1) / 2, Y1 - DEP / 2, 0.1 + (CT - 0.14) / 2), (x1 - x0, DEP, CT - 0.14), M_CABIN, 0)
    n = max(1, round((x1 - x0) / 0.5)); w = (x1 - x0) / n
    for i in range(n):
        cx = x0 + w * (i + 0.5)
        box("Door", (cx, Y1 - DEP - 0.01, 0.1 + (CT - 0.3) / 2 + 0.01), (w - 0.012, 0.02, CT - 0.32), M_CAB)
        box("Drawer", (cx, Y1 - DEP - 0.01, CT - 0.12), (w - 0.012, 0.02, 0.13), M_CAB)
        box("Pull", (cx, Y1 - DEP - 0.03, CT - 0.12), (0.12, 0.015, 0.012), M_HANDLE, 0.4)
        box("Knob", (cx + (w / 2 - 0.06) * (1 if i % 2 else -1), Y1 - DEP - 0.03, CT - 0.3), (0.014, 0.02, 0.07), M_HANDLE, 0.4)
    box("Top", ((x0 + x1) / 2, Y1 - DEP / 2 + 0.01, CT - 0.02), (x1 - x0 + 0.02, DEP + 0.04, 0.04), M_TOP, 0.2)
base_run(-2.3, 0.05)
place("electric_stove", (0.31, Y1 - 0.34, 0), 0, name="Stove")
base_run(0.57, 1.05)
# fridge (code-built, tall, two doors)
FX0, FX1 = 1.08, 1.83
box("FridgeBody", ((FX0 + FX1) / 2, Y1 - 0.36, 0.95), (FX1 - FX0, 0.7, 1.9), M_FRIDGE, 0.15)
box("FridgeSplit", ((FX0 + FX1) / 2, Y1 - 0.715, 1.25), (FX1 - FX0 - 0.02, 0.01, 0.012), M_DARK, 0)
for z0, z1 in ((0.08, 1.24), (1.27, 1.86)):
    box("FridgeHandle", (FX0 + 0.07, Y1 - 0.75, (z0 + z1) / 2 + (0.15 if z1 < 1.3 else -0.1)), (0.022, 0.03, 0.42), M_STEEL, 0.4)
# magnets + a kid drawing on the fridge
for i in range(6):
    c = [(0.9, 0.2, 0.15), (0.15, 0.5, 0.9), (0.95, 0.8, 0.1), (0.2, 0.7, 0.3)][i % 4]
    box("Magnet", (FX0 + 0.18 + 0.09 * (i % 3), Y1 - 0.72, 1.45 + 0.13 * (i // 3)), (0.04, 0.012, 0.04), plain("Mag", c, 0.4), 0.3)
# upper cabinets
UZ0, UZ1, UD = 1.5, 2.25, 0.36
for x0, x1 in ((-2.3, -1.65), (-0.35, 1.05)):
    box("Upper", ((x0 + x1) / 2, Y1 - UD / 2, (UZ0 + UZ1) / 2), (x1 - x0, UD, UZ1 - UZ0), M_CABIN, 0)
    n = max(1, round((x1 - x0) / 0.45)); w = (x1 - x0) / n
    for i in range(n):
        cx = x0 + w * (i + 0.5)
        box("UDoor", (cx, Y1 - UD - 0.01, (UZ0 + UZ1) / 2), (w - 0.012, 0.02, UZ1 - UZ0 - 0.012), M_CAB)
        box("UKnob", (cx + (w / 2 - 0.05) * (1 if i % 2 else -1), Y1 - UD - 0.03, UZ0 + 0.08), (0.014, 0.02, 0.07), M_HANDLE, 0.4)
box("Hood", (0.31, Y1 - 0.25, 1.62), (0.6, 0.5, 0.12), M_STEEL, 0.1)
box("HoodChimney", (0.31, Y1 - 0.16, 2.0), (0.28, 0.3, 0.7), M_STEEL, 0.1)
# tiled backsplash
quad("Splash", [(-2.3, Y1 - 0.005, CT), (1.05, Y1 - 0.005, CT), (1.05, Y1 - 0.005, UZ0), (-2.3, Y1 - 0.005, UZ0)], M_TILE, 1.0)
# sink under the window
box("Sink", (-1.0, Y1 - 0.33, CT - 0.005), (0.62, 0.42, 0.012), M_STEEL, 0)
box("SinkBowl", (-1.0, Y1 - 0.33, CT - 0.06), (0.56, 0.36, 0.11), M_DARK, 0)
cyl("TapBase", (-1.0, Y1 - 0.1, CT + 0.03), 0.022, 0.06, M_STEEL)
cyl("TapNeck", (-1.0, Y1 - 0.1, CT + 0.2), 0.012, 0.32, M_STEEL)
box("TapSpout", (-1.0, Y1 - 0.2, CT + 0.35), (0.024, 0.2, 0.024), M_STEEL, 0.4)
# utensil rail with hanging tools
box("Rail", (-0.95 + 0.9, Y1 - 0.03, 1.38), (0.9, 0.015, 0.015), M_STEEL, 0)
for i in range(5):
    x = -0.35 + 0.17 * i + 0.4
    box("Hook", (x, Y1 - 0.04, 1.33), (0.006, 0.006, 0.09), M_STEEL, 0)
    box("Utensil", (x, Y1 - 0.045, 1.2), (0.03 if i % 2 else 0.05, 0.008, 0.18), plain("Ut", [(0.12, 0.1, 0.09), (0.7, 0.5, 0.3)][i % 2], 0.4), 0.3)

# ---------------------------------------------------------------- props on the counter
CY = Y1 - 0.33
BOARD = (-0.55, CY - 0.05)
place("wooden_cutting_board", (BOARD[0], BOARD[1], CT), 8, name="Board")
place("yellow_onion", (BOARD[0] + 0.06, BOARD[1] + 0.03, CT + 0.04), 0, name="OnionWhole")
place("yellow_onion", (BOARD[0] - 0.24, BOARD[1] + 0.12, CT), 40, name="OnionSpare")
def chef_knife():
    bm = bmesh.new()
    # blade: flat, 20 cm, wide heel, curved edge to a point (x = along the blade)
    prof = [(0.0, 0.0), (0.2, 0.0), (0.205, 0.004), (0.17, 0.022), (0.08, 0.042), (0.0, 0.045)]
    top = [bm.verts.new((x, 0.0011, y)) for x, y in prof]; bot = [bm.verts.new((x, -0.0011, y)) for x, y in prof]
    bm.faces.new(top); bm.faces.new(bot[::-1])
    for i in range(len(prof)):
        j = (i + 1) % len(prof); bm.faces.new((top[i], top[j], bot[j], bot[i]))
    me = bpy.data.meshes.new("Blade"); bm.to_mesh(me); bm.free()
    blade = bpy.data.objects.new("KnifeBlade", me); sc.collection.objects.link(blade)
    me.materials.append(plain("BladeSteel", (0.82, 0.83, 0.85), 0.12, metal=1.0))
    h = box("KnifeHandle", (-0.06, 0, 0.022), (0.12, 0.018, 0.026), plain("HandleBlack", (0.03, 0.03, 0.03), 0.35), 0.45)
    for i in (-0.09, -0.06, -0.03):
        cyl("Rivet", (i, 0.0095, 0.022), 0.003, 0.002, M_STEEL, 12).rotation_euler = (math.radians(90), 0, 0)
    root = bpy.data.objects.new("Knife", None); sc.collection.objects.link(root)
    for o in [blade, h] + [o for o in bpy.data.objects if o.name.startswith("Rivet") and o.parent is None]: o.parent = root
    return root
kn = chef_knife(); kn.location = (BOARD[0] - 0.03, BOARD[1] - 0.06, CT + 0.026); kn.rotation_euler = (math.radians(90), 0, math.radians(15))
place("metal_jug", (-1.85, CY, CT), 0)
place("wooden_bowl_02", (-1.55, CY + 0.08, CT), 0)
place("lemon", (-1.55, CY + 0.08, CT + 0.05), 10, 1.0)
place("food_apple_01", (-1.48, CY + 0.06, CT + 0.04), 0)
place("pot_enamel_01", (0.24, Y1 - 0.42, CT + 0.0), 20, name="Pot")
place("brass_pan_01", (0.42, Y1 - 0.22, CT + 0.0), -30)
place("wooden_spoon", (0.76, CY, CT + 0.01), 60)
place("tea_set_01", (0.8, CY + 0.05, CT), 0, 0.55)
place("potted_plant_04", (-1.25, Y1 - 0.08, wz0 + 0.02), 0)
place("ceramic_vase_04", (-0.7, Y1 - 0.08, wz0 + 0.02), 0, 0.7)
# spice jars
for i in range(5):
    cyl("Jar", (-2.15 + 0.07 * i, Y1 - 0.12, CT + 0.06), 0.028, 0.12, plain("Glass", (0.9, 0.95, 1.0), 0.05))
    cyl("Spice", (-2.15 + 0.07 * i, Y1 - 0.12, CT + 0.04), 0.026, 0.08, plain("Sp", [(0.6, 0.2, 0.05), (0.85, 0.6, 0.1), (0.2, 0.35, 0.1), (0.5, 0.1, 0.05), (0.9, 0.85, 0.7)][i], 0.8))
    cyl("Lid", (-2.15 + 0.07 * i, Y1 - 0.12, CT + 0.125), 0.029, 0.012, M_DARK)
# kitchen roll
cyl("Roll", (-0.15, Y1 - 0.12, CT + 0.13), 0.055, 0.25, plain("Paper", (0.96, 0.96, 0.94), 0.8))
# glass panes of the upper-left cabinet hold plates (simple stacked discs)
for i in range(6):
    cyl("Plate", (-2.0, Y1 - 0.2, UZ0 + 0.06 + 0.012 * i), 0.12, 0.01, plain("Plt", (0.95, 0.95, 0.93), 0.2), 32)

# ---------------------------------------------------------------- dining table with food (left-centre)
TABLE = (-1.05, -0.55)
place("dining_table", (TABLE[0], TABLE[1], 0), 0, 0.62, name="Table")
TT = 0.88 * 0.62 + 0.0                                    # table top height after scaling
place("dining_chair_02", (TABLE[0] - 0.32, TABLE[1] + 0.55, 0), 0, name="ChairBack1")
place("dining_chair_02", (TABLE[0] + 0.32, TABLE[1] + 0.55, 0), 0, name="ChairBack2")
place("dining_chair_02", (TABLE[0] + 0.25, TABLE[1] - 0.55, 0), 180, name="ChairFront")
place("bananas", (TABLE[0] - 0.3, TABLE[1] + 0.05, TT), 20, 0.5)
place("carrot_cake", (TABLE[0] + 0.25, TABLE[1] + 0.1, TT), 0)
place("croissant", (TABLE[0] + 0.0, TABLE[1] - 0.15, TT), 30)
place("food_pears_asian_01", (TABLE[0] - 0.05, TABLE[1] + 0.2, TT + 0.03), 0, 0.6)
place("hamburger_buns", (TABLE[0] - 0.4, TABLE[1] - 0.2, TT), -10, 0.6)
# backpack on the front chair (the hiding place) - soft rounded box
bp = box("Backpack", (TABLE[0] + 0.25, TABLE[1] - 0.68, 0.62), (0.3, 0.16, 0.38), plain("BackpackFab", (0.12, 0.25, 0.55), 0.8), 0.45)
sub = bp.modifiers.new("s", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
# wall clock + a framed picture on the left wall, rug under the table
place("wall_clock", (X0 + 0.03, 0.1, 2.05), 90)
rug = quad("Rug", [(TABLE[0] - 1.0, TABLE[1] - 0.9, 0.004), (TABLE[0] + 1.0, TABLE[1] - 0.9, 0.004),
                   (TABLE[0] + 1.0, TABLE[1] + 0.9, 0.004), (TABLE[0] - 1.0, TABLE[1] + 0.9, 0.004)], plain("RugFab", (0.62, 0.22, 0.16), 0.95))
# pendant lamp over the table
cyl("LampCord", (TABLE[0], TABLE[1], H - 0.35), 0.004, 0.7, M_DARK, 8)
lamp = cyl("LampShade", (TABLE[0], TABLE[1], H - 0.75), 0.17, 0.16, plain("Shade", (0.12, 0.28, 0.26), 0.4), 32)
bulb = cyl("Bulb", (TABLE[0], TABLE[1], H - 0.84), 0.04, 0.05, plain("BulbGlow", (1.0, 0.85, 0.6), 0.3, emit=8.0), 16)


# ---------------------------------------------------------------- extra detail
mw = box("Microwave", (-1.9, Y1 - 0.3, CT + 0.15), (0.48, 0.36, 0.28), plain("MWBody", (0.12, 0.12, 0.13), 0.3), 0.08)
box("MWDoor", (-1.95, Y1 - 0.485, CT + 0.15), (0.32, 0.01, 0.22), plain("MWGlass", (0.02, 0.02, 0.025), 0.05, coat=1.0), 0)
box("MWPanel", (-1.73, Y1 - 0.485, CT + 0.15), (0.1, 0.01, 0.22), plain("MWPanel", (0.25, 0.25, 0.27), 0.3), 0)
box("MWClock", (-1.73, Y1 - 0.492, CT + 0.24), (0.06, 0.004, 0.02), plain("Digits", (0.2, 0.9, 0.4), 0.3, emit=3.0), 0)
box("Toaster", (-0.2, Y1 - 0.4, CT + 0.1), (0.28, 0.16, 0.19), plain("ToasterRed", (0.7, 0.08, 0.06), 0.25, coat=0.8), 0.25)
for dx in (-0.05, 0.05): box("Slot", (-0.2 + dx, Y1 - 0.4, CT + 0.195), (0.03, 0.12, 0.004), M_DARK, 0)
cyl("Kettle", (0.62, Y1 - 0.25, CT + 0.11), 0.08, 0.2, M_STEEL, 32)
cyl("KettleLid", (0.62, Y1 - 0.25, CT + 0.22), 0.05, 0.02, M_DARK, 24)
for i, col in enumerate([(0.9, 0.75, 0.1), (0.2, 0.45, 0.85), (0.85, 0.2, 0.15)]):
    box("Cereal", (FX0 + 0.15 + 0.2 * i, Y1 - 0.4, 1.9 + 0.15), (0.17, 0.07, 0.3), plain("CerealBox", col, 0.5), 0.05)
# wall calendar + kid drawing on the fridge
cp = os.path.join(HERE, "tex", "calendar.png")
def picture(name, path, c, w, h, normal_axis="-x"):
    m = bpy.data.materials.new(name); nt = m.node_tree; t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"]); nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    x, y, z = c
    if normal_axis == "+x":
        pts = [(x, y + w / 2, z - h / 2), (x, y - w / 2, z - h / 2), (x, y - w / 2, z + h / 2), (x, y + w / 2, z + h / 2)]
    else:
        pts = [(x - w / 2, y, z - h / 2), (x + w / 2, y, z - h / 2), (x + w / 2, y, z + h / 2), (x - w / 2, y, z + h / 2)]
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in pts]; f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
    for l, cc in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]): l[uv].uv = cc
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(m); return ob
picture("Calendar", cp, (X0 + 0.012, -1.2, 1.55), 0.3, 0.42, "+x")
dp = os.path.join(HERE, "tex", "drawing.png")
picture("KidDrawing", dp, (FX0 + 0.38, Y1 - 0.722, 1.52), 0.3, 0.22)
# towel on the oven handle
box("Towel", (0.31, Y1 - 0.69, 0.62), (0.22, 0.015, 0.3), plain("TowelFab", (0.85, 0.85, 0.8), 0.95), 0.3)
for i in range(4): box("TowelStripe", (0.31, Y1 - 0.699, 0.52 + 0.06 * i), (0.22, 0.004, 0.015), plain("TowelRed", (0.75, 0.1, 0.1), 0.9), 0)
# fruit bowl on the table + hanging plant by the window
place("wooden_bowl_01", (TABLE[0] + 0.45, TABLE[1] - 0.2, TT), 0, 1.2)
place("food_apple_01", (TABLE[0] + 0.43, TABLE[1] - 0.2, TT + 0.05), 0)
place("lemon", (TABLE[0] + 0.5, TABLE[1] - 0.17, TT + 0.05), 30)
place("potted_plant_04", (-2.05, Y1 - 0.25, UZ1 + 0.0), 0, 1.3)

# ---------------------------------------------------------------- light: morning sun through the window + soft fill
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 4.5; sun_d.color = (1.0, 0.9, 0.76); sun_d.angle = math.radians(2)
sun = bpy.data.objects.new("Sun", sun_d); sc.collection.objects.link(sun); sun.rotation_euler = (math.radians(-55), 0, math.radians(200))
def area(name, loc, target, size, energy, col=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.size = size; l.energy = energy; l.color = col
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); return o
area("WindowFill", (-1.0, Y1 - 0.2, 1.7), (-0.6, -0.5, 1.1), 1.1, 160, (0.85, 0.92, 1.0))
area("CeilFill", (0.0, -0.4, H - 0.05), (0.0, -0.4, 0.0), 2.6, 100, (1.0, 0.95, 0.88))
area("CamFill", (0.6, -2.4, 1.6), (0.0, 0.5, 1.2), 1.6, 70, (1.0, 0.97, 0.92))
pl = bpy.data.lights.new("LampPt", "POINT"); pl.energy = 25; pl.color = (1.0, 0.8, 0.55); pl.shadow_soft_size = 0.05
plo = bpy.data.objects.new("LampPt", pl); sc.collection.objects.link(plo); plo.location = (TABLE[0], TABLE[1], H - 0.88)
w = sc.world.node_tree.nodes.get("Background")
w.inputs["Color"].default_value = (0.6, 0.72, 0.9, 1); w.inputs["Strength"].default_value = 0.15

# ---------------------------------------------------------------- characters: mom at the board, kid at the door (shots move them)
mom = bpy.data.objects["Mom_rig"]; kid = bpy.data.objects["Kid_rig"]
mom.location = (BOARD[0] + 0.02, Y1 - DEP - 0.3, 0); mom.rotation_euler = (0, 0, math.radians(180))
kid.location = (1.4, -0.6, 0); kid.rotation_euler = (0, 0, math.radians(30))
cam = bpy.data.objects["Cam"]; cam.data.lens = 24
cam.location = (1.7, -2.3, 1.45)
cam.rotation_euler = (Vector((-0.4, 0.6, 0.95)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.view_settings.view_transform = "Khronos PBR Neutral"; sc.view_settings.exposure = -0.25
r = sc.render; r.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 6
r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "kitchen.blend"))
if OUT != "none":
    r.filepath = os.path.abspath(OUT); bpy.ops.render.render(write_still=True); print("RENDERED", r.filepath)
