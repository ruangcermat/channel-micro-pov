#!/usr/bin/env python3
"""Compatibility shim re-exporting universal MPFB2 & Mas Dimas helpers from `03_pipeline/core/mpfb_helpers.py`."""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from core.mpfb_helpers import *  # noqa: F401, F403
