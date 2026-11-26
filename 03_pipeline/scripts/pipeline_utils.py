#!/usr/bin/env python3
"""Shared utilities for the channel-micro-pov zero-manual production pipeline.

Handles:
- Automatic Google Drive vs local repository path resolution
- Episode spec loading & JSON Schema validation
- Atomic asset_catalog.json updates
- Resilient HTTP downloads with User-Agent, retry, and content validation
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DRIVE_PROJECT_DIR = Path("/content/drive/MyDrive/channel-micro-pov")
USER_AGENT = "channel-micro-pov-pipeline/2.0 (https://github.com/ruangcermat/channel-micro-pov)"


def get_repo_root() -> Path:
    """Return the root directory of the git repository."""
    return Path(__file__).resolve().parents[2]


def resolve_assets_dir(explicit_dir: Optional[str] = None) -> Path:
    """Resolve the persistent asset cache directory.

    Priority:
    1. Explicit CLI flag (--assets-dir)
    2. Environment variable MICRO_POV_ASSETS_DIR
    3. Google Drive cache (/content/drive/MyDrive/channel-micro-pov/02_assets) if Drive is mounted
    4. Local repo fallback (<repo>/02_assets)
    """
    if explicit_dir:
        path = Path(explicit_dir).expanduser().resolve()
    elif os.environ.get("MICRO_POV_ASSETS_DIR"):
        path = Path(os.environ["MICRO_POV_ASSETS_DIR"]).expanduser().resolve()
    elif DEFAULT_DRIVE_PROJECT_DIR.parent.exists():
        path = DEFAULT_DRIVE_PROJECT_DIR / "02_assets"
    else:
        path = get_repo_root() / "02_assets"

    for sub in ("models_3d", "textures", "hdri", "sfx", "bgm"):
        (path / sub).mkdir(parents=True, exist_ok=True)
    return path


def resolve_episode_work_dir(spec_path: Path, explicit_work_dir: Optional[str] = None) -> Path:
    """Resolve working/output directory for an episode.

    On Google Colab with Drive mounted, stores renders/outputs persistently inside
    /content/drive/MyDrive/channel-micro-pov/04_episodes/<episode_slug>/ so
    previews, VO, and final MP4 survive runtime restarts.
    """
    if explicit_work_dir:
        work_dir = Path(explicit_work_dir).expanduser().resolve()
    elif os.environ.get("MICRO_POV_WORK_DIR"):
        work_dir = Path(os.environ["MICRO_POV_WORK_DIR"]).expanduser().resolve()
    elif DEFAULT_DRIVE_PROJECT_DIR.parent.exists():
        episode_slug = spec_path.resolve().parent.name
        work_dir = DEFAULT_DRIVE_PROJECT_DIR / "04_episodes" / episode_slug
    else:
        work_dir = spec_path.resolve().parent

    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp_path.replace(path)


def load_and_validate_spec(spec_path: Path) -> Dict[str, Any]:
    """Load an episode spec JSON and validate it against 03_pipeline/spec_schema.json."""
    spec = load_json(spec_path)
    schema_path = get_repo_root() / "03_pipeline" / "spec_schema.json"
    if schema_path.exists():
        try:
            import jsonschema

            schema = load_json(schema_path)
            jsonschema.validate(instance=spec, schema=schema)
        except ImportError:
            # Lightweight fallback validation if jsonschema isn't installed inside Blender Python
            required = [
                "episode_id",
                "title",
                "universe",
                "target_duration_sec",
                "pov_config",
                "bgm_plan",
                "scenes",
            ]
            missing = [k for k in required if k not in spec]
            if missing:
                raise ValueError(f"Spec missing required keys: {missing}")
    return spec


def load_catalog(assets_dir: Path) -> Dict[str, Any]:
    """Load asset_catalog.json from assets_dir, seeding from repo if absent."""
    catalog_path = assets_dir / "asset_catalog.json"
    if catalog_path.exists():
        data = load_json(catalog_path)
    else:
        repo_seed = get_repo_root() / "02_assets" / "asset_catalog.json"
        if repo_seed.exists():
            data = load_json(repo_seed)
        else:
            data = {
                "catalog_version": "2.0",
                "models_3d": [],
                "textures": [],
                "hdri": [],
                "sfx": [],
                "bgm": [],
            }
    for key in ("models_3d", "textures", "hdri", "sfx", "bgm"):
        data.setdefault(key, [])
    return data


def upsert_catalog_entry(
    assets_dir: Path,
    section: str,
    entry: Dict[str, Any],
    also_sync_repo: bool = False,
) -> None:
    """Insert or update an entry by 'id' inside asset_catalog.json."""
    catalog = load_catalog(assets_dir)
    items: List[Dict[str, Any]] = catalog.setdefault(section, [])
    entry = dict(entry)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for idx, existing in enumerate(items):
        if existing.get("id") == entry.get("id"):
            merged = dict(existing)
            merged.update(entry)
            items[idx] = merged
            break
    else:
        items.append(entry)

    catalog["last_updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_json(assets_dir / "asset_catalog.json", catalog)

    if also_sync_repo:
        repo_catalog = get_repo_root() / "02_assets" / "asset_catalog.json"
        if repo_catalog.resolve() != (assets_dir / "asset_catalog.json").resolve():
            save_json(repo_catalog, catalog)


def http_get_json(url: str, timeout: int = 20, retries: int = 3) -> Dict[str, Any]:
    """Fetch JSON from a public HTTP API with retry and backoff."""
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"Failed to GET JSON from {url}: {last_err}")


def http_head_status(url: str, timeout: int = 15) -> int:
    """Return HTTP status code for a URL using HEAD (falling back to ranged GET)."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        if exc.code == 405:
            req_get = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-15"}
            )
            with urllib.request.urlopen(req_get, timeout=timeout) as resp:
                return int(resp.status)
        return int(exc.code)


def download_file(
    url: str,
    dest_path: Path,
    force: bool = False,
    min_bytes: int = 128,
    timeout: int = 60,
    retries: int = 3,
) -> bool:
    """Download a file atomically if not already cached.

    Returns True if a fresh download happened, False if served from cache.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if not force and dest_path.exists() and dest_path.stat().st_size >= min_bytes:
        return False

    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if status not in (200, 206):
                    raise RuntimeError(f"Unexpected HTTP status {status}")
                with tmp_path.open("wb") as out_fh:
                    shutil.copyfileobj(resp, out_fh, length=1024 * 64)
            size = tmp_path.stat().st_size
            if size < min_bytes:
                raise RuntimeError(f"Downloaded file too small ({size} bytes)")
            tmp_path.replace(dest_path)
            return True
        except Exception as exc:
            last_err = exc
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(2.0 * attempt)
    raise RuntimeError(f"Failed to download {url} -> {dest_path}: {last_err}")


def resolve_family_ready_blend(assets_dir: Optional[Path] = None) -> Optional[Path]:
    """Locate MPFB2 `family_ready.blend` from Drive/Kaggle/local cache and sync to project cache.

    Search order:
    1. Environment variable `MICRO_POV_FAMILY_BLEND`
    2. Project cache `<assets_dir>/models_3d/family_ready.blend`
    3. Google Drive primary skill pack path:
       `/content/drive/MyDrive/Skill referensi/Zack Blender Pack/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend`
    4. Google Drive project skills_ref fallback:
       `/content/drive/MyDrive/channel-micro-pov/05_skills_ref/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend`
    5. Kaggle input datasets (`/kaggle/input/**/family_ready.blend`)
    6. Local repo / VM cache (`/tmp/zack_cache/family_ready.blend`)
    """
    cache_dir = (assets_dir or resolve_assets_dir()) / "models_3d"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_dest = cache_dir / "family_ready.blend"

    candidates: List[Path] = []
    if os.environ.get("MICRO_POV_FAMILY_BLEND"):
        candidates.append(Path(os.environ["MICRO_POV_FAMILY_BLEND"]).expanduser())
    candidates.append(cached_dest)
    candidates.extend([
        Path("/content/drive/MyDrive/Skill referensi/Zack Blender Pack/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend"),
        Path("/content/drive/MyDrive/channel-micro-pov/05_skills_ref/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend"),
        get_repo_root() / "skills/zack-3d-short/ready/family_ready.blend",
        Path("/tmp/zack_cache/family_ready.blend"),
    ])

    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for found in sorted(kaggle_input.rglob("family_ready.blend")):
            candidates.append(found)

    for cand in candidates:
        if cand.exists() and cand.stat().st_size > 1_000_000:
            if cand.resolve() != cached_dest.resolve():
                try:
                    tmp_copy = cached_dest.with_suffix(".blend.part")
                    shutil.copy2(cand, tmp_copy)
                    tmp_copy.replace(cached_dest)
                    log("ASSETS", f"Cached family_ready.blend -> {cached_dest} (from {cand})")
                    return cached_dest
                except Exception as exc:
                    log("WARN", f"Could not copy family_ready.blend to cache ({exc}); using source directly: {cand}")
                    return cand
            return cand
    return None


def apply_post_camera_look(src_png: Path, dst_png: Optional[Path] = None, seed: int = 7) -> Path:
    """Apply the Zack-Blender-Pack `post.py` real-camera pass (soft lens, glow, vignette, film grain).

    Uses in-process Pillow+NumPy when available; falls back cleanly to system `python3` running
    `skills/blender-render-farm/scripts/post.py` (needed when invoked inside Blender's embedded Python).
    """
    target = dst_png or src_png
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError:
        import subprocess

        post_script = get_repo_root() / "skills" / "blender-render-farm" / "scripts" / "post.py"
        py_bin = shutil.which("python3") or shutil.which("python")
        if post_script.exists() and py_bin:
            res = subprocess.run(
                [py_bin, str(post_script), str(src_png), str(target)],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return target
            log("WARN", f"post.py subprocess failed ({res.stderr.strip()}); keeping raw render.")
        else:
            log("WARN", "Pillow not available in Blender Python and system post.py unavailable; skipping post pass.")
        return target

    im = Image.open(src_png).convert("RGB")
    w, h = im.size
    s = max(0.25, w / 1080.0)
    a = np.asarray(im, dtype=np.float32) / 255.0

    # 1. Soft lens: subtle optical blur blend (35%)
    soft = np.asarray(im.filter(ImageFilter.GaussianBlur(0.7 * s)), dtype=np.float32) / 255.0
    a = a * 0.65 + soft * 0.35

    # 2. Highlight glow / bloom (screen blend)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = np.clip((lum - 0.72) / 0.28, 0.0, 1.0)[..., None] * a
    glow_img = Image.fromarray((np.clip(bright, 0.0, 1.0) * 255.0).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(18.0 * s)
    )
    a = 1.0 - (1.0 - a) * (1.0 - (np.asarray(glow_img, dtype=np.float32) / 255.0) * 0.45)

    # 3. Vignette (28% corner falloff)
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx - w / 2.0) / (w / 2.0), (yy - h / 2.0) / (h / 2.0)) / np.sqrt(2.0)
    a *= (1.0 - 0.28 * np.clip((d - 0.35) / 0.65, 0.0, 1.0) ** 1.6)[..., None]

    # 4. Film grain (luma noise, slightly stronger in shadows)
    rng = np.random.default_rng(seed)
    n = rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
    n_u8 = (np.clip(n * 0.25 + 0.5, 0.0, 1.0) * 255.0).astype(np.uint8)
    n_blur = np.asarray(Image.fromarray(n_u8).filter(ImageFilter.GaussianBlur(0.6 * s)), dtype=np.float32) / 255.0 - 0.5
    a += (n_blur * 0.045 * (1.2 - np.clip(lum, 0.0, 1.0)))[..., None]

    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0).astype(np.uint8)).save(target)
    return target


def check_ffmpeg_available() -> str:
    """Return path to ffmpeg binary or raise clear error."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it via `sudo apt-get install -y ffmpeg`."
        )
    return ffmpeg_bin


def log(stage: str, message: str) -> None:
    print(f"[{stage}] {message}", flush=True)

