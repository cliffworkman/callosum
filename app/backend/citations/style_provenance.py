"""Durable local provenance for user-installed citation styles."""

from __future__ import annotations

import json
import os
import stat
import threading
from datetime import datetime, timezone
from typing import Any

from app.backend.citations import style_store

_VERSION = 1
_SOURCE_TYPES = {"local_file", "repository", "url", "duplicate", "personal"}
_lock = threading.RLock()


def _path():
    return style_store.custom_styles_dir() / "provenance.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: object, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:maximum] if value else None


def _clean_record(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("source_type") not in _SOURCE_TYPES:
        return None
    record: dict[str, Any] = {"source_type": value["source_type"]}
    limits = {
        "source_url": 2048,
        "source_name": 255,
        "repository_id": 200,
        "source_style_id": 120,
        "source_canonical_id": 500,
        "installed_at": 40,
        "updated_at": 40,
        "last_checked_at": 40,
        "locally_modified_at": 40,
        "upstream_updated": 80,
    }
    for key, maximum in limits.items():
        cleaned = _text(value.get(key), maximum)
        if cleaned:
            record[key] = cleaned
    return record


def _load_unlocked() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _VERSION or not isinstance(data.get("styles"), dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for style_id, value in data["styles"].items():
        cleaned = _clean_record(value)
        if (
            isinstance(style_id, str)
            and style_store.STYLE_ID_PATTERN.fullmatch(style_id)
            and style_id.startswith("custom-")
            and cleaned
        ):
            out[style_id] = cleaned
    return out


def _write_unlocked(styles: dict[str, dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"version": _VERSION, "styles": styles}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def provenance_for(style_id: str) -> dict[str, Any] | None:
    with _lock:
        record = _load_unlocked().get(style_id)
        return dict(record) if record else None


def record_install(
    style_id: str,
    *,
    source_type: str,
    source_url: str | None = None,
    source_name: str | None = None,
    repository_id: str | None = None,
    source_style_id: str | None = None,
    source_canonical_id: str | None = None,
    upstream_updated: str | None = None,
) -> dict[str, Any]:
    if (
        source_type not in _SOURCE_TYPES
        or not style_id.startswith("custom-")
        or not style_store.STYLE_ID_PATTERN.fullmatch(style_id)
    ):
        raise ValueError("invalid citation-style provenance")
    now = _now()
    with _lock:
        styles = _load_unlocked()
        previous = styles.get(style_id, {})
        same_source = previous.get("source_type") == source_type
        record = _clean_record(
            {
                "source_type": source_type,
                "source_url": source_url,
                "source_name": (str(source_name or "").replace("\\", "/").rsplit("/", 1)[-1] if source_name else None),
                "repository_id": repository_id,
                "source_style_id": source_style_id,
                "source_canonical_id": source_canonical_id,
                "installed_at": previous.get("installed_at") if same_source else now,
                "updated_at": now,
                "last_checked_at": now if source_type in {"repository", "url"} else None,
                "upstream_updated": upstream_updated,
            }
        )
        assert record is not None
        styles[style_id] = record
        _write_unlocked(styles)
        return dict(record)


def record_check(style_id: str, *, upstream_updated: str | None = None) -> dict[str, Any]:
    with _lock:
        styles = _load_unlocked()
        record = styles.get(style_id)
        if record is None or record.get("source_type") not in {"repository", "url"}:
            raise ValueError("This citation style has no remote source to check")
        record["last_checked_at"] = _now()
        if upstream_updated:
            record["upstream_updated"] = upstream_updated[:80]
        styles[style_id] = record
        _write_unlocked(styles)
        return dict(record)


def record_edit(style_id: str) -> dict[str, Any]:
    """Keep original lineage while marking that the installed XML now has local edits."""
    if not style_id.startswith("custom-") or not style_store.STYLE_ID_PATTERN.fullmatch(style_id):
        raise ValueError("invalid personal citation style")
    now = _now()
    with _lock:
        styles = _load_unlocked()
        record = styles.get(style_id) or {
            "source_type": "personal",
            "installed_at": now,
        }
        record["updated_at"] = now
        record["locally_modified_at"] = now
        cleaned = _clean_record(record)
        assert cleaned is not None
        styles[style_id] = cleaned
        _write_unlocked(styles)
        return dict(cleaned)


def remove_provenance(style_id: str) -> None:
    with _lock:
        styles = _load_unlocked()
        if styles.pop(style_id, None) is not None:
            _write_unlocked(styles)
