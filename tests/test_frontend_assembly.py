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


def test_workspace_menubar_structure_present():
    raw = assemble_jsx()
    # The registry + menu bar + workspace pane are wired (inc 280).
    assert "function registerWorkspace(" in raw and "function registerWorkspaceTab(" in raw
    assert "function MenuBar(" in raw and "function WorkspacePane(" in raw
    # The core workspaces are registered in menu order, with Library default.
    for wid in (
        'id: "profile"',
        'id: "library"',
        'id: "synthesis"',
        'id: "discover"',
        'id: "work"',
        'id: "extract"',
    ):
        assert wid in raw, wid
    assert 'id: "profile", label: "My Publications", order: 10' in raw
    # Discover holds Search+Journals+Funding; Feed is embedded below Search results (inc 285).
    # Work holds Cite+CRediT; Extract holds Workbench+Effect-Size+Meta-Analysis.
    assert 'id: "search"' in raw and 'id: "feed"' not in raw and 'id: "workbench"' in raw
    assert 'id: "journals"' in raw and 'id: "funding"' in raw and 'id: "effectsize"' in raw
    assert 'label: "Effect-Size"' in raw and 'label: "Meta-Analysis"' in raw and 'label: "CRediT statement"' in raw
    assert "function CiteWorkspacePane(" in raw and "function registerCiteTab(" in raw
    assert 'id: "suggest", label: "Suggest", order: 10' in raw
    assert 'id: "meta-references", label: "Meta Reference List", order: 15' in raw
    assert 'id: "citation-equity", label: "Citation concentration", order: 20' in raw
    assert 'id: "citation-context", label: "How it\'s cited", order: 30' in raw
    # The relocated sections no longer register as THEORY/METHODS pane sections.
    assert 'id: "publishers"' not in raw and 'id: "funding-discovery"' not in raw
    assert 'label: "Effect-size converter"' not in raw and 'label: "Meta-analysis reporting"' not in raw
    assert 'id: "synthesis", label: "Synthesis", paneId: "theory"' not in raw
    assert 'id: "cite", label: "Cite", tabLabel: "Suggest", paneId: "theory"' not in raw
    assert 'id: "meta-references", label: "Meta Reference List", paneId: "theory"' not in raw
    assert 'id: "credit", label: "CRediT statement", paneId: "theory"' not in raw
    # The shell renders the menu bar + persists the active workspace.
    assert "menubar-nav" in raw and '"callosum.workspace"' in raw
    assert 'activeWorkspace === "library"' in raw and 'activeWorkspace === "profile"' in raw
    assert 'activeWorkspace === "synthesis"' in raw and 'activeWorkspace === "work"' in raw
    # Stage 3: Help + Settings are utility workspaces (center views), not modals.
    assert 'id: "help"' in raw and 'id: "settings"' in raw and "utility: true" in raw
    assert "function HelpView(" in raw and "function SettingsView(" in raw
    assert "function HelpModal(" not in raw and "function SettingsModal(" not in raw
    # inc 285: library discovery modals launch from Discover Search, not the Library header; Feed renders below Search.
    assert "<FeedPane onSaved={onSaved} active={active} embedded />" in raw
    assert "onOpenWanted={ctx.onOpenWanted}" in raw and "onOpenGaps={ctx.onOpenGaps}" in raw
    assert "onOpenOverlooked={ctx.onOpenOverlooked}" in raw
    assert 'title="Papers you want an OA copy of' in raw and 'title="Works related to several of your papers' in raw
    assert 'title="Per axis: works relevant to it but under-cited' in raw
    assert "onFindDuplicates, onOpenWanted" not in raw and "onFindDuplicates, onOpenScan" in raw
    # inc 284: returning users get a one-time Library hint for relocated tools.
    assert "callosum.workspaces-whatsnew" in raw
    assert "function WorkspacesWhatsNewHint(" in raw
    assert "New layout:" in raw and "Synthesis" in raw and "Meta Reference List" in raw and "CRediT" in raw
    assert "Discover → Search" in raw and "Wanted" in raw and "Gaps" in raw and "Overlooked" in raw
    assert "Effect-Size" in raw and "Meta-Analysis" in raw and "Work" in raw
    assert '_saveLayout(WORKSPACES_WHATSNEW_KEY, "1")' in raw
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert (
        ".workspace-body { display: flex; flex: 1 1 auto; min-height: 0; flex-direction: column; overflow-y: auto; }"
        in css
    )


def test_library_selected_paper_tab_and_pdf_reorder_present():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert "selectedPaperTab" in raw
    assert "tabs.some(t => t.paperId === selected)" in raw
    assert 'className="frame-tab frame-tab-selected"' in raw
    assert 'title="Selected paper, not open' in raw
    assert "onOpenPdf({ id: selectedPaperTab.id, title: selectedPaperTab.title })" in raw
    assert 'const PDF_TAB_DRAG_TYPE = "application/x-callosum-pdftab"' in raw
    assert "draggable" in raw and "onReorderTabs(dragged, t.key)" in raw
    assert "function LibraryFrame({ libraryProps, tabs, selectedPaperTab" in raw
    assert "const reorderPdfTabs = useCallback((draggedKey, targetKey)" in raw
    assert ".frame-tab-selected" in css
    assert ".frame-tab.dragover" in css


def test_my_publications_workspace_loads_without_axis_card_button():
    raw = assemble_jsx()
    assert "function MyPubsDashboard({ axisId, axisRefresh, onSummarize, onSelectPaper, onOpenPdf })" in raw
    assert "const [resolvedAxisId, setResolvedAxisId] = useState(axisId || null)" in raw
    assert 'const ax = (r.data || []).find(a => a.kind === "my_publications")' in raw
    assert "axisId={resolvedAxisId}" in raw
    assert "axisRefresh={axisRefresh}" in raw
    assert 'title="Open the impact dashboard"' not in raw


def test_overlooked_lens_panel_present_and_honest():
    raw = assemble_jsx()
    # The panel exists and wires to its endpoints.
    assert "function OverlookedLensModal(" in raw
    assert '"/overlooked/refresh"' in raw and "/overlooked?axis_id=" in raw
    assert "onOpenOverlooked" in raw  # the header entry point is wired through
    # The two SEPARABLE visible inputs are shown as distinct copy (relevance + citations-vs-vintage percentile)...
    assert "relevance" in raw and "percentile for" in raw and "cited" in raw
    # ...and framed honestly (silence-not-a-certificate): possibly overlooked, possibly just low-impact.
    assert "possibly overlooked" in raw.lower()
    assert "low-impact" in raw.lower()
    # The vetoes: never a composite "hidden-gem"/opaque score in the panel.
    assert "hidden-gem" not in raw.lower() and "hidden gem" not in raw.lower()
    # Add/Dismiss reuse the gap flow.
    assert '"/gaps/add"' in raw and '"/gaps/dismiss"' in raw
    # Credit-the-lineage (inc 282): the lens credits the Matthew-effect source in-panel + offers it to the library
    # via the shared .method-credit recipe.
    assert "function OverlookedCredit(" in raw and "method-credit" in raw
    assert "MERTON1968_CSL" in raw and "10.1126/science.159.3810.56" in raw


def test_stale_discover_placeholder_is_removed_from_theory_accordion():
    raw = assemble_jsx()
    assert 'label: "Funding"' in raw  # relocated to the Discover workspace (inc 280); was THEORY "Funding Discovery"
    assert '{ id: "discover", label: "Discover", paneId: "theory"' not in raw
    assert 'label: "Beyond library"' not in raw
    assert 'title="Beyond library"' not in raw
    assert "Discover/Search (inc 184) + embedded Feed (inc 188/285) now ship in the Discover workspace" in raw


def test_meta_reference_list_sits_before_journal_search_with_accessible_review_controls():
    raw = assemble_jsx()
    assert 'id: "meta-references", label: "Meta Reference List", order: 15' in raw
    assert 'aria-label="Cite tools"' in raw and "callosum.citetab" in raw
    # inc 280: "Where to submit" relocated out of THEORY to the Discover workspace as the Journals tab.
    assert 'id: "publishers", label: "Where to submit", paneId: "theory"' not in raw
    assert 'id: "journals", label: "Journals"' in raw
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
    assert 'requestWorkspaceTab("work", "cite")' in raw
    assert 'requestCiteTab("meta-references")' in raw
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
    assert "Check PDF Text Health" in raw
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
    assert "Text Health: <b>{libraryTextHealthFilter.label}</b>" in raw
    assert "<span>PDF Text Health</span>" in raw
    assert "OCR remains a" in raw
    assert 'apiPost("/papers/text-health/reprocess", { mode: "selected", paper_ids: ids })' in raw
    assert "No OCR, no metadata changes, no network." in raw
    assert "<TextHealthButton onOpen={onOpenTextHealth} />" in raw
    assert "<ReprocessSelectedTextButton paperIds={[...selectedLibraryIds]} onDone={onEnriched} />" in raw


def test_library_header_polish_labels_and_positive_open_data_signal():
    raw = assemble_jsx()
    assert '"Metadata ↻"' in raw
    assert "Filled ${done.fields_filled}" in raw
    assert "Last refreshed ${fmtDateTime(lastRun)}" in raw
    assert '"Text Health"' in raw
    assert "Last refreshed ${fmtDateTime(lastLoaded)}" in raw
    assert "🔎 Open Data · {openDataDetected}" in raw
    assert 'onShowTransparencyReview("transparency-data-detected")' in raw
    assert "⚠ Flagged · {statcheckFlagged}" in raw
    assert "⚠ Retracted · {retractionFlagged}" in raw
    assert "📋 Review · {findingsToReview}" in raw
    assert "open data not detected</button>" not in raw


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
