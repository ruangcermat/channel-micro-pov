#!/usr/bin/env python3
"""Universal Camera Look Post-Processing Pass (`Jadi Apa` Studio Core).

Wraps `skills/blender-render-farm/scripts/post.py` (soft lens 35%, subtle glow on
bright highlights, natural lens vignette, luma film grain) with automatic system Python
fallback when invoked from inside Blender's bundled Python (which lacks Pillow).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def apply_camera_look(
    src_path: Path,
    dst_path: Optional[Path] = None,
    seed: int = 7,
) -> Path:
    """Apply `post.py` camera finish to a rendered PNG frame."""
    dst = dst_path or src_path
    post_script = _repo_root() / "skills" / "blender-render-farm" / "scripts" / "post.py"
    if not post_script.exists():
        return dst

    try:
        from PIL import Image  # noqa: F401
        import importlib.util

        spec = importlib.util.spec_from_file_location("zack_post", str(post_script))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.grade(str(src_path), str(dst), seed=seed)
            return dst
    except Exception:
        pass

    py_bin = shutil.which("python3")
    if not py_bin:
        return dst
    try:
        subprocess.run(
            [py_bin, str(post_script), str(src_path), str(dst)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except Exception as exc:
        print(f"[POST_WARN] post.py skipped on {src_path.name}: {exc}", flush=True)
    return dst
