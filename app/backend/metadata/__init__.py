"""Metadata acquisition and enrichment helpers."""

from app.backend.metadata.doi import DoiCandidate, find_doi_in_pdf, find_doi_in_text
from app.backend.metadata.enrichment import (
    MetadataEnrichmentResult,
    MetadataEnrichmentRunResult,
    enrich_paper_metadata_from_crossref,
    enrich_pdf_scaffold_library,
)

__all__ = [
    "DoiCandidate",
    "find_doi_in_pdf",
    "find_doi_in_text",
    "MetadataEnrichmentResult",
    "MetadataEnrichmentRunResult",
    "enrich_paper_metadata_from_crossref",
    "enrich_pdf_scaffold_library",
]
