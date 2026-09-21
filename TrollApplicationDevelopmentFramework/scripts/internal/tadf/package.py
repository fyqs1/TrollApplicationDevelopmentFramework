from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import TrollAppConfig, load_config
from .generate import generate, snapshot_used_config


class PackageError(RuntimeError):
    pass


def package(cfg: TrollAppConfig, *, clean: bool = True) -> Path:
    generate(cfg)
    work = cfg.work_dir
    derived = work / "build"
    if clean and derived.exists():
        shutil.rmtree(derived)
    derived.mkdir(parents=True, exist_ok=True)

    _require("xcodegen")
    _require("xcodebuild")
    ldid = shutil.which("ldid") or shutil.which("ldid2")
    if not ldid:
        raise PackageError("ldid/ldid2 not found. brew install ldid")

    _run(
        [
            "xcodegen",
            "generate",
            "--spec",
            str(cfg.project_yml_file),
            "--project",
            str(work),
        ],
        cwd=work,
    )

    if cfg.packages:
        _run(
            [
                "xcodebuild",
                "-resolvePackageDependencies",
                "-project",
                str(cfg.xcodeproj),
                "-scheme",
                cfg.name,
                "-derivedDataPath",
                str(derived),
            ],
            cwd=work,
        )

    _run(
        [
            "xcodebuild",
            "-project",
            str(cfg.xcodeproj),
            "-scheme",
            cfg.name,
            "-configuration",
            "Release",
            "-sdk",
            "iphoneos",
            "-derivedDataPath",
            str(derived),
            "CODE_SIGNING_ALLOWED=NO",
            "CODE_SIGNING_REQUIRED=NO",
            "CODE_SIGN_IDENTITY=",
            "ONLY_ACTIVE_ARCH=NO",
            "build",
        ],
        cwd=work,
    )

    app = derived / "Build" / "Products" / "Release-iphoneos" / f"{cfg.name}.app"
    if not app.is_dir():
        raise PackageError(f"app not found at {app}")

    app_ents = cfg.entitlements_file
    shutil.copy2(app_ents, app / f"{cfg.name}.entitlements")
    binary = app / cfg.name
    _run([ldid, f"-S{app_ents}", str(binary)], cwd=work)
    _run([ldid, f"-S{app_ents}", str(app)], cwd=work)

    appex = app / "PlugIns" / "PacketTunnel.appex"
    if cfg.packet_tunnel.enabled:
        if not appex.is_dir():
            raise PackageError(f"PacketTunnel.appex not embedded at {appex}")
        tunnel_ents = cfg.tunnel_dir / "PacketTunnel.entitlements"
        shutil.copy2(tunnel_ents, appex / "PacketTunnel.entitlements")
        tunnel_bin = appex / "PacketTunnel"
        if tunnel_bin.exists():
            _run([ldid, f"-S{tunnel_ents}", str(tunnel_bin)], cwd=work)
        _run([ldid, f"-S{tunnel_ents}", str(appex)], cwd=work)
    elif appex.is_dir():
        print("warning: PacketTunnel.appex present but packet_tunnel is false")

    stage = derived / "ipa_stage"
    if stage.exists():
        shutil.rmtree(stage)
    payload = stage / "Payload"
    payload.mkdir(parents=True)
    shutil.copytree(app, payload / app.name)

    dist = cfg.root / cfg.dist_dir
    dist.mkdir(parents=True, exist_ok=True)
    ipa = cfg.ipa_path
    if ipa.exists():
        ipa.unlink()
    _run(["zip", "-qr", str(ipa), "Payload"], cwd=stage)
    snapshot_used_config(cfg)
    check = subprocess.run([ldid, "-e", str(binary)], cwd=work, capture_output=True, text=True)
    if check.returncode == 0 and check.stdout.strip():
        print("Entitlements check:")
        print("\n".join(check.stdout.splitlines()[:40]))
    return ipa


def package_from_path(config_path: Path, *, clean: bool = True) -> Path:
    return package(load_config(config_path), clean=clean)


def _require(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PackageError(f"{name} not found on PATH")
    return path


def _run(argv: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    proc = subprocess.run(argv, cwd=cwd, env=env, text=True)
    if proc.returncode != 0:
        raise PackageError(f"command failed ({proc.returncode}): {' '.join(argv)}")
