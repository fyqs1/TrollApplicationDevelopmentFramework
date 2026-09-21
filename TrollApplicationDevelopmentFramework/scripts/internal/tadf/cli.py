from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from . import FRAMEWORK_NAME, FRAMEWORK_SHORT, __version__, capabilities as capmod
from .config import find_config, load_config
from .generate import generate
from .package import PackageError, package
from .render import app_entitlements, tunnel_entitlements
from .validate import doctor, validate
from . import _yaml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tadf",
        description=f"{FRAMEWORK_NAME} — used by scripts/package_ipa.sh",
    )
    parser.add_argument("--version", action="version", version=f"{FRAMEWORK_SHORT} {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("generate", help="write entitlements / Info.plist / project.yml")
    p_gen.add_argument("--config", type=Path, default=None)

    p_env = sub.add_parser("env", help="print shell assignments for package_ipa.sh")
    p_env.add_argument("--config", type=Path, default=None)

    p_pkg = sub.add_parser("package", help="internal fallback packer")
    p_pkg.add_argument("--config", type=Path, default=None)
    p_pkg.add_argument("--no-clean", action="store_true")

    p_val = sub.add_parser("validate")
    p_val.add_argument("--config", type=Path, default=None)

    sub.add_parser("capabilities")
    sub.add_parser("doctor")

    p_show = sub.add_parser("show")
    p_show.add_argument("--config", type=Path, default=None)
    p_show.add_argument("--tunnel", action="store_true")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except (FileNotFoundError, ValueError, PackageError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.cmd == "capabilities":
        catalog = capmod.load_catalog()
        for cap_id, cap in catalog.items():
            extra = f" (implies: {', '.join(cap.implies)})" if cap.implies else ""
            print(f"{cap_id:20} {cap.title}{extra}")
        return 0

    if args.cmd == "doctor":
        for line in doctor():
            print(line)
        return 0

    config_path = find_config(args.config)
    cfg = load_config(config_path)

    if args.cmd == "env":
        values = {
            "TADF_NAME": cfg.name,
            "TADF_SLOT": cfg.slot_dir,
            "TADF_PACK_SOURCE": cfg.pack_source,
            "TADF_SOURCE_DIR": cfg.source_dir,
            "TADF_WORK": f"work/{cfg.pack_source}",
            "TADF_DIST": cfg.dist_dir,
            "TADF_BUNDLE_ID": cfg.bundle_id,
            "TADF_TUNNEL": "1" if cfg.packet_tunnel.enabled else "0",
            "TADF_PACKAGES": "1" if cfg.packages else "0",
        }
        for key, value in values.items():
            print(f"{key}={shlex.quote(str(value))}")
        return 0

    if args.cmd == "validate":
        warnings = validate(cfg)
        print(f"config     {cfg.path}")
        print(f"app        {cfg.name} ({cfg.bundle_id})")
        print(f"slot       {cfg.slot_dir}/")
        print(f"pack_source {cfg.pack_source}")
        print(f"source     {cfg.source_dir}")
        print(f"work       work/{cfg.pack_source}/")
        print(f"dist       {cfg.dist_dir}/")
        print(f"capabilities {', '.join(cfg.capabilities)}")
        print(f"tunnel     {cfg.packet_tunnel.enabled}")
        if cfg.packages:
            listed = ", ".join(
                f"{pkg.name}:" + "/".join(pkg.products) for pkg in cfg.packages
            )
            print(f"packages   {listed}")
        for warning in warnings:
            print(f"warning: {warning}")
        print("ok")
        return 0

    if args.cmd == "show":
        data = tunnel_entitlements(cfg) if args.tunnel else app_entitlements(cfg)
        sys.stdout.write(_yaml.dump(data))
        return 0

    if args.cmd == "generate":
        written = generate(cfg)
        print(f"generated from {cfg.path}")
        for item in written:
            print(f"  {item}")
        return 0

    if args.cmd == "package":
        ipa = package(cfg, clean=not args.no_clean)
        print(f"ok: {ipa}")
        return 0

    raise ValueError(f"unknown command {args.cmd}")
