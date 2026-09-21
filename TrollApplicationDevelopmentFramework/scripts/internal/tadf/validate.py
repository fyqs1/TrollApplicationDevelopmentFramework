from __future__ import annotations

import shutil
from pathlib import Path

from . import SCHEMA_VERSION, __version__, capabilities as capmod
from .config import TrollAppConfig, load_config
from .render import app_entitlements


def validate(cfg: TrollAppConfig) -> list[str]:
    warnings: list[str] = []
    if cfg.schema_version != SCHEMA_VERSION:
        warnings.append(
            f"schema_version {cfg.schema_version} != TADF {SCHEMA_VERSION}; generate may still work"
        )
    if cfg.channel != "trollstore":
        raise ValueError("only channel: trollstore is supported")
    if not cfg.pack_path.is_dir():
        raise ValueError(f"pack_source directory missing: {cfg.source_dir}")
    siblings = [p.name for p in cfg.slot_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
    extra = [name for name in siblings if name != cfg.pack_source]
    if extra:
        warnings.append(
            f"App/ also contains {', '.join(extra)}; packing only {cfg.pack_source}"
        )
    if "fs_root" in cfg.capabilities and "unsandboxed" not in cfg.capabilities:
        warnings.append("fs_root should imply unsandboxed; check capability catalog")
    if cfg.packet_tunnel.enabled and "network_extension" not in cfg.capabilities:
        warnings.append("packet tunnel enabled but network_extension was not resolved")
    ents = app_entitlements(cfg)
    if ents.get("com.apple.private.security.no-sandbox") and not ents.get("platform-application"):
        warnings.append("no-sandbox without platform-application is unusual for TrollStore apps")
    if cfg.packages:
        warnings.append(
            "SPM packages are resolved at pack time from trollapp.yml; do not copy .xcodeproj"
        )
        mmp = any(
            "adjust" in pkg.url.lower() or "appsflyer" in pkg.url.lower()
            for pkg in cfg.packages
        )
        if mmp and "tracking" not in cfg.usage:
            warnings.append(
                "Adjust/AppsFlyer needs info.usage.tracking for NSUserTrackingUsageDescription"
            )
    return warnings


def doctor() -> list[str]:
    rows = [
        f"TADF {__version__}",
        f"schema {SCHEMA_VERSION}",
    ]
    for name in ("xcodegen", "ldid", "ldid2", "xcodebuild", "python3"):
        path = shutil.which(name)
        rows.append(f"{name}: {path or 'MISSING'}")
    catalog = capmod.load_catalog()
    rows.append("capabilities: " + ", ".join(sorted(catalog)))
    return rows


def validate_path(config_path: Path) -> tuple[TrollAppConfig, list[str]]:
    cfg = load_config(config_path)
    return cfg, validate(cfg)
