"""Crossref DOI metadata resolver with database-backed caching."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from sqlalchemy import Connection, insert, select, update

from app.backend.persistence.schema import external_api_cache

CROSSREF_PROVIDER = "crossref"
CROSSREF_BASE_URL = "https://api.crossref.org/works"


class CrossrefFetcher(Protocol):
    def __call__(self, doi: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
        """Return HTTP status and parsed JSON body."""


@dataclass(frozen=True)
class CrossrefResolution:
    doi: str
    resolved: bool
    csl_json: dict[str, Any] | None = None
    status_code: int | None = None
    source: str = "network"
    error: str | None = None


class CrossrefClient:
    def __init__(
        self,
        *,
        fetcher: CrossrefFetcher | None = None,
        mailto: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.fetcher = fetcher or _httpx_fetcher
        self.mailto = mailto or os.environ.get("CALLOSUM_CROSSREF_MAILTO")
        self.timeout = timeout

    def resolve_doi(self, conn: Connection, doi: str) -> CrossrefResolution:
        normalized_doi = _normalize_doi(doi)
        cached = _cached_response(conn, normalized_doi)
        if cached is not None:
            status_code = int(cached["status_code"]) if cached["status_code"] is not None else None
            response_json = cached["response_json"]
            if status_code == 200 and isinstance(response_json, dict):
                return CrossrefResolution(
                    doi=normalized_doi,
                    resolved=True,
                    csl_json=_crossref_message_to_csl(response_json.get("message") or response_json, normalized_doi),
                    status_code=status_code,
                    source="cache",
                )
            return CrossrefResolution(
                doi=normalized_doi,
                resolved=False,
                status_code=status_code,
                source="cache",
                error="cached unresolved Crossref response",
            )

        try:
            status_code, body = self.fetcher(normalized_doi, headers=self._headers(), timeout=self.timeout)
        except Exception as exc:
            _store_cache(
                conn,
                normalized_doi,
                request_json={"doi": normalized_doi},
                response_json={"error": str(exc)},
                status_code=None,
            )
            return CrossrefResolution(
                doi=normalized_doi, resolved=False, source="network", error=f"{type(exc).__name__}: {exc}"
            )

        _store_cache(
            conn, normalized_doi, request_json={"doi": normalized_doi}, response_json=body, status_code=status_code
        )
        if status_code != 200 or not isinstance(body, dict):
            return CrossrefResolution(
                doi=normalized_doi,
                resolved=False,
                status_code=status_code,
                source="network",
                error=f"Crossref returned HTTP {status_code}",
            )
        return CrossrefResolution(
            doi=normalized_doi,
            resolved=True,
            csl_json=_crossref_message_to_csl(body.get("message") or body, normalized_doi),
            status_code=status_code,
            source="network",
        )

    def lookup_retraction(self, conn: Connection, doi: str) -> dict[str, Any] | None:
        """Read Crossref's retraction/correction/concern record for a DOI (inc 131). Ensures the work is
        fetched+cached (via `resolve_doi`), then parses the RAW `message.update-to` (the Retraction-Watch-fed
        relation a retracted item carries pointing at its notice). Returns the richest flagged record
        `{status, nature, date, notice_doi, notice_url}` or None (no retraction record / unresolved)."""
        normalized = _normalize_doi(doi)
        self.resolve_doi(conn, normalized)  # populate the cache (network or cache-hit); never raises
        cached = _cached_response(conn, normalized)
        if cached is None or cached["status_code"] != 200:
            return None
        body = cached["response_json"]
        message = body.get("message") if isinstance(body, dict) else None
        if not isinstance(message, dict):
            return None
        return _parse_retraction(message)

    def _headers(self) -> dict[str, str]:
        user_agent = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            user_agent = f"{user_agent}; mailto:{self.mailto}"
        return {"User-Agent": user_agent, "Accept": "application/json"}


def _httpx_fetcher(doi: str, *, headers: dict[str, str], timeout: float) -> tuple[int, dict[str, Any] | None]:
    url = f"{CROSSREF_BASE_URL}/{quote(doi, safe='')}"
    response = httpx.get(url, headers=headers, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _cached_response(conn: Connection, doi: str):
    return (
        conn.execute(
            select(external_api_cache).where(
                external_api_cache.c.provider == CROSSREF_PROVIDER,
                external_api_cache.c.cache_key == doi,
            )
        )
        .mappings()
        .first()
    )


def _store_cache(
    conn: Connection,
    doi: str,
    *,
    request_json: dict[str, Any],
    response_json: dict[str, Any] | None,
    status_code: int | None,
) -> None:
    existing = _cached_response(conn, doi)
    values = {
        "request_json": request_json,
        "response_json": response_json,
        "status_code": status_code,
    }
    if existing is None:
        conn.execute(
            insert(external_api_cache).values(
                provider=CROSSREF_PROVIDER,
                cache_key=doi,
                **values,
            )
        )
    else:
        conn.execute(update(external_api_cache).where(external_api_cache.c.id == int(existing["id"])).values(**values))


def _crossref_message_to_csl(message: dict[str, Any], doi: str) -> dict[str, Any]:
    title = _first_string(message.get("title"))
    container_title = _first_string(message.get("container-title"))
    issued = message.get("issued") or message.get("published-print") or message.get("published-online")
    date_parts = _date_parts(issued)
    csl: dict[str, Any] = {
        "id": doi,
        "type": _crossref_type_to_csl(str(message.get("type") or "article-journal")),
        "DOI": str(message.get("DOI") or doi).lower(),
        "title": title or doi,
    }
    if container_title:
        csl["container-title"] = container_title
    if date_parts:
        csl["issued"] = {"date-parts": [date_parts]}
    if message.get("author"):
        csl["author"] = [
            {
                key: value
                for key, value in {
                    "family": author.get("family"),
                    "given": author.get("given"),
                    "literal": author.get("name"),
                }.items()
                if value
            }
            for author in message["author"]
            if isinstance(author, dict)
        ]
    if message.get("abstract"):
        csl["abstract"] = str(message["abstract"])
    subjects = _subject_list(message.get("subject"))
    if subjects:
        csl["subject"] = (
            subjects  # Crossref subject categories → kept in the canonical record + → keyword tags (inc 73)
        )
    return csl


def _subject_list(value: Any) -> list[str]:
    """Crossref `subject` is an array of category strings; keep non-empty, stripped, de-duped (order-preserving)."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = str(item).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def _first_string(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str):
        return value
    return None


def _date_parts(value: Any) -> list[int] | None:
    if not isinstance(value, dict):
        return None
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    first = date_parts[0]
    if not isinstance(first, list):
        return None
    parts = []
    for item in first[:3]:
        try:
            parts.append(int(item))
        except (TypeError, ValueError):
            break
    return parts or None


def _crossref_type_to_csl(value: str) -> str:
    return {
        "journal-article": "article-journal",
        "book-chapter": "chapter",
        "proceedings-article": "paper-conference",
        "book": "book",
    }.get(value, value)


# Crossref `update-to[].type` → our retraction status (inc 131). Kept local (no import from app.backend.methods,
# which imports this adapter — would cycle). The merge layer re-ranks across sources.
_UPDATE_TYPE_TO_STATUS = {
    "retraction": "retracted",
    "withdrawal": "retracted",
    "removal": "retracted",
    "correction": "correction",
    "erratum": "correction",
    "addendum": "correction",
    "expression_of_concern": "concern",
    "concern": "concern",
}
_RETRACTION_RANK = {"concern": 0, "correction": 1, "retracted": 2}


def _parse_retraction(message: dict[str, Any]) -> dict[str, Any] | None:
    """Pick the highest-severity `update-to` entry of a recognized retraction type, or None."""
    entries = message.get("update-to")
    if not isinstance(entries, list):
        return None
    best: tuple[int, dict[str, Any]] | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("type") or "").strip().lower().replace("-", "_")
        status = _UPDATE_TYPE_TO_STATUS.get(kind)
        if status is None:
            continue
        rank = _RETRACTION_RANK[status]
        if best is not None and rank <= best[0]:
            continue
        notice_doi = entry.get("DOI")
        notice_doi = str(notice_doi).strip().lower() if notice_doi else None
        parts = _date_parts(entry.get("updated"))
        best = (
            rank,
            {
                "status": status,
                "nature": str(entry.get("label")) if entry.get("label") else None,
                "date": "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts)) if parts else None,
                "notice_doi": notice_doi,
                "notice_url": f"https://doi.org/{notice_doi}" if notice_doi else None,
            },
        )
    return best[1] if best is not None else None


def _normalize_doi(doi: str) -> str:
    return doi.strip().lower()
