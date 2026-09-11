"""Candidate-cascade acquisition: try each authorized-OA candidate in order until one downloads.

Backlog #59: the OA lane previously downloaded only the FIRST resolver's hit, so a stale/forbidden URL
(HTTP 403/404) from the primary resolver was a terminal dead end even when another resolver would have
returned a working copy. This module iterates the resolver cascade lazily — resolving the next resolver
only if the current candidate fails to download — so:

* **Resolver priority is unchanged.** The first candidate tried is exactly the one the old
  ``registry.resolve()`` would have returned; later resolvers are consulted only after an expected
  download failure. This is a resilience fix, never a ranking/selection-policy change.
* **Only an expected ``OaFetchError`` triggers fallback.** Any other exception propagates — an unexpected
  bug is never silently converted into "candidates exhausted".
* **A known-bad URL is never re-fetched** — candidates are de-duplicated by ``pdf_url``.
* **The OA bright line is untouched** — still only ``OaLocation`` objects, still ``download_oa_pdf``; this
  changes *which* candidate is chosen and *how* failure is reported, nothing about OA eligibility.

The outcome is **machine-readable** (``reason_code``), so callers branch on structured state rather than
parsing human strings; ``human_detail()`` is the bounded, path-free, credential-free display string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy import Engine

from app.backend.acquisition.fetch import OaFetchError, download_oa_pdf
from app.backend.acquisition.registry import OaLocation, PaperRef, ResolverRegistry

# Outcome reason codes (stable, machine-readable).
ACQUIRED = "acquired"
NO_CANDIDATE = "no_candidate"  # no resolver asserted any OA copy
CANDIDATES_EXHAUSTED = "candidates_exhausted"  # candidate(s) found, but none could be downloaded

_MAX_DETAIL_LEN = 200


@dataclass(frozen=True)
class CandidateFailure:
    """One candidate that resolved to an OA location but failed to download — structured, not a string."""

    source: str  # the resolver id (e.g. "openalex")
    reason_code: str  # OaFetchError.reason_code (e.g. "http_error")
    http_status: int | None  # set iff reason_code == "http_error"


@dataclass(frozen=True)
class AcquireOutcome:
    """The result of a candidate cascade. ``reason_code`` is the machine-readable state; ``failures``
    records every candidate that resolved but did not download."""

    reason_code: str  # ACQUIRED | NO_CANDIDATE | CANDIDATES_EXHAUSTED
    location: OaLocation | None = None  # the working candidate (iff ACQUIRED)
    temp_path: Path | None = None  # the downloaded temp file (iff ACQUIRED) — caller imports then moves it
    candidates_tried: int = 0
    failures: tuple[CandidateFailure, ...] = field(default_factory=tuple)

    @property
    def acquired(self) -> bool:
        return self.reason_code == ACQUIRED

    def human_detail(self) -> str:
        """A bounded, path-free, credential-free line for a user-facing result / log."""
        if self.reason_code == ACQUIRED and self.location is not None:
            return f"imported an OA copy from {self.location.source}"
        if self.reason_code == NO_CANDIDATE:
            return "no authorized open-access copy found"
        # candidates_exhausted
        last = self.failures[-1] if self.failures else None
        n = self.candidates_tried
        plural = "candidate" if n == 1 else "candidates"
        if last is not None:
            reason = f"HTTP {last.http_status}" if last.http_status is not None else last.reason_code
            return f"{n} OA {plural} found, but none could be downloaded (last: {reason} from {last.source})"[
                :_MAX_DETAIL_LEN
            ]
        return f"{n} OA {plural} found, but none could be downloaded"[:_MAX_DETAIL_LEN]


def acquire_first_working(
    engine: Engine,
    registry: ResolverRegistry,
    ref: PaperRef,
    *,
    download: Callable[[OaLocation], Path] = download_oa_pdf,
) -> AcquireOutcome:
    """Resolve → download the FIRST resolver whose OA candidate downloads; fall through on ``OaFetchError``.

    Resolvers are consulted lazily and each in its own short transaction (a resolver may write the
    per-source ``external_api_cache``); the download happens outside any transaction, exactly as before.
    On success the returned ``temp_path`` is the ONLY downloaded file — a failed candidate leaves no temp
    file behind (``download_oa_pdf`` writes only after full validation), so nothing to clean up.
    """
    seen_urls: set[str] = set()
    failures: list[CandidateFailure] = []
    tried = 0
    for resolver in registry.resolvers():
        with engine.begin() as conn:  # each resolve writes its own external_api_cache
            location = resolver.resolve(conn, ref)
        if location is None:
            continue
        if location.pdf_url in seen_urls:
            continue  # a prior resolver already tried this exact URL — never re-fetch a known-bad candidate
        seen_urls.add(location.pdf_url)
        tried += 1
        try:
            temp_path = download(location)  # network, outside any transaction
        except OaFetchError as exc:
            failures.append(
                CandidateFailure(
                    source=location.source,
                    reason_code=getattr(exc, "reason_code", "fetch_failed"),
                    http_status=getattr(exc, "http_status", None),
                )
            )
            continue  # try the next resolver's candidate
        return AcquireOutcome(
            reason_code=ACQUIRED,
            location=location,
            temp_path=temp_path,
            candidates_tried=tried,
            failures=tuple(failures),
        )
    reason = CANDIDATES_EXHAUSTED if tried > 0 else NO_CANDIDATE
    return AcquireOutcome(reason_code=reason, candidates_tried=tried, failures=tuple(failures))
