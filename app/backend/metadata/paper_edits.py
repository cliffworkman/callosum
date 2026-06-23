"""Compute a safe partial metadata update from Details-pane edits (inc 49).

The Details pane is a Mendeley-style editor over a paper's bibliographic record. The canonical
record is `papers.csl_json` (CSL-JSON); the scalar columns (title, year, venue, doi, ...) are
projections of it kept for querying. A hand-edit must:
  * merge ONLY the fields the user actually changed into a COPY of the existing csl_json — never a
    blind full re-projection, which would wipe csl fields the edit didn't touch;
  * keep the affected scalar columns in sync; and
  * stamp provenance as user-edited.

`build_paper_update` is a pure function (no DB) so the field mapping is exhaustively unit-testable.
The caller (the PATCH handler) is responsible for validating/normalising the `edits` it passes in
(strings stripped with ""→None, ints parsed, the generic `csl` patch key/value-checked).
"""

from __future__ import annotations

from typing import Any

from app.backend.metadata.enrichment import USER_EDITED_SOURCE

# csl_json keys owned by a dedicated/structured core field below. The generic "More" passthrough
# (free-form scalar csl fields surfaced because a DOI populated them) must never touch these —
# they have typed handling, and a string write would corrupt the structured ones (author/issued).
RESERVED_CSL_KEYS = frozenset(
    {
        "title",
        "abstract",
        "DOI",
        "container-title",
        "language",
        "type",
        "volume",
        "issue",
        "page",
        "URL",
        "PMID",
        "arxiv",
        "ISSN",
        "ISBN",
        "author",
        "translator",
        "issued",
        "id",
    }
)

# Core csl-only scalar fields (no mirror column) → their csl key.
_CSL_ONLY = {
    "volume": "volume",
    "issue": "issue",
    "page": "page",
    "url": "URL",
    "pmid": "PMID",
    "arxiv": "arxiv",
    "issn": "ISSN",
    "isbn": "ISBN",
}


def build_paper_update(existing_row: Any, edits: dict[str, Any]) -> dict[str, Any]:
    """Return update_paper_metadata kwargs for the fields the user changed.

    `edits` carries only the user-set fields (already normalised). Returns the changed scalar
    columns + a merged copy of csl_json + imported_source=user-edited.
    """
    csl: dict[str, Any] = dict(existing_row["csl_json"] or {})
    cols: dict[str, Any] = {}

    # columns that mirror one csl key 1:1
    if "title" in edits:
        title = (edits["title"] or "").strip()
        cols["title"] = title
        csl["title"] = title
    if "abstract" in edits:
        cols["abstract"] = edits["abstract"]
        _set_or_pop(csl, "abstract", edits["abstract"])
    if "venue" in edits:
        cols["venue"] = edits["venue"]
        _set_or_pop(csl, "container-title", edits["venue"])
    if "language" in edits:
        cols["language"] = edits["language"]
        _set_or_pop(csl, "language", edits["language"])
    if "item_type" in edits:
        cols["item_type"] = edits["item_type"]
        _set_or_pop(csl, "type", edits["item_type"])
    if "doi" in edits:
        doi = _normalize_doi(edits["doi"])
        cols["doi"] = doi
        _set_or_pop(csl, "DOI", doi)
    if "citation_key" in edits:
        cols["citation_key"] = edits["citation_key"]  # column-only (not a CSL field)

    # csl-only scalar fields (no column)
    for field, key in _CSL_ONLY.items():
        if field in edits:
            _set_or_pop(csl, key, edits[field])

    # date parts: year / month / day → issued.date-parts + year/publication_date columns
    if any(k in edits for k in ("year", "month", "day")):
        _apply_date(csl, cols, existing=_existing_date(csl), edits=edits)

    # authors: a list of literal strings (lossless round-trip; no fragile name parsing)
    if "authors" in edits:
        _apply_authors(csl, cols, edits["authors"])

    # translators: same literal-list model as authors; CSL `translator` array, no mirror column (inc 111)
    if "translators" in edits:
        _apply_translators(csl, edits["translators"])

    # generic "More" passthrough: arbitrary scalar csl fields a DOI populated (reserved keys skipped)
    generic = edits.get("csl")
    if isinstance(generic, dict):
        for key, value in generic.items():
            if key in RESERVED_CSL_KEYS:
                continue
            _set_or_pop(csl, key, value)

    return {**cols, "csl_json": csl, "imported_source": USER_EDITED_SOURCE}


def _set_or_pop(csl: dict[str, Any], key: str, value: Any) -> None:
    if value is None or value == "":
        csl.pop(key, None)
    else:
        csl[key] = value


def _existing_date(csl: dict[str, Any]) -> list[int]:
    issued = csl.get("issued")
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            parts: list[int] = []
            for item in date_parts[0][:3]:
                try:
                    parts.append(int(item))
                except (TypeError, ValueError):
                    break
            return parts
    return []


def _apply_date(csl: dict[str, Any], cols: dict[str, Any], *, existing: list[int], edits: dict[str, Any]) -> None:
    y = edits["year"] if "year" in edits else (existing[0] if len(existing) > 0 else None)
    m = edits["month"] if "month" in edits else (existing[1] if len(existing) > 1 else None)
    d = edits["day"] if "day" in edits else (existing[2] if len(existing) > 2 else None)
    parts: list[int] = []
    for value in (y, m, d):  # CSL date-parts has no gaps — stop at the first missing component
        if value is None:
            break
        parts.append(int(value))
    if parts:
        csl["issued"] = {"date-parts": [parts]}
        cols["year"] = parts[0]
        cols["publication_date"] = "-".join(str(part) for part in parts)
    else:
        csl.pop("issued", None)
        cols["year"] = None
        cols["publication_date"] = None


def _apply_authors(csl: dict[str, Any], cols: dict[str, Any], authors: list[str] | None) -> None:
    cleaned = [author for author in (authors or []) if author and author.strip()]
    if cleaned:
        csl["author"] = [{"literal": author.strip()} for author in cleaned]
        # Best-effort family-name projection: first whitespace token of the first author
        # (matches the "Family Initials" convention; used only for sort/fallback display).
        first_tokens = cleaned[0].split()
        cols["first_author_family_name"] = first_tokens[0] if first_tokens else None
    else:
        csl.pop("author", None)
        cols["first_author_family_name"] = None


def _apply_translators(csl: dict[str, Any], translators: list[str] | None) -> None:
    cleaned = [t for t in (translators or []) if t and t.strip()]
    if cleaned:
        csl["translator"] = [{"literal": t.strip()} for t in cleaned]
    else:
        csl.pop("translator", None)


def _normalize_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    normalized = str(doi).strip().lower()
    return normalized or None
