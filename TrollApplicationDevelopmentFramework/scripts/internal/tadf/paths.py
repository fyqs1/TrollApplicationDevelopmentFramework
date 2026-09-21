from __future__ import annotations

from pathlib import Path

WORK_DIR = "work"
USED_CONFIG_NAME = "trollapp.used.yml"


def framework_root() -> Path:
    # scripts/internal/tadf/paths.py → framework root
    return Path(__file__).resolve().parents[3]


def capabilities_dir() -> Path:
    return framework_root() / "scripts" / "internal" / "capabilities"


def templates_dir() -> Path:
    return framework_root() / "scripts" / "internal" / "templates"
