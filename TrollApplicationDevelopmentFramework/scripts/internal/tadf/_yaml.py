"""Minimal YAML 1.1 subset loader/dumper for TADF configs (no PyYAML)."""

from __future__ import annotations

from typing import Any


def load(text: str) -> Any:
    lines = _preprocess(text)
    if not lines:
        return None
    value, _ = _parse_block(lines, 0, 0)
    return value


def load_path(path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return load(handle.read())


def dump(data: Any) -> str:
    return _dump(data, 0).rstrip() + "\n"


def _preprocess(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if "\t" in line[:indent]:
            raise ValueError("YAML tabs are not supported; use spaces")
        out.append((indent, line.strip()))
    return out


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_block(lines: list[tuple[int, str]], idx: int, indent: int) -> tuple[Any, int]:
    if idx >= len(lines):
        return None, idx
    cur_indent, content = lines[idx]
    if cur_indent < indent:
        return None, idx
    if content.startswith("- "):
        return _parse_list(lines, idx, cur_indent)
    return _parse_map(lines, idx, cur_indent)


def _parse_map(lines: list[tuple[int, str]], idx: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while idx < len(lines):
        cur_indent, content = lines[idx]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"Unexpected indent at: {content}")
        if content.startswith("- "):
            raise ValueError(f"Expected mapping key, got list item: {content}")
        key, sep, rest = content.partition(":")
        if not sep:
            raise ValueError(f"Expected 'key:' at: {content}")
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            result[key] = _parse_scalar(rest)
            continue
        if idx >= len(lines) or lines[idx][0] <= indent:
            result[key] = {}
            continue
        child_indent = lines[idx][0]
        if child_indent <= indent:
            result[key] = {}
            continue
        value, idx = _parse_block(lines, idx, child_indent)
        result[key] = value
    return result, idx


def _parse_list(lines: list[tuple[int, str]], idx: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while idx < len(lines):
        cur_indent, content = lines[idx]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"Unexpected indent at: {content}")
        if not content.startswith("- "):
            break
        rest = content[2:].strip()
        idx += 1
        if rest == "":
            if idx < len(lines) and lines[idx][0] > indent:
                value, idx = _parse_block(lines, idx, lines[idx][0])
                result.append(value)
            else:
                result.append(None)
            continue
        if rest.endswith(":") and not rest.startswith("{") and ":" in rest:
            key = rest[:-1].strip()
            nested: dict[str, Any] = {}
            if idx < len(lines) and lines[idx][0] > indent:
                value, idx = _parse_block(lines, idx, lines[idx][0])
                nested[key] = value
            else:
                nested[key] = {}
            result.append(nested)
            continue
        if ":" in rest and not rest.startswith(("{", "[", "'", '"')):
            # inline map item: `- key: value`
            key, _, val = rest.partition(":")
            item: dict[str, Any] = {key.strip(): _parse_scalar(val.strip())}
            if idx < len(lines) and lines[idx][0] > indent:
                extra, idx = _parse_block(lines, idx, lines[idx][0])
                if isinstance(extra, dict):
                    item.update(extra)
                else:
                    raise ValueError("Nested value under list map must be a mapping")
            result.append(item)
            continue
        result.append(_parse_scalar(rest))
        if idx < len(lines) and lines[idx][0] > indent:
            extra, idx = _parse_block(lines, idx, lines[idx][0])
            last = result[-1]
            if isinstance(last, str) and isinstance(extra, dict):
                result[-1] = {last: extra}
            elif isinstance(last, dict) and isinstance(extra, dict):
                last.update(extra)
            else:
                raise ValueError(f"Cannot attach nested block to {last!r}")
    return result, idx


def _parse_scalar(text: str) -> Any:
    if text == "" or text in ("null", "Null", "NULL", "~"):
        return None
    if text in ("true", "True", "TRUE", "yes", "Yes"):
        return True
    if text in ("false", "False", "FALSE", "no", "No"):
        return False
    if (len(text) >= 2) and (
        (text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")
    ):
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in _split_flow(inner)]
    if text.startswith("{") and text.endswith("}"):
        inner = text[1:-1].strip()
        if not inner:
            return {}
        mapping: dict[str, Any] = {}
        for part in _split_flow(inner):
            key, sep, val = part.partition(":")
            if not sep:
                raise ValueError(f"Invalid flow mapping entry: {part}")
            mapping[key.strip()] = _parse_scalar(val.strip())
        return mapping
    if text.startswith("0x"):
        try:
            return int(text, 16)
        except ValueError:
            return text
    try:
        if text.startswith("0") and len(text) > 1 and text.isdigit():
            return text
        return int(text)
    except ValueError:
        pass
    try:
        if "." in text or "e" in text.lower():
            return float(text)
    except ValueError:
        pass
    return text


def _split_flow(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch in "[({":
            depth += 1
            buf.append(ch)
            continue
        if ch in "])}":
            depth -= 1
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _dump(data: Any, indent: int) -> str:
    pad = "  " * indent
    if isinstance(data, dict):
        if not data:
            return "{}\n" if indent == 0 else "{}\n"
        chunks: list[str] = []
        for key, value in data.items():
            key_s = str(key)
            if isinstance(value, dict):
                if not value:
                    chunks.append(f"{pad}{key_s}: {{}}\n")
                else:
                    chunks.append(f"{pad}{key_s}:\n{_dump(value, indent + 1)}")
            elif isinstance(value, list):
                if not value:
                    chunks.append(f"{pad}{key_s}: []\n")
                else:
                    chunks.append(f"{pad}{key_s}:\n{_dump(value, indent + 1)}")
            else:
                chunks.append(f"{pad}{key_s}: {_dump_scalar(value)}\n")
        return "".join(chunks)
    if isinstance(data, list):
        if not data:
            return "[]\n"
        chunks = []
        for item in data:
            if isinstance(item, dict):
                if not item:
                    chunks.append(f"{pad}- {{}}\n")
                    continue
                first = True
                for key, value in item.items():
                    prefix = f"{pad}- " if first else f"{pad}  "
                    first = False
                    if isinstance(value, (dict, list)) and value:
                        chunks.append(f"{prefix}{key}:\n{_dump(value, indent + 2)}")
                    elif isinstance(value, dict):
                        chunks.append(f"{prefix}{key}: {{}}\n")
                    elif isinstance(value, list):
                        chunks.append(f"{prefix}{key}: []\n")
                    else:
                        chunks.append(f"{prefix}{key}: {_dump_scalar(value)}\n")
            elif isinstance(item, list):
                chunks.append(f"{pad}-\n{_dump(item, indent + 1)}")
            else:
                chunks.append(f"{pad}- {_dump_scalar(item)}\n")
        return "".join(chunks)
    return f"{pad}{_dump_scalar(data)}\n"


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if (
        text == ""
        or any(ch in text for ch in ":#{}[]&*!|>%@`")
        or text in ("true", "false", "null", "yes", "no")
        or (text.count(".") >= 1 and all(part.isdigit() for part in text.split(".")))
    ):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text
