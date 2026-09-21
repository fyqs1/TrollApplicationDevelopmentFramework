from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _yaml
from .paths import capabilities_dir


@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    summary: str
    entitlements: dict[str, Any] = field(default_factory=dict)
    tunnel_entitlements: dict[str, Any] = field(default_factory=dict)
    implies: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    usage_keys: tuple[str, ...] = ()


def load_catalog() -> dict[str, Capability]:
    catalog: dict[str, Capability] = {}
    root = capabilities_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"capability catalog missing: {root}")
    for path in sorted(root.glob("*.yml")):
        data = _yaml.load_path(path) or {}
        cap_id = str(data.get("id") or path.stem)
        catalog[cap_id] = Capability(
            id=cap_id,
            title=str(data.get("title") or cap_id),
            summary=str(data.get("summary") or ""),
            entitlements=dict(data.get("entitlements") or {}),
            tunnel_entitlements=dict(data.get("tunnel_entitlements") or {}),
            implies=tuple(data.get("implies") or []),
            frameworks=tuple(data.get("frameworks") or []),
            usage_keys=tuple(data.get("usage_keys") or []),
        )
    return catalog


def resolve(requested: list[str], catalog: dict[str, Capability] | None = None) -> list[str]:
    catalog = catalog or load_catalog()
    unknown = [item for item in requested if item not in catalog]
    if unknown:
        known = ", ".join(sorted(catalog))
        raise ValueError(f"unknown capabilities: {', '.join(unknown)} (known: {known})")
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(cap_id: str) -> None:
        if cap_id in seen:
            return
        seen.add(cap_id)
        for implied in catalog[cap_id].implies:
            visit(implied)
        ordered.append(cap_id)

    for cap_id in requested:
        visit(cap_id)
    return ordered


def merge_entitlements(values: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in values:
        for key, value in item.items():
            if key not in merged:
                merged[key] = _clone(value)
                continue
            merged[key] = _merge_value(merged[key], value)
    return merged


def _merge_value(left: Any, right: Any) -> Any:
    if isinstance(left, dict) and isinstance(right, dict):
        out = dict(left)
        for key, value in right.items():
            out[key] = _merge_value(out[key], value) if key in out else _clone(value)
        return out
    if isinstance(left, list) and isinstance(right, list):
        out = list(left)
        for item in right:
            if item not in out:
                out.append(item)
        return out
    if isinstance(left, bool) and isinstance(right, bool):
        return left or right
    return _clone(right)


def _clone(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value


def swift_flag_name(cap_id: str) -> str:
    parts = [part for part in cap_id.replace("-", "_").split("_") if part]
    return "has" + "".join(part[:1].upper() + part[1:] for part in parts)
