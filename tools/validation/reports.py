"""Report data structures produced by the validation harness probes."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, TextIO

from app.backend.importers.zotero import ZoteroImportResult


@dataclass
class ProgressReporter:
    enabled: bool = True
    stream: TextIO = sys.stderr
    width: int = 28
    _active: bool = field(default=False, init=False, repr=False)

    def start(self, label: str, *, total: int | None = None) -> None:
        if not self.enabled:
            return
        self._active = total is not None and total > 0
        if self._active:
            self.update(label, current=0, total=total)
        else:
            self.stream.write(f"[callosum] {label}...\n")
            self.stream.flush()

    def update(self, label: str, *, current: int, total: int) -> None:
        if not self.enabled:
            return
        if total <= 0:
            self.start(label)
            return
        filled = int(self.width * min(current, total) / total)
        bar = "#" * filled + "-" * (self.width - filled)
        message = f"\r[callosum] {label} [{bar}] {min(current, total)}/{total}"
        self.stream.write(message)
        self.stream.flush()

    def finish(self, label: str, *, total: int | None = None) -> None:
        if not self.enabled:
            return
        if self._active and total is not None:
            self.update(label, current=total, total=total)
            self.stream.write("\n")
        else:
            self.stream.write(f"[callosum] {label} done.\n")
        self.stream.flush()
        self._active = False


@dataclass(frozen=True)
class QuoteCheck:
    pdf_name: str
    quote: str


@dataclass
class PageDetail:
    page_number: int
    has_text: bool
    hint: str | None = None


@dataclass
class PdfReport:
    path: str
    page_count: int = 0
    pages_with_text: int = 0
    chunk_count: int = 0
    zero_text: bool = False
    reused_existing: bool = False
    error: str | None = None
    quote_results: list[dict[str, Any]] = field(default_factory=list)
    pages_without_text: list[int] = field(default_factory=list)
    page_details: list[PageDetail] = field(default_factory=list)


@dataclass
class ZoteroSchemaReport:
    source_db_checksum_before: str | None = None
    source_db_checksum_after: str | None = None
    read_only_unchanged: bool | None = None
    present_tables: list[str] = field(default_factory=list)
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)
    optional_present: list[str] = field(default_factory=list)
    optional_missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ZoteroImportReport:
    result: ZoteroImportResult | None = None
    attachment_errors: list[str] = field(default_factory=list)
    imported_items: int = 0
    imported_attachments: int = 0
    available_attachments: int = 0
    missing_attachments: int = 0
    url_attachments: int = 0
    error: str | None = None


@dataclass
class RetrievalReport:
    embedding_error: str | None = None
    chunk_embeddings: int = 0
    paper_embeddings: int = 0
    query_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass(frozen=True)
class AxisCalibrationSpec:
    label: str
    description: str | None = None


@dataclass(frozen=True)
class AxisCalibrationScore:
    rank: int
    paper_id: int
    title: str
    score: float
    gap_to_next: float | None


@dataclass
class AxisCalibrationReport:
    label: str
    description: str | None
    scores: list[AxisCalibrationScore] = field(default_factory=list)
    largest_gap_rank: int | None = None
    largest_gap: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class SummarizationSpec:
    query: str | None = None
    paper_ids: list[int] | None = None
    cluster_node_id: int | None = None


@dataclass(frozen=True)
class SupportScoreDistributionItem:
    rank: int
    sentence_ordinal: int
    chunk_id: int
    status: str
    score: float


@dataclass
class SummarizationCitationReport:
    chunk_id: int
    paper_id: int | None
    paper_title: str | None
    page_start: int | None
    page_end: int | None
    quote_text: str
    quote_located: bool
    status: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float


@dataclass
class SummarizationSentenceReport:
    ordinal: int
    text: str
    flagged: bool
    citations: list[SummarizationCitationReport] = field(default_factory=list)


@dataclass
class SummarizationReport:
    scope: dict[str, Any]
    support_scorer: str
    support_threshold: float
    source_chunk_count: int = 0
    zero_chunk_message: str | None = None
    skipped_reason: str | None = None
    error: str | None = None
    summary_id: int | None = None
    status: str | None = None
    verified_sentences: int = 0
    flagged_sentences: int = 0
    sentences: list[SummarizationSentenceReport] = field(default_factory=list)
    support_scores: list[SupportScoreDistributionItem] = field(default_factory=list)


@dataclass
class ValidationReport:
    output_dir: str
    database_path: str
    database_reused: bool = False
    database_created: bool = False
    database_migrated: bool = False
    pdf_reports: list[PdfReport] = field(default_factory=list)
    zotero_schema: ZoteroSchemaReport | None = None
    zotero_import: ZoteroImportReport | None = None
    retrieval: RetrievalReport = field(default_factory=RetrievalReport)
    axis_calibration: list[AxisCalibrationReport] = field(default_factory=list)
    summarization: SummarizationReport | None = None
