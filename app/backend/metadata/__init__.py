"""Metadata acquisition and enrichment helpers."""

from app.backend.metadata.doi import DoiCandidate, find_doi_in_pdf, find_doi_in_text
from app.backend.metadata.enrichment import (
    MetadataEnrichmentResult,
    MetadataEnrichmentRunResult,
    MultiEnrichResult,
    enrich_paper_metadata_from_crossref,
    enrich_paper_metadata_from_identifier,
    enrich_paper_metadata_multi,
    enrich_pdf_scaffold_library,
    import_registry_keyword_tags,
)

__all__ = [
    "DoiCandidate",
    "find_doi_in_pdf",
    "find_doi_in_text",
    "MetadataEnrichmentResult",
    "MetadataEnrichmentRunResult",
    "MultiEnrichResult",
    "enrich_paper_metadata_from_crossref",
    "enrich_paper_metadata_from_identifier",
    "enrich_paper_metadata_multi",
    "enrich_pdf_scaffold_library",
    "import_registry_keyword_tags",
]
