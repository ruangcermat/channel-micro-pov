#!/usr/bin/env python3
"""Stylized Low-Poly Procedural 3D Props Builder for Blender (bpy).

Creates high-contrast, properly proportioned Indonesian kosan kitchen props that do not
exist on public CC0 APIs (NO crude default cubes):
  1. build_kitchen_tile_floor      - 30x30cm beveled ceramic floor + Poly Haven PBR + walls + TL neon fixture
  2. build_indomie_bowl_spill      - Glossy oily yellow kuah puddle + curled wavy noodles + chili/scallion + tipped bowl
  3. build_sandal_jepit_swallow    - Ergonomic green-white Swallow flip-flop sole + curved V-strap & toe-post
  4. build_cockroach_antennae_rig  - Camera-parented segmented antennae + foldable translucent wings
  5. build_human_silhouette_giant  - 1.72m proportional low-poly human in t-shirt & shorts with rigged arm/foot/eyes
  6. build_fridge_under_gap        - Kosan 2-door fridge on 4 rubber feet with crisp 5.5cm dark under-gap
  7. build_wind_lines              - Glowing cyan bullet-time airflow ribbons (Scene 3)
  8. build_dust_puff               - Stylized low-poly impact dust clouds (Scene 4)
  9. build_speed_lines_rig         - Camera-parented action sprint speed streaks (Scene 4)

Can also be invoked directly via Blender CLI to export cached `.glb` files:
  blender --background --python 03_pipeline/scripts/procedural_props.py -- --export-glb 02_assets
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector


# =============================================================================
# MATERIAL & MESH HELPERS (Blender 3.6 / 4.2+ Safe)
# =============================================================================

def _set_bsdf(bsdf: Any, name: str, value: Any) -> None:
    """Safely assign a Principled BSDF socket across Blender 3.x and 4.x naming."""
    aliases = {
        "Coat Weight": ("Coat Weight", "Clearcoat"),
        "Coat Roughness": ("Coat Roughness", "Clearcoat Roughness"),
        "Transmission Weight": ("Transmission Weight", "Transmission"),
        "Specular IOR Level": ("Specular IOR Level", "Specular"),
        "Emission Color": ("Emission Color", "Emission"),
    }
    for cand in aliases.get(name, (name,)):
        if cand in bsdf.inputs:
            bsdf.inputs[cand].default_value = value
            return


def make_material(
    name: str,
    color: Tuple[float, float, float, float],
    roughness: float = 0.45,
    metallic: float = 0.0,
    coat: float = 0.0,
    emission_color: Optional[Tuple[float, float, float, float]] = None,
    emission_strength: float = 0.0,
    alpha: float = 1.0,
    transmission: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    _set_bsdf(bsdf, "Base Color", color)
    _set_bsdf(bsdf, "Roughness", roughness)
    _set_bsdf(bsdf, "Metallic", metallic)
    _set_bsdf(bsdf, "Coat Weight", coat)
    _set_bsdf(bsdf, "Transmission Weight", transmission)
    _set_bsdf(bsdf, "Alpha", alpha)
    if emission_color is not None and emission_strength > 0.0:
        _set_bsdf(bsdf, "Emission Color", emission_color)
        _set_bsdf(bsdf, "Emission Strength", emission_strength)

    if alpha < 1.0 and hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    return mat


def _link_obj(obj: bpy.types.Object, collection: Optional[bpy.types.Collection] = None) -> bpy.types.Object:
    col = collection or bpy.context.scene.collection
    if obj.name not in col.objects:
        col.objects.link(obj)
    return obj


def _make_empty(
    name: str,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    parent: Optional[bpy.types.Object] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> bpy.types.Object:
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.05
    empty.location = location
    _link_obj(empty, collection)
    if parent is not None:
        empty.parent = parent
    return empty


def _new_mesh_obj(
    name: str,
    bm: bmesh.types.BMesh,
    material: Optional[bpy.types.Material] = None,
    smooth: bool = True,
    parent: Optional[bpy.types.Object] = None,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    if material is not None:
        obj.data.materials.append(material)
    _link_obj(obj, collection)
    if parent is not None:
        obj.parent = parent
    return obj


def _make_beveled_box(
    name: str,
    size: Tuple[float, float, float],
    bevel: float = 0.008,
    material: Optional[bpy.types.Material] = None,
    parent: Optional[bpy.types.Object] = None,
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0.0:
        bmesh.ops.bevel(
            bm,
            geom=list(bm.edges),
            offset=min(bevel, min(size) * 0.3),
            segments=2,
            affect="EDGES",
            clamp_overlap=True,
        )
    return _new_mesh_obj(name, bm, material, True, parent, location, rotation, collection)


def _make_tube_curve(
    name: str,
    points: List[Tuple[float, float, float, float]],
    bevel_depth: float,
    material: bpy.types.Material,
    resolution: int = 10,
    bevel_res: int = 4,
    parent: Optional[bpy.types.Object] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> bpy.types.Object:
    """Build a smooth 3D curve tube where each point is (x, y, z, radius_scale)."""
    curve_data = bpy.data.curves.new(name=name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = resolution
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = bevel_res
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for idx, (x, y, z, rad) in enumerate(points):
        spline.points[idx].co = (x, y, z, 1.0)
        spline.points[idx].radius = rad

    # Convert to smooth NURBS-like feel via Bezier/Catmull smoothing by switching to NURBS
    nurbs_data = bpy.data.curves.new(name=name + "_nurbs", type="CURVE")
    nurbs_data.dimensions = "3D"
    nurbs_data.resolution_u = resolution
    nurbs_data.bevel_depth = bevel_depth
    nurbs_data.bevel_resolution = bevel_res
    nurbs_data.use_fill_caps = True
    n_spline = nurbs_data.splines.new("NURBS")
    n_spline.points.add(len(points) - 1)
    for idx, (x, y, z, rad) in enumerate(points):
        n_spline.points[idx].co = (x, y, z, 1.0)
        n_spline.points[idx].radius = rad
    n_spline.use_endpoint_u = True
    n_spline.order_u = min(4, len(points))

    bpy.data.curves.remove(curve_data)
    obj = bpy.data.objects.new(name, nurbs_data)
    obj.data.materials.append(material)
    _link_obj(obj, collection)
    if parent is not None:
        obj.parent = parent
    return obj


# =============================================================================
# 1. KITCHEN TILE FLOOR + KOSAN WALLS + OVERHEAD FLUORESCENT NEON FIXTURE
# =============================================================================

def _build_tile_pbr_material(assets_dir: Optional[Path]) -> bpy.types.Material:
    mat = bpy.data.materials.new("Mat_Kitchen_Tile_Floor")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (12.0, 12.0, 1.0)
    nt.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    diff_path = None
    rough_path = None
    nor_path = None
    if assets_dir is not None:
        tile_dir = assets_dir / "textures" / "interior_tiles"
        if tile_dir.exists():
            for p in tile_dir.iterdir():
                low = p.name.lower()
                if "diff" in low:
                    diff_path = p
                elif "rough" in low:
                    rough_path = p
                elif "nor_gl" in low:
                    nor_path = p

    if diff_path and diff_path.exists():
        img_diff = nt.nodes.new("ShaderNodeTexImage")
        img_diff.image = bpy.data.images.load(str(diff_path), check_existing=True)
        nt.links.new(mapping.outputs["Vector"], img_diff.inputs["Vector"])

        # Slight cool-white tint so Indonesian kitchen tiles look clean & bright under neon
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MIX"
        mix.inputs[0].default_value = 0.25
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = (0.88, 0.91, 0.93, 1.0)
        nt.links.new(img_diff.outputs["Color"], sock_a)
        nt.links.new(sock_out, bsdf.inputs["Base Color"])

        if rough_path and rough_path.exists():
            img_r = nt.nodes.new("ShaderNodeTexImage")
            img_r.image = bpy.data.images.load(str(rough_path), check_existing=True)
            img_r.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mapping.outputs["Vector"], img_r.inputs["Vector"])
            # Make ceramic glossy enough to reflect puddle & neon dramatically
            math_r = nt.nodes.new("ShaderNodeMath")
            math_r.operation = "MULTIPLY"
            math_r.inputs[1].default_value = 0.42
            nt.links.new(img_r.outputs["Color"], math_r.inputs[0])
            nt.links.new(math_r.outputs["Value"], bsdf.inputs["Roughness"])
        else:
            _set_bsdf(bsdf, "Roughness", 0.20)

        if nor_path and nor_path.exists():
            img_n = nt.nodes.new("ShaderNodeTexImage")
            img_n.image = bpy.data.images.load(str(nor_path), check_existing=True)
            img_n.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mapping.outputs["Vector"], img_n.inputs["Vector"])
            n_map = nt.nodes.new("ShaderNodeNormalMap")
            n_map.inputs["Strength"].default_value = 0.65
            nt.links.new(img_n.outputs["Color"], n_map.inputs["Color"])
            nt.links.new(n_map.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        # Crisp procedural 30x30cm ceramic tile brick shader fallback
        brick = nt.nodes.new("ShaderNodeTexBrick")
        brick.offset = 0.0
        brick.inputs["Scale"].default_value = 2.6
        brick.inputs["Mortar Size"].default_value = 0.025
        brick.inputs["Mortar Smooth"].default_value = 0.12
        brick.inputs["Color1"].default_value = (0.82, 0.84, 0.85, 1.0)
        brick.inputs["Color2"].default_value = (0.76, 0.79, 0.81, 1.0)
        brick.inputs["Mortar"].default_value = (0.20, 0.22, 0.24, 1.0)
        nt.links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
        nt.links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])

        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.35
        nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        _set_bsdf(bsdf, "Roughness", 0.18)

    _set_bsdf(bsdf, "Coat Weight", 0.35)
    _set_bsdf(bsdf, "Coat Roughness", 0.08)
    return mat


def build_kitchen_tile_floor(
    assets_dir: Optional[Path] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build 8m x 8m Indonesian kosan kitchen tile floor with real grout strips + walls + neon tube."""
    root = _make_empty("Kitchen_Environment_Root", (0.0, 0.0, 0.0), collection=collection)
    tile_mat = _build_tile_pbr_material(assets_dir)

    # Main floor mesh with UVs
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=24, y_segments=24, size=4.0)
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            co = loop.vert.co
            loop[uv_layer].uv = ((co.x + 4.0) / 8.0, (co.y + 4.0) / 8.0)
    floor = _new_mesh_obj("Kitchen_Tile_Floor", bm, tile_mat, False, root, (0.0, 1.8, 0.0), collection=collection)

    # Prominent physical grout guide lines every 0.30m near cockroach sprint lane (ultra-readable motion!)
    grout_mat = make_material("Mat_Tile_Grout", (0.14, 0.15, 0.17, 1.0), roughness=0.85)
    for gx in (-0.90, -0.60, -0.30, 0.0, 0.30, 0.60, 0.90):
        _make_beveled_box(
            f"Grout_Y_{gx:.2f}",
            (0.005, 6.0, 0.0012),
            bevel=0.0,
            material=grout_mat,
            parent=root,
            location=(gx, 1.8, 0.0005),
            collection=collection,
        )
    for gy in [round(-0.6 + 0.30 * i, 2) for i in range(17)]:
        _make_beveled_box(
            f"Grout_X_{gy:.2f}",
            (3.2, 0.005, 0.0012),
            bevel=0.0,
            material=grout_mat,
            parent=root,
            location=(0.0, gy, 0.0005),
            collection=collection,
        )

    # Kosan kitchen walls: Left wall (Scene 6 "kiri tembok"), Back wall behind fridge, Right wall
    wall_mat = make_material("Mat_Kosan_Wall", (0.78, 0.80, 0.76, 1.0), roughness=0.78)
    baseboard_mat = make_material("Mat_Wall_Baseboard", (0.36, 0.38, 0.40, 1.0), roughness=0.45)

    # Left wall at x = -0.85m (tight kosan kitchen corridor!)
    _make_beveled_box("Wall_Left", (0.12, 7.0, 2.8), 0.005, wall_mat, root, (-0.91, 1.8, 1.4), collection=collection)
    _make_beveled_box("Baseboard_Left", (0.02, 7.0, 0.10), 0.004, baseboard_mat, root, (-0.84, 1.8, 0.05), collection=collection)

    # Back wall behind fridge at y = 3.55m
    _make_beveled_box("Wall_Back", (4.0, 0.12, 2.8), 0.005, wall_mat, root, (0.6, 3.61, 1.4), collection=collection)
    _make_beveled_box("Baseboard_Back", (4.0, 0.02, 0.10), 0.004, baseboard_mat, root, (0.6, 3.54, 0.05), collection=collection)

    # Right wall at x = 1.65m
    _make_beveled_box("Wall_Right", (0.12, 7.0, 2.8), 0.005, wall_mat, root, (1.71, 1.8, 1.4), collection=collection)

    # Ceiling + Classic Indonesian TL Fluorescent Tube Fixture directly overhead
    ceil_mat = make_material("Mat_Ceiling", (0.84, 0.85, 0.86, 1.0), roughness=0.85)
    _make_beveled_box("Ceiling", (4.0, 7.0, 0.10), 0.0, ceil_mat, root, (0.4, 1.8, 2.75), collection=collection)

    fixture_mat = make_material("Mat_Neon_Fixture", (0.72, 0.74, 0.76, 1.0), roughness=0.35, metallic=0.6)
    _make_beveled_box("Neon_Housing", (0.09, 1.25, 0.045), 0.006, fixture_mat, root, (0.0, 1.55, 2.67), collection=collection)

    neon_tube_mat = make_material(
        "Mat_Neon_Tube_Glow",
        (0.95, 0.98, 1.0, 1.0),
        roughness=0.1,
        emission_color=(0.90, 0.96, 1.0, 1.0),
        emission_strength=0.1,  # Animated to 28.0 when switch clicks on!
    )
    bm_tube = bmesh.new()
    bmesh.ops.create_cone(bm_tube, cap_ends=True, cap_tris=False, segments=16, radius1=0.018, radius2=0.018, depth=1.18)
    neon_tube = _new_mesh_obj(
        "Neon_TL_Tube",
        bm_tube,
        neon_tube_mat,
        True,
        root,
        (0.0, 1.55, 2.62),
        (math.radians(90.0), 0.0, 0.0),
        collection=collection,
    )

    return {
        "root": root,
        "floor": floor,
        "neon_tube": neon_tube,
        "neon_mat": neon_tube_mat,
    }


# =============================================================================
# 2. INDOMIE BROTH SPILL & CURLED NOODLES (SCENE 1 FOREGROUND)
# =============================================================================

def build_indomie_bowl_spill(
    location: Tuple[float, float, float] = (0.0, 0.16, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build glossy yellow Indomie kuah puddle, wavy low-poly noodle strands, chili, scallion & bowl."""
    root = _make_empty("Indomie_Spill_Root", location, collection=collection)

    # Oily reflective golden-amber Indomie broth puddle (irregular organic disk)
    broth_mat = make_material(
        "Mat_Indomie_Kuah",
        (0.92, 0.56, 0.06, 1.0),
        roughness=0.04,
        coat=0.95,
        transmission=0.25,
        emission_color=(0.85, 0.52, 0.05, 1.0),
        emission_strength=0.08,
    )
    bm = bmesh.new()
    segs = 28
    center_v = bm.verts.new((0.0, 0.0, 0.0024))
    ring_verts = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / segs
        r = 0.088 * (1.0 + 0.18 * math.sin(3.0 * ang + 0.5) + 0.11 * math.cos(5.0 * ang - 0.3))
        ring_verts.append(bm.verts.new((r * math.cos(ang), r * math.sin(ang) * 0.86, 0.0016)))
    outer_verts = []
    for i in range(segs):
        ang = (2.0 * math.pi * i) / segs
        r = 0.095 * (1.0 + 0.18 * math.sin(3.0 * ang + 0.5) + 0.11 * math.cos(5.0 * ang - 0.3))
        outer_verts.append(bm.verts.new((r * math.cos(ang), r * math.sin(ang) * 0.86, 0.0004)))
    for i in range(segs):
        ni = (i + 1) % segs
        bm.faces.new((center_v, ring_verts[i], ring_verts[ni]))
        bm.faces.new((ring_verts[i], outer_verts[i], outer_verts[ni], ring_verts[ni]))
    puddle = _new_mesh_obj("Indomie_Kuah_Puddle", bm, broth_mat, True, root, collection=collection)

    # Curled wavy Indomie noodle strands (warm golden yellow, slightly glossy)
    noodle_mat = make_material("Mat_Indomie_Noodle", (0.98, 0.78, 0.24, 1.0), roughness=0.22, coat=0.65)
    noodle_specs = [
        ((-0.045, -0.025), (0.045, 0.018), 0.008, 3.0),
        ((-0.020, 0.032), (0.055, -0.015), 0.009, 2.5),
        ((-0.055, 0.012), (0.012, -0.040), 0.007, 3.2),
        ((0.005, -0.038), (0.062, 0.032), 0.008, 2.8),
        ((-0.032, -0.005), (0.035, 0.042), 0.010, 3.5),
        ((-0.068, -0.018), (-0.008, 0.026), 0.007, 2.7),
        ((0.022, 0.005), (0.072, -0.028), 0.006, 2.4),
        ((-0.015, -0.048), (0.040, -0.008), 0.009, 3.1),
    ]
    for idx, (p0, p1, amp, waves) in enumerate(noodle_specs):
        pts = []
        steps = 12
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = max(1e-5, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        for s in range(steps):
            u = s / (steps - 1)
            w = math.sin(u * waves * math.pi) * amp
            x = p0[0] + dx * u + nx * w
            y = p0[1] + dy * u + ny * w
            z = 0.0032 + 0.0022 * abs(math.cos(u * waves * math.pi)) + (0.0012 if idx % 2 == 0 else 0.0)
            pts.append((x, y, z, 1.0))
        _make_tube_curve(f"Indomie_Noodle_{idx:02d}", pts, 0.0024, noodle_mat, resolution=8, bevel_res=3, parent=root, collection=collection)

    # Red chili bits (serpihan cabai) & green scallion rings (daun bawang)
    chili_mat = make_material("Mat_Chili_Flake", (0.86, 0.09, 0.05, 1.0), roughness=0.25, coat=0.5)
    scallion_mat = make_material("Mat_Scallion", (0.12, 0.62, 0.14, 1.0), roughness=0.30, coat=0.4)
    for i, (cx, cy) in enumerate([(-0.025, 0.008), (0.018, -0.012), (0.040, 0.020), (-0.042, -0.022), (0.002, 0.032)]):
        _make_beveled_box(
            f"Chili_Bit_{i}",
            (0.007, 0.005, 0.0025),
            0.001,
            chili_mat,
            root,
            (cx, cy, 0.0035),
            (0.1 * i, 0.2, 0.8 * i),
            collection=collection,
        )
    for i, (sx, sy) in enumerate([(-0.010, -0.015), (0.032, 0.006), (-0.036, 0.025), (0.014, 0.018)]):
        bm_s = bmesh.new()
        bmesh.ops.create_cone(bm_s, cap_ends=True, segments=10, radius1=0.0045, radius2=0.0045, depth=0.0022)
        _new_mesh_obj(f"Scallion_{i}", bm_s, scallion_mat, True, root, (sx, sy, 0.0032), (0.15, 0.0, 0.5 * i), collection=collection)

    # Classic Indonesian rooster/plastic bowl tipped behind puddle (adds instant scale cue!)
    bowl_mat = make_material("Mat_Kosan_Bowl", (0.94, 0.94, 0.91, 1.0), roughness=0.18, coat=0.6)
    bm_b = bmesh.new()
    bmesh.ops.create_cone(bm_b, cap_ends=True, segments=18, radius1=0.048, radius2=0.078, depth=0.068)
    _new_mesh_obj(
        "Tipped_Noodle_Bowl",
        bm_b,
        bowl_mat,
        True,
        root,
        (-0.14, 0.13, 0.052),
        (math.radians(74.0), math.radians(-18.0), math.radians(-38.0)),
        collection=collection,
    )

    return {"root": root, "puddle": puddle}


# =============================================================================
# 3. SANDAL JEPIT SWALLOW HIJAU-PUTIH (ICONIC INDONESIAN FLIP-FLOP)
# =============================================================================

def build_sandal_jepit_swallow(
    location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build iconic Indonesian green-white flip-flop (~0.27m long) with contoured sole & V-strap."""
    root = _make_empty("Sandal_Jepit_Root", location, collection=collection)

    white_rubber = make_material("Mat_Sandal_White", (0.95, 0.96, 0.94, 1.0), roughness=0.52)
    swallow_green = make_material("Mat_Sandal_Green", (0.05, 0.68, 0.24, 1.0), roughness=0.45)
    dark_green = make_material("Mat_Sandal_DarkGreen", (0.02, 0.42, 0.14, 1.0), roughness=0.50)

    # Ergonomic flip-flop silhouette (Y from -0.135 heel to +0.135 toe, X width ~0.105)
    footprint_xy = [
        (0.000, -0.135),
        (0.026, -0.130),
        (0.039, -0.105),
        (0.041, -0.055),
        (0.044, 0.005),
        (0.052, 0.062),
        (0.050, 0.106),
        (0.032, 0.132),
        (0.002, 0.137),
        (-0.028, 0.126),
        (-0.048, 0.095),
        (-0.051, 0.052),
        (-0.042, -0.005),
        (-0.037, -0.065),
        (-0.035, -0.110),
        (-0.022, -0.131),
    ]

    def _extrude_sole_layer(name: str, z_bot: float, z_top: float, mat: bpy.types.Material, scale_xy: float = 1.0):
        bm = bmesh.new()
        bot_v = [bm.verts.new((x * scale_xy, y * scale_xy, z_bot)) for x, y in footprint_xy]
        top_v = [bm.verts.new((x * scale_xy, y * scale_xy, z_top)) for x, y in footprint_xy]
        n = len(footprint_xy)
        bm.faces.new(list(reversed(bot_v)))
        bm.faces.new(top_v)
        for i in range(n):
            ni = (i + 1) % n
            bm.faces.new((bot_v[i], bot_v[ni], top_v[ni], top_v[i]))
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0022, segments=2, affect="EDGES", clamp_overlap=True)
        return _new_mesh_obj(name, bm, mat, True, root, collection=collection)

    # Green bottom rubber tread layer (0.0 -> 0.007m) + White top EVA foam layer (0.007 -> 0.017m)
    sole_green = _extrude_sole_layer("Sandal_Sole_GreenBottom", 0.0, 0.0075, swallow_green, 1.0)
    sole_white = _extrude_sole_layer("Sandal_Sole_WhiteTop", 0.0072, 0.0170, white_rubber, 0.995)

    # Iconic Swallow green oval heel badge on white footbed
    bm_badge = bmesh.new()
    bmesh.ops.create_cone(bm_badge, cap_ends=True, segments=16, radius1=0.022, radius2=0.022, depth=0.0015)
    bmesh.ops.scale(bm_badge, vec=Vector((0.82, 1.35, 1.0)), verts=bm_badge.verts)
    _new_mesh_obj("Sandal_Heel_Badge", bm_badge, swallow_green, True, root, (0.0, -0.072, 0.0176), collection=collection)

    # Iconic Green V-Strap (left wing + right wing meeting at toe-post)
    strap_left_pts = [
        (-0.044, -0.012, 0.014, 1.0),
        (-0.040, 0.015, 0.036, 1.1),
        (-0.024, 0.052, 0.048, 1.05),
        (-0.004, 0.084, 0.042, 0.95),
        (0.002, 0.090, 0.016, 0.85),
    ]
    strap_right_pts = [
        (0.046, -0.008, 0.014, 1.0),
        (0.042, 0.018, 0.036, 1.1),
        (0.026, 0.054, 0.048, 1.05),
        (0.007, 0.084, 0.042, 0.95),
        (0.002, 0.090, 0.016, 0.85),
    ]
    _make_tube_curve("Sandal_Strap_Left", strap_left_pts, 0.0072, swallow_green, resolution=12, bevel_res=5, parent=root, collection=collection)
    _make_tube_curve("Sandal_Strap_Right", strap_right_pts, 0.0072, swallow_green, resolution=12, bevel_res=5, parent=root, collection=collection)

    # Central toe-post collar accent
    bm_post = bmesh.new()
    bmesh.ops.create_cone(bm_post, cap_ends=True, segments=12, radius1=0.006, radius2=0.0075, depth=0.028)
    _new_mesh_obj("Sandal_Toe_Post", bm_post, dark_green, True, root, (0.002, 0.090, 0.028), collection=collection)

    return {"root": root, "sole_green": sole_green, "sole_white": sole_white}


# =============================================================================
# 4. FOREGROUND COCKROACH ANTENNAE & WINGS RIG (PARENTED TO POV CAMERA)
# =============================================================================

def build_cockroach_antennae_rig(
    camera_obj: Optional[bpy.types.Object] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build two expressive curved antennae + two foldable translucent wings in camera local space.

    Blender camera local axes: +X right, +Y up, -Z forward.
    """
    rig_root = _make_empty("Cockroach_POV_Rig", (0.0, 0.0, 0.0), parent=camera_obj, collection=collection)

    chitin_mat = make_material(
        "Mat_Cockroach_Antenna",
        (0.14, 0.045, 0.015, 1.0),
        roughness=0.22,
        coat=0.80,
    )
    wing_mat = make_material(
        "Mat_Cockroach_Wing",
        (0.36, 0.16, 0.04, 1.0),
        roughness=0.28,
        coat=0.65,
        alpha=0.58,
        transmission=0.25,
    )

    ant_l_pivot = _make_empty("Ant_Left_Pivot", (-0.032, -0.046, -0.044), parent=rig_root, collection=collection)
    ant_r_pivot = _make_empty("Ant_Right_Pivot", (0.032, -0.046, -0.044), parent=rig_root, collection=collection)

    # Graceful tapered whip-like curved antennae emerging from bottom-left & bottom-right corners
    left_pts = [
        (0.000, 0.000, 0.000, 1.15),
        (-0.004, 0.011, -0.018, 0.90),
        (-0.009, 0.022, -0.040, 0.68),
        (-0.011, 0.029, -0.066, 0.45),
        (-0.006, 0.030, -0.092, 0.25),
        (0.002, 0.025, -0.114, 0.10),
    ]
    right_pts = [(-x, y, z, r) for (x, y, z, r) in left_pts]

    _make_tube_curve("Cockroach_Antenna_L", left_pts, 0.0014, chitin_mat, resolution=12, bevel_res=4, parent=ant_l_pivot, collection=collection)
    _make_tube_curve("Cockroach_Antenna_R", right_pts, 0.0014, chitin_mat, resolution=12, bevel_res=4, parent=ant_r_pivot, collection=collection)

    # Translucent brownish wings at frame edges (hidden until Scene 7 emergency flight!)
    wing_l_pivot = _make_empty("Wing_Left_Pivot", (-0.028, 0.006, -0.055), parent=rig_root, collection=collection)
    wing_r_pivot = _make_empty("Wing_Right_Pivot", (0.028, 0.006, -0.055), parent=rig_root, collection=collection)

    def _build_wing_mesh(name: str, side: float, parent: bpy.types.Object) -> bpy.types.Object:
        bm = bmesh.new()
        pts = [
            (0.0, 0.0, 0.0),
            (side * 0.018, 0.024, -0.018),
            (side * 0.038, 0.034, -0.046),
            (side * 0.046, 0.018, -0.072),
            (side * 0.028, -0.008, -0.056),
            (side * 0.010, -0.012, -0.022),
        ]
        verts = [bm.verts.new(p) for p in pts]
        bm.faces.new(verts if side > 0 else list(reversed(verts)))
        # Add subtle thickness so Cycles renders translucent chitin cleanly
        res = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
        ext_verts = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=ext_verts, vec=Vector((0.0, 0.0008, 0.0)))
        return _new_mesh_obj(name, bm, wing_mat, True, parent, collection=collection)

    wing_l = _build_wing_mesh("Cockroach_Wing_L", -1.0, wing_l_pivot)
    wing_r = _build_wing_mesh("Cockroach_Wing_R", 1.0, wing_r_pivot)

    return {
        "root": rig_root,
        "ant_l": ant_l_pivot,
        "ant_r": ant_r_pivot,
        "wing_l_pivot": wing_l_pivot,
        "wing_r_pivot": wing_r_pivot,
        "wing_l": wing_l,
        "wing_r": wing_r,
    }


# =============================================================================
# 5. HUMAN SILHOUETTE GIANT (1.72m INDONESIAN KOSAN GUY — RIGGED PARTS)
# =============================================================================

def build_human_silhouette_giant(
    location: Tuple[float, float, float] = (0.0, 1.35, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build proportional stylized low-poly human in t-shirt & shorts facing -Y toward cockroach."""
    root = _make_empty("Human_Giant_Root", location, collection=collection)

    skin_mat = make_material("Mat_Human_Skin", (0.64, 0.42, 0.28, 1.0), roughness=0.58)
    shirt_mat = make_material("Mat_Human_KausOblong", (0.11, 0.14, 0.20, 1.0), roughness=0.82)
    shorts_mat = make_material("Mat_Human_Shorts", (0.18, 0.19, 0.22, 1.0), roughness=0.85)
    hair_mat = make_material("Mat_Human_Hair", (0.04, 0.04, 0.05, 1.0), roughness=0.72)
    eye_white = make_material("Mat_Eye_White", (0.96, 0.96, 0.96, 1.0), roughness=0.15)
    eye_pupil = make_material("Mat_Eye_Pupil", (0.02, 0.02, 0.02, 1.0), roughness=0.10)

    def _limb(name: str, r_bot: float, r_top: float, length: float, mat: bpy.types.Material, parent: bpy.types.Object, loc: Tuple[float, float, float], rot=(0.0, 0.0, 0.0)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r_bot, radius2=r_top, depth=length)
        return _new_mesh_obj(name, bm, mat, True, parent, loc, rot, collection=collection)

    def _foot(name: str, parent: bpy.types.Object, loc: Tuple[float, float, float]):
        # Stylized bare human foot facing -Y
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((0.095, 0.245, 0.068)), verts=bm.verts)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.022, segments=2, affect="EDGES", clamp_overlap=True)
        return _new_mesh_obj(name, bm, skin_mat, True, parent, loc, collection=collection)

    # --- RIGHT LEG (fixed stance, facing -Y so character's right is -X) ---
    r_leg_root = _make_empty("Human_RightLeg_Pivot", (-0.12, 0.0, 0.0), parent=root, collection=collection)
    _foot("Human_Right_Foot", r_leg_root, (0.0, -0.045, 0.034))
    _limb("Human_Right_Calf", 0.044, 0.062, 0.43, skin_mat, r_leg_root, (0.0, 0.0, 0.26))
    _limb("Human_Right_ShortLeg", 0.088, 0.102, 0.36, shorts_mat, r_leg_root, (0.0, 0.0, 0.64))

    # --- LEFT LEG (independently movable to stomp in front of fridge gap in Scene 5-6!) ---
    l_leg_root = _make_empty("Human_LeftLeg_Pivot", (0.12, 0.0, 0.0), parent=root, collection=collection)
    _foot("Human_Left_Foot", l_leg_root, (0.0, -0.045, 0.034))
    _limb("Human_Left_Calf", 0.044, 0.062, 0.43, skin_mat, l_leg_root, (0.0, 0.0, 0.26))
    _limb("Human_Left_ShortLeg", 0.088, 0.102, 0.36, shorts_mat, l_leg_root, (0.0, 0.0, 0.64))

    # --- PELVIS & KAUS OBLONG TORSO ---
    _make_beveled_box("Human_Pelvis", (0.34, 0.21, 0.18), 0.05, shorts_mat, root, (0.0, 0.0, 0.84), collection=collection)
    _make_beveled_box("Human_Torso_Kaus", (0.43, 0.24, 0.54), 0.065, shirt_mat, root, (0.0, 0.0, 1.18), collection=collection)

    # Left arm (relaxed at side, +X)
    l_arm_pivot = _make_empty("Human_LeftArm_Pivot", (0.26, 0.0, 1.38), parent=root, collection=collection)
    _limb("Human_Left_Sleeve", 0.072, 0.080, 0.22, shirt_mat, l_arm_pivot, (0.03, 0.0, -0.10), (0.0, math.radians(-12.0), 0.0))
    _limb("Human_Left_Forearm", 0.042, 0.054, 0.44, skin_mat, l_arm_pivot, (0.07, -0.04, -0.38), (math.radians(-12.0), math.radians(-8.0), 0.0))

    # Right arm (SANDAL-WIELDING ARM at -X, fully keyframeable shoulder pivot!)
    r_arm_pivot = _make_empty("Human_RightArm_Pivot", (-0.26, 0.0, 1.38), parent=root, collection=collection)
    _limb("Human_Right_Sleeve", 0.072, 0.080, 0.22, shirt_mat, r_arm_pivot, (-0.02, -0.02, -0.08), (0.0, math.radians(15.0), 0.0))
    _limb("Human_Right_UpperArm", 0.048, 0.058, 0.30, skin_mat, r_arm_pivot, (-0.04, -0.04, -0.24), (math.radians(-20.0), 0.0, 0.0))
    _limb("Human_Right_Forearm", 0.038, 0.048, 0.30, skin_mat, r_arm_pivot, (-0.04, -0.15, -0.45), (math.radians(-42.0), 0.0, 0.0))
    bm_hand = bmesh.new()
    bmesh.ops.create_icosphere(bm_hand, subdivisions=2, radius=0.048)
    _new_mesh_obj("Human_Right_Hand", bm_hand, skin_mat, True, r_arm_pivot, (-0.04, -0.26, -0.58), collection=collection)

    # Attachment empty right inside the gripping right hand for Sandal Jepit!
    sandal_hand_socket = _make_empty("Human_Sandal_Socket", (-0.04, -0.29, -0.60), parent=r_arm_pivot, collection=collection)

    # --- NECK, HEAD & EXPRESSIVE FACE (FACING -Y) ---
    head_pivot = _make_empty("Human_Head_Pivot", (0.0, 0.0, 1.48), parent=root, collection=collection)
    _limb("Human_Neck", 0.058, 0.055, 0.11, skin_mat, head_pivot, (0.0, 0.0, 0.04))

    bm_head = bmesh.new()
    bmesh.ops.create_icosphere(bm_head, subdivisions=3, radius=0.118)
    bmesh.ops.scale(bm_head, vec=Vector((0.88, 0.96, 1.12)), verts=bm_head.verts)
    _new_mesh_obj("Human_Head", bm_head, skin_mat, True, head_pivot, (0.0, -0.01, 0.18), collection=collection)

    # Messy dark Indonesian kosan hair cap
    bm_hair = bmesh.new()
    bmesh.ops.create_icosphere(bm_hair, subdivisions=2, radius=0.125)
    bmesh.ops.scale(bm_hair, vec=Vector((0.92, 1.00, 0.88)), verts=bm_hair.verts)
    _new_mesh_obj("Human_Hair", bm_hair, hair_mat, True, head_pivot, (0.0, 0.01, 0.23), collection=collection)

    # Expressive wide eyes (keyframe scale in Scene 8 for shocked "melotot!" reaction!)
    eyes = {}
    for side_name, sx in (("L", 0.040), ("R", -0.040)):
        eye_p = _make_empty(f"Human_Eye_{side_name}_Pivot", (sx, -0.102, 0.195), parent=head_pivot, collection=collection)
        bm_ew = bmesh.new()
        bmesh.ops.create_icosphere(bm_ew, subdivisions=2, radius=0.020)
        bmesh.ops.scale(bm_ew, vec=Vector((1.0, 0.55, 1.0)), verts=bm_ew.verts)
        _new_mesh_obj(f"Human_EyeWhite_{side_name}", bm_ew, eye_white, True, eye_p, collection=collection)

        bm_ep = bmesh.new()
        bmesh.ops.create_icosphere(bm_ep, subdivisions=2, radius=0.009)
        _new_mesh_obj(f"Human_EyePupil_{side_name}", bm_ep, eye_pupil, True, eye_p, (0.0, -0.010, 0.0), collection=collection)
        eyes[side_name] = eye_p

    # Expressive shocked mouth (starts narrow, opens wide in Scene 8!)
    mouth_mat = make_material("Mat_Human_Mouth", (0.14, 0.03, 0.03, 1.0), roughness=0.7)
    bm_m = bmesh.new()
    bmesh.ops.create_icosphere(bm_m, subdivisions=2, radius=0.022)
    bmesh.ops.scale(bm_m, vec=Vector((1.3, 0.45, 0.35)), verts=bm_m.verts)
    mouth_obj = _new_mesh_obj("Human_Mouth", bm_m, mouth_mat, True, head_pivot, (0.0, -0.105, 0.125), collection=collection)

    return {
        "root": root,
        "left_leg": l_leg_root,
        "right_leg": r_leg_root,
        "right_arm": r_arm_pivot,
        "left_arm": l_arm_pivot,
        "sandal_socket": sandal_hand_socket,
        "head": head_pivot,
        "eye_l": eyes["L"],
        "eye_r": eyes["R"],
        "mouth": mouth_obj,
    }


# =============================================================================
# 6. FRIDGE WITH CRISP 5.5cm DARK UNDER-GAP (KOLONG KULKAS)
# =============================================================================

def build_fridge_under_gap(
    location: Tuple[float, float, float] = (-0.18, 2.95, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build stylized Indonesian kosan 2-door fridge raised 5.5cm off the floor on 4 rubber feet."""
    root = _make_empty("Fridge_UnderGap_Root", location, collection=collection)

    body_mat = make_material("Mat_Fridge_Body", (0.82, 0.86, 0.90, 1.0), roughness=0.26, metallic=0.18, coat=0.5)
    chrome_mat = make_material("Mat_Fridge_Chrome", (0.85, 0.87, 0.90, 1.0), roughness=0.15, metallic=0.92)
    rubber_mat = make_material("Mat_Fridge_RubberFoot", (0.05, 0.05, 0.06, 1.0), roughness=0.78)
    void_mat = make_material("Mat_UnderGap_ShadowVoid", (0.008, 0.009, 0.012, 1.0), roughness=0.98)

    gap_h = 0.055  # 5.5 cm dark refuge gap for 1.5cm cockroach!
    # 4 rubber leveling feet
    for fx in (-0.25, 0.25):
        for fy in (-0.25, 0.25):
            bm_f = bmesh.new()
            bmesh.ops.create_cone(bm_f, cap_ends=True, segments=12, radius1=0.028, radius2=0.022, depth=gap_h)
            _new_mesh_obj(f"Fridge_Foot_{fx:+.2f}_{fy:+.2f}", bm_f, rubber_mat, True, root, (fx, fy, gap_h * 0.5), collection=collection)

    # Main fridge chassis sitting cleanly at z = gap_h (0.055m -> 1.485m)
    _make_beveled_box("Fridge_Chassis", (0.60, 0.60, 1.43), 0.018, body_mat, root, (0.0, 0.0, gap_h + 0.715), collection=collection)

    # Lower main door + upper freezer door facing -Y
    _make_beveled_box("Fridge_Door_Lower", (0.58, 0.045, 0.90), 0.012, body_mat, root, (0.0, -0.315, gap_h + 0.46), collection=collection)
    _make_beveled_box("Fridge_Door_Upper", (0.58, 0.045, 0.47), 0.012, body_mat, root, (0.0, -0.315, gap_h + 1.175), collection=collection)

    # Vertical chrome handles
    _make_beveled_box("Fridge_Handle_Lower", (0.022, 0.032, 0.22), 0.006, chrome_mat, root, (0.24, -0.352, gap_h + 0.76), collection=collection)
    _make_beveled_box("Fridge_Handle_Upper", (0.022, 0.032, 0.14), 0.006, chrome_mat, root, (0.24, -0.352, gap_h + 1.03), collection=collection)

    # Deep black shadow recess tucked inside under-gap so the "safe dark tunnel" reads instantly
    _make_beveled_box("Fridge_UnderGap_Void", (0.48, 0.42, gap_h * 0.94), 0.0, void_mat, root, (0.0, 0.06, gap_h * 0.48), collection=collection)

    return {"root": root}


# =============================================================================
# 7, 8, 9. VFX PROPS: CYAN WIND WAVES (SC3), DUST PUFF (SC4), SPEED LINES (SC4)
# =============================================================================

def build_wind_lines(
    location: Tuple[float, float, float] = (0.0, 0.55, 0.12),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Glowing cyan airflow wave ribbons streaking from swinging sandal toward cockroach (Scene 3)."""
    root = _make_empty("Wind_Lines_Root", location, collection=collection)
    cyan_mat = make_material(
        "Mat_Cyan_WindGlow",
        (0.05, 0.92, 1.0, 1.0),
        roughness=0.1,
        emission_color=(0.05, 0.92, 1.0, 1.0),
        emission_strength=14.0,
        alpha=0.82,
    )
    ribbons = []
    offsets = [
        (-0.18, 0.14),
        (-0.08, 0.22),
        (0.00, 0.17),
        (0.09, 0.24),
        (0.18, 0.13),
        (-0.12, 0.06),
        (0.12, 0.07),
    ]
    for idx, (ox, oz) in enumerate(offsets):
        pts = [
            (ox * 1.4, 0.42, oz + 0.18, 0.35),
            (ox * 1.1, 0.18, oz + 0.07, 1.0),
            (ox * 0.8, -0.08, oz - 0.02, 1.15),
            (ox * 0.5, -0.32, oz - 0.08, 0.25),
        ]
        r_obj = _make_tube_curve(f"Wind_Ribbon_{idx:02d}", pts, 0.0045, cyan_mat, resolution=10, bevel_res=3, parent=root, collection=collection)
        ribbons.append(r_obj)
    return {"root": root, "ribbons": ribbons}


def build_dust_puff(
    location: Tuple[float, float, float] = (0.0, 0.35, 0.02),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Stylized low-poly dust cloud ring that bursts outward when sandal slams floor (Scene 4)."""
    root = _make_empty("Dust_Puff_Root", location, collection=collection)
    dust_mat = make_material("Mat_Dust_Puff", (0.88, 0.85, 0.78, 1.0), roughness=0.92, alpha=0.88)
    puffs = []
    for i in range(10):
        ang = (2.0 * math.pi * i) / 10.0
        r = 0.09 + 0.03 * (i % 2)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.038 + 0.012 * (i % 3))
        p_obj = _new_mesh_obj(
            f"Dust_Cloud_{i:02d}",
            bm,
            dust_mat,
            False,
            root,
            (r * math.cos(ang), r * math.sin(ang), 0.025 + 0.015 * (i % 2)),
            collection=collection,
        )
        puffs.append(p_obj)
    return {"root": root, "puffs": puffs}


def build_speed_lines_rig(
    camera_obj: Optional[bpy.types.Object] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Subtle radial action speed-lines around screen edges for 300 km/h sprint (Scene 4)."""
    root = _make_empty("Speed_Lines_Root", (0.0, 0.0, 0.0), parent=camera_obj, collection=collection)
    line_mat = make_material(
        "Mat_Speed_Lines",
        (1.0, 1.0, 1.0, 1.0),
        roughness=0.1,
        emission_color=(0.88, 0.96, 1.0, 1.0),
        emission_strength=6.0,
        alpha=0.65,
    )
    for i in range(14):
        ang = (2.0 * math.pi * i) / 14.0
        rx = 0.072 * math.cos(ang)
        ry = 0.115 * math.sin(ang)
        pts = [
            (rx * 1.15, ry * 1.15, -0.09, 0.2),
            (rx * 0.92, ry * 0.92, -0.18, 0.8),
            (rx * 0.78, ry * 0.78, -0.26, 0.1),
        ]
        _make_tube_curve(f"Speed_Line_{i:02d}", pts, 0.0009, line_mat, resolution=4, bevel_res=2, parent=root, collection=collection)
    return {"root": root}


# =============================================================================
# OPTIONAL CLI EXPORT TO .GLB CACHE
# =============================================================================

def export_all_procedural_glbs(assets_dir: Path) -> None:
    """Export standalone procedural Indonesian props as reusable cached .glb files."""
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from pipeline_utils import log, upsert_catalog_entry

    models_dir = assets_dir / "models_3d"
    models_dir.mkdir(parents=True, exist_ok=True)

    builders = [
        ("indomie_bowl_spill", "prop", lambda: build_indomie_bowl_spill((0.0, 0.0, 0.0))),
        ("sandal_jepit_swallow", "prop", lambda: build_sandal_jepit_swallow((0.0, 0.0, 0.0))),
        ("fridge_under_gap", "environment", lambda: build_fridge_under_gap((0.0, 0.0, 0.0))),
        ("human_silhouette_giant", "character_prop", lambda: build_human_silhouette_giant((0.0, 0.0, 0.0))),
        ("cockroach_antennae_rig", "pov_foreground", lambda: build_cockroach_antennae_rig(None)),
    ]

    for asset_id, category, fn in builders:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        fn()
        out_glb = models_dir / f"{asset_id}.glb"
        bpy.ops.export_scene.gltf(filepath=str(out_glb), export_format="GLB")
        upsert_catalog_entry(
            assets_dir,
            "models_3d",
            {
                "id": asset_id,
                "category": category,
                "source": "procedural_blender",
                "license": "CC0",
                "file": f"02_assets/models_3d/{asset_id}.glb",
                "cached": True,
            },
        )
        log("PROPS", f"Exported procedural GLB -> {out_glb}")


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        extra = argv[argv.index("--") + 1 :]
        if "--export-glb" in extra:
            idx = extra.index("--export-glb")
            target = Path(extra[idx + 1]).resolve()
            export_all_procedural_glbs(target)
