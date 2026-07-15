"""Deterministic frontend-assembly smoke (no browser, no network).

The frontend ships as ordered ``app/frontend/js/*.jsx`` chunks concatenated by
``frontend.assemble_jsx`` and **precompiled to plain JS by esbuild** (inc 102) into the single
``<script>`` of ``frontend.build_frontend_document``, mirrored to the generated
``callosum-app.html`` by ``tools/build_frontend.py``. The most likely frontend regression is an
assembly break — a dropped chunk, a consumed placeholder left behind, a missing SRI tag, or a
``callosum-app.html`` left stale after a source edit. These guard exactly that, fast and offline.
The live browser smoke (``tests/e2e/``) covers runtime rendering and is opt-in for CI.

The transpiling tests require the build toolchain (``npm install`` → pinned esbuild); the
chunk-completeness test checks the raw concatenation, so it needs no toolchain.
"""

from __future__ import annotations

from pathlib import Path

from app.backend.api.frontend import (
    FRONTEND_DIR,
    assemble_jsx,
    build_frontend_document,
    frontend_sources_available,
)
from app.backend.api.startup import PROJECT_ROOT

BUILT_ARTIFACT = PROJECT_ROOT / "callosum-app.html"


def test_frontend_sources_present():
    assert frontend_sources_available()


def test_assembles_and_placeholders_consumed():
    doc = build_frontend_document()
    assert isinstance(doc, str) and len(doc) > 100_000  # a real assembled document, not a stub
    assert "{{STYLES}}" not in doc and "{{SCRIPT}}" not in doc  # both placeholders filled
    assert '<div id="root"></div>' in doc  # the React mount point
    # The JSX is precompiled (inc 102) — plain JS, no in-browser Babel.
    assert 'type="text/babel"' not in doc and "babel.min.js" not in doc
    assert "React.createElement(" in doc  # proof the JSX was transpiled to the classic runtime


def test_all_cdn_scripts_have_sri():
    """Every third-party CDN <script> must carry a Subresource-Integrity hash (inc 53)."""
    doc = build_frontend_document()
    assert doc.count('integrity="sha384-') >= 2
    for src in ("react.production.min.js", "react-dom.production.min.js"):
        assert src in doc, f"missing CDN script {src}"


def test_every_js_chunk_is_included():
    # Checked against the RAW concatenation (pre-transpile), so completeness is verified without esbuild.
    chunks = sorted((FRONTEND_DIR / "js").glob("*.jsx"))
    assert chunks, "no js chunks found"
    raw = assemble_jsx()
    for chunk in chunks:
        text = chunk.read_text(encoding="utf-8")
        assert text in raw, f"{chunk.name} is missing from the assembled frontend"


def test_stale_discover_placeholder_is_removed_from_theory_accordion():
    raw = assemble_jsx()
    assert 'label: "Funding Discovery"' in raw
    assert '{ id: "discover", label: "Discover", paneId: "theory"' not in raw
    assert 'label: "Beyond library"' not in raw
    assert 'title="Beyond library"' not in raw
    assert "Discover/Search (inc 184) + Feed (inc 188) shipped as center-pane tabs" in raw


def test_meta_reference_list_sits_before_journal_search_with_accessible_review_controls():
    raw = assemble_jsx()
    assert 'id: "meta-references", label: "Meta Reference List", paneId: "theory", order: 28' in raw
    assert 'id: "publishers", label: "Where to submit", paneId: "theory", order: 30' in raw
    assert 'aria-label="Reviewed and dismissed"' in raw
    assert 'aria-label="Reviewed and confirmed as a concern"' in raw
    assert "aria-pressed={dismissed}" in raw and "aria-pressed={confirmed}" in raw
    assert "ref-source-link" in raw and "onOpenPaper" in raw
    assert "Source coverage for last run" in raw
    assert "Retry reference check" in raw
    assert 'ProgressBar progress={state.progress} label="Checking reference list…"' in raw
    assert "data.last_checked_at" in raw
    assert "function BulkReferenceCheckButton(" in raw
    assert 'apiPost("/reference-integrity/run-selected", { paper_ids: ids })' in raw
    assert "onBulkReferenceCheckDone" in raw
    assert "libraryReferenceFilter" in raw
    assert "Reference checks: <b>{libraryReferenceFilter.label}</b>" in raw
    assert 'aria-label="Open Meta Reference List for this paper"' in raw
    assert "onOpenReferenceWarnings && onOpenReferenceWarnings(p)" in raw
    assert 'setTheoryOpen("meta-references")' in raw
    assert "onOpenReferenceWarnings: openReferenceWarnings" in raw


def test_tag_validation_errors_are_inline_and_accessible():
    raw = assemble_jsx()
    assert 'const [error, setError] = useState("")' in raw
    assert "setError(r.error || `Couldn't add" in raw
    assert 'setError(r.error || "Couldn\'t set that color.")' in raw
    assert 'setError(r.error || "Couldn\'t remove that tag.")' in raw
    assert "aria-invalid={!!error}" in raw
    assert "aria-describedby={error ? errorId : undefined}" in raw
    assert 'className="axis-err tag-error" role="alert"' in raw
    assert '.tag-add[aria-invalid="true"]' in Path("app/frontend/styles.css").read_text(encoding="utf-8")


def test_tag_lock_controls_are_per_paper_and_accessible():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert "const setLocked = async (tagId, locked)" in raw
    assert "apiPost(`/papers/${paperId}/tags/${tagId}/lock`, { locked })" in raw
    assert 'aria-label={t.locked ? "Unlock this tag on this paper" : "Lock this tag on this paper"}' in raw
    assert "aria-pressed={!!t.locked}" in raw
    assert '!t.locked && <button className="tag-chip-x"' in raw
    assert ".tag-chip-lock" in css and ".tag-chip-lock.on" in css


def test_library_header_actions_wrap_at_narrow_widths():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert 'className="lib-head-actions"' in raw
    assert ".lib-head { display: flex; flex-wrap: wrap;" in css
    assert ".lib-head .eyebrow { flex: 0 0 auto; }" in css
    assert "display: flex; flex: 1 1 220px; flex-wrap: wrap;" in css
    assert "gap: 6px 10px; min-width: 0;" in css
    assert ".lib-head-actions .trash-toggle" in css
    assert "white-space: normal" in css


def test_statcheck_rows_render_inline_context_evidence():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert '<EvidenceQuote text={r.context} match={r.raw} label="Context"' in raw
    assert "section={r.section}" in raw
    assert "precision={r.coordinate_precision} hasSourcePage={r.page != null}" in raw
    assert '<EvidenceTrail detector="statcheck" matched={r.raw}' in raw
    assert "page={r.page} section={r.section}" in raw
    assert 'className="statcheck-item-main"' in raw
    assert 'className="statcheck-context"' in raw
    assert 'precision: r.coordinate_precision || "region"' in raw
    assert "bboxJson: r.bbox_json || null" in raw
    assert "Open and highlight this reported test" in raw
    assert ".statcheck-context" in css
    assert ".evidence-mark" in css
    assert ".evidence-trail" in css


def test_synthesis_quotes_open_existing_pdf_highlight_route():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert "<EvidenceQuote" in raw
    assert 'label="Evidence quote"' in raw
    assert "precision={citation.coordinate_precision}" in raw
    assert "section={citation.section}" in raw
    assert "hasSourcePage={citation.page_start != null || citation.page_end != null}" in raw
    assert 'openLabel={citation.coordinate_precision === "exact" ? "Open source and highlight this quote"' in raw
    assert "onOpenCitation(citation)" in raw
    assert ".evidence-quote.is-clickable" in css
    assert ".evidence-precision" in css
    assert ".coord.page" in css


def test_synthesis_section_filter_is_retrieval_only_control():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert "SYNTH_SECTION_OPTIONS" in raw
    assert 'className="tags-srcfilter synth-section-filter"' in raw
    assert 'aria-label="Synthesis evidence section filter"' in raw
    assert 'title="Search all eligible chunks"' in raw
    assert "selectedSynthesisSections(sectionFilter)" in raw
    assert "sections.length ? { ...requestBody, sections } : requestBody" in raw
    assert "section filter only narrows retrieval; verification thresholds are unchanged" in raw
    assert ".tags-srcfilter { display: flex; flex-wrap: wrap;" in css
    assert ".synth-section-filter .tags-srcfilter-btn { flex: 0 1 auto; white-space: normal; }" in css


def test_synthesis_failure_recovery_actions_are_wired():
    raw = assemble_jsx()
    assert "function classifySynthesisFailure(error)" in raw
    assert "function SynthesisFailure(" in raw
    assert "function synthesisSourceDiagnostic(" in raw
    assert "function SynthesisSourceDiagnostic(" in raw
    assert "Repair cache and retry" in raw
    assert 'apiPost("/settings/repair-summary-cache", {})' in raw
    assert "Open Text Health" in raw
    assert "Check PDF text health" in raw
    assert 'onOpenTextHealth({ source: "synthesis", paperIds: body.paper_ids || [], onRetry: retryLast })' in raw
    assert 'api("/papers/text-health/overview")' in raw
    assert "No source chunks matched this query" in raw
    assert "no extracted text" in raw
    assert "stale extraction" in raw
    assert "Open scoped Text Health" in raw
    assert "Technical detail" in raw
    assert "lastLaunchRef.current = { body, runningMessage }" in raw
    assert "onOpenTextHealth={ctx.onOpenTextHealth}" in raw
    assert "onOpenTextHealth: openTextHealth" in raw


def test_pdf_text_health_controls_are_present_and_local_only_worded():
    raw = assemble_jsx()
    assert "function TextHealthButton(" in raw
    assert "function TextHealthModal(" in raw
    assert "function ReprocessSelectedTextButton(" in raw
    assert "const [textHealthContext, setTextHealthContext] = useState(null)" in raw
    assert "function TextHealthModal({ onClose, onOpenPaper, onOpenDetails, onShowLibrary, onChanged, context })" in raw
    assert "Opened from Synthesis · showing text-health signals for" in raw
    assert "Return to synthesis scope" in raw
    assert "Reprocess scoped papers" in raw
    assert "scopedActionableIds" in raw
    assert 'apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: scopedActionableIds })' in raw
    assert "No scoped paper has a reprocessable text-health signal." in raw
    assert "Retry synthesis" in raw
    assert "context={textHealthContext}" in raw
    assert "setTextHealthContext(null)" in raw
    assert 'api("/papers/text-health/overview")' in raw
    assert "onOpenTextHealth: () => openTextHealth()" in raw
    assert (
        "<TextHealthModal onClose={() => { setTextHealthOpen(false); setTextHealthContext(null); }} onOpenPaper={openPdf}"
        in raw
    )
    assert "onOpenDetails={openPaperDetails}" in raw
    assert 'setMethodsOpen("details")' in raw
    assert "Reprocess missing section labels" in raw
    assert "Stale extraction version" in raw
    assert "counts.stale_chunk_version" in raw
    assert "details for OCR" in raw
    assert "Show in Library" in raw
    assert "onShowLibrary={showTextHealthFilter}" in raw
    assert "libraryTextHealthFilter" in raw
    assert "Text health: <b>{libraryTextHealthFilter.label}</b>" in raw
    assert "OCR remains a" in raw
    assert 'apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: ids })' in raw
    assert "No OCR, no metadata changes, no network." in raw
    assert "<TextHealthButton onOpen={onOpenTextHealth} />" in raw
    assert "<ReprocessSelectedTextButton paperIds={[...selectedLibraryIds]} onDone={onEnriched} />" in raw


def test_details_extra_urls_are_first_class_rows():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert "function PaperUrlsEditor(" in raw
    assert "apiPost(`/papers/${paper.id}/urls`, { url: trimmed, label: label.trim() || null })" in raw
    assert "apiDelete(`/papers/${paper.id}/urls/${item.id}`)" in raw
    assert "<PaperUrlsEditor paper={p} readOnly={readOnly} onChanged={refreshDetail} />" in raw
    assert ".paper-url-row" in css
    assert ".paper-url-add" in css


def test_reresolve_reports_displayed_metadata_changes():
    raw = assemble_jsx()
    assert "function describeReresolveChanges(before, after)" in raw
    assert '["doi", "DOI"]' in raw
    assert '["publication_date", "publication date"]' in raw
    assert "paperTagNames(before)" in raw
    assert "added ${addedTags.length} keyword tag" in raw
    assert "Resolved from ${srcName}. ${diff}." in raw
    assert "Resolved from ${srcName}; no displayed fields changed." in raw


def test_methods_auditors_use_shared_evidence_source_targets():
    raw = assemble_jsx()
    assert "function methodEvidenceTarget(" in raw
    for expected in (
        "`bayes-check:${it.key}`",
        "`bayes-advisory:${a.key}:${i}`",
        "`lmm-check:${c.key}`",
        "`meta-check:${c.key}`",
        "`transparency-check:${c.key}`",
    ):
        assert expected in raw
    assert raw.count('label="Evidence" className="bayes-check-ev"') >= 5
    assert "function evidencePrecisionText(" in raw
    assert "function EvidenceTrail(" in raw
    assert "exact highlight" in raw and "page only" in raw and "no source page" in raw
    assert raw.count("hasSourcePage={") >= 7
    assert raw.count("<EvidenceTrail detector=") >= 6


def test_set_critical_review_modal_shipped():
    """Backlog #12 (set critical review): the multi-paper modal + its two entry points assemble, and the
    honesty framing (fact-matrix caption, amber candidate reuse, no score) ships with it."""
    raw = assemble_jsx()
    assert "function CriticalSetModal(" in raw  # the modal component
    assert '"/critical-read/set"' in raw  # it drives the set endpoint
    assert "Critically review these sources" in raw  # the synthesis entry-point button
    assert "not a score" in raw  # the fact-matrix honesty caption (never a composite score)
    assert "cr-candidate" in raw  # amber candidate rendering reused for Tier-2 cross-paper candidates
    assert "the model’s framing, not a verified link" in raw  # related_paper_ids is framing, not a #13-verified link


def test_built_artifact_is_in_sync():
    """callosum-app.html must equal the live assembly — i.e. it was rebuilt after the last source
    edit (CLAUDE.md: re-run tools/build_frontend.py after editing app/frontend/)."""
    assert BUILT_ARTIFACT.is_file(), "callosum-app.html missing — run python tools/build_frontend.py"
    assert BUILT_ARTIFACT.read_text(encoding="utf-8") == build_frontend_document(), (
        "callosum-app.html is stale — re-run python tools/build_frontend.py"
    )
