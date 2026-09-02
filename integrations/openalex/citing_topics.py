"""Bounded OpenAlex citing-work windows for My Publications emerging topics (inc 390).

The query takes only validated OpenAlex work ids and fixed date windows. It fetches the union once per window,
keeps each result's primary topic plus the exact source works it cites, and caches the normalized response.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import Connection, Engine

from integrations.api_cache import get_cached, put_cached, put_cached_committing
from integrations.openalex.request import OPENALEX_CACHE_TTL_SECONDS, openalex_headers, openalex_params

OPENALEX_CITING_TOPICS_PROVIDER = "openalex_citing_topics"
MAX_SOURCE_WORKS = 50
WORKS_PER_PAGE = 100
MAX_PAGES = 2
MAX_WINDOW_WORKS = WORKS_PER_PAGE * MAX_PAGES
MAX_AUTHORS = 8
MAX_AUTHOR_RECORDS = 25


class CitingTopicWindowUnavailable(RuntimeError):
    """The provider did not return a complete bounded window; callers must preserve the prior snapshot."""


class OpenAlexCitingTopicsClient:
    """Small adapter over an existing OpenAlex client's fetcher/configuration."""

    def __init__(self, openalex_client, *, cache_engine: Engine | None = None) -> None:
        self.fetcher = openalex_client.fetcher
        self.mailto = openalex_client.mailto
        self.timeout = openalex_client.timeout
        self.cache_engine = cache_engine

    def with_cache_engine(self, engine: Engine) -> OpenAlexCitingTopicsClient:
        clone = object.__new__(OpenAlexCitingTopicsClient)
        clone.fetcher = self.fetcher
        clone.mailto = self.mailto
        clone.timeout = self.timeout
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
        """Return normalized citing works and whether the equal-window result cap was reached."""
        source_ids = sorted({work_id for work_id in work_ids if re.fullmatch(r"W\d+", work_id or "")})
        if not source_ids or len(source_ids) > MAX_SOURCE_WORKS or not _valid_years(start_year, end_year):
            return [], False
        cache_key = _cache_key(source_ids, start_year, end_year)
        cached = get_cached(
            conn, OPENALEX_CITING_TOPICS_PROVIDER, cache_key, max_age_seconds=OPENALEX_CACHE_TTL_SECONDS
        )
        if cached is not None and int(cached["status_code"] or 0) == 200 and isinstance(cached["response_json"], dict):
            response = cached["response_json"]
            if int(cached["status_code"] or 0) == 200 and isinstance(response.get("works"), list):
                return [_cached_work(work) for work in response["works"] if isinstance(work, dict)], bool(
                    response.get("capped")
                )

        works: list[dict[str, Any]] = []
        cursor = "*"
        capped = False
        request_filter = (
            f"cites:{'|'.join(source_ids)},"
            f"from_publication_date:{start_year}-01-01,to_publication_date:{end_year}-12-31"
        )
        for page_index in range(MAX_PAGES):
            params = {
                "filter": request_filter,
                "per-page": str(WORKS_PER_PAGE),
                "cursor": cursor,
                "sort": "publication_date:desc",
                "select": "id,doi,title,publication_year,authorships,primary_topic,referenced_works",
                **self._polite_params(),
            }
            try:
                status, body = self.fetcher("", params=params, headers=self._headers(), timeout=self.timeout)
            except Exception as exc:
                raise CitingTopicWindowUnavailable("OpenAlex citing-topic window fetch failed.") from exc
            if status != 200 or not isinstance(body, dict):
                raise CitingTopicWindowUnavailable(f"OpenAlex citing-topic window returned HTTP {status}.")
            results = body.get("results")
            meta = body.get("meta")
            if not isinstance(results, list) or (meta is not None and not isinstance(meta, dict)):
                raise CitingTopicWindowUnavailable("OpenAlex citing-topic window response was malformed.")
            for raw in results[:WORKS_PER_PAGE]:
                normalized = _work_from_obj(raw, set(source_ids))
                if normalized is not None:
                    works.append(normalized)
            next_cursor = (meta or {}).get("next_cursor")
            if not next_cursor:
                break
            if page_index == MAX_PAGES - 1:
                capped = True
                break
            cursor = str(next_cursor)

        response = {"works": works[:MAX_WINDOW_WORKS], "capped": capped}
        self._put(
            conn,
            cache_key,
            request_json={"source_work_ids": source_ids, "start_year": start_year, "end_year": end_year},
            response_json=response,
            status_code=200,
        )
        return works[:MAX_WINDOW_WORKS], capped

    def _put(self, conn: Connection, cache_key: str, **fields: Any) -> None:
        if self.cache_engine is not None:
            put_cached_committing(self.cache_engine, OPENALEX_CITING_TOPICS_PROVIDER, cache_key, **fields)
        else:
            put_cached(conn, OPENALEX_CITING_TOPICS_PROVIDER, cache_key, **fields)

    def _polite_params(self) -> dict[str, str]:
        return openalex_params(self.mailto)

    def _headers(self) -> dict[str, str]:
        return openalex_headers(self.mailto)


def _work_from_obj(work: Any, source_ids: set[str]) -> dict[str, Any] | None:
    if not isinstance(work, dict):
        return None
    raw_id = str(work.get("id") or "")
    work_id = raw_id.rsplit("/", 1)[-1]
    if re.fullmatch(r"W\d+", work_id) is None:
        return None
    cited_source_ids = sorted(
        {
            candidate
            for value in (work.get("referenced_works") or [])
            if isinstance(value, str)
            for candidate in [value.rsplit("/", 1)[-1]]
            if candidate in source_ids
        }
    )
    if not cited_source_ids:
        return None
    topic = _topic_from_obj(work.get("primary_topic"))
    year = work.get("publication_year")
    authorships = [value for value in (work.get("authorships") or []) if isinstance(value, dict)]
    return {
        "openalex_work_id": work_id,
        "doi": _normalize_doi(work.get("doi") or (work.get("ids") or {}).get("doi")),
        "title": str(work.get("title") or work.get("display_name") or "").strip() or None,
        "year": int(year) if isinstance(year, int) else None,
        "authors": [
            str((authorship.get("author") or {}).get("display_name") or "").strip()
            for authorship in authorships
            if (authorship.get("author") or {}).get("display_name")
        ][:MAX_AUTHORS],
        "author_records": normalize_author_records(authorships),
        "authorship_count": len(authorships),
        "primary_topic": topic,
        "cited_source_work_ids": cited_source_ids,
    }


def _topic_from_obj(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    topic_id = str(value.get("id") or "").rsplit("/", 1)[-1]
    name = str(value.get("display_name") or "").strip()
    if re.fullmatch(r"T\d+", topic_id) is None or not name:
        return None
    topic = {"id": topic_id, "name": name}
    for key in ("subfield", "field", "domain"):
        nested = value.get(key)
        label = str(nested.get("display_name") or "").strip() if isinstance(nested, dict) else ""
        if label:
            topic[key] = label
    return topic


def _cached_work(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "openalex_work_id": value.get("openalex_work_id"),
        "doi": value.get("doi"),
        "title": value.get("title"),
        "year": value.get("year"),
        "authors": list(value.get("authors") or [])[:MAX_AUTHORS],
        "author_records": normalize_author_records(value.get("author_records")),
        "authorship_count": _bounded_nonnegative_int(value.get("authorship_count")),
        "primary_topic": value.get("primary_topic") if isinstance(value.get("primary_topic"), dict) else None,
        "cited_source_work_ids": list(value.get("cited_source_work_ids") or [])[:MAX_SOURCE_WORKS],
    }


def _cache_key(work_ids: list[str], start_year: int, end_year: int) -> str:
    identity = "\0".join([str(start_year), str(end_year), *work_ids]).encode()
    return f"window:v2:{hashlib.sha256(identity).hexdigest()[:32]}"


def normalize_author_records(values: Any) -> list[dict[str, str]]:
    """Keep stable OpenAlex author ids plus display names, bounded in provider order."""
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    if not isinstance(values, list):
        return records
    for value in values:
        author = value.get("author") if isinstance(value, dict) and isinstance(value.get("author"), dict) else value
        if not isinstance(author, dict):
            continue
        author_id = str(author.get("id") or "").rsplit("/", 1)[-1]
        name = str(author.get("display_name") or author.get("name") or "").strip()
        if re.fullmatch(r"A\d+", author_id) is None or not name or author_id in seen:
            continue
        seen.add(author_id)
        records.append({"id": author_id, "name": name[:300]})
        if len(records) == MAX_AUTHOR_RECORDS:
            break
    return records


def _valid_years(start_year: int, end_year: int) -> bool:
    return 1900 <= start_year <= end_year <= 2100 and end_year - start_year == 2


def _normalize_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi or None


def _bounded_nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(parsed, 100))
