"""Bounded OpenAlex authorship metadata for My Publications citing-author evidence (inc 391)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import Connection, Engine

from integrations.api_cache import get_cached, put_cached, put_cached_committing
from integrations.openalex.citing_topics import (
    MAX_AUTHOR_RECORDS,
    MAX_SOURCE_WORKS,
    OpenAlexCitingTopicsClient,
    normalize_author_records,
)

OPENALEX_CITING_AUTHORS_PROVIDER = "openalex_citing_authors"


class CitingAuthorMetadataUnavailable(RuntimeError):
    """The provider did not return the bounded own-work authorship set."""


class OpenAlexCitingAuthorsClient:
    """Reuse cached citing-work windows and fetch one bounded batch of own-work authorships."""

    def __init__(
        self,
        openalex_client,
        *,
        window_client: OpenAlexCitingTopicsClient | None = None,
        cache_engine: Engine | None = None,
    ) -> None:
        self.fetcher = openalex_client.fetcher
        self.mailto = openalex_client.mailto
        self.timeout = openalex_client.timeout
        self.window_client = window_client or OpenAlexCitingTopicsClient(openalex_client)
        self.cache_engine = cache_engine

    def with_cache_engine(self, engine: Engine) -> OpenAlexCitingAuthorsClient:
        clone = object.__new__(OpenAlexCitingAuthorsClient)
        clone.fetcher = self.fetcher
        clone.mailto = self.mailto
        clone.timeout = self.timeout
        clone.window_client = (
            self.window_client.with_cache_engine(engine)
            if hasattr(self.window_client, "with_cache_engine")
            else self.window_client
        )
        clone.cache_engine = engine
        return clone

    def fetch_window(
        self,
        conn: Connection,
        work_ids: list[str],
        *,
        start_year: int,
        end_year: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        return self.window_client.fetch_window(
            conn,
            work_ids,
            start_year=start_year,
            end_year=end_year,
        )

    def fetch_source_authorships(
        self,
        conn: Connection,
        work_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Return own-work authorships keyed by validated source work id."""
        source_ids = sorted({work_id for work_id in work_ids if re.fullmatch(r"W\d+", work_id or "")})
        if not source_ids or len(source_ids) > MAX_SOURCE_WORKS:
            return {}
        cache_key = _cache_key(source_ids)
        cached = get_cached(conn, OPENALEX_CITING_AUTHORS_PROVIDER, cache_key)
        if cached is not None and isinstance(cached["response_json"], dict):
            response = cached["response_json"]
            if int(cached["status_code"] or 0) == 200 and isinstance(response.get("works"), list):
                return {
                    row["openalex_work_id"]: row
                    for raw in response["works"]
                    if isinstance(raw, dict) and (row := _cached_source(raw)) is not None
                }
            raise CitingAuthorMetadataUnavailable("Cached OpenAlex own-work authorships are unavailable.")

        params = {
            "filter": f"openalex:{'|'.join(source_ids)}",
            "per-page": str(MAX_SOURCE_WORKS),
            "select": "id,authorships",
            **self._polite_params(),
        }
        try:
            status, body = self.fetcher("", params=params, headers=self._headers(), timeout=self.timeout)
        except Exception as exc:
            raise CitingAuthorMetadataUnavailable("OpenAlex own-work authorship fetch failed.") from exc
        if status != 200 or not isinstance(body, dict):
            raise CitingAuthorMetadataUnavailable(f"OpenAlex own-work authorship fetch returned HTTP {status}.")
        if not isinstance(body.get("results"), list):
            raise CitingAuthorMetadataUnavailable("OpenAlex own-work authorship response was malformed.")

        works: list[dict[str, Any]] = []
        source_set = set(source_ids)
        for raw in body["results"]:
            normalized = _source_from_obj(raw, source_set)
            if normalized is not None:
                works.append(normalized)
        response = {"works": works}
        self._put(
            conn,
            cache_key,
            request_json={"source_work_ids": source_ids},
            response_json=response,
            status_code=200,
        )
        return {row["openalex_work_id"]: row for row in works}

    def _put(self, conn: Connection, cache_key: str, **fields: Any) -> None:
        if self.cache_engine is not None:
            put_cached_committing(self.cache_engine, OPENALEX_CITING_AUTHORS_PROVIDER, cache_key, **fields)
        else:
            put_cached(conn, OPENALEX_CITING_AUTHORS_PROVIDER, cache_key, **fields)

    def _polite_params(self) -> dict[str, str]:
        return {"mailto": self.mailto} if self.mailto else {}

    def _headers(self) -> dict[str, str]:
        user_agent = "Callosum/0.1 (local-first reference manager)"
        if self.mailto:
            user_agent = f"{user_agent}; mailto:{self.mailto}"
        return {"User-Agent": user_agent, "Accept": "application/json"}


def _source_from_obj(value: Any, source_ids: set[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    work_id = str(value.get("id") or "").rsplit("/", 1)[-1]
    if work_id not in source_ids:
        return None
    authorships = [row for row in (value.get("authorships") or []) if isinstance(row, dict)]
    return {
        "openalex_work_id": work_id,
        "authors": normalize_author_records(authorships),
        "authorship_count": min(len(authorships), 100),
        "authorship_cap_reached": len(authorships) > MAX_AUTHOR_RECORDS,
    }


def _cached_source(value: dict[str, Any]) -> dict[str, Any] | None:
    work_id = str(value.get("openalex_work_id") or "")
    if re.fullmatch(r"W\d+", work_id) is None:
        return None
    return {
        "openalex_work_id": work_id,
        "authors": normalize_author_records(value.get("authors")),
        "authorship_count": _bounded_count(value.get("authorship_count")),
        "authorship_cap_reached": bool(value.get("authorship_cap_reached")),
    }


def _cache_key(work_ids: list[str]) -> str:
    identity = "\0".join(work_ids).encode()
    return f"sources:v1:{hashlib.sha256(identity).hexdigest()[:32]}"


def _bounded_count(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(parsed, 100))
