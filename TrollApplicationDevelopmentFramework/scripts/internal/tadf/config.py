from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, _yaml, capabilities as capmod
from .paths import USED_CONFIG_NAME, WORK_DIR


BUNDLE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z][A-Za-z0-9-]*)+$")
APP_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
PACK_SOURCE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
KNOWN_CHANNELS = ("trollstore",)
SLOT_DIR = "App"
PLACEHOLDER_NAME = "HelloTroll"
DIST_NAME = "dist"


@dataclass
class SwiftPackage:
    name: str
    products: list[str]
    url: str = ""
    path: str = ""
    from_version: str = ""
    exact: str = ""
    branch: str = ""
    revision: str = ""


@dataclass
class PacketTunnelConfig:
    enabled: bool = False
    bundle_suffix: str = "PacketTunnel"
    display_name: str = ""

    def bundle_id(self, app_bundle_id: str) -> str:
        return f"{app_bundle_id}.{self.bundle_suffix}"


@dataclass
class TrollAppConfig:
    path: Path
    root: Path
    schema_version: int
    name: str
    display_name: str
    bundle_id: str
    version: str
    build: str
    min_ios: str
    team_id: str
    channel: str
    capabilities: list[str]
    packet_tunnel: PacketTunnelConfig
    slot_dir: str
    pack_source: str
    source_dir: str
    dist_dir: str
    sources: list[str]
    bridging_header: str | None
    swift_version: str
    frameworks: list[str]
    libraries: list[str]
    ldflags: list[str]
    packages: list[SwiftPackage]
    query_schemes: list[str]
    usage: dict[str, str]
    extra_entitlements: dict[str, Any] = field(default_factory=dict)
    extra_tunnel_entitlements: dict[str, Any] = field(default_factory=dict)
    extra_info: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def product_name(self) -> str:
        return self.name

    @property
    def executable(self) -> str:
        return self.name

    @property
    def slot_path(self) -> Path:
        return self.root / self.slot_dir

    @property
    def pack_path(self) -> Path:
        return self.root / self.source_dir

    @property
    def work_dir(self) -> Path:
        return self.root / WORK_DIR / self.pack_source

    @property
    def generated_dir(self) -> Path:
        return self.work_dir / "Generated"

    @property
    def project_yml_file(self) -> Path:
        return self.work_dir / "project.yml"

    @property
    def used_config_file(self) -> Path:
        return self.work_dir / USED_CONFIG_NAME

    @property
    def tunnel_dir(self) -> Path:
        return self.work_dir / "PacketTunnel"

    @property
    def ipa_path(self) -> Path:
        return self.root / self.dist_dir / f"{self.name}.ipa"

    @property
    def entitlements_file(self) -> Path:
        return self.generated_dir / f"{self.name}.entitlements"

    @property
    def info_plist_file(self) -> Path:
        return self.generated_dir / "Info.plist"

    @property
    def xcodeproj(self) -> Path:
        return self.work_dir / f"{self.name}.xcodeproj"


def load_config(path: Path) -> TrollAppConfig:
    path = path.resolve()
    data = _yaml.load_path(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a mapping")
    app = data.get("app") or {}
    if not isinstance(app, dict):
        raise ValueError("app: must be a mapping")
    name = str(app.get("name") or "").strip()
    bundle_id = str(app.get("bundle_id") or "").strip()
    if not APP_NAME_RE.match(name):
        raise ValueError("app.name must be a Swift/Xcode product name: letters, digits, underscore")
    if not BUNDLE_ID_RE.match(bundle_id):
        raise ValueError("app.bundle_id must be a reverse-DNS identifier")

    schema_version = int(data.get("schema_version") or SCHEMA_VERSION)
    if schema_version > SCHEMA_VERSION:
        raise ValueError(
            f"trollapp.yml schema_version {schema_version} is newer than TADF {SCHEMA_VERSION}"
        )

    channel = str(data.get("channel") or "trollstore").strip()
    if channel not in KNOWN_CHANNELS:
        raise ValueError(f"unsupported channel {channel!r}; known: {', '.join(KNOWN_CHANNELS)}")

    requested = list(data.get("capabilities") or [])
    catalog = capmod.load_catalog()
    resolved = capmod.resolve(requested, catalog)

    ext_raw = data.get("packet_tunnel")
    if ext_raw is None:
        ext_raw = (data.get("extensions") or {}).get("packet_tunnel")
    if ext_raw is None:
        ext_raw = {}
    if isinstance(ext_raw, bool):
        ext_raw = {"enabled": ext_raw}
    packet_tunnel = PacketTunnelConfig(
        enabled=bool(ext_raw.get("enabled", False)),
        bundle_suffix=str(ext_raw.get("bundle_suffix") or "PacketTunnel"),
        display_name=str(ext_raw.get("display_name") or ""),
    )
    if packet_tunnel.enabled and "network_extension" not in resolved:
        resolved = capmod.resolve(resolved + ["network_extension"], catalog)
    if packet_tunnel.enabled and not packet_tunnel.display_name:
        packet_tunnel.display_name = f"{app.get('display_name') or name} Tunnel"

    root = _framework_root(path)
    slot_dir = str(data.get("slot") or SLOT_DIR).strip() or SLOT_DIR
    if "/" in slot_dir or slot_dir in (".", "..") or slot_dir == WORK_DIR:
        raise ValueError("slot must be a single directory name at the framework root")
    pack_source = str(data.get("pack_source") or PLACEHOLDER_NAME).strip()
    if not PACK_SOURCE_RE.match(pack_source):
        raise ValueError(
            "pack_source must be a single folder name under App/ (letters, digits, _-)"
        )
    source_dir = f"{slot_dir}/{pack_source}"
    pack_path = root / slot_dir / pack_source
    if not pack_path.is_dir():
        available = _list_slot_dirs(root / slot_dir)
        hint = f" available: {', '.join(available)}" if available else " (slot is empty)"
        raise ValueError(
            f"pack_source {pack_source!r} not found at {slot_dir}/{pack_source}.{hint}"
        )

    work_dir = root / WORK_DIR / pack_source
    rel_source = _posix_rel(work_dir, pack_path)
    sources = [rel_source, "Generated"]
    dist_dir = f"{WORK_DIR}/{pack_source}/{DIST_NAME}"

    frameworks = [str(item) for item in (data.get("frameworks") or [])]
    for cap_id in resolved:
        for fw in catalog[cap_id].frameworks:
            if fw not in frameworks:
                frameworks.append(fw)

    info = data.get("info") or {}
    usage = {str(k): str(v) for k, v in (info.get("usage") or {}).items()}
    for cap_id in resolved:
        for usage_key in catalog[cap_id].usage_keys:
            usage.setdefault(usage_key, _default_usage(usage_key))

    bridging = data.get("bridging_header")
    bridging_header = None
    if bridging:
        header = Path(str(bridging))
        if header.is_absolute():
            bridging_header = str(header)
        else:
            bridging_header = _posix_rel(work_dir, root / header)

    packages = _parse_packages(data.get("packages") or [], root, work_dir)
    ldflags = [str(item) for item in (data.get("ldflags") or [])]

    return TrollAppConfig(
        path=path,
        root=root,
        schema_version=schema_version,
        name=name,
        display_name=str(app.get("display_name") or name),
        bundle_id=bundle_id,
        version=str(app.get("version") or "1.0.0"),
        build=str(app.get("build") or "1"),
        min_ios=str(app.get("min_ios") or "15.0"),
        team_id=str(app.get("team_id") or "FYQS"),
        channel=channel,
        capabilities=resolved,
        packet_tunnel=packet_tunnel,
        slot_dir=slot_dir,
        pack_source=pack_source,
        source_dir=source_dir,
        dist_dir=dist_dir,
        sources=sources,
        bridging_header=bridging_header,
        swift_version=str(data.get("swift_version") or "5.0"),
        frameworks=frameworks,
        libraries=[str(item) for item in (data.get("libraries") or [])],
        ldflags=ldflags,
        packages=packages,
        query_schemes=[str(item) for item in (info.get("query_schemes") or [])],
        usage=usage,
        extra_entitlements=dict(data.get("extra_entitlements") or {}),
        extra_tunnel_entitlements=dict(data.get("extra_tunnel_entitlements") or {}),
        extra_info=dict(info.get("extra") or {}),
        raw=data,
    )


def find_config(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    if start.is_file():
        return start
    search = [start, *start.parents]
    for directory in search:
        candidate = directory / "trollapp.yml"
        if candidate.is_file():
            nested_work = directory.parent.name == WORK_DIR
            at_framework = (directory / "scripts" / "package_ipa.sh").is_file()
            if nested_work and not at_framework:
                continue
            return candidate
        if (directory / "scripts" / "package_ipa.sh").is_file() and directory != start:
            break
    raise FileNotFoundError("trollapp.yml not found; run from the framework root")


def _framework_root(config_path: Path) -> Path:
    start = config_path.parent if config_path.is_file() else config_path
    for directory in [start, *start.parents]:
        if (directory / "scripts" / "package_ipa.sh").is_file() and (directory / SLOT_DIR).is_dir():
            return directory
    raise ValueError(f"cannot find TADF root from {config_path}")


def _posix_rel(from_dir: Path, to: Path) -> str:
    return Path(os.path.relpath(to, from_dir)).as_posix()


def _parse_packages(raw: Any, root: Path, work_dir: Path) -> list[SwiftPackage]:
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                raise ValueError("packages list items must be mappings with name/url/product")
            items.append(entry)
    elif isinstance(raw, dict):
        for name, body in raw.items():
            if body is None:
                body = {}
            if not isinstance(body, dict):
                raise ValueError(f"packages.{name} must be a mapping")
            merged = dict(body)
            merged.setdefault("name", name)
            items.append(merged)
    else:
        raise ValueError("packages: must be a list or mapping")

    packages: list[SwiftPackage] = []
    seen: set[str] = set()
    for entry in items:
        name = str(entry.get("name") or "").strip()
        if not PACKAGE_NAME_RE.match(name):
            raise ValueError("packages.name must be letters, digits, _-")
        if name in seen:
            raise ValueError(f"duplicate package name {name!r}")
        seen.add(name)

        products_raw = entry.get("products")
        if products_raw is None and entry.get("product") is not None:
            products_raw = [entry.get("product")]
        products = [str(item).strip() for item in (products_raw or []) if str(item).strip()]
        if not products:
            raise ValueError(f"package {name!r} needs product or products")

        url = str(entry.get("url") or "").strip()
        path_raw = str(entry.get("path") or "").strip()
        if bool(url) == bool(path_raw):
            raise ValueError(f"package {name!r} needs exactly one of url or path")

        rel_path = ""
        if path_raw:
            local = Path(path_raw)
            resolved = local if local.is_absolute() else (root / local)
            if not resolved.exists():
                raise ValueError(f"package {name!r} path not found: {resolved}")
            rel_path = _posix_rel(work_dir, resolved)
        elif not (url.startswith("https://") or url.startswith("http://") or url.startswith("git@")):
            raise ValueError(f"package {name!r} url must be a git URL")

        packages.append(
            SwiftPackage(
                name=name,
                products=products,
                url=url,
                path=rel_path,
                from_version=str(entry.get("from") or "").strip(),
                exact=str(entry.get("exact") or entry.get("exactVersion") or "").strip(),
                branch=str(entry.get("branch") or "").strip(),
                revision=str(entry.get("revision") or "").strip(),
            )
        )
    return packages


def _list_slot_dirs(slot: Path) -> list[str]:
    if not slot.is_dir():
        return []
    names = [p.name for p in sorted(slot.iterdir()) if p.is_dir() and not p.name.startswith(".")]
    return names


def _default_usage(key: str) -> str:
    defaults = {
        "location": "Location permission is required by iOS to show the current Wi-Fi name (SSID).",
        "local_network": "Used to read local network interface information.",
        "camera": "Only used to show camera permission status.",
        "microphone": "Only used to show microphone permission status.",
        "photos": "Only used to show photo library permission status.",
        "tracking": "Used only to display advertising identifier status. No ads are shown.",
    }
    return defaults.get(key, f"Required for {key} capability.")
