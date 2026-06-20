"""Render a ValidationReport as a human-readable markdown report."""

from __future__ import annotations

from pathlib import Path

from tools.validation.reports import (
    ValidationReport,
)


def render_markdown_report(report: ValidationReport) -> str:
    lines = [
        "# Callosum Validation Report",
        "",
        f"- Output directory: `{report.output_dir}`",
        f"- Scratch database: `{report.database_path}`",
        f"- Scratch database reused: {report.database_reused}",
        f"- Scratch database created: {report.database_created}",
        f"- Scratch database migrated: {report.database_migrated}",
        "",
        "## PDF Extraction Fidelity",
        "",
    ]
    if not report.pdf_reports:
        lines.append("No standalone PDF directory was validated.")
    for pdf_report in report.pdf_reports:
        fraction = pdf_report.pages_with_text / pdf_report.page_count if pdf_report.page_count else 0
        lines.extend(
            [
                f"### {Path(pdf_report.path).name}",
                f"- Path: `{pdf_report.path}`",
                f"- Page count: {pdf_report.page_count}",
                f"- Chunk count: {pdf_report.chunk_count}",
                f"- Pages with extractable text: {pdf_report.pages_with_text}/{pdf_report.page_count} ({fraction:.0%})",
                f"- Zero text / likely scanned: {pdf_report.zero_text}",
                f"- Reused existing ingest: {pdf_report.reused_existing}",
            ]
        )
        if pdf_report.pages_without_text:
            lines.append(f"- Pages without text: {', '.join(map(str, pdf_report.pages_without_text))}")
            lines.append("  - Per-page hints:")
            for pd in pdf_report.page_details:
                if not pd.has_text:
                    lines.append(f"    - Page {pd.page_number}: {pd.hint}")
        if pdf_report.error:
            lines.append(f"- Extraction error: `{pdf_report.error}`")
        if pdf_report.quote_results:
            lines.append("- Quote checks:")
            for result in pdf_report.quote_results:
                lines.append(
                    f"  - {'found' if result['found'] else 'not found'}"
                    f" page={result.get('page_start')} quote={result['quote']!r}"
                )
        lines.append("")

    lines.extend(["## Zotero Schema And Import", ""])
    if report.zotero_schema is None:
        lines.append("No Zotero directory was validated.")
    else:
        schema = report.zotero_schema
        lines.extend(
            [
                f"- Source DB unchanged: {schema.read_only_unchanged}",
                f"- Expected tables present: {', '.join(schema.present_tables) or 'none'}",
                f"- Expected tables missing: {', '.join(schema.missing_tables) or 'none'}",
                f"- Optional tables present: {', '.join(schema.optional_present) or 'none'}",
                f"- Optional tables missing: {', '.join(schema.optional_missing) or 'none'}",
            ]
        )
        if schema.missing_columns:
            lines.append("- Missing expected columns:")
            for table, missing in schema.missing_columns.items():
                lines.append(f"  - {table}: {', '.join(missing)}")
        if schema.warnings:
            lines.append("- Schema warnings:")
            for warning in schema.warnings:
                lines.append(f"  - {warning}")
        if report.zotero_import:
            imported = report.zotero_import
            lines.extend(
                [
                    f"- Import error: {imported.error or 'none'}",
                    f"- Papers in Callosum DB: {imported.imported_items}",
                    f"- Attachments in Callosum DB: {imported.imported_attachments}",
                    f"- Available attachments: {imported.available_attachments}",
                    f"- Missing attachments: {imported.missing_attachments}",
                    f"- URL attachments: {imported.url_attachments}",
                ]
            )
            if imported.result:
                lines.extend(
                    [
                        f"- Papers created: {imported.result.papers_created}",
                        f"- Papers matched: {imported.result.papers_matched}",
                        f"- Attachments created: {imported.result.attachments_created}",
                        f"- Chunks created: {imported.result.chunks_created}",
                    ]
                )
            if imported.attachment_errors:
                lines.append("- Attachment extraction errors:")
                for error in imported.attachment_errors:
                    lines.append(f"  - {error}")
    lines.extend(["", "## Retrieval Spot Check", ""])
    retrieval = report.retrieval
    if retrieval.embedding_error:
        lines.append(f"- Embedding/retrieval error: `{retrieval.embedding_error}`")
    lines.extend(
        [
            f"- Chunk embeddings: {retrieval.chunk_embeddings}",
            f"- Paper embeddings: {retrieval.paper_embeddings}",
        ]
    )
    if not retrieval.query_results:
        lines.append("No queries were run.")
    for query, hits in retrieval.query_results.items():
        lines.append(f"### Query: {query}")
        if not hits:
            lines.append("- No hits.")
            continue
        for index, hit in enumerate(hits, start=1):
            lines.append(
                f"{index}. score={hit['score']:.3f} paper_id={hit['paper_id']} "
                f"chunk_id={hit.get('chunk_id')} page={hit.get('page_start')} "
                f"title={hit.get('title')!r}"
            )
            if hit.get("snippet"):
                lines.append(f"   - {hit['snippet']}")
    lines.append("")
    lines.extend(["## Axis Calibration", ""])
    if not report.axis_calibration:
        lines.append("No axis calibration probes were run.")
    for axis_report in report.axis_calibration:
        lines.append(f"### Axis: {axis_report.label}")
        if axis_report.description:
            lines.append(f"- Description: {axis_report.description}")
        if axis_report.error:
            lines.append(f"- Error: `{axis_report.error}`")
            continue
        if axis_report.largest_gap_rank is not None and axis_report.largest_gap is not None:
            lines.append(
                f"- Largest adjacent score gap: rank {axis_report.largest_gap_rank} gap={axis_report.largest_gap:.3f}"
            )
        if not axis_report.scores:
            lines.append("- No paper scores.")
            continue
        lines.append("| Rank | Score | Gap to next | Paper ID | Title |")
        lines.append("| ---: | ---: | ---: | ---: | :--- |")
        for score in axis_report.scores:
            gap = "" if score.gap_to_next is None else f"{score.gap_to_next:.3f}"
            lines.append(f"| {score.rank} | {score.score:.3f} | {gap} | {score.paper_id} | {score.title} |")
    lines.append("")
    lines.extend(["## Summarization Probe", ""])
    if report.summarization is None:
        lines.append("No summarization probe was run.")
    else:
        summary = report.summarization
        lines.extend(
            [
                f"- Scope: `{summary.scope}`",
                f"- Source chunks available: {summary.source_chunk_count}",
                f"- Support scorer: {summary.support_scorer}",
                f"- Support threshold: {summary.support_threshold:.3f}",
            ]
        )
        if summary.zero_chunk_message:
            lines.append(f"- WARNING: {summary.zero_chunk_message}")
        if summary.skipped_reason:
            lines.append(f"- Generation skipped: {summary.skipped_reason}")
        if summary.error:
            lines.append(f"- Summarization error: `{summary.error}`")
        if summary.summary_id is not None:
            lines.extend(
                [
                    f"- Summary ID: {summary.summary_id}",
                    f"- Summary status: {summary.status}",
                    f"- Verified sentences: {summary.verified_sentences}",
                    f"- Flagged sentences: {summary.flagged_sentences}",
                ]
            )
        for sentence in summary.sentences:
            marker = "FLAGGED" if sentence.flagged else "VERIFIED"
            lines.extend(
                [
                    "",
                    f"### Sentence {sentence.ordinal + 1}: {marker}",
                    f"> {sentence.text}",
                ]
            )
            if not sentence.citations:
                lines.append("- No citations.")
            for index, citation in enumerate(sentence.citations, start=1):
                page = (
                    str(citation.page_start)
                    if citation.page_start == citation.page_end or citation.page_end is None
                    else f"{citation.page_start}-{citation.page_end}"
                )
                lines.extend(
                    [
                        (
                            f"- Citation {index}: status={citation.status} "
                            f"paper={citation.paper_title!r} page={page} chunk_id={citation.chunk_id}"
                        ),
                        f"  - Quote located: {citation.quote_located}",
                        f"  - Quote: {citation.quote_text!r}",
                        (
                            "  - Scores: "
                            f"retrieval={citation.retrieval_confidence:.3f} "
                            f"quote={citation.quote_confidence:.3f} "
                            f"support={citation.support_confidence:.3f}"
                        ),
                    ]
                )
        if summary.support_scores:
            lines.extend(
                [
                    "",
                    "### Support-Score Distribution",
                    "| Rank | Support | Status | Sentence | Chunk |",
                    "| ---: | ---: | :--- | ---: | ---: |",
                ]
            )
            for item in summary.support_scores:
                lines.append(
                    f"| {item.rank} | {item.score:.3f} | {item.status} | "
                    f"{item.sentence_ordinal + 1} | {item.chunk_id} |"
                )
    lines.append("")
    return "\n".join(lines)
