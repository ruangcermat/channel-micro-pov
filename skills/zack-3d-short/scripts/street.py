# Street view outside a window (back wall faces +Y): garden, fence, pavement, road, a row of houses, trees, a car.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

def build(sc, o, plain, box, quad, cyl, seed=5, x_span=(-16, 16)):
    rnd = random.Random(seed); ox, oy = o.x, o.y
    grass = plain("Grass", (0.16, 0.36, 0.1), 0.95); pave = plain("Pave", (0.55, 0.54, 0.52), 0.9)
    road = plain("Road", (0.12, 0.12, 0.13), 0.85); line = plain("RoadLine", (0.95, 0.9, 0.7), 0.6)
    quad("StGrass", [(ox - 32, oy + 0.15, -0.02), (ox + 34, oy + 0.15, -0.02), (ox + 34, oy + 6, -0.02), (ox - 32, oy + 6, -0.02)], grass)
    quad("StPave1", [(ox - 32, oy + 6, -0.01), (ox + 34, oy + 6, -0.01), (ox + 34, oy + 7.5, -0.01), (ox - 32, oy + 7.5, -0.01)], pave)
    quad("StRoad", [(ox - 32, oy + 7.5, -0.03), (ox + 34, oy + 7.5, -0.03), (ox + 34, oy + 14, -0.03), (ox - 32, oy + 14, -0.03)], road)
    for i in range(-12, 13):
        quad("StDash", [(ox + i * 2.5, oy + 10.68, -0.02), (ox + i * 2.5 + 1.2, oy + 10.68, -0.02), (ox + i * 2.5 + 1.2, oy + 10.82, -0.02), (ox + i * 2.5, oy + 10.82, -0.02)], line)
    quad("StPave2", [(ox - 32, oy + 14, -0.01), (ox + 34, oy + 14, -0.01), (ox + 34, oy + 15.5, -0.01), (ox - 32, oy + 15.5, -0.01)], pave)
    quad("StGrass2", [(ox - 32, oy + 15.5, -0.02), (ox + 34, oy + 15.5, -0.02), (ox + 34, oy + 40, -0.02), (ox - 32, oy + 40, -0.02)], grass)
    # white picket fence along the garden
    white = plain("Picket", (0.92, 0.92, 0.9), 0.6)
    for i in range(-45, 110):
        box("Picket", (ox + i * 0.18, oy + 5.6, 0.45), (0.07, 0.03, 0.9), white, 0)
    for z in (0.3, 0.75): box("Rail", (ox + 5.85, oy + 5.62, z), (27.9, 0.03, 0.06), white, 0)
    # houses across the road
    walls = [(0.62, 0.25, 0.18), (0.88, 0.82, 0.68), (0.55, 0.62, 0.7), (0.9, 0.78, 0.45), (0.75, 0.72, 0.68), (0.45, 0.2, 0.15)]
    roof_m = [plain("Roof%d" % i, c, 0.8) for i, c in enumerate([(0.25, 0.12, 0.1), (0.18, 0.18, 0.2), (0.35, 0.18, 0.12)])]
    glass = plain("HouseGlass", (0.05, 0.07, 0.1), 0.05, coat=1.0); glow = plain("HouseGlow", (1.0, 0.8, 0.5), 0.5, emit=2.0)
    trim = plain("HouseTrim", (0.95, 0.95, 0.92), 0.5)
    x = x_span[0]
    while x < x_span[1]:
        w = rnd.uniform(5.0, 7.5); h = rnd.uniform(3.6, 5.8); d = 6.0; cx = ox + x + w / 2; cy = oy + 17 + rnd.uniform(0, 1.5)
        wm = plain("HouseWall", walls[rnd.randrange(len(walls))], 0.85)
        box("House", (cx, cy + d / 2, h / 2), (w, d, h), wm, 0)
        # gable roof (triangular prism)
        bm = bmesh.new(); rh = rnd.uniform(1.4, 2.4)
        pts = [(-w / 2 - 0.3, -0.4, h), (w / 2 + 0.3, -0.4, h), (0, -0.4, h + rh), (-w / 2 - 0.3, d + 0.4, h), (w / 2 + 0.3, d + 0.4, h), (0, d + 0.4, h + rh)]
        vs = [bm.verts.new((cx + p[0], cy + p[1], p[2])) for p in pts]
        for f in ((0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)): bm.faces.new([vs[i] for i in f])
        me = bpy.data.meshes.new("Roof"); bm.to_mesh(me); bm.free()
        rf = bpy.data.objects.new("Roof", me); sc.collection.objects.link(rf); me.materials.append(roof_m[rnd.randrange(3)])
        # windows (2 floors) + door
        cols = max(2, int(w / 1.6))
        for fl in range(2 if h > 4.2 else 1):
            for c in range(cols):
                wx = cx - w / 2 + (c + 0.5) * w / cols; wz = 1.3 + fl * 2.0
                if fl == 0 and c == cols // 2: 
                    box("HDoor", (wx, cy - 0.02, 1.05), (0.95, 0.06, 2.1), plain("DoorPaint", [(0.6, 0.1, 0.1), (0.1, 0.25, 0.45), (0.15, 0.35, 0.2)][rnd.randrange(3)], 0.4), 0)
                    continue
                box("HWinFrame", (wx, cy - 0.02, wz), (1.0, 0.06, 1.2), trim, 0)
                box("HWin", (wx, cy - 0.05, wz), (0.86, 0.04, 1.06), glow if rnd.random() < 0.18 else glass, 0)
                box("HWinBar", (wx, cy - 0.075, wz), (0.05, 0.02, 1.06), trim, 0)
        if rnd.random() < 0.6: box("Chimney", (cx + w * 0.25, cy + 2, h + rh * 0.6), (0.5, 0.5, 1.4), plain("Brick", (0.45, 0.18, 0.12), 0.9), 0)
        x += w + rnd.uniform(1.5, 3.0)
    # trees (trunk + clumpy leaf blobs)
    leaf = [plain("Leaf%d" % i, c, 0.8) for i, c in enumerate([(0.1, 0.3, 0.07), (0.16, 0.36, 0.09), (0.08, 0.24, 0.06)])]
    bark = plain("Bark", (0.22, 0.15, 0.1), 0.9)
    for tx, ty in [(-8.5, 3.5), (9.5, 3.2), (-11, 15.2), (-2, 15.0), (8, 15.3), (13, 15.1), (4.5, 4.6)]:
        s_ = rnd.uniform(0.8, 1.25)
        cyl("Trunk", (ox + tx, oy + ty, 1.2 * s_), 0.13 * s_, 2.4 * s_, bark, 10)
        for k in range(5):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=rnd.uniform(0.8, 1.3) * s_,
                location=(ox + tx + rnd.uniform(-0.7, 0.7) * s_, oy + ty + rnd.uniform(-0.6, 0.6) * s_, (2.6 + rnd.uniform(0, 1.2)) * s_))
            b = bpy.context.active_object; b.name = "Leaves"; b.data.materials.append(leaf[rnd.randrange(3)])
            dm = b.modifiers.new("d", "DISPLACE"); tex = bpy.data.textures.new("lv", "CLOUDS"); tex.noise_scale = 0.35; dm.texture = tex; dm.strength = 0.35
            b.data.shade_smooth()
    # a parked car on the road
    carm = plain("CarPaint", (0.08, 0.25, 0.55), 0.2, coat=1.0)
    box("CarBody", (ox - 3.0, oy + 8.6, 0.55), (4.2, 1.8, 0.7), carm, 0.25)
    box("CarCabin", (ox - 3.2, oy + 8.6, 1.15), (2.3, 1.6, 0.6), plain("CarGlass", (0.05, 0.07, 0.1), 0.05, coat=1.0), 0.3)
    for wx in (-1.4, 1.4):
        for wy in (-0.85, 0.85):
            c = cyl("Wheel", (ox - 3.0 + wx, oy + 8.6 + wy, 0.33), 0.33, 0.25, plain("Tyre", (0.03, 0.03, 0.03), 0.8), 20)
            c.rotation_euler = (math.radians(90), 0, 0)
    # street lamp
    cyl("LampPost", (ox + 3.0, oy + 7.2, 2.0), 0.06, 4.0, plain("PostPaint", (0.1, 0.12, 0.1), 0.5), 12)
    box("LampHead", (ox + 3.0, oy + 7.6, 4.0), (0.25, 0.8, 0.12), plain("PostPaint2", (0.1, 0.12, 0.1), 0.5), 0.3)
