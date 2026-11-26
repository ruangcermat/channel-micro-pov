# Living-room set for Doc, built in code from real CC0 scans (Poly Haven) + textured walls/floor,
# window with warm sunlight. Opened on top of the character file, replaces the studio backdrop.
# Run: blender -b renders/doc_mpfb.blend -P room_set.py -- <out_png> <samples> <width>
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "renders/room_test.png"
SAMPLES = int(argv[1]) if len(argv) > 1 else 24
WIDTH = int(argv[2]) if len(argv) > 2 else 540
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")
sc = bpy.context.scene

# ---------------------------------------------------------------- remove the studio (backdrop, studio lights, rig)
for name in ("ViewRig", "Backdrop", "Key", "Fill", "Rim", "RimL"):
    o = bpy.data.objects.get(name)
    if o: bpy.data.objects.remove(o, do_unlink=True)
cam = bpy.data.objects["Cam"]; cam.parent = None

# ---------------------------------------------------------------- room shell  (x: -2.4..2.4, y: -3..1.6, z: 0..2.7)
X0, X1, Y0, Y1, H = -2.4, 2.4, -3.2, 1.6, 2.7
WIN = (0.55, 1.75, 0.85, 2.25)          # window in back wall: x0, x1, z0, z1

def tex_mat(name, tex, scale, rough=0.7, tint=None, bump=0.25):
    m = bpy.data.materials.new(name); nt = m.node_tree; b = nt.nodes["Principled BSDF"]; L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale); L(tc.outputs["UV"], mp.inputs["Vector"])
    d = os.path.join(A, "tex_" + tex)
    def img(kind, non_color=False):
        f = next((os.path.join(d, x) for x in os.listdir(d) if f"_{kind}." in x), None)
        if not f: return None
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(f, check_existing=True)
        if non_color: n.image.colorspace_settings.name = "Non-Color"
        L(mp.outputs["Vector"], n.inputs["Vector"]); return n
    dif = img("Diffuse")
    if dif:
        if tint:
            mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
            mx.inputs["Factor"].default_value = 1.0; L(dif.outputs["Color"], mx.inputs["A"])
            mx.inputs["B"].default_value = (*tint, 1); L(mx.outputs["Result"], b.inputs["Base Color"])
        else: L(dif.outputs["Color"], b.inputs["Base Color"])
    if not dif and tint: b.inputs["Base Color"].default_value = (*tint, 1)
    r = img("Rough", True)
    if r: L(r.outputs["Color"], b.inputs["Roughness"])
    else: b.inputs["Roughness"].default_value = rough
    n = img("nor_gl", True)
    if n:
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = bump
        L(n.outputs["Color"], nm.inputs["Color"]); L(nm.outputs["Normal"], b.inputs["Normal"])
    return m

def plain(name, col, rough=0.6, emit=0.0):
    m = bpy.data.materials.new(name); b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = emit
    return m

M_FLOOR = tex_mat("Floor", "laminate_floor_02", 0.5, bump=0.4)
M_WALL = tex_mat("Wall", "painted_plaster_wall", 0.45, tint=(0.93, 0.86, 0.76), bump=0.5)
M_RUG = tex_mat("Rug", "fabric_pattern_05", 0.9, tint=(0.55, 0.42, 0.33), bump=0.6)
M_TRIM = plain("Trim", (0.85, 0.84, 0.80), 0.35)
M_CEIL = plain("Ceiling", (0.88, 0.87, 0.84), 0.9)
M_SKY = plain("Sky", (0.55, 0.75, 1.0), 1.0, emit=3.0)

def quad(name, pts, mat, uv_scale=1.0):
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in pts]; f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    # planar UV in metres from the two longest in-plane axes
    n = f.normal; ax = max(range(3), key=lambda i: abs(n[i])); u, v = [i for i in range(3) if i != ax]
    for l in f.loops: l[uv].uv = (l.vert.co[u] * uv_scale, l.vert.co[v] * uv_scale)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat); return ob

def box(name, c, s, mat):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)), verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(mat)
    bev = ob.modifiers.new("b", "BEVEL"); bev.width = min(s) * 0.25; bev.segments = 2
    return ob

quad("Floor", [(X0, Y0, 0), (X1, Y0, 0), (X1, Y1, 0), (X0, Y1, 0)], M_FLOOR)
quad("Ceiling", [(X0, Y0, H), (X0, Y1, H), (X1, Y1, H), (X1, Y0, H)], M_CEIL)
quad("WallL", [(X0, Y0, 0), (X0, Y1, 0), (X0, Y1, H), (X0, Y0, H)], M_WALL)
quad("WallR", [(X1, Y1, 0), (X1, Y0, 0), (X1, Y0, H), (X1, Y1, H)], M_WALL)
wx0, wx1, wz0, wz1 = WIN       # back wall in 4 pieces around the window
quad("WallB1", [(X0, Y1, 0), (wx0, Y1, 0), (wx0, Y1, H), (X0, Y1, H)], M_WALL)
quad("WallB2", [(wx1, Y1, 0), (X1, Y1, 0), (X1, Y1, H), (wx1, Y1, H)], M_WALL)
quad("WallB3", [(wx0, Y1, 0), (wx1, Y1, 0), (wx1, Y1, wz0), (wx0, Y1, wz0)], M_WALL)
quad("WallB4", [(wx0, Y1, wz1), (wx1, Y1, wz1), (wx1, Y1, H), (wx0, Y1, H)], M_WALL)
# window frame, sill, mullion, glass-less opening onto a bright sky card
d = 0.12
box("WinTop", ((wx0 + wx1) / 2, Y1, wz1), (wx1 - wx0 + 0.1, d, 0.06), M_TRIM)
box("WinBot", ((wx0 + wx1) / 2, Y1 - 0.04, wz0), (wx1 - wx0 + 0.16, d + 0.08, 0.05), M_TRIM)
box("WinL", (wx0, Y1, (wz0 + wz1) / 2), (0.06, d, wz1 - wz0), M_TRIM)
box("WinR", (wx1, Y1, (wz0 + wz1) / 2), (0.06, d, wz1 - wz0), M_TRIM)
box("WinMid", ((wx0 + wx1) / 2, Y1, (wz0 + wz1) / 2), (0.04, d * 0.8, wz1 - wz0), M_TRIM)
box("WinCross", ((wx0 + wx1) / 2, Y1, (wz0 + wz1) / 2 + 0.15), (wx1 - wx0, d * 0.8, 0.04), M_TRIM)
sky = quad("SkyCard", [(wx0 - 1.5, Y1 + 2.5, -0.5), (wx1 + 1.5, Y1 + 2.5, -0.5), (wx1 + 1.5, Y1 + 2.5, 3.5), (wx0 - 1.5, Y1 + 2.5, 3.5)], M_SKY)
sky.visible_shadow = False
# skirting boards
for nm, c, s in (("SkirtB", (0, Y1 - 0.01, 0.05), (X1 - X0, 0.02, 0.1)), ("SkirtL", (X0 + 0.01, (Y0 + Y1) / 2, 0.05), (0.02, Y1 - Y0, 0.1)),
                 ("SkirtR", (X1 - 0.01, (Y0 + Y1) / 2, 0.05), (0.02, Y1 - Y0, 0.1))):
    box(nm, c, s, M_TRIM)
# rug under the coffee table
def rug_mat():
    m = bpy.data.materials.new("RugKilim"); nt = m.node_tree; b = nt.nodes["Principled BSDF"]; L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); L(tc.outputs["UV"], sep.inputs[0])
    nz0 = nt.nodes.new("ShaderNodeTexNoise"); nz0.inputs["Scale"].default_value = 40; nz0.inputs["Detail"].default_value = 6
    L(tc.outputs["UV"], nz0.inputs["Vector"])
    cr = nt.nodes.new("ShaderNodeValToRGB"); L(nz0.outputs["Fac"], cr.inputs["Fac"])
    cr.color_ramp.elements[0].color = (0.02, 0.03, 0.07, 1); cr.color_ramp.elements[1].color = (0.06, 0.08, 0.16, 1)
    class _B: pass
    br = _B(); br.outputs = {"Color": cr.outputs["Color"]}
    # cream border: distance from UV edges
    def mr(src, a, b_):
        n = nt.nodes.new("ShaderNodeMapRange"); n.clamp = True; n.inputs["From Min"].default_value = a; n.inputs["From Max"].default_value = b_
        L(src, n.inputs["Value"]); return n.outputs["Result"]
    def mn(a, b_):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = "MINIMUM"; L(a, n.inputs[0]); L(b_, n.inputs[1]); return n.outputs[0]
    def inv(a):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = "SUBTRACT"; n.inputs[0].default_value = 1.0; L(a, n.inputs[1]); return n.outputs[0]
    ex = mn(mr(sep.outputs["X"], 0.04, 0.045), mr(inv(sep.outputs["X"]), 0.04, 0.045))
    ey = mn(mr(sep.outputs["Y"], 0.05, 0.055), mr(inv(sep.outputs["Y"]), 0.05, 0.055))
    inner = mn(ex, ey)
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; L(inner, mx.inputs["Factor"])
    mx.inputs["A"].default_value = (0.82, 0.74, 0.60, 1); L(br.outputs["Color"], mx.inputs["B"])
    ex2 = mn(mr(sep.outputs["X"], 0.075, 0.08), mr(inv(sep.outputs["X"]), 0.075, 0.08))
    ey2 = mn(mr(sep.outputs["Y"], 0.09, 0.095), mr(inv(sep.outputs["Y"]), 0.09, 0.095))
    line = inv(mn(ex2, ey2)); lm = nt.nodes.new("ShaderNodeMath"); lm.operation = "MULTIPLY"; L(line, lm.inputs[0]); L(inner, lm.inputs[1])
    mx2 = nt.nodes.new("ShaderNodeMix"); mx2.data_type = "RGBA"; L(lm.outputs[0], mx2.inputs["Factor"])
    L(mx.outputs["Result"], mx2.inputs["A"]); mx2.inputs["B"].default_value = (0.45, 0.15, 0.07, 1); mx = mx2
    L(mx.outputs["Result"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.95
    b.inputs["Sheen Weight"].default_value = 0.5
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 900
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.3; L(nz.outputs["Fac"], bp.inputs["Height"]); L(bp.outputs["Normal"], b.inputs["Normal"])
    return m
rug = quad("Rug", [(-0.15, -1.3, 0.006), (2.05, -1.3, 0.006), (2.05, 0.3, 0.006), (-0.15, 0.3, 0.006)], rug_mat())
uvl = rug.data.uv_layers[0]
for li, lp in enumerate(rug.data.loops):
    co = rug.data.vertices[lp.vertex_index].co; uvl.data[li].uv = ((co.x + 0.15) / 2.2, (co.y + 1.3) / 1.6)

# ---------------------------------------------------------------- props (real scans)
def place(asset, loc, rot_z=0.0, scale=1.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(A, asset, asset + ".gltf"))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new("P_" + asset, None); sc.collection.objects.link(root)
    for o in new:
        if o.parent is None: o.parent = root
    root.location = loc; root.rotation_euler = (0, 0, math.radians(rot_z)); root.scale = (scale,) * 3
    for o in new:
        if o.type == "MESH":
            for m in o.data.materials:
                if not m or not m.node_tree: continue
                for n in m.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED" and n.inputs["Transmission Weight"].default_value > 0.01:
                        print("GLASS", asset, m.name, "-> hidden"); o.hide_render = True
    return root

CHAIR = (-0.55, 0.55)                                      # where Doc sits (chair faces -Y, the camera)
place("dining_chair_02", (CHAIR[0], CHAIR[1], 0), 0)     # backrest at the wall side, seat faces the camera
# shelving unit on the left wall, every shelf dressed
place("wooden_display_shelves_01", (-1.85, 1.3, 0), 90)
SY = 1.3
place("book_encyclopedia_set_01", (-2.12, SY, 0.785), 0, 0.62)
place("ceramic_vase_03", (-1.49, SY, 0.785), 0)
place("alarm_clock_01", (-1.85, SY, 0.785), 0)
place("standing_picture_frame_01", (-2.21, SY, 1.165), 0)
place("jug_01", (-1.85, SY, 1.165), 20)
place("wooden_bowl_01", (-1.49, SY, 1.165), 0, 0.8)
place("potted_plant_04", (-2.21, SY, 1.545), 0)
place("ceramic_vase_04", (-1.75, SY, 1.545), 0)
place("wooden_candlestick", (-1.45, SY, 1.545), 0)
place("cassette_player", (-1.49, SY, 0.405 + 0.11), 0)
# back wall left: side table with lamp-ish details, wall art, sconces
place("side_table_01", (-1.12, 1.32, 0), 0)            # clear of the sofa arm
place("ceramic_vase_02", (-1.24, 1.35, 0.55), 0)
place("mantel_clock_01", (-1.02, 1.38, 0.55), 0, 0.7)
place("standing_picture_frame_02", (-0.97, 1.22, 0.55), 160)
place("brass_vase_01", (-0.05, 1.4, 0), 0)
place("industrial_wall_sconce", (-1.42, Y1, 2.0), 0)   # clear of his head in the seated shot
place("industrial_wall_sconce", (-0.06, Y1, 1.95), 0)   # clear of the curtain, matches the left one
# window wall: sofa + pillows, big plant, basket
place("sofa_03", (1.15, 1.08, 0), 0)
place("throw_pillows_01", (1.15, 1.12, 0.45), 0)
place("potted_plant_01", (2.1, 1.2, 0), 30)
place("wicker_basket_02", (2.15, 0.25, 0), 20)
# centre: coffee table dressed, pouf
place("modern_coffee_table_01", (0.95, -0.98, 0), 90)   # further from his walk path
place("chess_set", (1.05, -0.8, 0.39), 15, 0.75)          # fully on the table top
place("wooden_bowl_01", (1.28, -1.04, 0.39), 0)           # fully on the table top
place("potted_plant_04", (0.72, -1.03, 0.39), 0)
place("Ottoman_01", (1.0, -1.9, 0), 80, 0.8)
# left foreground: tall side table with clock, floor plant
place("side_table_tall_01", (-0.95, -0.45, 0), 0)
place("ceramic_vase_01", (-0.95, -0.45, 0.76), 0)
place("potted_plant_02", (-1.75, -0.9, 0), 40)            # out of the foreground edge
place("planter_pot_clay", (-1.5, 0.95, 0), 0)
place("wall_clock", (X0 + 0.03, -0.55, 1.95), 90)
place("modern_ceiling_lamp_01", (0.6, 0.0, H - 1.17 * 0.8), 0, 0.8)   # flush to ceiling, bottom ~1.94 m clears his head

def framed(img_path, cx, cz, w, h, v0=0.0, v1=1.0):
    m = bpy.data.materials.new("Art"); nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(img_path, check_existing=True)
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.35
    y = Y1 - 0.025
    bm = bmesh.new(); vs = [bm.verts.new(p) for p in [(cx + w / 2, y, cz - h / 2), (cx - w / 2, y, cz - h / 2), (cx - w / 2, y, cz + h / 2), (cx + w / 2, y, cz + h / 2)]]
    f = bm.faces.new(vs); uv = bm.loops.layers.uv.new()
    for l, c in zip(f.loops, [(0, v0), (1, v0), (1, v1), (0, v1)]): l[uv].uv = c
    me = bpy.data.meshes.new("Art"); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Art", me); sc.collection.objects.link(ob); me.materials.append(m)
    fm = plain("FrameWood", (0.06, 0.045, 0.035), 0.4); t_ = 0.035
    for c, sz in (((cx, y + 0.01, cz + h / 2 + t_ / 2), (w + 2 * t_, 0.03, t_)), ((cx, y + 0.01, cz - h / 2 - t_ / 2), (w + 2 * t_, 0.03, t_)),
                  ((cx - w / 2 - t_ / 2, y + 0.01, cz), (t_, 0.03, h)), ((cx + w / 2 + t_ / 2, y + 0.01, cz), (t_, 0.03, h))):
        box("Frame", c, sz, fm)
framed(os.path.join(A, "hanging_picture_frame_02", "textures", next(f for f in os.listdir(os.path.join(A, "hanging_picture_frame_02", "textures")) if "artwork_diff" in f)), -0.55, 1.65, 0.72, 0.41, 0.225, 0.775)   # crop the texture's streaked padding
framed(os.path.join(A, "hanging_picture_frame_01", "textures", "hanging_picture_frame_01_artwork_diff_1k.jpg"), -1.85, 2.05, 0.36, 0.48)
# (small frame at x 0.25 removed: it was hidden behind the curtain)
# curtains: folded fabric panels each side of the window
def curtain(cx):
    m = bpy.data.materials.new("Curtain"); b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.36, 0.42, 0.33, 1); b.inputs["Roughness"].default_value = 0.85
    b.inputs["Sheen Weight"].default_value = 0.6; b.inputs["Transmission Weight"].default_value = 0.0
    bm = bmesh.new(); nx, nz = 24, 30; w, hgt, top = 0.36, 2.35, 2.5
    grid = [[bm.verts.new((cx - w / 2 + w * i / nx, Y1 - 0.12 - 0.035 * math.sin(i / nx * math.pi * 6), top - hgt * j / nz)) for i in range(nx + 1)] for j in range(nz + 1)]
    for j in range(nz):
        for i in range(nx): bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    me = bpy.data.meshes.new("Curtain"); bm.to_mesh(me); bm.free(); me.shade_smooth()
    ob = bpy.data.objects.new("Curtain", me); sc.collection.objects.link(ob); me.materials.append(m)
    so = ob.modifiers.new("s", "SOLIDIFY"); so.thickness = 0.01
box("CurtainRod", ((wx0 + wx1) / 2, Y1 - 0.12, 2.52), (wx1 - wx0 + 1.3, 0.025, 0.025), plain("Rod", (0.05, 0.05, 0.05), 0.3))
curtain(wx0 - 0.25); curtain(wx1 + 0.25)
# wall details: light switch + sockets
for c in ((-2.38, -1.6, 1.15), (X0 + 0.01, -2.2, 1.15)):
    box("Switch", c, (0.015, 0.08, 0.12), M_TRIM)
for c in ((-0.2, Y1 - 0.008, 0.3), (1.95, Y1 - 0.008, 0.3)):
    box("Socket", c, (0.08, 0.015, 0.08), M_TRIM)

# ---------------------------------------------------------------- light: warm low sun through the window + soft room fill
sun_d = bpy.data.lights.new("Sun", "SUN"); sun_d.energy = 7.0; sun_d.color = (1.0, 0.88, 0.72); sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("Sun", sun_d); sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(-50), 0, math.radians(-25))
def area(name, loc, target, size, energy, col=(1, 1, 1)):
    l = bpy.data.lights.new(name, "AREA"); l.size = size; l.energy = energy; l.color = col
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("WindowFill", (1.15, Y1 - 0.15, 1.55), (0.2, -1.0, 0.8), 1.2, 140, (0.85, 0.92, 1.0))
area("CeilFill", (0.0, -0.8, H - 0.05), (0.0, -0.8, 0.0), 2.5, 120, (1.0, 0.95, 0.88))
area("CamFill", (0.6, -3.0, 1.6), (0.0, 0.3, 1.0), 1.5, 60, (1.0, 0.97, 0.92))
w = sc.world.node_tree.nodes.get("Background")
w.inputs["Color"].default_value = (0.6, 0.72, 0.9, 1); w.inputs["Strength"].default_value = 0.15

# ---------------------------------------------------------------- camera: wide establishing view, slightly low, Zack-style
cam.data.lens = 26
cam.location = (0.45, -2.7, 1.1)
cam.rotation_euler = (Vector((-0.15, 0.5, 0.75)) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.view_settings.view_transform = "Khronos PBR Neutral"

# Doc stands in front of the chair for the test still
sys.path.insert(0, HERE); import doc_pose as D
arm = D.get_arm(); arm.location = (CHAIR[0], CHAIR[1] - 0.45, 0)
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="POSE")
for pb in arm.pose.bones:
    if pb.name.startswith(("upperarm", "lowerarm01", "shoulder01", "upperleg")): pb.matrix_basis.identity()
D.relaxed_hands(arm); D.pose_arms(arm); bpy.ops.object.mode_set(mode="OBJECT")

r = sc.render; r.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
r.resolution_x = WIDTH; r.resolution_y = int(WIDTH * 16 / 9) // 2 * 2
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "renders", "doc_room.blend"))
if OUT != "none":
    r.filepath = os.path.abspath(OUT); bpy.ops.render.render(write_still=True); print("RENDERED", r.filepath)
