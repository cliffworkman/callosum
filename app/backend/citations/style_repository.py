"""Explicit CSL repository search/install and guarded import-by-URL.

The CSL project directs users to the Zotero Style Repository, whose public index mirrors the official CSL
repository's validated 1.0.2 styles. Repository search downloads only that fixed index after an explicit search;
URL import fetches only after an explicit install action. Neither path sends library content or uses the AI
egress toggle.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.backend.citations import style_store
from app.backend.citations.style_fetch import (
    MAX_URL_LENGTH as MAX_URL_LENGTH,
)
from app.backend.citations.style_fetch import (
    BytesFetcher,
    HostResolver,
    StyleFetchError,
)
from app.backend.citations.style_fetch import (
    httpx_fetcher as _httpx_fetcher,
)
from app.backend.citations.style_fetch import (
    require_public_https as _require_public_https,
)
from app.backend.citations.style_manager import (
    MAX_CSL_BYTES,
    MAX_STYLE_QUERY,
    StyleUpdateRequired,
    candidate_source_metadata,
    inspect_style_install,
    install_style,
    list_catalog_styles,
)
from app.backend.citations.style_preflight_cache import discard_prepared, get_prepared, store_prepared

REPOSITORY_INDEX_URL = "https://www.zotero.org/styles-files/styles.json"
REPOSITORY_STYLE_ROOT = "https://www.zotero.org/styles/"
REPOSITORY_ATTRIBUTION_URL = "https://citationstyles.org/"
MAX_REPOSITORY_RESULTS = 60
MAX_REPOSITORY_INDEX_BYTES = 5_000_000
MAX_DEPENDENCY_DEPTH = 8
_CATALOG_TTL_SECONDS = 6 * 60 * 60
_REPOSITORY_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,199}$")
_cache_lock = threading.Lock()
_cached_catalog: tuple[dict[str, Any], ...] | None = None
_cached_at = 0.0


@dataclass(frozen=True)
class _Candidate:
    filename: str
    url: str
    xml: str
    title: str
    canonical_id: str
    parent_canonical_id: str | None
    updated: str | None


def _repository_url(name: str) -> str:
    if not _REPOSITORY_NAME.fullmatch(str(name or "")):
        raise ValueError("Unknown CSL repository style")
    return REPOSITORY_STYLE_ROOT + name


def _require_repository_url(url: str) -> None:
    if url == REPOSITORY_INDEX_URL:
        return
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.zotero.org"
        or parsed.port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise StyleFetchError("The CSL repository returned an unexpected URL")
    name = parsed.path.removeprefix("/styles/")
    if parsed.path != f"/styles/{name}" or not _REPOSITORY_NAME.fullmatch(name):
        raise StyleFetchError("The CSL repository returned an unexpected style URL")


def _decode_csl(data: bytes) -> str:
    if len(data) > MAX_CSL_BYTES:
        raise StyleFetchError(f"The CSL file is too large (max {MAX_CSL_BYTES // 1000} KB)")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise StyleFetchError("The CSL file must be UTF-8 text") from exc


def _catalog_rows(*, fetcher: BytesFetcher | None = None, timeout: float = 20.0) -> tuple[dict[str, Any], ...]:
    global _cached_at, _cached_catalog
    if fetcher is None:
        with _cache_lock:
            if _cached_catalog is not None and time.monotonic() - _cached_at < _CATALOG_TTL_SECONDS:
                return _cached_catalog
    _require_repository_url(REPOSITORY_INDEX_URL)
    fetch = fetcher or (
        lambda url, *, timeout, max_bytes: _httpx_fetcher(
            url,
            timeout=timeout,
            max_bytes=max_bytes,
            guard=_require_repository_url,
        )
    )
    raw = fetch(REPOSITORY_INDEX_URL, timeout=timeout, max_bytes=MAX_REPOSITORY_INDEX_BYTES)
    if len(raw) > MAX_REPOSITORY_INDEX_BYTES:
        raise StyleFetchError("The CSL repository index is larger than expected")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StyleFetchError("The CSL repository returned an invalid catalog") from exc
    if not isinstance(payload, list) or len(payload) > 20_000:
        raise StyleFetchError("The CSL repository returned an invalid catalog")
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        title = str(item.get("title") or "").strip()
        if not title or len(title) > 300 or not _REPOSITORY_NAME.fullmatch(name):
            continue
        categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
        fields = categories.get("fields") if isinstance(categories.get("fields"), list) else []
        rows.append(
            {
                "repository_id": name,
                "title": title,
                "short_title": str(item.get("titleShort") or "").strip()[:120],
                "citation_format": str(categories.get("format") or "in-text")[:40],
                "fields": [str(field)[:60] for field in fields if isinstance(field, str)][:30],
                "dependent": bool(item.get("dependent")),
                "updated": str(item.get("updated") or "")[:40],
                "source_url": _repository_url(name),
            }
        )
    result = tuple(rows)
    if fetcher is None:
        with _cache_lock:
            _cached_catalog = result
            _cached_at = time.monotonic()
    return result


def _installed_repository_ids() -> dict[str, str]:
    installed: dict[str, str] = {}
    for style_id, path, _ in style_store.installed_style_paths():
        try:
            canonical = urlparse(style_store.canonical_id(path))
        except (OSError, ValueError):
            continue
        if canonical.hostname == "www.zotero.org" and canonical.path.startswith("/styles/"):
            name = canonical.path.removeprefix("/styles/")
            if _REPOSITORY_NAME.fullmatch(name):
                installed[name] = style_id
    return installed


def search_repository_styles(
    query: str,
    *,
    fetcher: BytesFetcher | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    query = str(query or "").strip()
    if len(query) < 2:
        raise ValueError("Enter at least 2 characters to search the CSL repository")
    if len(query) > MAX_STYLE_QUERY:
        raise ValueError(f"style search is too long (max {MAX_STYLE_QUERY} characters)")
    tokens = re.findall(r"[\w-]+", query.casefold())
    installed = _installed_repository_ids()
    matches: list[tuple[tuple[int, str], dict[str, Any]]] = []
    for row in _catalog_rows(fetcher=fetcher, timeout=timeout):
        haystack = " ".join(
            [
                row["repository_id"].replace("-", " "),
                row["title"],
                row["short_title"],
                row["citation_format"],
                *row["fields"],
                *(field.replace("_", " ") for field in row["fields"]),
            ]
        ).casefold()
        if not all(token in haystack for token in tokens):
            continue
        title = row["title"].casefold()
        short = row["short_title"].casefold()
        rank = 0 if query.casefold() in {title, short} else 1 if title.startswith(query.casefold()) else 2
        matches.append(((rank, title), {**row, "installed_id": installed.get(row["repository_id"])}))
    return {
        "styles": [row for _, row in sorted(matches, key=lambda item: item[0])[:MAX_REPOSITORY_RESULTS]],
        "query": query,
        "result_limit": MAX_REPOSITORY_RESULTS,
        "source": "Zotero Style Repository",
        "attribution_url": REPOSITORY_ATTRIBUTION_URL,
    }


def _repository_name_from_canonical(canonical: str) -> str:
    parsed = urlparse(canonical)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "www.zotero.org":
        raise StyleFetchError("A repository style points to a parent outside the CSL repository")
    name = parsed.path.removeprefix("/styles/")
    if parsed.path != f"/styles/{name}" or not _REPOSITORY_NAME.fullmatch(name):
        raise StyleFetchError("A repository style has an invalid parent reference")
    return name


def _public_download_url(canonical: str) -> str:
    parsed = urlparse(canonical)
    if parsed.hostname == "www.zotero.org" and parsed.path.startswith("/styles/"):
        name = parsed.path.removeprefix("/styles/")
        if _REPOSITORY_NAME.fullmatch(name):
            return _repository_url(name)
    return canonical


def _collect_candidates(
    root_url: str,
    *,
    repository_mode: bool,
    fetcher: BytesFetcher | None,
    resolver: HostResolver | None,
    timeout: float,
    refresh_installed_parents: bool = False,
) -> list[_Candidate]:
    if repository_mode:
        guard = _require_repository_url
    else:

        def guard(url: str) -> None:
            _require_public_https(url, resolver=resolver)

    fetch = fetcher or (
        lambda url, *, timeout, max_bytes: _httpx_fetcher(
            url,
            timeout=timeout,
            max_bytes=max_bytes,
            guard=guard,
            require_public_peer=not repository_mode,
        )
    )
    candidates: list[_Candidate] = []
    visited: set[str] = set()
    current = root_url
    for _ in range(MAX_DEPENDENCY_DEPTH):
        guard(current)
        xml = _decode_csl(fetch(current, timeout=timeout, max_bytes=MAX_CSL_BYTES))
        filename = urlparse(current).path.rsplit("/", 1)[-1] or "citation-style"
        if not filename.casefold().endswith(".csl"):
            filename += ".csl"
        metadata = candidate_source_metadata(filename, xml)
        canonical = str(metadata["canonical_id"])
        if canonical in visited:
            raise StyleFetchError("The citation style dependency chain contains a cycle")
        visited.add(canonical)
        candidate = _Candidate(
            filename=filename,
            url=current,
            xml=str(metadata["csl"]),
            title=str(metadata["title"]),
            canonical_id=canonical,
            parent_canonical_id=metadata["parent_canonical_id"],
            updated=metadata["updated"],
        )
        candidates.append(candidate)
        parent = candidate.parent_canonical_id
        installed_parent = style_store.canonical_index().get(parent) if parent else None
        if not parent or (installed_parent is not None and (not refresh_installed_parents or not installed_parent[2])):
            return candidates
        if repository_mode:
            current = _repository_url(_repository_name_from_canonical(parent))
        else:
            current = _public_download_url(parent)
    raise StyleFetchError(f"The citation style has more than {MAX_DEPENDENCY_DEPTH} dependency levels")


def _inspect_candidates(candidates: list[_Candidate]) -> tuple[list[dict[str, Any]], frozenset[str]]:
    available = frozenset(candidate.canonical_id for candidate in candidates) | frozenset(style_store.canonical_index())
    inspections = [
        inspect_style_install(
            candidate.filename,
            candidate.xml,
            available_parent_canonicals=available,
        )
        for candidate in candidates
    ]
    return inspections, available


def _install_candidates(
    candidates: list[_Candidate],
    *,
    mode: str,
    replace: bool,
) -> dict[str, Any]:
    inspections, _ = _inspect_candidates(candidates)
    if not replace:
        pending_update = next(
            (inspection for inspection in inspections if inspection["action"] == "update_available"),
            None,
        )
        if pending_update:
            style = pending_update["style"]
            raise StyleUpdateRequired(style["id"], style["full_title"])
    installed: list[dict[str, Any]] = []
    root_result: dict[str, Any] | None = None
    for candidate in reversed(candidates):
        result = install_style(
            candidate.filename,
            candidate.xml,
            replace=replace,
            provenance={
                "source_type": mode,
                "source_url": candidate.url,
                "repository_id": (
                    _repository_name_from_canonical(candidate.canonical_id) if mode == "repository" else None
                ),
                "upstream_updated": candidate.updated,
            },
        )
        if candidate is candidates[0]:
            root_result = result
        elif result["action"] in {"installed", "updated"}:
            installed.append(result)
    if root_result is None:
        raise RuntimeError("The requested citation style was not installed")
    if root_result["action"] == "already_installed" and any(item["action"] == "updated" for item in installed):
        root_result = {**root_result, "action": "updated"}
    return {
        **root_result,
        "source_url": candidates[0].url,
        "dependencies": [item["style"] for item in installed],
    }


def _prepare_response(mode: str, source: str, candidates: list[_Candidate]) -> dict[str, Any]:
    inspections, _ = _inspect_candidates(candidates)
    root = inspections[0]
    action = "update_available" if any(item["action"] == "update_available" for item in inspections) else root["action"]
    return {
        "token": store_prepared(mode, source, candidates),
        "action": action,
        "style": root["style"],
        "dependencies": [inspection["style"] for inspection in inspections[1:]],
        "upstream_updated": candidates[0].updated,
    }


def prepare_repository_style(
    repository_id: str,
    *,
    fetcher: BytesFetcher | None = None,
    timeout: float = 20.0,
    refresh_installed_parents: bool = False,
) -> dict[str, Any]:
    name = str(repository_id or "")
    root_url = _repository_url(name)
    installed_id = _installed_repository_ids().get(name)
    if installed_id and installed_id in style_store.BUILTIN_STYLE_IDS:
        style = next(row for row in list_catalog_styles() if row["id"] == installed_id)
        return {"token": None, "action": "already_installed", "style": style, "dependencies": []}
    rows = _catalog_rows(fetcher=fetcher, timeout=timeout)
    if name not in {row["repository_id"] for row in rows}:
        raise ValueError("Unknown CSL repository style")
    candidates = _collect_candidates(
        root_url,
        repository_mode=True,
        fetcher=fetcher,
        resolver=None,
        timeout=timeout,
        refresh_installed_parents=refresh_installed_parents,
    )
    return _prepare_response("repository", name, candidates)


def prepare_style_from_url(
    url: str,
    *,
    fetcher: BytesFetcher | None = None,
    resolver: HostResolver | None = None,
    timeout: float = 20.0,
    refresh_installed_parents: bool = False,
) -> dict[str, Any]:
    root_url = str(url or "").strip()
    _require_public_https(root_url, resolver=resolver)
    candidates = _collect_candidates(
        root_url,
        repository_mode=False,
        fetcher=fetcher,
        resolver=resolver,
        timeout=timeout,
        refresh_installed_parents=refresh_installed_parents,
    )
    return _prepare_response("url", root_url, candidates)


def install_prepared_style(
    token: str,
    *,
    mode: str,
    source: str,
    replace: bool = False,
) -> dict[str, Any]:
    candidates = list(get_prepared(token, mode=mode, source=source))
    result = _install_candidates(candidates, mode=mode, replace=replace)
    discard_prepared(token)
    return result


def install_repository_style(
    repository_id: str,
    *,
    replace: bool = False,
    fetcher: BytesFetcher | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    name = str(repository_id or "")
    root_url = _repository_url(name)
    installed_id = _installed_repository_ids().get(name)
    if installed_id and installed_id in style_store.BUILTIN_STYLE_IDS:
        style = next(row for row in list_catalog_styles() if row["id"] == installed_id)
        return {"action": "already_installed", "style": style, "source_url": root_url, "dependencies": []}
    rows = _catalog_rows(fetcher=fetcher, timeout=timeout)
    if name not in {row["repository_id"] for row in rows}:
        raise ValueError("Unknown CSL repository style")
    candidates = _collect_candidates(
        root_url,
        repository_mode=True,
        fetcher=fetcher,
        resolver=None,
        timeout=timeout,
    )
    return _install_candidates(candidates, mode="repository", replace=replace)


def install_style_from_url(
    url: str,
    *,
    replace: bool = False,
    fetcher: BytesFetcher | None = None,
    resolver: HostResolver | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    root_url = str(url or "").strip()
    _require_public_https(root_url, resolver=resolver)
    candidates = _collect_candidates(
        root_url,
        repository_mode=False,
        fetcher=fetcher,
        resolver=resolver,
        timeout=timeout,
    )
    return _install_candidates(candidates, mode="url", replace=replace)
