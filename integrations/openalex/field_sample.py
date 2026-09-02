"""OpenAlex field-sample + batch-id-filter fetches (split from adapter.py, inc 456 -- adapter.py was at the
600-line cap). A mixin, not free functions: these methods reuse `OpenAlexClient`'s own instance state
(`self.fetcher`/`self.mailto`/`self.timeout`/`self.cache_engine`) and private helpers (`self._store`,
`self._polite_params`, `self._headers`) via normal Python method resolution, so `OpenAlexClient(FieldSampleMixin)`
keeps every existing call site (`client.fetch_field_sample(...)` etc.) unchanged -- the established rule-#1 split
pattern applied to a class instead of a router/module of free functions.

Imports only from `work_meta.py` (never from `adapter.py`) so there is no import cycle: `adapter.py` imports this
module to build `OpenAlexClient`, so this module cannot import anything back from `adapter.py`.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy import Connection

from integrations.openalex.request import OpenAlexResponseUnavailable
from integrations.openalex.work_meta import _cached_response, _meta_from_work, _meta_with_abstract

MAX_BYIDS = 50  # cap on ids fetched in one batch `?filter=openalex_id:` call (inc 228; OpenAlex's OR-filter limit)


class FieldSampleMixin:
    def _field_sample_body(self, conn: Connection, topic_id: str, size: int) -> dict[str, Any] | None:
        """Raw OpenAlex listing body for a topic sample (cached `field:<id>`) -- shared by `fetch_field_sample`
        (inc 227) + `fetch_topic_candidates` (inc 228), so the audit's sample + the overlooked candidates reuse one
        cached call. `topic_id` validated `^T\\d+$` **before** any request (no SSRF). Fail-closed -> None."""
        if not re.fullmatch(r"T\d+", topic_id or ""):
            return None
        size = max(1, min(int(size), 200))
        cache_key = f"field:{topic_id}:size:{size}"
        cached = _cached_response(conn, cache_key)
        if cached is not None and cached["status_code"] == 200:
            return cached["response_json"]
        try:
            status, body = self.fetcher(
                "",
                params={
                    "filter": f"primary_topic.id:{topic_id}",
                    "sample": str(size),
                    "seed": "42",  # fixed -> a reproducible sample (re-runs hit the cache anyway)
                    "per-page": str(size),
                    **self._polite_params(),
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
        except Exception:
            return None
        if status == 200 and isinstance(body, dict):
            self._store(
                conn,
                cache_key,
                request_json={"topic_id": topic_id, "size": size},
                response_json=body,
                status_code=status,
            )
            return body
        return None

    def fetch_field_sample(self, conn: Connection, topic_id: str, *, size: int = 200) -> list[dict[str, Any]]:
        """A random sample of recent works in an OpenAlex topic (inc 227 citation-equity) -- the descriptive
        "field" a paper's reference list is shown against. Returns `_meta_from_work` dicts."""
        body = self._field_sample_body(conn, topic_id, size)
        if not isinstance(body, dict):
            return []
        results = body.get("results")
        if not isinstance(results, list):
            return []
        return [m for work in results[:size] if (m := _meta_from_work(work))]

    def fetch_field_sample_strict(self, conn: Connection, topic_id: str, *, size: int = 200) -> list[dict[str, Any]]:
        """Return a complete field sample, raising when the response is unavailable or malformed."""
        body = self._field_sample_body(conn, topic_id, size)
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise OpenAlexResponseUnavailable("OpenAlex field sample was unavailable or malformed")
        return [m for work in results[:size] if (m := _meta_from_work(work))]

    def fetch_topic_candidates(self, conn: Connection, topic_id: str, *, size: int = 200) -> list[dict[str, Any]]:
        """Topic-sample works WITH the reconstructed abstract (inc 228 overlooked-work) -- candidates from the field,
        ranked by local embedding similarity to the focal paper. Shares the `field:<id>` cache with
        `fetch_field_sample` (no extra HTTP if the audit already ran). Returns `_meta_with_abstract` dicts."""
        body = self._field_sample_body(conn, topic_id, size)
        if not isinstance(body, dict):
            return []
        results = body.get("results")
        if not isinstance(results, list):
            return []
        return [m for work in results[:size] if (m := _meta_with_abstract(work))]

    def fetch_topic_candidates_strict(
        self, conn: Connection, topic_id: str, *, size: int = 200
    ) -> list[dict[str, Any]]:
        """Return complete topic candidates, raising when the response is unavailable or malformed."""
        body = self._field_sample_body(conn, topic_id, size)
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise OpenAlexResponseUnavailable("OpenAlex topic candidates were unavailable or malformed")
        return [m for work in results[:size] if (m := _meta_with_abstract(work))]

    def fetch_works_by_ids(
        self, conn: Connection, ids: list[str], *, with_abstract: bool = True
    ) -> list[dict[str, Any]]:
        """Batch-fetch OpenAlex works by their `W…` ids (inc 228 overlooked-work) -- one
        `?filter=openalex_id:W1|W2|…` call (≤MAX_BYIDS ids, each validated `^W\\d+$` **before** the request → no
        SSRF), cached per id-set. Returns `_meta_with_abstract` dicts (title+abstract+concepts for ranking).
        Fail-closed -> []."""
        try:
            return self.fetch_works_by_ids_strict(conn, ids, with_abstract=with_abstract)
        except OpenAlexResponseUnavailable:
            return []

    def fetch_works_by_ids_strict(
        self, conn: Connection, ids: list[str], *, with_abstract: bool = True
    ) -> list[dict[str, Any]]:
        """Batch-fetch ids, raising rather than converting an unavailable response into an empty set."""
        valid = [w for w in (ids or []) if re.fullmatch(r"W\d+", w or "")][:MAX_BYIDS]
        if not valid:
            return []
        cache_key = "byids:" + hashlib.sha256("|".join(sorted(valid)).encode("utf-8")).hexdigest()[:24]
        cached = _cached_response(conn, cache_key)
        if cached is not None and cached["status_code"] == 200:
            body = cached["response_json"] if cached["status_code"] == 200 else None
        else:
            try:
                status, body = self.fetcher(
                    "",
                    params={
                        "filter": "openalex_id:" + "|".join(valid),
                        "per-page": str(len(valid)),
                        **self._polite_params(),
                    },
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception as exc:
                raise OpenAlexResponseUnavailable("OpenAlex work batch was unavailable") from exc
            if status == 200 and isinstance(body, dict):
                self._store(conn, cache_key, request_json={"ids": valid}, response_json=body, status_code=status)
            else:
                raise OpenAlexResponseUnavailable(f"OpenAlex work batch returned HTTP {status}")
        if not isinstance(body, dict):
            raise OpenAlexResponseUnavailable("OpenAlex work batch response was malformed")
        results = body.get("results")
        if not isinstance(results, list):
            raise OpenAlexResponseUnavailable("OpenAlex work batch results were malformed")
        out: list[dict[str, Any]] = []
        for work in results[:MAX_BYIDS]:
            meta = _meta_with_abstract(work) if with_abstract else _meta_from_work(work)
            if meta and meta.get("openalex_work_id"):
                out.append(meta)
        return out

    def fetch_self_citation_hit_count(
        self, conn: Connection, *, ref_ids: list[str], author_ids: list[str]
    ) -> int | None:
        """Of `ref_ids` (a paper's own referenced-work ids), how many were authored by any of `author_ids` (that
        same paper's own authors) -- inc 456, the self-citation field baseline. One count-only OpenAlex request
        per chunk of ≤MAX_BYIDS ref ids (`filter=openalex_id:{chunk},authorships.author.id:{author_ids}`, reading
        only `meta.count` -- no metadata payload, cheaper than `fetch_works_by_ids`), summed across chunks. Both
        id lists are validated `^[WA]\\d+$` **before** any request (no SSRF). Cached per (ref_ids, author_ids)
        hash. Returns None (not 0) if either input list is empty or a chunk's fetch fails -- an honest "not
        computed", never a silently-wrong zero."""
        refs = sorted({r for r in (ref_ids or []) if re.fullmatch(r"W\d+", r or "")})
        authors = sorted({a for a in (author_ids or []) if re.fullmatch(r"A\d+", a or "")})
        if not refs or not authors:
            return None
        total = 0
        for i in range(0, len(refs), MAX_BYIDS):
            chunk = refs[i : i + MAX_BYIDS]
            count = self._self_citation_chunk_count(conn, ref_chunk=chunk, author_ids=authors)
            if count is None:
                return None  # one failed chunk -> the whole count is untrustworthy, not silently partial
            total += count
        return total

    def _self_citation_chunk_count(
        self, conn: Connection, *, ref_chunk: list[str], author_ids: list[str]
    ) -> int | None:
        cache_key = (
            "selfcite:"
            + hashlib.sha256(("|".join(ref_chunk) + "::" + "|".join(author_ids)).encode("utf-8")).hexdigest()[:24]
        )
        cached = _cached_response(conn, cache_key)
        if cached is not None and cached["status_code"] == 200:
            body = cached["response_json"] if cached["status_code"] == 200 else None
        else:
            try:
                status, body = self.fetcher(
                    "",
                    params={
                        "filter": "openalex_id:"
                        + "|".join(ref_chunk)
                        + ",authorships.author.id:"
                        + "|".join(author_ids),
                        "per-page": "1",  # count-only -- meta.count is populated regardless of per-page
                        **self._polite_params(),
                    },
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except Exception:
                return None
            if status == 200 and isinstance(body, dict):
                self._store(
                    conn,
                    cache_key,
                    request_json={"ref_chunk": ref_chunk, "author_ids": author_ids},
                    response_json=body,
                    status_code=status,
                )
            else:
                body = None
        if not isinstance(body, dict):
            return None
        count = (body.get("meta") or {}).get("count")
        return int(count) if isinstance(count, int) else None
