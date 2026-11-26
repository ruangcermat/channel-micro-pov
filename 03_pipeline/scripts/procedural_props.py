#!/usr/bin/env python3
"""Stylized Indonesian Procedural 3D Props & Micro-POV Rig Builder for Blender (bpy).

Creates properly proportioned Indonesian kosan kitchen props that do not exist on public CC0 APIs
(real human character is handled by MPFB2 via `mpfb_human.py`, never procedural blocks):
  1. build_kitchen_tile_floor      - 30x30cm beveled ceramic floor + Poly Haven PBR tile & plaster walls + TL neon
  2. build_indomie_bowl_spill      - Glossy oily yellow kuah puddle + curled wavy noodles + chili/scallion + tipped bowl
  3. build_sandal_jepit_swallow    - Ergonomic green-white Swallow flip-flop sole + curved V-strap & toe-post
  4. build_cockroach_antennae_rig  - Camera-parented segmented antennae + translucent amber-brown veined wings
  5. build_fridge_under_gap        - Kosan 2-door fridge on 4 rubber feet with crisp 5.5cm dark under-gap
  6. build_wind_lines              - Subtle translucent cyan bullet-time airflow ribbons (Scene 3)
  7. build_dust_puff               - Stylized impact dust cloud burst (Scene 4)
  8. build_speed_lines_rig         - Subtle thin semi-transparent edge speed streaks (Scene 4 & 8)

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

        # Warm kosan ceramic tile tint (albedo ~0.58 max so neon highlights never blow out)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 0.65
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = (0.62, 0.60, 0.56, 1.0)
        nt.links.new(img_diff.outputs["Color"], sock_a)
        nt.links.new(sock_out, bsdf.inputs["Base Color"])

        if rough_path and rough_path.exists():
            img_r = nt.nodes.new("ShaderNodeTexImage")
            img_r.image = bpy.data.images.load(str(rough_path), check_existing=True)
            img_r.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mapping.outputs["Vector"], img_r.inputs["Vector"])
            # Varied ceramic roughness (~0.24 - 0.38) for controlled reflections
            math_r = nt.nodes.new("ShaderNodeMath")
            math_r.operation = "MULTIPLY"
            math_r.inputs[1].default_value = 0.52
            nt.links.new(img_r.outputs["Color"], math_r.inputs[0])
            nt.links.new(math_r.outputs["Value"], bsdf.inputs["Roughness"])
        else:
            _set_bsdf(bsdf, "Roughness", 0.28)

        if nor_path and nor_path.exists():
            img_n = nt.nodes.new("ShaderNodeTexImage")
            img_n.image = bpy.data.images.load(str(nor_path), check_existing=True)
            img_n.image.colorspace_settings.name = "Non-Color"
            nt.links.new(mapping.outputs["Vector"], img_n.inputs["Vector"])
            n_map = nt.nodes.new("ShaderNodeNormalMap")
            n_map.inputs["Strength"].default_value = 0.55
            nt.links.new(img_n.outputs["Color"], n_map.inputs["Color"])
            nt.links.new(n_map.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        # Warm kosan cream/gray 30x30cm ceramic tile shader fallback (albedo <= 0.60)
        brick = nt.nodes.new("ShaderNodeTexBrick")
        brick.offset = 0.0
        brick.inputs["Scale"].default_value = 2.6
        brick.inputs["Mortar Size"].default_value = 0.015
        brick.inputs["Mortar Smooth"].default_value = 0.15
        brick.inputs["Color1"].default_value = (0.58, 0.56, 0.52, 1.0)
        brick.inputs["Color2"].default_value = (0.53, 0.51, 0.47, 1.0)
        brick.inputs["Mortar"].default_value = (0.20, 0.19, 0.18, 1.0)
        nt.links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
        nt.links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])

        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.30
        nt.links.new(brick.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        _set_bsdf(bsdf, "Roughness", 0.26)

    _set_bsdf(bsdf, "Coat Weight", 0.22)
    _set_bsdf(bsdf, "Coat Roughness", 0.12)
    return mat


def _build_wall_pbr_material(assets_dir: Optional[Path]) -> bpy.types.Material:
    """Build muted warm Indonesian kosan plaster wall shader (albedo <= 0.56, no white blowout)."""
    mat = bpy.data.materials.new("Mat_Kosan_Wall")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    diff_path = None
    rough_path = None
    nor_path = None
    if assets_dir is not None:
        wall_dir = assets_dir / "textures" / "painted_plaster_wall"
        if wall_dir.exists():
            for p in wall_dir.iterdir():
                low = p.name.lower()
                if "diff" in low:
                    diff_path = p
                elif "rough" in low:
                    rough_path = p
                elif "nor_gl" in low:
                    nor_path = p

    if diff_path and diff_path.exists():
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.6, 1.6, 1.6)
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

        img_d = nt.nodes.new("ShaderNodeTexImage")
        img_d.image = bpy.data.images.load(str(diff_path), check_existing=True)
        img_d.projection = "BOX"
        img_d.projection_blend = 0.2
        nt.links.new(mp.outputs["Vector"], img_d.inputs["Vector"])

        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        sock_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
        sock_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
        sock_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
        sock_b.default_value = (0.56, 0.53, 0.47, 1.0)
        nt.links.new(img_d.outputs["Color"], sock_a)
        nt.links.new(sock_out, bsdf.inputs["Base Color"])

        if rough_path and rough_path.exists():
            img_r = nt.nodes.new("ShaderNodeTexImage")
            img_r.image = bpy.data.images.load(str(rough_path), check_existing=True)
            img_r.image.colorspace_settings.name = "Non-Color"
            img_r.projection = "BOX"
            nt.links.new(mp.outputs["Vector"], img_r.inputs["Vector"])
            nt.links.new(img_r.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            _set_bsdf(bsdf, "Roughness", 0.85)

        if nor_path and nor_path.exists():
            img_n = nt.nodes.new("ShaderNodeTexImage")
            img_n.image = bpy.data.images.load(str(nor_path), check_existing=True)
            img_n.image.colorspace_settings.name = "Non-Color"
            img_n.projection = "BOX"
            nt.links.new(mp.outputs["Vector"], img_n.inputs["Vector"])
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.inputs["Strength"].default_value = 0.35
            nt.links.new(img_n.outputs["Color"], nmap.inputs["Color"])
            nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        _set_bsdf(bsdf, "Base Color", (0.54, 0.52, 0.47, 1.0))
        _set_bsdf(bsdf, "Roughness", 0.85)
    return mat


def build_kitchen_tile_floor(
    assets_dir: Optional[Path] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build 8m x 8m Indonesian kosan kitchen tile floor with subtle grout strips + walls + neon tube."""
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

    # Thin natural ceramic grout lines every 0.30m (readable motion without distracting thick bars)
    grout_mat = make_material("Mat_Tile_Grout", (0.19, 0.18, 0.17, 1.0), roughness=0.88)
    for gx in (-0.90, -0.60, -0.30, 0.0, 0.30, 0.60, 0.90):
        _make_beveled_box(
            f"Grout_Y_{gx:.2f}",
            (0.0024, 6.0, 0.0008),
            bevel=0.0,
            material=grout_mat,
            parent=root,
            location=(gx, 1.8, 0.0003),
            collection=collection,
        )
    for gy in [round(-0.6 + 0.30 * i, 2) for i in range(17)]:
        _make_beveled_box(
            f"Grout_X_{gy:.2f}",
            (3.2, 0.0024, 0.0008),
            bevel=0.0,
            material=grout_mat,
            parent=root,
            location=(0.0, gy, 0.0003),
            collection=collection,
        )

    # Kosan kitchen walls: Poly Haven painted_plaster_wall PBR tinted warm muted cream (albedo <= 0.56)
    wall_mat = _build_wall_pbr_material(assets_dir)
    baseboard_mat = make_material("Mat_Wall_Baseboard", (0.20, 0.21, 0.23, 1.0), roughness=0.52)
    counter_wood_mat = make_material("Mat_Kosan_CounterBody", (0.22, 0.16, 0.12, 1.0), roughness=0.58)
    counter_top_mat = make_material("Mat_Kosan_CounterTop", (0.34, 0.33, 0.31, 1.0), roughness=0.28, coat=0.25)

    # Left wall widened to x = -1.32m (comfortable Indonesian kosan kitchen, not a cramped tunnel!)
    _make_beveled_box("Wall_Left", (0.12, 7.6, 2.8), 0.005, wall_mat, root, (-1.38, 1.8, 1.4), collection=collection)
    _make_beveled_box("Baseboard_Left", (0.02, 7.6, 0.10), 0.004, baseboard_mat, root, (-1.31, 1.8, 0.05), collection=collection)

    # Back wall behind fridge at y = 3.55m
    _make_beveled_box("Wall_Back", (4.6, 0.12, 2.8), 0.005, wall_mat, root, (0.35, 3.61, 1.4), collection=collection)
    _make_beveled_box("Baseboard_Back", (4.6, 0.02, 0.10), 0.004, baseboard_mat, root, (0.35, 3.54, 0.05), collection=collection)

    # Right wall at x = 1.62m with REAL recessed kosan bedroom doorway (y = 2.00..2.86, z = 0..2.06)!
    # Split Wall_Right into front segment, back segment, and lintel header so bedroom door opens naturally into room alcove.
    _make_beveled_box("Wall_Right_Front", (0.12, 4.00, 2.8), 0.005, wall_mat, root, (1.68, 0.00, 1.4), collection=collection)
    _make_beveled_box("Wall_Right_Back", (0.12, 2.74, 2.8), 0.005, wall_mat, root, (1.68, 4.23, 1.4), collection=collection)
    _make_beveled_box("Wall_Right_Header", (0.12, 0.90, 0.74), 0.005, wall_mat, root, (1.68, 2.43, 2.43), collection=collection)
    _make_beveled_box("Baseboard_Right_Front", (0.02, 4.00, 0.10), 0.004, baseboard_mat, root, (1.61, 0.00, 0.05), collection=collection)
    _make_beveled_box("Baseboard_Right_Back", (0.02, 2.74, 0.10), 0.004, baseboard_mat, root, (1.61, 4.23, 0.05), collection=collection)

    # Cozy kosan bedroom alcove behind the right doorway (warm plaster + wood floor so light spills realistically!)
    bed_wall_mat = make_material("Mat_Bedroom_Wall", (0.42, 0.34, 0.25, 1.0), roughness=0.82)
    bed_floor_mat = make_material("Mat_Bedroom_Floor", (0.28, 0.22, 0.16, 1.0), roughness=0.55)
    _make_beveled_box("Bedroom_Alcove_Back", (0.08, 1.60, 2.6), 0.0, bed_wall_mat, root, (2.42, 2.43, 1.3), collection=collection)
    _make_beveled_box("Bedroom_Alcove_Side1", (0.85, 0.08, 2.6), 0.0, bed_wall_mat, root, (2.04, 1.68, 1.3), collection=collection)
    _make_beveled_box("Bedroom_Alcove_Side2", (0.85, 0.08, 2.6), 0.0, bed_wall_mat, root, (2.04, 3.18, 1.3), collection=collection)
    _make_beveled_box("Bedroom_Alcove_Floor", (0.90, 1.60, 0.04), 0.0, bed_floor_mat, root, (2.04, 2.43, -0.018), collection=collection)
    _make_beveled_box("Bedroom_Alcove_Ceil", (0.90, 1.60, 0.08), 0.0, bed_wall_mat, root, (2.04, 2.43, 2.60), collection=collection)

    # Classic Indonesian wooden kosan bedroom door frame (kusen) + slightly ajar paneled wooden door leaf (~28 deg inward)
    door_frame_mat = make_material("Mat_Door_FrameWood", (0.16, 0.09, 0.045, 1.0), roughness=0.55)
    door_leaf_mat = make_material("Mat_Door_LeafWood", (0.24, 0.135, 0.065, 1.0), roughness=0.48, coat=0.12)
    door_panel_mat = make_material("Mat_Door_PanelWood", (0.19, 0.105, 0.050, 1.0), roughness=0.52)
    brass_knob_mat = make_material("Mat_Door_BrassKnob", (0.76, 0.58, 0.22, 1.0), roughness=0.26, metallic=0.92)
    door_root = _make_empty("Kosan_BedroomDoor_Root", (1.62, 2.43, 0.0), parent=root, collection=collection)
    # Kusen jambs & top header
    _make_beveled_box("Door_Kusen_Front", (0.14, 0.06, 2.08), 0.004, door_frame_mat, door_root, (0.04, -0.45, 1.04), collection=collection)
    _make_beveled_box("Door_Kusen_Back", (0.14, 0.06, 2.08), 0.004, door_frame_mat, door_root, (0.04, 0.45, 1.04), collection=collection)
    _make_beveled_box("Door_Kusen_Top", (0.14, 0.96, 0.06), 0.004, door_frame_mat, door_root, (0.04, 0.0, 2.07), collection=collection)
    # Hinged door leaf pivot at back jamb (y=+0.42), swung inward +30 deg into bedroom so warm gap faces kitchen!
    door_pivot = _make_empty("Door_Leaf_Pivot", (0.03, 0.42, 0.0), parent=door_root, collection=collection)
    door_pivot.rotation_euler = (0.0, 0.0, math.radians(32.0))
    _make_beveled_box("Door_Leaf_Main", (0.042, 0.84, 2.02), 0.004, door_leaf_mat, door_pivot, (0.0, -0.42, 1.015), collection=collection)
    _make_beveled_box("Door_Panel_Top", (0.048, 0.58, 0.68), 0.003, door_panel_mat, door_pivot, (0.0, -0.42, 1.46), collection=collection)
    _make_beveled_box("Door_Panel_Bot", (0.048, 0.58, 0.64), 0.003, door_panel_mat, door_pivot, (0.0, -0.42, 0.56), collection=collection)
    # Brass doorknob on kitchen side & room side
    _make_beveled_box("Door_Knob_Kitchen", (0.06, 0.045, 0.045), 0.015, brass_knob_mat, door_pivot, (-0.045, -0.75, 0.98), collection=collection)

    # Front wall behind camera start at y = -1.6m (prevents empty void reflections!)
    _make_beveled_box("Wall_Front", (4.6, 0.12, 2.8), 0.005, wall_mat, root, (0.35, -1.65, 1.4), collection=collection)

    # Indonesian kosan concrete/wood kitchen counter along front-right wall (x=1.08..1.60, y=-0.3..1.45, z=0..0.82)
    _make_beveled_box("Kosan_Counter_Base", (0.52, 1.72, 0.78), 0.006, counter_wood_mat, root, (1.35, 0.56, 0.39), collection=collection)
    _make_beveled_box("Kosan_Counter_Top", (0.56, 1.76, 0.045), 0.006, counter_top_mat, root, (1.33, 0.56, 0.805), collection=collection)
    # Floating wall shelf above counter
    _make_beveled_box("Kosan_Wall_Shelf", (0.24, 1.40, 0.03), 0.004, counter_wood_mat, root, (1.49, 0.58, 1.48), collection=collection)

    # Wall Detail 1: Classic Indonesian Broco Light Switch squarely beside RIGHT side of fridge (near bedroom door!)
    switch_plate_mat = make_material("Mat_Switch_Plate", (0.82, 0.81, 0.78, 1.0), roughness=0.30)
    switch_key_mat = make_material("Mat_Switch_Key", (0.72, 0.71, 0.68, 1.0), roughness=0.34)
    sw_root = _make_empty("Wall_LightSwitch_0", (0.56, 3.535, 1.24), parent=root, collection=collection)
    sw_root.rotation_euler = (0.0, 0.0, 0.0)
    _make_beveled_box("Switch_Plate_0", (0.092, 0.014, 0.092), 0.003, switch_plate_mat, sw_root, (0.0, 0.0, 0.0), collection=collection)
    _make_beveled_box("Switch_Rocker_0", (0.024, 0.018, 0.046), 0.002, switch_key_mat, sw_root, (0.0, -0.007, 0.0), (math.radians(8.0), 0.0, 0.0), collection=collection)

    # Wall Detail 2: Classic Indonesian Kosan Wall Calendar (red header + crisp date grid) on back wall
    cal_root = _make_empty("Kosan_WallCalendar", (-0.86, 3.535, 1.82), parent=root, collection=collection)
    cal_red = make_material("Mat_Calendar_Red", (0.62, 0.09, 0.08, 1.0), roughness=0.55)
    cal_paper = make_material("Mat_Calendar_Paper", (0.76, 0.74, 0.70, 1.0), roughness=0.72)
    cal_ink = make_material("Mat_Calendar_Ink", (0.12, 0.12, 0.14, 1.0), roughness=0.80)
    cal_metal = make_material("Mat_Calendar_Clamp", (0.45, 0.46, 0.48, 1.0), roughness=0.30, metallic=0.85)
    _make_beveled_box("Calendar_Clamp", (0.34, 0.010, 0.016), 0.002, cal_metal, cal_root, (0.0, -0.003, 0.215), collection=collection)
    _make_beveled_box("Calendar_Header", (0.33, 0.006, 0.085), 0.001, cal_red, cal_root, (0.0, -0.002, 0.165), collection=collection)
    _make_beveled_box("Calendar_Body", (0.33, 0.006, 0.34), 0.001, cal_paper, cal_root, (0.0, -0.002, -0.045), collection=collection)
    for row_i in range(5):
        _make_beveled_box(
            f"Calendar_Row_{row_i}",
            (0.28, 0.003, 0.004),
            0.0,
            cal_ink,
            cal_root,
            (0.0, -0.006, 0.075 - row_i * 0.052),
            collection=collection,
        )
    for col_i in range(7):
        _make_beveled_box(
            f"Calendar_Col_{col_i}",
            (0.003, 0.003, 0.22),
            0.0,
            cal_ink,
            cal_root,
            (-0.135 + col_i * 0.045, -0.006, -0.03),
            collection=collection,
        )

    # Ceiling + Classic Indonesian TL Fluorescent Tube Fixture directly overhead
    ceil_mat = make_material("Mat_Ceiling", (0.50, 0.51, 0.52, 1.0), roughness=0.88)
    _make_beveled_box("Ceiling", (4.6, 7.6, 0.10), 0.0, ceil_mat, root, (0.35, 1.8, 2.75), collection=collection)

    fixture_mat = make_material("Mat_Neon_Fixture", (0.62, 0.64, 0.66, 1.0), roughness=0.35, metallic=0.6)
    _make_beveled_box("Neon_Housing", (0.09, 1.25, 0.045), 0.006, fixture_mat, root, (0.0, 2.05, 2.67), collection=collection)

    neon_tube_mat = make_material(
        "Mat_Neon_Tube_Glow",
        (0.95, 0.98, 1.0, 1.0),
        roughness=0.1,
        emission_color=(0.90, 0.96, 1.0, 1.0),
        emission_strength=0.1,  # Animated to 18.0 when switch clicks on!
    )
    bm_tube = bmesh.new()
    bmesh.ops.create_cone(bm_tube, cap_ends=True, cap_tris=False, segments=16, radius1=0.018, radius2=0.018, depth=1.18)
    neon_tube = _new_mesh_obj(
        "Neon_TL_Tube",
        bm_tube,
        neon_tube_mat,
        True,
        root,
        (0.0, 2.05, 2.62),
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
        (-0.28, 0.06, 0.052),
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
    """Build sharp glossy segmented cockroach antennae + tiny front leg tips + translucent veined wings.

    Blender camera local axes: +X right, +Y up, -Z forward.
    """
    rig_root = _make_empty("Cockroach_POV_Rig", (0.0, 0.0, 0.0), parent=camera_obj, collection=collection)

    # Rich dark glossy mahogany-brown chitin material (always crisp dark brown, never blows out white!)
    chitin_mat = make_material(
        "Mat_Cockroach_Antenna",
        (0.055, 0.016, 0.005, 1.0),
        roughness=0.30,
        coat=0.32,
    )
    segment_mat = make_material(
        "Mat_Cockroach_Segment",
        (0.022, 0.006, 0.002, 1.0),
        roughness=0.34,
        coat=0.28,
    )
    wing_mat = make_material(
        "Mat_Cockroach_Wing",
        (0.24, 0.10, 0.022, 1.0),
        roughness=0.28,
        coat=0.35,
        alpha=0.36,
        transmission=0.12,
    )
    vein_mat = make_material(
        "Mat_Cockroach_WingVein",
        (0.08, 0.03, 0.008, 1.0),
        roughness=0.36,
        alpha=0.60,
    )

    ant_l_pivot = _make_empty("Ant_Left_Pivot", (-0.030, -0.044, -0.048), parent=rig_root, collection=collection)
    ant_r_pivot = _make_empty("Ant_Right_Pivot", (0.030, -0.044, -0.048), parent=rig_root, collection=collection)

    # Graceful outward-sweeping tapered insect antennae framing left & right edges (never forming a center arch!)
    left_pts = [
        (0.000, 0.000, 0.000, 1.15),
        (-0.004, 0.010, -0.020, 0.88),
        (-0.009, 0.020, -0.044, 0.65),
        (-0.014, 0.029, -0.070, 0.42),
        (-0.018, 0.035, -0.096, 0.24),
        (-0.024, 0.038, -0.120, 0.10),
    ]
    right_pts = [(-x, y, z, r) for (x, y, z, r) in left_pts]

    ant_l_curve = _make_tube_curve("Cockroach_Antenna_L", left_pts, 0.00135, chitin_mat, resolution=14, bevel_res=5, parent=ant_l_pivot, collection=collection)
    ant_r_curve = _make_tube_curve("Cockroach_Antenna_R", right_pts, 0.00135, chitin_mat, resolution=14, bevel_res=5, parent=ant_r_pivot, collection=collection)

    # Subtle glossy dark chitin segment rings along mid-antenna so insect segmentation reads crisply
    for side_tag, pts, piv in (("L", left_pts, ant_l_pivot), ("R", right_pts, ant_r_pivot)):
        for seg_idx in (1, 2, 3):
            px, py, pz, pr = pts[seg_idx]
            bm_r = bmesh.new()
            bmesh.ops.create_icosphere(bm_r, subdivisions=1, radius=0.00165 * pr)
            _new_mesh_obj(f"Cockroach_AntSeg_{side_tag}_{seg_idx}", bm_r, segment_mat, True, piv, (px, py, pz), collection=collection)

    # Subtle front tarsus leg tips peeking at very bottom-left / bottom-right edge (Scenes 1, 4, 5)
    leg_l_pivot = _make_empty("LegTip_Left_Pivot", (-0.028, -0.056, -0.056), parent=rig_root, collection=collection)
    leg_r_pivot = _make_empty("LegTip_Right_Pivot", (0.028, -0.056, -0.056), parent=rig_root, collection=collection)
    leg_l_pts = [
        (-0.012, -0.006, 0.008, 1.0),
        (-0.003, 0.004, -0.012, 0.72),
        (0.007, 0.007, -0.032, 0.45),
        (0.013, 0.002, -0.044, 0.22),
    ]
    leg_r_pts = [(-x, y, z, r) for (x, y, z, r) in leg_l_pts]
    leg_l = _make_tube_curve("Cockroach_LegTip_L", leg_l_pts, 0.0011, chitin_mat, resolution=8, bevel_res=3, parent=leg_l_pivot, collection=collection)
    leg_r = _make_tube_curve("Cockroach_LegTip_R", leg_r_pts, 0.0011, chitin_mat, resolution=8, bevel_res=3, parent=leg_r_pivot, collection=collection)
    # Tiny spiny tibial bristles along front leg tips for unmistakable insect silhouette
    for side_tag, s_sign, leg_obj in (("L", -1.0, leg_l), ("R", 1.0, leg_r)):
        for b_i, (bx, by, bz) in enumerate([(0.002 * -s_sign, 0.005, -0.018), (0.007 * -s_sign, 0.006, -0.030)]):
            _make_tube_curve(
                f"Cockroach_LegSpine_{side_tag}_{b_i}",
                [(bx, by, bz, 0.8), (bx - s_sign * 0.004, by + 0.004, bz - 0.004, 0.15)],
                0.00045,
                segment_mat,
                resolution=4,
                bevel_res=2,
                parent=leg_obj,
                collection=collection,
            )

    # Translucent amber-brown insect wings anchored at bottom-left/bottom-right camera edges
    wing_l_pivot = _make_empty("Wing_Left_Pivot", (-0.028, -0.034, -0.048), parent=rig_root, collection=collection)
    wing_r_pivot = _make_empty("Wing_Right_Pivot", (0.028, -0.034, -0.048), parent=rig_root, collection=collection)

    def _build_wing_mesh(name: str, side: float, parent: bpy.types.Object) -> bpy.types.Object:
        bm = bmesh.new()
        pts = [
            (0.0, 0.0, 0.0),
            (side * 0.008, 0.006, -0.016),
            (side * 0.020, 0.008, -0.042),
            (side * 0.026, -0.010, -0.062),
            (side * 0.010, -0.020, -0.046),
            (side * 0.002, -0.012, -0.018),
        ]
        verts = [bm.verts.new(p) for p in pts]
        bm.faces.new(verts if side > 0 else list(reversed(verts)))
        res = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
        ext_verts = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=ext_verts, vec=Vector((0.0, 0.0005, 0.0)))
        w_obj = _new_mesh_obj(name, bm, wing_mat, True, parent, collection=collection)

        for v_idx, tip in enumerate([(side * 0.022, -0.004, -0.054), (side * 0.014, -0.014, -0.042)]):
            _make_tube_curve(
                f"{name}_Vein_{v_idx}",
                [(0.0, 0.0, 0.0, 1.0), (tip[0] * 0.5, tip[1] * 0.5, tip[2] * 0.5, 0.7), (tip[0], tip[1], tip[2], 0.3)],
                0.00055,
                vein_mat,
                resolution=6,
                bevel_res=2,
                parent=w_obj,
                collection=collection,
            )
        return w_obj

    wing_l = _build_wing_mesh("Cockroach_Wing_L", -1.0, wing_l_pivot)
    wing_r = _build_wing_mesh("Cockroach_Wing_R", 1.0, wing_r_pivot)

    return {
        "root": rig_root,
        "ant_l": ant_l_pivot,
        "ant_r": ant_r_pivot,
        "leg_l_pivot": leg_l_pivot,
        "leg_r_pivot": leg_r_pivot,
        "leg_l": leg_l,
        "leg_r": leg_r,
        "wing_l_pivot": wing_l_pivot,
        "wing_r_pivot": wing_r_pivot,
        "wing_l": wing_l,
        "wing_r": wing_r,
    }


def build_cockroach_shadow_caster(
    location: Tuple[float, float, float] = (0.0, 0.04, 0.014),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build an invisible-to-camera cockroach body + 6 legs + 2 antennae that casts an unmistakable
    insect silhouette shadow onto the ceramic floor & Indomie spill in Scene 1!
    """
    root = _make_empty("Cockroach_ShadowCaster_Root", location, collection=collection)
    shad_mat = make_material("Mat_Cockroach_Shadow", (0.02, 0.01, 0.01, 1.0), roughness=0.9)

    def _shadow_only(obj: bpy.types.Object) -> bpy.types.Object:
        obj.visible_camera = False
        obj.visible_diffuse = False
        obj.visible_glossy = False
        obj.visible_transmission = False
        obj.visible_shadow = True
        return obj

    # Elongated oval cockroach body (length ~5.2cm, width ~2.0cm)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector((0.013, 0.028, 0.006)), verts=bm.verts)
    _shadow_only(_new_mesh_obj("Cockroach_Shadow_Body", bm, shad_mat, True, root, (0.0, 0.0, 0.0), collection=collection))

    # Pronotum / head shield
    bm_h = bmesh.new()
    bmesh.ops.create_icosphere(bm_h, subdivisions=2, radius=1.0)
    bmesh.ops.scale(bm_h, vec=Vector((0.009, 0.010, 0.005)), verts=bm_h.verts)
    _shadow_only(_new_mesh_obj("Cockroach_Shadow_Head", bm_h, shad_mat, True, root, (0.0, 0.028, 0.0), collection=collection))

    # 6 spiky bent insect legs (3 left, 3 right) -> iconic cockroach shadow silhouette!
    for side_tag, sx in (("L", -1.0), ("R", 1.0)):
        for l_idx, (y0, y_mid, y_tip, span) in enumerate([
            (0.018, 0.028, 0.042, 0.032),   # front leg
            (0.002, 0.000, -0.010, 0.038),  # mid leg
            (-0.016, -0.028, -0.046, 0.042),  # hind leg
        ]):
            pts = [
                (sx * 0.010, y0, 0.0, 1.0),
                (sx * (span * 0.68), y_mid, 0.004, 0.75),
                (sx * span, y_tip, -0.008, 0.45),
            ]
            _shadow_only(
                _make_tube_curve(f"Cockroach_Shadow_Leg_{side_tag}_{l_idx}", pts, 0.0018, shad_mat, resolution=4, bevel_res=2, parent=root, collection=collection)
            )
        # 2 long sweeping antennae
        ant_pts = [
            (sx * 0.004, 0.034, 0.001, 1.0),
            (sx * 0.018, 0.056, 0.004, 0.75),
            (sx * 0.034, 0.088, 0.002, 0.45),
        ]
        _shadow_only(
            _make_tube_curve(f"Cockroach_Shadow_Ant_{side_tag}", ant_pts, 0.0012, shad_mat, resolution=6, bevel_res=2, parent=root, collection=collection)
        )

    return {"root": root}


# =============================================================================
# 5. FRIDGE WITH CRISP 5.5cm DARK UNDER-GAP (KOLONG KULKAS)
# =============================================================================

def build_fridge_under_gap(
    location: Tuple[float, float, float] = (-0.18, 2.95, 0.0),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Build stylized Indonesian kosan 2-door fridge raised 5.5cm off the floor on 4 rubber feet."""
    root = _make_empty("Fridge_UnderGap_Root", location, collection=collection)

    # Capped albedo <= 0.62 so overhead neon highlights stay controlled under AgX
    body_mat = make_material("Mat_Fridge_Body", (0.56, 0.60, 0.64, 1.0), roughness=0.28, metallic=0.22, coat=0.45)
    chrome_mat = make_material("Mat_Fridge_Chrome", (0.76, 0.78, 0.82, 1.0), roughness=0.16, metallic=0.92)
    rubber_mat = make_material("Mat_Fridge_RubberFoot", (0.04, 0.04, 0.05, 1.0), roughness=0.78)
    void_mat = make_material("Mat_UnderGap_ShadowVoid", (0.006, 0.007, 0.010, 1.0), roughness=0.98)

    gap_h = 0.055  # 5.5 cm dark refuge gap for 1.5cm cockroach!
    for fx in (-0.25, 0.25):
        for fy in (-0.25, 0.25):
            bm_f = bmesh.new()
            bmesh.ops.create_cone(bm_f, cap_ends=True, segments=12, radius1=0.028, radius2=0.022, depth=gap_h)
            _new_mesh_obj(f"Fridge_Foot_{fx:+.2f}_{fy:+.2f}", bm_f, rubber_mat, True, root, (fx, fy, gap_h * 0.5), collection=collection)

    _make_beveled_box("Fridge_Chassis", (0.60, 0.60, 1.43), 0.018, body_mat, root, (0.0, 0.0, gap_h + 0.715), collection=collection)
    _make_beveled_box("Fridge_Door_Lower", (0.58, 0.045, 0.90), 0.012, body_mat, root, (0.0, -0.315, gap_h + 0.46), collection=collection)
    _make_beveled_box("Fridge_Door_Upper", (0.58, 0.045, 0.47), 0.012, body_mat, root, (0.0, -0.315, gap_h + 1.175), collection=collection)
    _make_beveled_box("Fridge_Handle_Lower", (0.022, 0.032, 0.22), 0.006, chrome_mat, root, (0.24, -0.352, gap_h + 0.76), collection=collection)
    _make_beveled_box("Fridge_Handle_Upper", (0.022, 0.032, 0.14), 0.006, chrome_mat, root, (0.24, -0.352, gap_h + 1.03), collection=collection)
    _make_beveled_box("Fridge_UnderGap_Void", (0.48, 0.42, gap_h * 0.94), 0.0, void_mat, root, (0.0, 0.06, gap_h * 0.48), collection=collection)

    return {"root": root}


# =============================================================================
# 6, 7, 8. VFX PROPS: CYAN WIND WAVES (SC3), DUST PUFF (SC4), SPEED LINES (SC4)
# =============================================================================

def build_wind_lines(
    location: Tuple[float, float, float] = (0.0, 0.55, 0.12),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Subtle, thin semi-transparent cyan airflow ribbons strictly at frame perimeter (Scene 3)."""
    root = _make_empty("Wind_Lines_Root", location, collection=collection)
    cyan_mat = make_material(
        "Mat_Cyan_WindGlow",
        (0.05, 0.88, 1.0, 1.0),
        roughness=0.15,
        emission_color=(0.05, 0.88, 1.0, 1.0),
        emission_strength=3.6,
        alpha=0.28,
    )
    ribbons = []
    offsets = [
        (-0.28, 0.16),
        (-0.22, 0.28),
        (0.22, 0.28),
        (0.28, 0.15),
        (-0.24, 0.06),
        (0.24, 0.06),
    ]
    for idx, (ox, oz) in enumerate(offsets):
        pts = [
            (ox * 1.35, 0.42, oz + 0.18, 0.25),
            (ox * 1.10, 0.18, oz + 0.07, 0.80),
            (ox * 0.88, -0.08, oz - 0.02, 0.90),
            (ox * 0.68, -0.32, oz - 0.08, 0.18),
        ]
        r_obj = _make_tube_curve(f"Wind_Ribbon_{idx:02d}", pts, 0.0014, cyan_mat, resolution=10, bevel_res=3, parent=root, collection=collection)
        ribbons.append(r_obj)
    return {"root": root, "ribbons": ribbons}


def build_dust_puff(
    location: Tuple[float, float, float] = (0.0, 0.35, 0.02),
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Airy, semi-transparent low impact dust puffs bursting outward when sandal slams (Scene 4)."""
    root = _make_empty("Dust_Puff_Root", location, collection=collection)
    dust_mat = make_material("Mat_Dust_Puff", (0.56, 0.52, 0.46, 1.0), roughness=0.96, alpha=0.22)
    puffs = []
    for i in range(16):
        ang = (2.0 * math.pi * i) / 16.0
        r = 0.10 + 0.06 * (i % 3)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.015 + 0.009 * (i % 3))
        bmesh.ops.scale(bm, vec=Vector((1.35, 1.15, 0.72)), verts=bm.verts)
        p_obj = _new_mesh_obj(
            f"Dust_Cloud_{i:02d}",
            bm,
            dust_mat,
            True,
            root,
            (r * math.cos(ang), r * math.sin(ang), 0.014 + 0.014 * (i % 3)),
            collection=collection,
        )
        puffs.append(p_obj)
    return {"root": root, "puffs": puffs}


def build_speed_lines_rig(
    camera_obj: Optional[bpy.types.Object] = None,
    collection: Optional[bpy.types.Collection] = None,
) -> Dict[str, bpy.types.Object]:
    """Subtle, thin semi-transparent radial speed-lines strictly around top & side outer frame edges.

    Intentionally excludes the lower-center zone (`sin(ang) < -0.45`) so no stray vertical lines
    ever cut across the human's chest/shirt in Scene 8!
    """
    root = _make_empty("Speed_Lines_Root", (0.0, 0.0, 0.0), parent=camera_obj, collection=collection)
    line_mat = make_material(
        "Mat_Speed_Lines",
        (0.88, 0.94, 1.0, 1.0),
        roughness=0.15,
        emission_color=(0.78, 0.90, 1.0, 1.0),
        emission_strength=1.5,
        alpha=0.18,
    )
    for i in range(12):
        ang = (2.0 * math.pi * i) / 12.0
        if math.sin(ang) < -0.45:
            continue  # Keep lower-center frame 100% clean (no vertical streaks over shirt!)
        rx = 0.145 * math.cos(ang)
        ry = 0.195 * math.sin(ang)
        pts = [
            (rx * 1.15, ry * 1.15, -0.09, 0.12),
            (rx * 0.98, ry * 0.98, -0.18, 0.55),
            (rx * 0.90, ry * 0.90, -0.26, 0.08),
        ]
        _make_tube_curve(f"Speed_Line_{i:02d}", pts, 0.00024, line_mat, resolution=4, bevel_res=2, parent=root, collection=collection)
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
