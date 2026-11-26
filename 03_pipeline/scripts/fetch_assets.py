#!/usr/bin/env python3
"""Auto-Fetcher & Persistent Cache for Free CC0 3D Assets, PBR Textures, and HDRIs.

Zero-Manual Workflow:
- Queries Poly Haven Public API (https://api.polyhaven.com/) — 100% CC0, no login required.
- Downloads & caches PBR kitchen tile/wood textures, indoor HDRIs, and CC0 GLTF furniture/props
  into Google Drive (/content/drive/MyDrive/channel-micro-pov/02_assets/) or local cache.
- Automatically updates 02_assets/asset_catalog.json after fetching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline_utils import (
    download_file,
    get_repo_root,
    http_get_json,
    http_head_status,
    load_and_validate_spec,
    log,
    resolve_assets_dir,
    resolve_family_ready_blend,
    upsert_catalog_entry,
)

POLYHAVEN_FILES_API = "https://api.polyhaven.com/files/{asset_id}"

# Curated 100% CC0 Poly Haven PBR textures for dense Indonesian kosan kitchen
POLYHAVEN_TEXTURES: List[Dict[str, Any]] = [
    {
        "id": "interior_tiles",
        "alias": "kitchen_tile_pbr",
        "desc": "Keramik lantai dapur PBR (CC0 Poly Haven)",
        "resolution": "1k",
        "maps": ["Diffuse", "Rough", "nor_gl"],
    },
    {
        "id": "painted_plaster_wall",
        "alias": "kosan_wall_pbr",
        "desc": "Tekstur tembok plester kosan PBR (CC0 Poly Haven)",
        "resolution": "1k",
        "maps": ["Diffuse", "Rough", "nor_gl"],
    },
    {
        "id": "kitchen_wood",
        "alias": "kitchen_wood_pbr",
        "desc": "Tekstur kayu lemari dapur PBR (CC0 Poly Haven)",
        "resolution": "1k",
        "maps": ["Diffuse", "Rough", "nor_gl"],
    },
]

POLYHAVEN_HDRIS: List[Dict[str, Any]] = [
    {
        "id": "small_empty_room_3",
        "alias": "indoor_room_hdri",
        "desc": "HDRI pencahayaan ruangan dalam kosan (CC0 Poly Haven)",
        "resolution": "1k",
    },
]

# 15 Real CC0 Poly Haven kitchen props (adopted from Zack-Blender-Pack polyhaven_assets.txt)
POLYHAVEN_MODELS: List[Dict[str, Any]] = [
    {
        "id": "modern_wooden_cabinet",
        "catalog_id": "kitchen_cabinet_gap",
        "category": "environment",
        "desc": "Lemari dapur kayu CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "Shelf_01",
        "catalog_id": "kitchen_shelf_01",
        "category": "environment",
        "desc": "Rak dapur kosan CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "cardboard_box_01",
        "catalog_id": "cardboard_box_01",
        "category": "prop",
        "desc": "Kardus buntu sudut dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "wooden_bowl_01",
        "catalog_id": "kitchen_bowl_01",
        "category": "prop",
        "desc": "Mangkuk dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "wooden_bowl_02",
        "catalog_id": "kitchen_bowl_02",
        "category": "prop",
        "desc": "Mangkuk kayu dapur kedua CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "pot_enamel_01",
        "catalog_id": "kitchen_pot_enamel",
        "category": "prop",
        "desc": "Panci enamel dapur kosan CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "brass_pan_01",
        "catalog_id": "kitchen_pan_01",
        "category": "prop",
        "desc": "Wajan penggorengan dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "metal_jug",
        "catalog_id": "kitchen_metal_jug",
        "category": "prop",
        "desc": "Ceret/teko logam dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "jug_01",
        "catalog_id": "kitchen_jug_01",
        "category": "prop",
        "desc": "Botol/kendi dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "tea_set_01",
        "catalog_id": "kitchen_tea_set",
        "category": "prop",
        "desc": "Teko & gelas teh dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "electric_stove",
        "catalog_id": "kitchen_stove",
        "category": "environment",
        "desc": "Kompor dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "wooden_cutting_board",
        "catalog_id": "kitchen_cutting_board",
        "category": "prop",
        "desc": "Talenan kayu dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "WoodenChair_01",
        "catalog_id": "kitchen_chair_01",
        "category": "environment",
        "desc": "Kursi kayu dapur kosan CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "wicker_basket_02",
        "catalog_id": "kitchen_basket_02",
        "category": "prop",
        "desc": "Keranjang dapur anyaman CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
    {
        "id": "wall_clock",
        "catalog_id": "kitchen_wall_clock",
        "category": "prop",
        "desc": "Jam dinding dapur CC0 (Poly Haven GLTF)",
        "resolution": "1k",
    },
]



def _pick_resolution(res_dict: Dict[str, Any], preferred: str) -> str:
    if preferred in res_dict:
        return preferred
    for cand in ("1k", "2k", "4k"):
        if cand in res_dict:
            return cand
    return next(iter(res_dict.keys()))


def fetch_polyhaven_texture(
    cfg: Dict[str, Any], assets_dir: Path, force: bool = False, verify_only: bool = False
) -> Dict[str, Any]:
    asset_id = cfg["id"]
    preferred_res = cfg.get("resolution", "1k")
    data = http_get_json(POLYHAVEN_FILES_API.format(asset_id=asset_id))
    tex_dir = assets_dir / "textures" / asset_id
    map_files: Dict[str, str] = {}
    verified_urls: List[str] = []

    for map_key in cfg.get("maps", ["Diffuse", "Rough", "nor_gl"]):
        if map_key not in data:
            continue
        res = _pick_resolution(data[map_key], preferred_res)
        fmt_dict = data[map_key][res]
        fmt = "jpg" if "jpg" in fmt_dict else ("png" if "png" in fmt_dict else next(iter(fmt_dict.keys())))
        url = fmt_dict[fmt]["url"]
        verified_urls.append(url)
        filename = Path(url).name
        dest = tex_dir / filename
        if verify_only:
            status = http_head_status(url)
            log("VERIFY", f"Texture {asset_id}/{map_key} -> HTTP {status} ({url})")
            if status != 200:
                raise RuntimeError(f"Expected HTTP 200 for {url}, got {status}")
        else:
            downloaded = download_file(url, dest, force=force)
            tag = "DOWNLOADED" if downloaded else "CACHED"
            log("FETCH", f"[{tag}] Texture {asset_id}/{map_key} -> {dest}")
        map_files[map_key.lower()] = f"02_assets/textures/{asset_id}/{filename}"

    entry = {
        "id": cfg["alias"],
        "polyhaven_id": asset_id,
        "desc": cfg["desc"],
        "source": "polyhaven_api",
        "license": "CC0",
        "resolution": preferred_res,
        "maps": map_files,
        "cached": not verify_only,
    }
    if not verify_only:
        upsert_catalog_entry(assets_dir, "textures", entry)
    return {"entry": entry, "urls": verified_urls}


def fetch_polyhaven_hdri(
    cfg: Dict[str, Any], assets_dir: Path, force: bool = False, verify_only: bool = False
) -> Dict[str, Any]:
    asset_id = cfg["id"]
    preferred_res = cfg.get("resolution", "1k")
    data = http_get_json(POLYHAVEN_FILES_API.format(asset_id=asset_id))
    hdri_data = data.get("hdri", {})
    if not hdri_data:
        raise RuntimeError(f"Poly Haven asset {asset_id} has no 'hdri' key")

    res = _pick_resolution(hdri_data, preferred_res)
    fmt_dict = hdri_data[res]
    fmt = "hdr" if "hdr" in fmt_dict else next(iter(fmt_dict.keys()))
    url = fmt_dict[fmt]["url"]
    filename = Path(url).name
    dest = assets_dir / "hdri" / filename

    if verify_only:
        status = http_head_status(url)
        log("VERIFY", f"HDRI {asset_id} -> HTTP {status} ({url})")
        if status != 200:
            raise RuntimeError(f"Expected HTTP 200 for {url}, got {status}")
    else:
        downloaded = download_file(url, dest, force=force)
        tag = "DOWNLOADED" if downloaded else "CACHED"
        log("FETCH", f"[{tag}] HDRI {asset_id} -> {dest}")

    entry = {
        "id": cfg["alias"],
        "polyhaven_id": asset_id,
        "desc": cfg["desc"],
        "source": "polyhaven_api",
        "license": "CC0",
        "resolution": res,
        "file": f"02_assets/hdri/{filename}",
        "cached": not verify_only,
    }
    if not verify_only:
        upsert_catalog_entry(assets_dir, "hdri", entry)
    return {"entry": entry, "urls": [url]}


def fetch_polyhaven_model(
    cfg: Dict[str, Any], assets_dir: Path, force: bool = False, verify_only: bool = False
) -> Dict[str, Any]:
    asset_id = cfg["id"]
    preferred_res = cfg.get("resolution", "1k")
    data = http_get_json(POLYHAVEN_FILES_API.format(asset_id=asset_id))
    gltf_root = data.get("gltf", {})
    if not gltf_root:
        raise RuntimeError(f"Poly Haven model {asset_id} has no 'gltf' format")

    res = _pick_resolution(gltf_root, preferred_res)
    gltf_entry = gltf_root[res]["gltf"]
    main_url = gltf_entry["url"]
    model_dir = assets_dir / "models_3d" / asset_id
    main_filename = Path(main_url).name
    main_dest = model_dir / main_filename

    urls_to_check = [(main_url, main_dest)]
    for rel_path, inc_info in gltf_entry.get("include", {}).items():
        urls_to_check.append((inc_info["url"], model_dir / rel_path))

    verified_urls: List[str] = []
    for url, dest in urls_to_check:
        verified_urls.append(url)
        if verify_only:
            status = http_head_status(url)
            log("VERIFY", f"Model {asset_id} ({dest.name}) -> HTTP {status}")
            if status != 200:
                raise RuntimeError(f"Expected HTTP 200 for {url}, got {status}")
        else:
            downloaded = download_file(url, dest, force=force)
            tag = "DOWNLOADED" if downloaded else "CACHED"
            log("FETCH", f"[{tag}] Model {asset_id}/{dest.name} -> {dest}")

    entry = {
        "id": cfg["catalog_id"],
        "polyhaven_id": asset_id,
        "category": cfg["category"],
        "source": "polyhaven_api",
        "license": "CC0",
        "file": f"02_assets/models_3d/{asset_id}/{main_filename}",
        "desc": cfg["desc"],
        "scale_hint": "1 unit = 1 meter",
        "cached": not verify_only,
    }
    if not verify_only:
        upsert_catalog_entry(assets_dir, "models_3d", entry)
    return {"entry": entry, "urls": verified_urls}


def ensure_procedural_catalog_entries(assets_dir: Path) -> None:
    """Register stylized Indonesian procedural Blender modules in asset_catalog.json."""
    procedural_items = [
        {
            "id": "kitchen_tile_floor",
            "category": "environment",
            "source": "procedural_blender_with_polyhaven_pbr",
            "license": "CC0",
            "module": "03_pipeline/scripts/procedural_props.py:build_kitchen_tile_floor",
            "file": "02_assets/models_3d/kitchen_tile_floor.glb",
            "scale_hint": "1 unit = 1 meter",
            "procedural_ready": True,
        },
        {
            "id": "indomie_bowl_spill",
            "category": "prop",
            "source": "procedural_blender",
            "license": "CC0",
            "module": "03_pipeline/scripts/procedural_props.py:build_indomie_bowl_spill",
            "file": "02_assets/models_3d/indomie_bowl_spill.glb",
            "scale_hint": "diameter genangan ~0.18m",
            "procedural_ready": True,
        },
        {
            "id": "sandal_jepit_swallow",
            "category": "prop",
            "source": "procedural_blender",
            "license": "CC0",
            "module": "03_pipeline/scripts/procedural_props.py:build_sandal_jepit_swallow",
            "file": "02_assets/models_3d/sandal_jepit_swallow.glb",
            "scale_hint": "panjang ~0.27m",
            "procedural_ready": True,
        },
        {
            "id": "fridge_under_gap",
            "category": "environment",
            "source": "procedural_blender",
            "license": "CC0",
            "module": "03_pipeline/scripts/procedural_props.py:build_fridge_under_gap",
            "file": "02_assets/models_3d/fridge_under_gap.glb",
            "scale_hint": "celah kolong 0.055m",
            "procedural_ready": True,
        },
        {
            "id": "human_silhouette_giant",
            "category": "character_rig",
            "source": "mpfb2_zack_blender_pack",
            "license": "CC0",
            "module": "03_pipeline/scripts/mpfb_human.py:prepare_mpfb2_human",
            "file": "02_assets/models_3d/family_ready.blend",
            "scale_hint": "MPFB2 adult rig (~1.67m) with ENHANCED_SSS + 31 ARKit face keys + Displace 0.006",
            "procedural_ready": False,
            "cached": (assets_dir / "models_3d" / "family_ready.blend").exists(),
        },
        {
            "id": "cockroach_antennae_rig",
            "category": "pov_foreground",
            "source": "procedural_blender",
            "license": "CC0",
            "module": "03_pipeline/scripts/procedural_props.py:build_cockroach_antennae_rig",
            "file": "02_assets/models_3d/cockroach_antennae_rig.glb",
            "scale_hint": "foreground kamera POV",
            "procedural_ready": True,
        },
    ]
    for item in procedural_items:
        upsert_catalog_entry(assets_dir, "models_3d", item)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fetch CC0 textures, HDRIs, and 3D models from Poly Haven API + sync MPFB2 rig."
    )
    parser.add_argument(
        "--spec",
        type=str,
        default=str(get_repo_root() / "04_episodes/ep001_kecoak_dapur/ep001_spec.json"),
        help="Path to episode spec JSON",
    )
    parser.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Override persistent cache directory (defaults to Drive 02_assets if mounted)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if already present in cache",
    )
    parser.add_argument(
        "--verify-urls",
        action="store_true",
        help="Verify all CC0 download URLs return HTTP 200 without downloading full files",
    )
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = load_and_validate_spec(spec_path)
    assets_dir = resolve_assets_dir(args.assets_dir)

    log("FETCH", f"Episode: {spec['episode_id']} — {spec['title']}")
    log("FETCH", f"Cache directory: {assets_dir}")

    # Sync MPFB2 family_ready.blend from Drive / Kaggle input into project cache
    if not args.verify_urls:
        fam_blend = resolve_family_ready_blend(assets_dir)
        if fam_blend:
            log("FETCH", f"[MPFB2] family_ready.blend ready -> {fam_blend}")
        else:
            log(
                "WARN",
                "family_ready.blend not found in Drive/cache yet. Ensure Google Drive is mounted or "
                "set MICRO_POV_FAMILY_BLEND before running build_and_render.py.",
            )

    all_urls: List[str] = []
    errors: List[str] = []

    for tex in POLYHAVEN_TEXTURES:
        try:
            res = fetch_polyhaven_texture(tex, assets_dir, force=args.force, verify_only=args.verify_urls)
            all_urls.extend(res["urls"])
        except Exception as exc:
            errors.append(f"Texture {tex['id']}: {exc}")
            log("WARN", f"Texture {tex['id']} failed: {exc}")

    for hdri in POLYHAVEN_HDRIS:
        try:
            res = fetch_polyhaven_hdri(hdri, assets_dir, force=args.force, verify_only=args.verify_urls)
            all_urls.extend(res["urls"])
        except Exception as exc:
            errors.append(f"HDRI {hdri['id']}: {exc}")
            log("WARN", f"HDRI {hdri['id']} failed: {exc}")

    for model in POLYHAVEN_MODELS:
        try:
            res = fetch_polyhaven_model(model, assets_dir, force=args.force, verify_only=args.verify_urls)
            all_urls.extend(res["urls"])
        except Exception as exc:
            errors.append(f"Model {model['id']}: {exc}")
            log("WARN", f"Model {model['id']} failed: {exc}")

    if not args.verify_urls:
        ensure_procedural_catalog_entries(assets_dir)
        log("FETCH", f"Catalog updated: {assets_dir / 'asset_catalog.json'}")

    log("FETCH", f"Checked/processed {len(all_urls)} CC0 asset URLs ({len(errors)} warnings).")
    if errors and args.verify_urls:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

