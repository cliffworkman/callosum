"""Identity evidence for provisional direct-PDF captures: extraction and scoring (#61 / #96).

Split out of ``provisional.py`` (rule #1, 600-line cap). Everything here is a pure function of a PDF and a metadata
resolver: it scans the front matter for DOI/title candidates, resolves and scores them against Crossref, and
serializes what was OBSERVED (`_Evidence`) without deciding anything about the canonical Library. It has no
dependency on the rest of the capture package, which is why it can be a leaf module.

Observation is not inference is not canonical fact (#96): candidates and resolutions recorded here are evidence;
promotion into the Library is decided (and gated) elsewhere.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz
from sqlalchemy import Connection

from app.backend.embeddings.models import normalize_text, strip_punctuation
from app.backend.metadata.doi import DOI_PATTERN, find_doi_in_text, normalize_doi
from app.backend.pdf_processing.sections import SectionTracker

# Only the front matter of a direct-PDF capture can ever influence the promotion decision (see
# `_classify_position`), so scanning past this page never changes the outcome -- bounding the scan
# here is a real optimization, not a coverage gap. Kept as a module constant so it is trivially
# revisited if a real-world fixture ever needs more front matter than this.
MAX_SCAN_PAGES = 3
MAX_RESOLVE_CANDIDATES = 3

# Schema version of the evidence/sidecar JSON this module's `_Evidence` serializes (also stamped by the core
# module's sidecar writer and defaulted by the review module).
SIDECAR_SCHEMA_VERSION = 1


# --- candidate extraction -------------------------------------------------------------------------


@dataclass(frozen=True)
class DoiCandidate:
    doi: str
    page_number: int
    position_class: str  # "front_matter" | "body" | "references"


@dataclass
class _Evidence:
    candidates: list[dict[str, Any]] = field(default_factory=list)
    title_candidates: list[str] = field(default_factory=list)
    resolutions: list[dict[str, Any]] = field(default_factory=list)
    decision: str = ""
    decision_reason: str = ""

    def as_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SIDECAR_SCHEMA_VERSION,
                "candidates": self.candidates,
                "title_candidates": self.title_candidates,
                "resolutions": self.resolutions,
                "decision": self.decision,
                "decision_reason": self.decision_reason,
            }
        )


def _classify_position(page_number: int, current_section: str | None) -> str:
    if current_section == "references":
        return "references"
    if page_number <= 2 and current_section is None:
        return "front_matter"
    return "body"


def _extract_candidates(pdf_path: Path) -> tuple[list[DoiCandidate], list[str]]:
    """Scan metadata + the first `MAX_SCAN_PAGES` pages for DOI and title candidates.

    Bounded to the front matter deliberately: `_promote_if_strong` only ever treats a
    `front_matter`-classified candidate as eligible, so nothing past this window can change the
    promotion decision.
    """
    candidates: list[DoiCandidate] = []
    title_candidates: list[str] = []
    with fitz.open(pdf_path) as document:
        meta_title = (document.metadata or {}).get("title")
        if meta_title and isinstance(meta_title, str) and len(meta_title.strip()) > 8:
            title_candidates.append(meta_title.strip())

        metadata_text = " ".join(str(v) for v in (document.metadata or {}).values() if v)
        meta_doi = find_doi_in_text(metadata_text)
        if meta_doi:
            candidates.append(DoiCandidate(doi=meta_doi, page_number=1, position_class="front_matter"))

        tracker = SectionTracker()
        page_count = min(document.page_count, MAX_SCAN_PAGES)
        first_page_lines: list[str] = []
        for page_index in range(page_count):
            page = document[page_index]
            page_number = page_index + 1
            text_dict = page.get_text("dict", sort=True)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines = []
                for line in block.get("lines", []):
                    line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                    if line_text.strip():
                        lines.append(line_text)
                block_text = "\n".join(lines).strip()
                if not block_text:
                    continue
                tracker.observe_block(block_text)
                if page_number == 1:
                    first_page_lines.extend(lines)
                for match in DOI_PATTERN.finditer(block_text):
                    doi = normalize_doi(match.group(1))
                    if not doi:
                        continue
                    position_class = _classify_position(page_number, tracker.current_section)
                    candidates.append(DoiCandidate(doi=doi, page_number=page_number, position_class=position_class))

        if not title_candidates:
            for line in first_page_lines:
                stripped = line.strip()
                if (
                    len(stripped) > 20
                    and not stripped.isupper()
                    and "doi" not in stripped.lower()
                    and not stripped.lower().startswith(("http://", "https://"))
                ):
                    title_candidates.append(stripped)
                    break

    return candidates, title_candidates


def _titles_agree(wanted: str, found: str | None) -> float:
    """NFKC+casefold+tokenize Jaccard AND difflib ratio -- the same two-part test as OpenAlex's
    private `_title_matches`, reimplemented locally rather than reaching into that module."""
    if not found:
        return 0.0

    def normalized(value: str) -> str:
        folded = unicodedata.normalize("NFKC", strip_punctuation(value)).casefold()
        return normalize_text(folded)

    a, b = normalized(wanted), normalized(found)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    a_tokens, b_tokens = set(a.split()), set(b.split())
    overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio if (overlap >= 0.9 and ratio >= 0.92) else 0.0


# --- resolution + scoring --------------------------------------------------------------------------


def _resolve_and_score(
    conn: Connection,
    candidates: list[DoiCandidate],
    title_candidates: list[str],
    *,
    crossref_client: Any,
    evidence: _Evidence,
) -> str | None:
    """Returns the single strong DOI iff exactly one qualifies; otherwise None. Every candidate and
    disposition is recorded in `evidence` regardless of outcome."""
    seen_dois: dict[str, DoiCandidate] = {}
    for candidate in candidates:
        if candidate.position_class == "references":
            evidence.candidates.append(
                {
                    "doi": candidate.doi,
                    "page": candidate.page_number,
                    "position_class": candidate.position_class,
                    "disposition": "rejected_reference_section",
                }
            )
            continue
        if candidate.doi not in seen_dois:
            seen_dois[candidate.doi] = candidate
        evidence.candidates.append(
            {
                "doi": candidate.doi,
                "page": candidate.page_number,
                "position_class": candidate.position_class,
                "disposition": "observed",
            }
        )

    front_matter_dois = [doi for doi, c in seen_dois.items() if c.position_class == "front_matter"]
    evidence.title_candidates = list(title_candidates)

    strong: list[str] = []
    for doi in front_matter_dois[:MAX_RESOLVE_CANDIDATES]:
        resolution = crossref_client.resolve_doi(conn, doi) if crossref_client is not None else None
        if resolution is None or not resolution.resolved or not resolution.csl_json:
            evidence.resolutions.append({"resolver": "crossref", "doi": doi, "disposition": "unresolved"})
            continue
        csl = resolution.csl_json
        resolved_title = csl.get("title")
        best_similarity = 0.0
        for title in title_candidates:
            best_similarity = max(best_similarity, _titles_agree(title, resolved_title))
        agrees = best_similarity > 0.0
        evidence.resolutions.append(
            {
                "resolver": "crossref",
                "doi": doi,
                "resolved_title": resolved_title,
                "title_similarity": round(best_similarity, 4),
                "disposition": "strong" if agrees else "insufficient_corroboration",
            }
        )
        if agrees:
            strong.append(doi)

    if len(strong) == 1:
        return strong[0]
    return None
