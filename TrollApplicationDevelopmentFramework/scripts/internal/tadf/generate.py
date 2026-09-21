from __future__ import annotations

import shutil
from pathlib import Path

from .config import TrollAppConfig, load_config
from .paths import templates_dir
from .render import (
    app_entitlements,
    capabilities_swift,
    info_plist,
    project_yml,
    tunnel_entitlements,
    tunnel_info_plist,
    write_plist,
)


def generate(cfg: TrollAppConfig) -> list[Path]:
    written: list[Path] = []
    work = cfg.work_dir
    generated_dir = cfg.generated_dir
    generated_dir.mkdir(parents=True, exist_ok=True)

    entitlements_path = cfg.entitlements_file
    write_plist(entitlements_path, app_entitlements(cfg))
    written.append(entitlements_path)

    info_path = cfg.info_plist_file
    write_plist(info_path, info_plist(cfg))
    written.append(info_path)

    swift_path = generated_dir / "Capabilities.generated.swift"
    swift_path.write_text(capabilities_swift(cfg), encoding="utf-8")
    written.append(swift_path)

    project_path = cfg.project_yml_file
    project_path.write_text(project_yml(cfg), encoding="utf-8")
    written.append(project_path)

    if cfg.packet_tunnel.enabled:
        tunnel_dir = cfg.tunnel_dir
        tunnel_dir.mkdir(parents=True, exist_ok=True)
        t_ent = tunnel_dir / "PacketTunnel.entitlements"
        write_plist(t_ent, tunnel_entitlements(cfg))
        written.append(t_ent)
        t_info = tunnel_dir / "Info.plist"
        write_plist(t_info, tunnel_info_plist(cfg))
        written.append(t_info)
        provider = tunnel_dir / "PacketTunnelProvider.swift"
        if not provider.exists():
            template = templates_dir() / "PacketTunnel" / "PacketTunnelProvider.swift"
            provider.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
            written.append(provider)

    return written


def snapshot_used_config(cfg: TrollAppConfig) -> Path:
    dest = cfg.used_config_file
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = cfg.path
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def generate_from_path(config_path: Path) -> list[Path]:
    return generate(load_config(config_path))
