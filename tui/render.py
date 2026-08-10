"""Plain-text rendering for the TUI — stdlib only, matching callosum's no-TUI-deps house style."""

from __future__ import annotations

import json
from typing import Any

MAX_CELL = 60
TABLE_COLUMNS = 6


def to_json(data: Any) -> str:
    if isinstance(data, (bytes, bytearray)):
        return json.dumps({"binary_bytes": len(data)})
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = ", ".join(str(v) for v in value[:4]) + ("…" if len(value) > 4 else "")
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    text = text.replace("\n", " ")
    return text[: MAX_CELL - 1] + "…" if len(text) > MAX_CELL else text


def table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no results)"
    # Column order: first row's key order, capped so wide models stay readable.
    cols = list(rows[0].keys())[:TABLE_COLUMNS]
    widths = {c: len(c) for c in cols}
    rendered = []
    for row in rows:
        r = {c: _cell(row.get(c)) for c in cols}
        for c in cols:
            widths[c] = max(widths[c], len(r[c]))
        rendered.append(r)
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    lines = [header, sep]
    lines += ["  ".join(r[c].ljust(widths[c]) for c in cols) for r in rendered]
    if len(rows[0].keys()) > TABLE_COLUMNS:
        lines.append(f"(+{len(rows[0].keys()) - TABLE_COLUMNS} more fields — use --format json)")
    return "\n".join(lines)


def detail(data: dict[str, Any]) -> str:
    width = max((len(k) for k in data), default=0)
    lines = []
    for k, v in data.items():
        if isinstance(v, (dict, list)) and v:
            v = json.dumps(v, ensure_ascii=False, default=str)
        lines.append(
            f"{k.rjust(width)}  {_cell(v) if not isinstance(v, str) else (v[:200] + '…' if len(str(v)) > 200 else v)}"
        )
    return "\n".join(lines) if lines else "(empty)"


def render(data: Any, fmt: str = "table") -> str:
    if fmt == "json":
        return to_json(data)
    if isinstance(data, (bytes, bytearray)):
        return f"(binary response, {len(data)} bytes — use --out FILE to save it)"
    if isinstance(data, list):
        if data and all(isinstance(r, dict) for r in data):
            return table(data)
        return "\n".join(str(x) for x in data) if data else "(no results)"
    if isinstance(data, dict):
        # A list wrapped in an envelope ({items: [...]}) renders as its table + the rest as detail.
        for key in ("items", "results", "papers", "hits", "suggestions", "gaps", "writes"):
            inner = data.get(key)
            if isinstance(inner, list) and inner and all(isinstance(r, dict) for r in inner):
                rest = {k: v for k, v in data.items() if k != key}
                head = detail(rest) + "\n\n" if rest else ""
                return head + table(inner)
        return detail(data)
    return str(data)
