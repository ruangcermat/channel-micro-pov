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
