"""Meta Reference List detectors.

Surfaces narrow negative reference signals for human review: could-not-verify, known retraction signal, and
own-library propagation. No positive citation state, no composite score, no author/citation verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import Connection

from app.backend.acquisition.registry import PaperRef
from app.backend.discovery.providers import normalized_title
from app.backend.methods.retraction import RetractionChecker, detect_retraction
from integrations.crossref.adapter import CrossrefClient
from integrations.openalex.adapter import OpenAlexClient

DETECTOR_VERSION = "reference-integrity-v1"


@dataclass(frozen=True)
class ReferenceCandidate:
    source_ordinal: int
    title: str | None
    authors: list[str]
    year: int | None
    doi: str | None
    raw_text: str
    context: dict[str, Any]


@dataclass(frozen=True)
class DetectorSignal:
    detector_kind: str
    detector_status: str
    evidence: dict[str, Any]
    source: str
    snapshot_marker: str

    @property
    def key(self) -> str:
        payload = {
            "kind": self.detector_kind,
            "status": self.detector_status,
            "evidence": self.evidence,
            "source": self.source,
            "snapshot": self.snapshot_marker,
        }
        return _hash(payload)


@dataclass(frozen=True)
class ReferenceCheckResult:
    candidate: ReferenceCandidate
    entity_metadata: dict[str, Any]
    signals: list[DetectorSignal]


def instance_key(candidate: ReferenceCandidate) -> str:
    payload = {
        "ordinal": candidate.source_ordinal,
        "title": normalized_title(candidate.title),
        "year": candidate.year,
        "doi": _normalize_doi(candidate.doi),
    }
    return _hash(payload)


def entity_key(metadata: Mapping[str, Any]) -> str:
    doi = _normalize_doi(metadata.get("doi"))
    if doi:
        return f"doi:{doi}"[:255]
    title = normalized_title(metadata.get("title"))
    year = metadata.get("year")
    first = _author_family((metadata.get("authors") or [None])[0])
    base = "|".join(str(x or "") for x in ("title", title, year, first))
    return ("title:" + hashlib.sha256(base.encode("utf-8")).hexdigest())[:255]


def signal_set_fingerprint(signals: list[Mapping[str, Any]]) -> str:
    shaped = [
        {
            "detector_kind": s["detector_kind"],
            "detector_status": s["detector_status"],
            "signal_key": s["signal_key"],
            "snapshot_marker": s["snapshot_marker"],
        }
        for s in sorted(signals, key=lambda x: (x["detector_kind"], x["signal_key"]))
    ]
    return _hash(shaped)


def inspect_reference(
    conn: Connection,
    candidate: ReferenceCandidate,
    *,
    crossref_client: CrossrefClient | None = None,
    openalex_client: OpenAlexClient | None = None,
    retraction_checkers: list[RetractionChecker],
    retraction_snapshot: str,
) -> ReferenceCheckResult:
    verification = _verify_bibliographic_entity(
        conn, candidate, crossref_client=crossref_client, openalex_client=openalex_client
    )
    entity = {**_candidate_metadata(candidate), **verification["entity"]}
    signals: list[DetectorSignal] = []
    if not verification["verified"]:
        signals.append(
            DetectorSignal(
                detector_kind="bibliographic_verification",
                detector_status="could_not_verify",
                evidence={
                    "label": "Could not verify with available sources",
                    "reason": verification["reason"],
                    "parsed": _candidate_metadata(candidate),
                    "sources_queried": verification["sources_queried"],
                    "candidate_matches": verification["candidate_matches"],
                },
                source="metadata-resolution",
                snapshot_marker=f"{DETECTOR_VERSION}:metadata",
            )
        )

    doi = _normalize_doi(entity.get("doi") or candidate.doi)
    if doi:
        outcome = detect_retraction(
            conn,
            {"doi": doi, "csl_json": {"DOI": doi, "title": entity.get("title") or candidate.title}},
            checkers=retraction_checkers,
        )
        if outcome.merged is not None:
            merged = outcome.merged
            evidence = {
                "label": "Known retraction signal",
                "status": merged.status,
                "nature": merged.nature,
                "sources": merged.sources,
                "doi": doi,
            }
            for key in ("date", "reason", "notice_doi", "notice_url"):
                value = getattr(merged, key)
                if value:
                    evidence[key] = value
            signals.append(
                DetectorSignal(
                    detector_kind="retraction",
                    detector_status="known_retraction_signal",
                    evidence=evidence,
                    source="retraction",
                    snapshot_marker=f"{DETECTOR_VERSION}:retraction:{retraction_snapshot}",
                )
            )
    return ReferenceCheckResult(candidate=candidate, entity_metadata=entity, signals=signals)


def propagation_signal(source_instances: list[Mapping[str, Any]]) -> DetectorSignal | None:
    if not source_instances:
        return None
    evidence = {
        "label": "Previously flagged in your library",
        "reason": "The same referenced entity has an active reference signal in another paper.",
        "source_instances": [
            {
                "citing_paper_id": int(row["citing_paper_id"]),
                "citation_instance_id": int(row["citation_instance_id"]),
                "review_state": row["review_state"],
                "detector_kinds": row["detector_kinds"],
                "title": row["title"],
            }
            for row in source_instances[:10]
        ],
    }
    return DetectorSignal(
        detector_kind="own_library_propagation",
        detector_status="previously_flagged_in_library",
        evidence=evidence,
        source="local-library",
        snapshot_marker=f"{DETECTOR_VERSION}:local-propagation",
    )


def _verify_bibliographic_entity(
    conn: Connection,
    candidate: ReferenceCandidate,
    *,
    crossref_client: CrossrefClient | None,
    openalex_client: OpenAlexClient | None,
) -> dict[str, Any]:
    sources: list[str] = []
    matches: list[dict[str, Any]] = []
    if candidate.context.get("reference_source") == "openalex:referenced_works" and candidate.title:
        meta = _candidate_metadata(candidate)
        return {
            "verified": True,
            "entity": meta,
            "sources_queried": ["openalex:referenced_works"],
            "candidate_matches": [{**meta, "source": "openalex", "match_basis": "referenced-work-record"}],
        }
    doi = _normalize_doi(candidate.doi)
    title = (candidate.title or "").strip()
    if not doi and not title:
        return {
            "verified": False,
            "entity": {},
            "sources_queried": [],
            "candidate_matches": [],
            "reason": "No DOI or parsed title was available to query.",
        }

    if doi:
        sources.append("crossref:doi")
        try:
            resolution = (crossref_client or CrossrefClient()).resolve_doi(conn, doi)
            if resolution.resolved and resolution.csl_json:
                meta = _metadata_from_csl(resolution.csl_json)
                matches.append({**meta, "source": "crossref", "match_basis": "doi"})
                return {"verified": True, "entity": meta, "sources_queried": sources, "candidate_matches": matches}
        except Exception:
            pass

    if doi or title:
        source_name = "openalex:doi" if doi else "openalex:title"
        sources.append(source_name)
        try:
            ref = PaperRef(doi=doi, title=None if doi else title)
            csl = (openalex_client or OpenAlexClient()).fetch_work_csl(conn, ref)
            if csl:
                meta = _metadata_from_csl(csl)
                basis = _match_basis(candidate, meta)
                matches.append({**meta, "source": "openalex", "match_basis": basis or "no conservative match"})
                if basis:
                    return {"verified": True, "entity": meta, "sources_queried": sources, "candidate_matches": matches}
        except Exception:
            pass

    return {
        "verified": False,
        "entity": {},
        "sources_queried": sources,
        "candidate_matches": matches,
        "reason": "No conservative match was returned by the available sources.",
    }


def _candidate_metadata(candidate: ReferenceCandidate) -> dict[str, Any]:
    return {
        "title": candidate.title,
        "authors": candidate.authors,
        "year": candidate.year,
        "doi": _normalize_doi(candidate.doi),
        "raw_text": candidate.raw_text,
    }


def _metadata_from_csl(csl: Mapping[str, Any]) -> dict[str, Any]:
    issued = csl.get("issued") if isinstance(csl.get("issued"), dict) else {}
    parts = issued.get("date-parts") if isinstance(issued, dict) else None
    year = parts[0][0] if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0] else None
    return {
        "title": str(csl.get("title") or "") or None,
        "authors": _authors_from_csl(csl),
        "year": int(year) if isinstance(year, int) else None,
        "doi": _normalize_doi(csl.get("DOI") or csl.get("doi")),
    }


def _authors_from_csl(csl: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for author in csl.get("author") or []:
        if not isinstance(author, dict):
            continue
        if author.get("literal"):
            out.append(str(author["literal"]))
        elif author.get("family") and author.get("given"):
            out.append(f"{author['given']} {author['family']}")
        elif author.get("family"):
            out.append(str(author["family"]))
    return out[:8]


def _match_basis(candidate: ReferenceCandidate, meta: Mapping[str, Any]) -> str | None:
    cand_doi = _normalize_doi(candidate.doi)
    meta_doi = _normalize_doi(meta.get("doi"))
    if cand_doi and meta_doi and cand_doi == meta_doi:
        return "doi"
    a = normalized_title(candidate.title)
    b = normalized_title(meta.get("title"))
    if not a or not b:
        return None
    if a == b and _years_compatible(candidate.year, meta.get("year")):
        return "normalized-title-year"
    ta, tb = set(a.split()), set(b.split())
    if ta and tb and len(ta & tb) / len(ta | tb) >= 0.85 and _years_compatible(candidate.year, meta.get("year")):
        return "high-title-overlap-year"
    return None


def _years_compatible(a: int | None, b: Any) -> bool:
    return a is None or b is None or int(a) == int(b)


def _author_family(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower()
    return re.split(r"\s+", text)[-1] if text else None


def _normalize_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip().lower().replace("https://doi.org/", "")
    return doi or None


def _hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
