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

import re
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


def test_frontend_uses_one_injectable_transport_without_changing_live_default():
    raw = assemble_jsx()
    assert "function callosumFetch(input, init)" in raw
    assert "window.CALLOSUM_DATA_PROVIDER" in raw
    assert "return window.fetch(input, init);" in raw
    assert 'if (isDemoMode()) return "";' in raw
    for chunk in sorted((FRONTEND_DIR / "js").glob("*.jsx")):
        source = chunk.read_text(encoding="utf-8")
        assert not re.search(r"(?<![.\w])fetch\(", source), f"{chunk.name} bypasses callosumFetch"


def test_my_publications_emerging_topics_is_explicit_grounded_and_scoped():
    raw = assemble_jsx()
    assert "function MyPubsEmergingTopics({ domains, onSelectPaper })" in raw
    assert 'apiPost("/my-publications/emerging-citing-topics/refresh"' in raw
    assert "No local snapshot for {scopeLabel}" in raw
    assert "Inspect the citing works behind both counts" in raw
    assert "The visible paper-count increase is descriptive evidence, not a forecast." in raw
    assert 'aria-label="Emerging-topic research-domain scope"' in raw


def test_my_publications_citing_authors_are_evidence_carried_and_not_recommendations():
    raw = assemble_jsx()
    assert "function MyPubsCitingAuthors" in raw
    assert 'apiPost("/my-publications/citing-authors/refresh"' in raw
    assert "at least two retrieved works" in raw
    assert "at least two of your confirmed publications" in raw
    assert "does not infer collaboration fit or recommend a person" in raw
    assert "Inspect every citing work and publication connection" in raw
    assert 'aria-label="Citing-author research-domain scope"' in raw
    assert "<MyPubsCitingAuthors domains={domains} onSelectPaper={onSelectPaper} />" in raw
    assert "onSelectPaper && onSelectPaper(paper.paper_id)" in raw
    assert "onSelectPaper({ id: paper.paper_id" not in raw
    assert "<MyPubsEmergingTopics domains={domains} onSelectPaper={onSelectPaper} />" in raw
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert ".mypubs-topic-change {" in css
    assert "@media (max-width: 520px)" in css


def test_workbench_batch_drafting_preserves_candidate_review_gate():
    src = (FRONTEND_DIR / "js" / "45_workbench.jsx").read_text(encoding="utf-8")
    css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
    assert "function workbenchDraftableRows(project)" in src
    assert "!(row.proposals || []).length" in src  # never replace candidates already awaiting review
    assert "Draft all un-filled rows →" in src
    assert 'label: "Drafting rows"' in src and "draftBatch.current" in src
    batch_body = src.split("const draftAll = async () => {", 1)[1].split("const acceptProposal", 1)[0]
    assert "for (let i = 0; i < targets.length; i += 1)" in batch_body
    assert "await requestDraft(row)" in batch_body  # sequential, bounded provider load
    assert "/accept" not in batch_body  # batching proposes only; every candidate still needs an individual choice
    assert "most relevant locally selected passages were sent" in src
    assert "only its first part was sent" not in src
    assert ".wb-gridwrap { overflow-x: auto; flex: 0 0 auto; }" in css  # table stays visible in the mobile flex pane


def test_workspace_menubar_structure_present():
    raw = assemble_jsx()
    # The registry + menu bar + workspace pane are wired (inc 280).
    assert "function registerWorkspace(" in raw and "function registerWorkspaceTab(" in raw
    assert "function MenuBar(" in raw and "function WorkspacePane(" in raw
    # The core workspaces are registered in menu order, with Library default. Extract no longer exists (folded
    # into Work in the Work/Extract reorg).
    for wid in (
        'id: "profile"',
        'id: "library"',
        'id: "synthesis"',
        'id: "discover"',
        'id: "work"',
    ):
        assert wid in raw, wid
    assert 'id: "extract"' not in raw
    assert 'id: "profile", label: "My Publications", order: 10' in raw
    # Discover holds Feed+Search+Journals+Funding.
    # Work holds Cite+Meta-Reference+CRediT+Meta-Analyze (Meta-Analyze = the relocated Workbench, with Effect-Size
    # folded in as its own subsection rather than a separate tab).
    assert 'id: "feed", label: "Feed", order: 10' in raw
    assert 'id: "search", label: "Search", order: 20' in raw and 'id: "meta-analyze"' in raw
    assert 'id: "journals"' in raw and 'id: "funding"' in raw
    assert 'id: "cite", label: "Cite", order: 10' in raw
    assert 'id: "meta-reference", label: "Meta-Reference", order: 20' in raw
    assert 'id: "credit", label: "CRediT", order: 30' in raw
    assert 'id: "meta-analyze", label: "Meta-Analyze", order: 40' in raw
    # The old nested Cite tab-strip (CITE_TABS/registerCiteTab/CiteWorkspacePane) is gone; Suggest, Meta Reference
    # List, Citation concentration, and How it's cited are no longer independently tab-registered.
    assert "function CiteWorkspacePane(" not in raw and "function registerCiteTab(" not in raw
    assert "const CITE_TABS" not in raw and "function citeTabs(" not in raw
    assert 'id: "suggest", label: "Suggest", order: 10' not in raw
    assert 'id: "meta-references", label: "Meta Reference List", order: 15' not in raw
    assert 'id: "citation-equity", label: "Citation concentration", order: 20' not in raw
    assert 'id: "citation-context", label: "How it\'s cited", order: 30' not in raw
    # Effect-Size no longer self-registers as an "extract" tab; it's called directly from WorkbenchPane.
    assert 'id: "effectsize", label: "Effect-Size"' not in raw
    assert "function EffectSizeSection()" in raw and "<EffectSizeSection />" in raw
    # Meta-Analysis no longer lives under Work/Extract; it moved into the METHODS accordion as a pane section.
    assert "function MetaSection(" in raw
    assert 'id: "meta", label: "Meta-Analysis", order: 30' not in raw
    # The new Meta-Reference wrapper stacks its tools as 5 subsections, not tabs: Meta Reference List, Citation
    # concentration (which itself contains Overlooked work), and citation-context's two directions -- each now an
    # independent, always-visible CitationContextSection instance (no more internal toggle).
    assert "function MetaReferencePane(" in raw
    assert "<MetaReferenceList ctx={ctx} />" in raw and "<CitationEquitySection ctx={ctx} />" in raw
    assert '<CitationContextSection ctx={ctx} direction="citations" />' in raw
    assert '<CitationContextSection ctx={ctx} direction="references" />' in raw
    assert "function CitationContextPaper({ paperId, direction })" in raw
    assert "function CitationContextSection({ ctx, direction })" in raw
    assert "citec-toggle" not in raw and "const switchDir" not in raw
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert ".citec-toggle" not in css
    assert 'label: "CRediT statement"' not in raw
    # The relocated sections no longer register as THEORY/METHODS pane sections.
    assert 'id: "publishers"' not in raw and 'id: "funding-discovery"' not in raw
    assert 'label: "Effect-size converter"' not in raw
    # Meta-Analysis IS a METHODS pane tab now (registerPaneTab against the "checklists" host, not a Work/Extract tab
    # and no longer its own top-level section -- folded into Checklists in the 2026-07-21 pane regroup).
    assert 'id: "meta", label: "Meta-analysis reporting", order: 40, hideInReadOnly: true' in raw
    assert 'id: "synthesis", label: "Synthesis", paneId: "theory"' not in raw
    assert 'id: "cite", label: "Cite", tabLabel: "Suggest", paneId: "theory"' not in raw
    assert 'id: "meta-references", label: "Meta Reference List", paneId: "theory"' not in raw
    assert 'id: "credit", label: "CRediT statement", paneId: "theory"' not in raw
    # The shell renders the menu bar + persists the active workspace.
    assert "menubar-nav" in raw and '"callosum.workspace"' in raw
    assert 'activeWorkspace === "library"' in raw and 'activeWorkspace === "profile"' in raw
    assert 'activeWorkspace === "synthesis"' in raw and 'activeWorkspace === "work"' in raw
    assert 'activeWorkspace === "extract"' not in raw and 'selectWorkspace("extract")' not in raw
    assert "function MenuBar({ active, onActivate, readOnly, mobile, onStatusNavigate, desktopUpdate })" in raw
    assert 'className="menubar menubar-mobile"' in raw
    assert 'id="mobile-workspace-select"' in raw
    assert '<optgroup label="Workspaces">' in raw and '<optgroup label="Utilities">' in raw
    assert (
        "<MenuBar active={activeWorkspace} onActivate={selectWorkspace} readOnly={readOnly} mobile={mobile} "
        "onStatusNavigate={onStatusNavigate} desktopUpdate={desktopUpdate} />" in raw
    )
    assert 'id: "synthesis", label: "Synthesize", order: 30' in raw
    assert 'id: "ask", label: "Ask", order: 10' in raw
    assert 'id: "critique", label: "Critique", order: 20, hideInReadOnly: true' in raw
    assert 'id: "critical_read", label: "Critical read", paneId: "methods"' not in raw
    assert 'wsId: "synthesis", tabId: "ask"' in raw
    # Stage 3: Help + Settings are utility workspaces (center views), not modals.
    assert 'id: "help"' in raw and 'id: "settings"' in raw and "utility: true" in raw
    assert "function HelpView(" in raw and "function SettingsView(" in raw
    assert "function HelpModal(" not in raw and "function SettingsModal(" not in raw
    # inc 297: library discovery modals stay in Discover Search; Feed is its own Discover tab again.
    assert "<FeedPane onSaved={ctx.onDiscoverSaved} active={active} />" in raw
    assert "<FeedPane onSaved={onSaved} active={active} embedded />" not in raw
    assert "onOpenWanted={ctx.onOpenWanted}" in raw and "onOpenGaps={ctx.onOpenGaps}" in raw
    assert "onOpenOverlooked={ctx.onOpenOverlooked}" in raw
    assert 'title="Papers you want an OA copy of' in raw and 'title="Works related to several of your papers' in raw
    assert 'title="Per axis: works relevant to it but under-cited' in raw
    assert "onFindDuplicates, onOpenWanted" not in raw and "onFindDuplicates, onOpenScan" in raw
    # inc 284: returning users get a one-time Library hint for relocated tools.
    assert "callosum.workspaces-whatsnew" in raw
    assert "function WorkspacesWhatsNewHint(" in raw
    assert "New layout:" in raw and "Synthesize" in raw and "Meta Reference List" in raw and "CRediT" in raw
    assert "Discover → Search" in raw and "Wanted" in raw and "Gaps" in raw and "Overlooked" in raw
    assert "Meta-Analyze" in raw and "Work" in raw
    assert '_saveLayout(WORKSPACES_WHATSNEW_KEY, "1")' in raw
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert (
        ".workspace-body { display: flex; flex: 1 1 auto; min-height: 0; flex-direction: column; overflow-y: auto; }"
        in css
    )


def test_discover_search_source_selector_present():
    raw = assemble_jsx()
    assert 'api("/discovery/sources")' in raw
    assert 'const sourceParam = selectedSource ? `&source=${encodeURIComponent(selectedSource)}` : "";' in raw
    assert 'className="lib-sort" value={source}' in raw
    assert '<option value="">All sources</option>' in raw
    assert "source choice controls where to query; the complete returned list is shown" in raw


def test_discover_search_and_journals_recent_history_controls():
    raw = assemble_jsx()
    assert 'const DISCOVER_SEARCH_HISTORY_KEY = "callosum.discover.searchHistory.v1"' in raw
    assert "function _discoverLoadSearchHistory()" in raw and "rememberSearch({ q: query" in raw
    assert 'title="Recall and re-run a recent Search query"' in raw
    assert 'title="Clear the current query and results (cancels an in-flight search)"' in raw
    assert 'setQ(""); setItems([]); setError(""); setCursor(-1)' in raw
    assert "Clear ×" in raw and "Recent searches" in raw and "Clear history" in raw
    assert 'const PUB_HISTORY_KEY = "callosum.discover.journalsHistory.v1"' in raw
    assert "function _pubLoadHistory()" in raw and "const rememberRun = (entry) =>" in raw
    assert 'title="Recall and re-run a recent Journals search"' in raw
    assert "Recent journal searches" in raw
    assert "run(null, h)" in raw
    assert "const [lastRunInput, setLastRunInput] = useState(null)" in raw
    assert 'if (state.status === "done") run(val, lastRunInput || undefined)' in raw
    assert "paper_id: input.paperId" in raw
    assert "abstract: input.abstract, subject: input.subject" in raw


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
    assert "function LibraryFrame({ libraryProps, wip, wipTabs, selectedWipTab, tabs, selectedPaperTab" in raw
    assert "const reorderPdfTabs = useCallback((draggedKey, targetKey)" in raw
    assert ".frame-tab-selected" in css
    assert ".frame-tab.dragover" in css


def test_every_workspace_tab_shows_selected_paper_tab_cue():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert "function WorkspacePaperCue({ ctx })" in raw
    # 2026-07-21: the per-tab whitelist (journals/funding/meta-reference/critique) was removed rather than grown
    # to a 10-item no-op list -- Ask/Feed/Search/Cite/CRediT/Meta-Analyze were added for visual consistency,
    # which meant the whitelist covered every registered workspace tab. Now shown unconditionally whenever ctx
    # exists (WorkspacePane only renders it when tabs.length > 1, i.e. every tab-based workspace).
    assert "if (!ctx) return null;" in raw
    assert '["journals", "funding", "meta-reference", "critique"].includes(activeTab)' not in raw
    assert "const openTab = ctx.selectedOpenPaperTab || null" in raw
    assert 'className="frame-tab active workspace-paper-cue"' in raw
    assert 'className="frame-tab frame-tab-selected workspace-paper-cue"' in raw
    assert "ctx.onActivatePaperTab(openTab.key)" in raw
    assert "ctx.onOpenPdf({ id: selectedTab.id, title: selectedTab.title })" in raw
    assert "<WorkspacePaperCue ctx={ctx} />" in raw
    assert 'ws.id === "discover" &&' not in raw
    assert "const selectedOpenPaperTab = selected == null ? null" in raw
    assert "selectedPaperTab: wipModeActive ? null : selectedPaperTab" in raw
    assert "selectedOpenPaperTab: wipModeActive ? null : selectedOpenPaperTab" in raw
    assert "onActivatePaperTab: activatePaperTab" in raw
    assert ".workspace-paper-cue" in css


def test_wip_is_a_distinct_library_level_context_and_never_leaks_stale_paper_selection():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")

    library_tab = raw.index(">Library</button>")
    wip_tab = raw.index(">WIP</button>")
    selected_paper_tab = raw.index("{selectedPaperTab &&", library_tab)
    assert library_tab < wip_tab < selected_paper_tab
    assert 'onClick={() => onActivate("wip")}' in raw
    assert "<WipBrowser wip={wip} onOpen={onOpenWip} />" in raw
    assert "<WipDetails manuscript={t.manuscript} onUpdate={wip.updateManuscript}" in raw
    assert "onRelinked={wip.reload} onOpenPaper={onOpenPdf} workspace externalRefresh={wip.refresh} />" in raw
    assert '["overview", "structure", "tasks", "files", "references", "checks", "activity"]' in raw
    assert "Create checkpoint" in raw
    assert "Run statcheck" in raw
    assert "Check transparency" in raw
    assert "Audit LMM reporting" in raw
    assert "Audit Bayesian reporting" in raw
    assert "Audit meta-analysis reporting" in raw
    assert (
        "function WipChecklistSection({ manuscript, ctx, toolId, label, labels, emptyText, selectText, "
        "renderResult, progressManagedBy })" in raw
    )
    assert "function WipTransparencySection({ manuscript, ctx })" in raw
    assert "function WipLmmSection({ manuscript, ctx })" in raw
    assert "function WipBayesSection({ manuscript, ctx })" in raw
    assert "function WipMetaAnalysisSection({ manuscript, ctx })" in raw
    assert "`/wip/manuscripts/${manuscriptId}/checks/${toolId}`" in raw
    assert 'toolId="transparency"' in raw
    assert 'toolId="lmm"' in raw
    assert 'toolId="bayes"' in raw
    assert 'toolId="meta-analysis"' in raw
    assert "Detected rows are retained as evidence-backed facts." in raw
    assert "retained as a reviewable candidate" in raw
    assert "Mismatches, reporting gaps, coherence flags, and advisories are retained" in raw
    assert "showRegistrationReferences={false}" in raw
    assert "running && <ProgressBar />" in raw
    assert "Open source file" in raw
    assert "An empty history is not a clean manuscript." in raw
    assert "run.coverage" in raw
    assert "finding.details_json.computed_p" in raw
    assert "function WipRelink({ manuscript, onRelinked })" in raw
    assert "Relink folder" in raw
    assert "Used in WIPs" in raw
    assert "onOpenWip={ctx.onOpenWip}" in raw
    assert "onRelinked={wip.reload}" in raw
    assert "title: manuscript.display_title || manuscript.derived_title || tab.title" in raw
    assert 'role="button" tabIndex={0}' in raw
    assert "function WipFilters({ wip })" in raw
    assert 'params.set("has_open_tasks", "true")' in raw
    assert "Unresolved findings" in raw
    assert "Missing primary" in raw
    assert "manuscript.stale_check_count" in raw
    assert "function WipContextMenu({ menu, onClose, onOpen, onUpdate, onRescan, onDelete })" in raw
    assert 'event.key === "ContextMenu"' in raw
    assert "WIP_TAB_DRAG_TYPE" in raw
    assert "onReorderWipTabs(dragged, t.key)" in raw
    assert "No tool result is implied by a content checkpoint." in raw
    assert 'const wipModeActive = activeTab === "wip" || !!activeWipTab' in raw
    assert 'kind: "manuscript", entity: activeWipManuscript || null' in raw
    assert 'const contextPaperId = researchContext.kind === "paper" ? selected : null' in raw
    assert "selectedPaper: contextPaperId" in raw
    assert 'ctx.researchContext.kind === "manuscript"' in raw
    assert "--wip:" in css and ".frame-tab-selected-wip" in css and ".workspace-wip-cue" in css


def test_my_publications_workspace_loads_without_axis_card_button():
    raw = assemble_jsx()
    assert (
        "function MyPubsDashboard({ axisId, axisRefresh, onSummarize, onSelectPaper, onOpenPdf, onLibraryChanged })"
        in raw
    )
    assert "const [resolvedAxisId, setResolvedAxisId] = useState(axisId || null)" in raw
    assert 'const ax = (r.data || []).find(a => a.kind === "my_publications")' in raw


def test_my_publications_citation_gaps_are_grounded_and_explicit_refresh():
    raw = assemble_jsx()
    assert "function MyPubsCitationGaps" in raw
    assert "api(listPath)" in raw
    assert "domain_key=${encodeURIComponent(key)}" in raw
    assert 'apiPost("/my-publications/citation-gaps/refresh", { domain_keys: selectedKeys })' in raw
    assert "each scope keeps its own local snapshot" in raw
    assert "aria-pressed={selectedDomainKeys.has(domain.key)}" in raw
    assert "Why this surfaced" in raw
    assert "Shared references are a retrieval trail" in raw
    assert "<MyPubsCitationGaps domains={domains}" in raw
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


def test_method_credit_button_checks_and_imports_only_missing_sources():
    raw = assemble_jsx()
    assert "function MethodCreditButton(" in raw
    assert 'apiPost("/library/credit/status", { dois })' in raw
    assert '"＋ add missing to library"' in raw
    assert '"✓ added to library"' in raw
    assert "state.importedAll ? [] : missingCreditItems(allItems, state.present)" in raw
    assert 'apiPost("/library/import", { content: JSON.stringify(missing), format: "csl-json" })' in raw
    assert raw.count("<MethodCreditButton items=") >= 12
    assert "<MethodCreditButton items={[OPENURL_CSL]} />" in raw
    assert "<MethodCreditButton items={CITATION_EQUITY_CSL} />" in raw
    assert "<MethodCreditButton items={LMM_CSL} />" in raw
    assert "<MethodCreditButton items={META_CSL} />" in raw
    assert "<MethodCreditButton items={[CREDIT_TENZING_CSL, CREDIT_TAXONOMY_CSL]} />" in raw


def test_watched_folder_rescan_is_standard_behavior_not_a_setting():
    raw = assemble_jsx()
    assert "autoScanWatched" not in raw
    assert "callosum.autoScanWatched" not in raw
    assert "Auto-scan watched folders on launch" not in raw
    assert 'apiPost("/library/watched/rescan", {})' in raw
    assert 'window.addEventListener("focus", onFocus)' in raw


def test_stale_discover_placeholder_is_removed_from_theory_accordion():
    raw = assemble_jsx()
    assert 'label: "Funding"' in raw  # relocated to the Discover workspace (inc 280); was THEORY "Funding Discovery"
    assert '{ id: "discover", label: "Discover", paneId: "theory"' not in raw
    assert 'label: "Beyond library"' not in raw
    assert 'title="Beyond library"' not in raw
    # inc 397: 09_placeholders.jsx (the file the Discover-removal comment used to live in) was deleted outright
    # once its last remaining "coming soon" stub (Statistics' "More checks") was cleared -- zero callers left, so
    # the whole scaffold + its .coming-soon* CSS went with it (rule #5), rather than a comment-only husk file.
    assert "ComingSoon" not in raw
    assert "coming-soon" not in raw
    assert "More checks" not in raw


def test_meta_reference_list_sits_before_journal_search_with_accessible_review_controls():
    raw = assemble_jsx()
    # Meta Reference List is now a MetaReferencePane subsection (Work -> Meta-Reference), not its own registered
    # cite-tab — the old nested Cite tab-strip (aria-label="Cite tools", the "callosum.citetab" persistence key)
    # is gone entirely along with CiteWorkspacePane.
    assert 'id: "meta-reference", label: "Meta-Reference", order: 20' in raw
    assert "function MetaReferenceList(" in raw and "<MetaReferenceList ctx={ctx} />" in raw
    assert 'aria-label="Cite tools"' not in raw and "callosum.citetab" not in raw
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
    # The ref-signal badge's click-through targets the real "meta-reference" workspace tab now (not the deleted
    # CiteWorkspacePane's citeTabRequest/"meta-references" cite-tab system).
    assert 'requestWorkspaceTab("work", "meta-reference")' in raw
    assert "requestCiteTab" not in raw and "citeTabRequest" not in raw
    assert "onOpenReferenceWarnings: openReferenceWarnings" in raw


def test_meta_reference_actions_share_one_aligned_fixed_width_column():
    raw = assemble_jsx()
    # Four Library-paper source rows render five controls at runtime because CitationContextPaper is mounted
    # once per direction. Inc 447 (backlog #48) adds two more source rows for the WIP-manuscript variants
    # (WipMetaReferenceList, CitationEquitySectionWip), reusing the same recipe rather than inventing new CSS.
    assert raw.count('className="meta-ref-action-row"') == 6
    assert raw.count('className="meta-ref-action-slot"') == 6
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert "--meta-ref-action-width: 150px" in css
    assert "grid-template-columns: minmax(0, 1fr) var(--meta-ref-action-width)" in css
    assert ".meta-ref-action-slot .btn-primary { width: 100%" in css
    assert ".app.mobile .meta-ref-action-row { grid-template-columns: minmax(0, 1fr)" in css


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
    assert '!t.locked && !tagIsSystemFact(t.source) && <button className="tag-chip-x"' in raw
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
    assert "methodEvidenceTarget(paperId, title, r" in raw
    assert "attachmentId: evidence.attachment_id ?? null" in raw
    assert "Open and highlight this reported test" in raw
    assert 'r.source_kind === "table"' in raw
    assert 'className="statcheck-source"' in raw
    assert "d.coverage.table_results" in raw and "d.coverage.table_rows_scanned" in raw
    assert "Ambiguous/unlabeled tables" in raw
    assert ".statcheck-context" in css
    assert ".statcheck-source" in css
    assert ".statcheck-coverage" in css
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


def test_cite_suggestions_open_the_matched_pdf_and_viewer_names_the_active_file():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert "attachment_id: s.attachment_id" in raw
    assert "page_start: opensMatchedPdf ? s.page_start : null" in raw
    assert '{opensMatchedPdf ? "Open source region" : "Open primary PDF"}' in raw
    assert "function responseFilename(response)" in raw
    assert 'response.headers.get("content-disposition")' in raw
    assert "filename: responseFilename(res)" in raw
    assert 'className="pdf-filename"' in raw
    assert ".pdf-source-title" in css and ".pdf-filename" in css
    assert ".app.mobile .pdf-source-title { flex: 1 0 100%; width: 100%; }" in css
    assert 'res.headers.get("x-callosum-attachment-id")' in raw
    assert "annotations?attachment_id=${state.attachmentId}" in raw
    assert "attachment_id: state.attachmentId" in raw


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


def test_single_paper_critical_read_lives_in_synthesize_critique():
    raw = assemble_jsx()
    assert 'id: "critique", label: "Critique", order: 20, hideInReadOnly: true' in raw
    assert "render: (ctx) => <CriticalReadSection ctx={ctx} />" in raw
    assert (
        "<CriticalReadPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper} "
        "onFindingsChanged={ctx.onFindingsChanged} />"
    ) in raw
    assert 'ctx.methodsOpen === "critical_read"' not in raw
    assert 'registerPaneSection({\n  id: "critical_read"' not in raw
    # Tier 1 is user-triggered (2026-07-20) -- no auto-run effect keyed off an `active` visibility flag.
    assert "function CriticalReadPaper({ paperId, onOpenPaper, onFindingsChanged })" in raw
    assert 'if (active && meta && meta.hasText && t1.status === "idle") runT1();' not in raw
    assert (
        'meta && meta.hasText && t1.status === "idle" &&\n        <button className="btn btn-primary" onClick={runT1}'
    ) in raw
    assert "Run critical read" in raw


def test_wip_critical_read_is_explicit_local_snapshot_bound_and_has_no_provider_action():
    raw = assemble_jsx()
    assert 'if (ctx.researchContext.kind === "manuscript")' in raw
    assert "function CriticalReadWip({ manuscript, ctx })" in raw
    assert "function WipCriticalReadResult({ run, ctx, onOpenSource })" in raw
    assert "Run local critical read" in raw
    assert "Comparing bounded claims with local Library evidence" in raw
    assert "Query embeddings are transient and never stored as paper embeddings" in raw
    assert "article-fulltext Library passages" in raw
    assert "surfaces disagreement; it does not decide which claim is correct" in raw
    assert "separate exact transmission preview and explicit consent design" in raw
    assert "`/wip/manuscripts/${manuscriptId}/critical-read`" in raw
    assert "`/wip/critical-read/${jobId}`" in raw
    assert "attachmentId: item.attachment_id" in raw
    assert "paperId: item.other_paper_id" in raw
    wip_branch = raw[
        raw.index('if (ctx.researchContext.kind === "manuscript")') : raw.index(
            "return (", raw.index('if (ctx.researchContext.kind === "manuscript")') + 1
        )
    ]
    assert "/candidates/generate" not in wip_branch


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
    assert "function RetractionCheckButton(" in raw
    assert '"Integrity ↻"' in raw
    assert "summary.corrections" in raw
    assert "function PositiveIntegrityFacts(" in raw
    assert '"system:self-correction:correction"' in raw
    assert "p.correction_evidence_linked === true" in raw
    assert "}, [paperId, refreshKey]);" in raw
    assert "<RetractionCheckButton onDone={onRetractionRan} />" in raw
    assert raw.index("<RetractionCheckButton onDone={onRetractionRan} />") < raw.index(
        "<TextHealthButton onOpen={onOpenTextHealth} />"
    )
    assert 'setDetail(r.data.detail || "")' in raw
    assert '"Text Health"' in raw
    assert "Last refreshed ${fmtDateTime(lastLoaded)}" in raw
    assert "🔎 Open Data · {openDataDetected}" in raw
    assert 'onShowTransparencyReview("transparency-data-detected")' in raw
    assert "⚠ Flagged · {statcheckFlagged}" in raw
    assert "⚠ Retracted · {retractionFlagged}" in raw
    assert "📋 Review · {findingsToReview}" in raw
    assert "open data not detected</button>" not in raw


def test_retracted_papers_show_danger_badge_on_cards_and_details():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert 'const retracted = p.retraction_status === "retracted"' in raw
    assert 'className="tier tier-retracted"' in raw
    assert ">RETRACTED</span>" in raw
    assert 'p.retraction_status === "retracted"' in raw
    assert ".tier-retracted { background: var(--danger-line); color: var(--danger); }" in css


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


def test_methods_pane_regrouped_details_data_statistics_checklists():
    """2026-07-21: the METHODS accordion collapsed from 7 top-level sections to 4 -- Details/Data/Statistics
    unchanged in place, and Transparency/Mixed-model/Bayesian/Meta-analysis folded into one "Checklists" section
    as a 2x2 grid of tabs (registerPaneTab against a shared host), rather than 4 sibling sections."""
    raw = assemble_jsx()
    # Data + Statistics were relabeled (same ids/order, GRIM/statcheck internals untouched).
    assert 'id: "grim", label: "Data", paneId: "methods", order: 20, hideInReadOnly: true' in raw
    assert 'label: "Data consistency (GRIM)"' not in raw
    assert 'id: "statcheck", label: "Statistics", paneId: "methods", order: 30, hideInReadOnly: true' in raw
    assert 'label: "Statistics check"' not in raw
    # The checklist tools no longer self-register as standalone sections...
    assert 'registerPaneSection({\n  id: "bayes"' not in raw
    assert 'registerPaneSection({\n  id: "lmm"' not in raw
    assert 'registerPaneSection({\n  id: "transparency"' not in raw
    # ...they register as tabs on one shared "checklists" host, ordered for the grid (transparency top-left,
    # lmm top-right, bayes bottom-left, meta bottom-right, analytic-flexibility added inc backlog #37 as a 5th).
    assert raw.count('{ id: "checklists", label: "Checklists", paneId: "methods", order: 40 }') == 5
    assert 'id: "transparency", label: "Transparency signals", order: 10, hideInReadOnly: true' in raw
    assert 'id: "lmm", label: "Mixed-model reporting", order: 20, hideInReadOnly: true' in raw
    assert 'id: "bayes", label: "Bayesian statistics", order: 30, hideInReadOnly: true' in raw
    assert 'id: "meta", label: "Meta-analysis reporting", order: 40, hideInReadOnly: true' in raw
    assert 'id: "analytic-flexibility", label: "Analytic flexibility", order: 50, hideInReadOnly: true' in raw
    # Each section's render signature now takes `active` as a real prop (not re-derived from ctx.methodsOpen).
    assert "function TransparencySection({ ctx, active })" in raw
    assert 'ctx.researchContext.kind === "manuscript"' in raw
    assert "<WipTransparencySection manuscript={ctx.researchContext.entity} ctx={ctx} />" in raw
    assert "exact primary-file checkpoint" in raw
    assert "function BayesSection({ ctx, active })" in raw
    assert "<WipBayesSection manuscript={ctx.researchContext.entity} ctx={ctx} />" in raw
    assert "exact primary-file checkpoint" in raw
    assert "function LmmSection({ ctx, active })" in raw
    assert "<WipLmmSection manuscript={ctx.researchContext.entity} ctx={ctx} />" in raw
    assert "never a correctness verdict or score" in raw
    assert "function MetaSection({ ctx, active })" in raw
    assert "<WipMetaAnalysisSection manuscript={ctx.researchContext.entity} ctx={ctx} />" in raw
    for stale in (
        'ctx.methodsOpen === "transparency"',
        'ctx.methodsOpen === "bayes"',
        'ctx.methodsOpen === "lmm"',
        'ctx.methodsOpen === "meta"',
    ):
        assert stale not in raw
    assert raw.count("render: (ctx, active) => <TransparencySection ctx={ctx} active={active} />") == 1
    assert raw.count("render: (ctx, active) => <BayesSection ctx={ctx} active={active} />") == 1
    assert raw.count("render: (ctx, active) => <LmmSection ctx={ctx} active={active} />") == 1
    assert raw.count("render: (ctx, active) => <MetaSection ctx={ctx} active={active} />") == 1
    # PaneAccordion threads a real isVisible bool into every tab/section render (WorkspacePane's own
    # render(ctx, active) contract, mirrored here so a merged section's tab can tell whether it's the open one).
    assert "t.render(ctx, s.id === active && t.id === at)" in raw
    assert "tabs[0].render(ctx, s.id === active)" in raw
    assert 'className={"tags-srcfilter pane-tabs pane-tabs-" + s.id}' in raw
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert (
        ".pane-tabs.pane-tabs-checklists { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; }"
        in css
    )
    assert ".app.mobile .pane-tabs-checklists { grid-template-columns: 1fr; }" in css


def test_registration_discovery_is_explicit_metadata_egress_and_never_auto_attaches():
    raw = assemble_jsx()
    assert "function MetaPreregistrationPane({ ctx, active })" in raw
    assert "<RegistrationDiscovery paperId={paperId} paperTitle={meta.title} onOpenPaper={ctx.onOpenPaper}" in raw
    assert "refreshKey={refreshKey}" in raw
    assert "Search public registry metadata?" in raw
    assert "Sends: <b>" in raw
    assert "Used only on this machine for matching" in raw
    assert "metadata_consent: true" in raw
    assert "Registration link confirmed. No registration content has been downloaded yet." in raw
    assert "Candidate evidence supports inspection" in raw
    assert "Fresh search, including dismissed candidates" in raw


def test_meta_preregistration_is_a_settings_consistent_synthesis_workspace_after_critique():
    raw = assemble_jsx()
    registration_source = "\n".join(
        (FRONTEND_DIR / "js" / name).read_text(encoding="utf-8")
        for name in ("08h_methods_transparency.jsx", "08i_registration_comparison.jsx")
    )
    transparency = raw.split("function TransparencyPaper(", 1)[1].split("function TransparencyChecklist", 1)[0]
    workspace = raw.split("function MetaPreregistrationPane(", 1)[1].split("registerWorkspaceTab(", 1)[0]
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")

    assert 'id: "critique", label: "Critique", order: 20' in raw
    assert 'id: "meta-preregistration", label: "Meta-Preregistration", order: 30' in raw
    assert 'requestWorkspaceTab("synthesis", "meta-preregistration")' in raw
    assert "onOpenMetaPreregistration={ctx.onOpenMetaPreregistration}" in raw
    assert "Open Meta-Preregistration" in transparency
    assert "<RegistrationDiscovery" not in transparency
    assert "<RegistrationReferenceActions" not in transparency
    assert "<RegistrationDiscovery" in workspace and "<RegistrationReferenceActions" in workspace

    # General UI structure and controls reuse Settings conventions; domain evidence remains purpose-built.
    assert 'className="settings-card registration-discovery"' in raw
    assert 'className="settings-card registration-comparison-workspace"' in raw
    assert 'className="settings-card registration-reference-actions"' in raw
    assert 'className="settings-input"' in raw
    assert 'textarea className="settings-input"' in raw
    assert 'className="btn btn-ghost"' in registration_source
    assert 'className="btn btn-secondary"' not in registration_source
    assert ".meta-preregistration-grid, .registration-workflow { display: grid; gap: 14px; }" in css
    assert ".registration-candidate-card { margin-top: 12px; padding: 12px;" in css
    assert "border-radius: var(--radius);" in css


def test_registration_acquisition_is_explicit_versioned_and_not_a_comparison():
    raw = assemble_jsx()
    assert "Acquire registration" in raw
    assert "Check for an updated version" in raw
    assert "registration-acquisition/${started.data.job_id}" in raw
    assert "registration-versions" in raw
    assert "Registration attached, not compared" in raw
    assert "No comparison has run yet." in raw
    assert "Callosum will not try to download an unavailable artifact." in raw
    # Loading the workspace reads only persisted local state; acquisition remains inside the click handler.
    component = raw.split("function RegistrationDiscovery({ paperId, paperTitle, onOpenPaper, refreshKey = 0 })", 1)[
        1
    ].split("function RegistrationCandidateCard", 1)[0]
    effect = component.split("useEffect(() =>", 1)[1].split("const showDisclosure", 1)[0]
    assert "/acquire" not in effect


def test_registration_comparison_ui_is_paired_reviewable_stale_aware_and_scoreless():
    raw = assemble_jsx()
    source = (FRONTEND_DIR / "js" / "08i_registration_comparison.jsx").read_text(encoding="utf-8")
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert "function RegistrationComparisonWorkspace(" in raw
    assert "Compare now" in source and "Re-run comparison" in source
    assert "Include relevant supplements" in source
    assert "Expand beyond expected sections when bounded search is weak" in source
    assert "Open registration evidence" in source and "Open publication evidence" in source
    assert "Inspect stored registration" in source and "Open registration attachment" in source
    assert "Mark reviewed" in source and "Dismiss flag" in source and "Save note" in source
    assert "Incorrect registration match" in raw
    assert "Comparison stale" in source
    assert "no positive certificate is implied" in source
    assert "Not located” is not proof of absence" in source
    for status in (
        "Potentially changed",
        "Planned item not located in publication",
        "Reported item not located in registration",
        "Ambiguous study mapping",
        "Not comparable",
        "Extraction uncertain",
    ):
        assert status in source
    for forbidden_field in ("compliance_score", "integrity_score", "risk_score", "deviation_score", "author_score"):
        assert forbidden_field not in source
    # Merely mounting/loading the workspace reads persisted state; comparison POST stays inside the click handler.
    effect = source.split("useEffect(() =>", 2)[2].split("const compare = async", 1)[0]
    assert "apiPost(`/papers/${paperId}/registration-comparisons`" not in effect
    assert ".registration-evidence-columns { display: grid; grid-template-columns: repeat(2" in css
    assert ".app.mobile .registration-evidence-columns { grid-template-columns: 1fr; }" in css
    # inc 435: optional AI triage is an explicit, reversible display layer over the unchanged crosswalk.
    assert "function RegistrationLlmTriageControls(" in source
    assert "Triage rows with AI" in source and "Re-triage rows with AI" in source
    assert "saved comparison fields and bounded registration/publication passages" in source
    assert "it cannot alter evidence, statuses, or review state" in source
    assert "All rows" in source and "AI-focused" in source
    assert "!row.llm_triage || row.llm_triage.show_in_triage" in source
    assert "Display aid only — not a revised comparison status" in source
    assert "/llm-triage`" in source
    assert "/llm-triage`" not in source.split("const triage = async", 1)[0]
    assert "Re-run the comparison, then triage the new rows." in source
    assert ".registration-row-triage.triage-likely_noise" in css
    assert ".app.mobile .registration-llm-triage-head" in css


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


def test_reading_queue_is_stratified_by_priority():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    # four priority strata; an unset paper falls into "Unprioritized"
    assert 'label: "Unprioritized"' in raw
    assert "const queueGroupOf =" in raw
    # a cross-group drag reuses POST /papers/{id}/priority (Unprioritized clears to null), then reorders via the
    # existing full-id-list contract — no new endpoint
    assert 'targetGroup === "unprioritized" ? null : targetGroup' in raw
    assert "apiPost(`/papers/${draggedId}/priority`, { priority })" in raw
    assert 'apiPut("/reading-queue/order", { paper_ids: order })' in raw
    # group headers reuse the muted priority colors + the queue-drop accent recipe (no new color semantics)
    assert ".queue-group.drop { background: var(--accent-soft); border-color: var(--accent); }" in css
    assert ".queue-group-head.pr-high" in css


def test_priority_syncs_between_cards_and_queue():
    # papers.priority is one source of truth shown in both the Library cards and the Queue strata; a change in
    # either pane must re-read it in the other (inc 294 cache-coherence wiring).
    raw = assemble_jsx()
    # queue → cards: a queue change also reloads the library list so each card re-reads papers.priority
    assert "onQueueChanged: () => { setQueueRefresh(n => n + 1); setLibRefresh(n => n + 1); }" in raw
    # cards → queue: a card priority change reloads the Queue tab
    assert "onReadingChanged: () => setQueueRefresh(n => n + 1)" in raw
    # the callback is threaded down to the priority control, which fires it only after a successful write
    assert "<ReadPriorityControl paper={p} onChanged={onReadingChanged}" in raw
    assert "function ReadPriorityControl({ paper, onChanged, demoLocked })" in raw
    assert "if (onChanged) onChanged();" in raw


def test_feed_suggests_journals_from_library():
    raw = assemble_jsx()
    # the Feed follows journals by TITLE; a Suggest modal + typeahead read the user's own library journals
    assert "function FeedSuggestModal(" in raw
    assert 'api("/feed/library-journals")' in raw
    assert 'apiPost("/feed/subscriptions", { kind: "journal", value: title, label: title })' in raw
    assert 'selKind === "journal"' in raw and "libJournals.map(j => j.journal)" in raw


def test_misc_ux_batch_wiring():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    # F2: the menu bar is hidden in read mode
    assert "!readingMode && <MenuBar active={activeWorkspace}" in raw
    # F5: sort = a field + a ▲/▼ direction toggle mapped onto the existing backend sort keys
    assert "const SORT_FIELDS = [" in raw and "function _sortKey(field, dir)" in raw
    assert 'className="lib-sort-dir"' in raw and ".lib-sort-dir {" in css
    # F6: the missing-PDF filter facet (fetch param + toggle chip)
    assert 'if (libraryMissingPdf) qs.set("missing_pdf", "true")' in raw
    assert 'className={"lib-facet-toggle" + (libraryMissingPdf ? " on" : "")}' in raw and ".lib-facet-toggle.on" in css
    # F1: read + priority filters are available in Trash too (the !trashView gate removed)
    assert "read + priority filter facets (your triage labels) — now available in Trash too" in raw
    # F3: Discover → Search reloads the last search on access
    assert "runSearch({ q: last.q, source: last.source" in raw
    # F4: a completed merge drops its duplicate card
    assert "mergedIds={dupMergedIds}" in raw
    assert "function DuplicatesModal({ onClose, onOpenPaper, onChanged, onMerge, mergedIds, onMergeDone })" in raw


def test_qa_20260719_mobile_batch_and_pdf_404_fix():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    # 4 mobile-CSS spacing fixes (browser-verified with Playwright, inc 308 follow-up)
    assert ".app.mobile .feed-controls .tags-srcfilter-btn { flex: 0 1 auto" in css
    assert ".app.mobile .provider-toggle { flex-wrap: wrap" in css
    # superseded by the padding-sweep fix below: .cite-pane now gets real base padding via .ws-pad, so the
    # mobile-only patch was removed rather than left as a contradictory one-off (DESIGN.md §3 #10).
    assert ".app.mobile .cite-pane { padding: 0 14px" not in css
    # the workspace "what moved" hint gets a shorter mobile-specific copy (was 4 lines / 82px on a phone)
    assert "function WorkspacesWhatsNewHint({ readOnly, mobile })" in raw
    assert "tools moved into <b>Discover</b> and <b>Work</b>" in raw
    assert "<b>Extract</b>" not in raw
    # a paper opened with a known attachment_count of 0 skips the doomed /pdf fetch entirely (no 404, no
    # console error) instead of relying on the 404 being handled gracefully after the fact
    assert "const hasPdf = paper.attachment_count == null ? null : paper.attachment_count > 0;" in raw
    assert "knownNoPdf={t.hasPdf === false}" in raw
    assert 'if (knownNoPdf) { setState({ status: "unavailable" }); return; }' in raw


def test_padding_sweep_ws_pad_on_six_workspace_tabs_only():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    assert ".ws-pad { padding: 16px 18px" in css
    # The 6 workspace tabs that had no outer padding each got ws-pad added to their existing root class.
    assert 'className="cite-pane ws-pad"' in raw
    assert 'className="cite-workspace ws-pad"' in raw
    assert 'className="grim-section ws-pad"' in raw
    assert 'className="pub-panel ws-pad"' in raw
    assert 'className="funding-panel ws-pad"' in raw
    assert 'className="statcheck-section ws-pad"' in raw
    # ws-pad must NOT leak onto the shared-class siblings that are already correctly padded elsewhere (a METHODS
    # accordion .acc-body, or EffectSizeSection nested inside Workbench's already-padded .wb-pane) — regression
    # guard for the exact double-padding collision the fix was designed to avoid.
    assert 'className="grim-section"' in raw  # GRIM's own accordion section, unchanged
    assert 'className="statcheck-section"' in raw  # statcheck/Bayes/LMM/transparency/meta-analysis, unchanged
    # The same promotion left .settings-sub's 300px cap (correct in the narrow Settings-sidebar home) wrapping
    # text at under half the available width in these same wide tabs -- relaxed via the same ws-pad/wb-pane
    # markers. inc 397 extended this to .acc-body too: the METHODS accordion's own Checklists/Statistics/Data
    # intro paragraphs (e.g. statcheck's "WHOLE LIBRARY" blurb) reuse .settings-sub and were wrapping at 300px
    # inside a much wider pane -- the bare .settings-sub rule itself (still 300px) is untouched; only these three
    # wider containers override it back to uncapped.
    assert ".ws-pad .settings-sub, .wb-pane .settings-sub, .acc-body .settings-sub { max-width: none" in css


def test_sync_settings_ui_wired_and_honest():
    raw = assemble_jsx()
    # SyncSettings (35c_sync.jsx, split from 35_settings.jsx at the 600-line cap) is wired into SettingsView.
    assert "function SyncSettings()" in raw
    assert "<SyncSettings />" in raw
    # the setup step never redisplays the passphrase; the recovery code is a distinct, explicitly one-time reveal
    assert 'type="password" autoComplete="new-password" placeholder="A strong passphrase"' in raw
    assert "Recovery code — shown once; save it now" in raw
    assert "There is no server-side reset" in raw
    # enable is gated on setup + signed-in + a server URL (mirrors the backend's own 422 gate order), never a
    # bare toggle
    assert "disabled={busy || !serverUrl.trim()}" in raw and "onClick={toggleEnabled}" in raw
    # the passphrase is re-entered every run — no session-remember in this slice
    assert "Re-enter your passphrase each time — it's never remembered between runs." in raw
    # conflicts: surfaced count + review list + a generic (not per-collection-bespoke) field diff, two explicit
    # actions, never an auto-pick
    assert "function ConflictReviewPanel(" in raw
    assert "function ConflictCard(" in raw
    assert "<th>Field</th><th>Mine</th><th>Current (theirs)</th>" in raw
    assert 'onClick={() => onResolve(c.id, "mine")}' in raw and 'onClick={() => onResolve(c.id, "theirs")}' in raw
    assert "Nothing is picked automatically" in raw
    # PDFs never sync — the honesty copy is present, not just the backend's own SYNCABLE exclusion
    assert "PDFs stay local" in raw and "never synced" in raw


def test_review_accordion_retired_into_critique():
    raw = assemble_jsx()
    css = (PROJECT_ROOT / "app/frontend/styles.css").read_text(encoding="utf-8")
    # 08_methods_findings.jsx (the left-pane "Review" accordion) is gone entirely — no dangling registration.
    assert 'id: "findings", label: "Review", paneId: "theory"' not in raw
    assert "function FindingsSection(" not in raw
    assert "function RetractionBatch(" not in raw
    assert "function RetractionStatusLine(" not in raw
    # The candidate-review queue (findingText/FindingCard) moved into Critique verbatim, plus a fetch of
    # /papers/{id}/findings and a "Needs your review" block wired to ctx.onFindingsChanged.
    assert "function findingText(" in raw and "function FindingCard(" in raw
    assert "/papers/${paperId}/findings" in raw and "cr-findings" in raw
    assert "onFindingsChanged={ctx.onFindingsChanged}" in raw
    # Facts (retraction included) stay covered by Tier-1's method_signals — no separate FactMark render; the
    # notice link now rides the signal row itself (critical_review.py's notice_url passthrough).
    assert "function FactMark(" not in raw
    assert "s.notice_url &&" in raw
    # The Retraction Watch DB admin panel relocated to Settings -> Local maintenance, wired to onRetractionRan.
    assert "function LocalMaintenanceSettings({ onRetractionRan })" in raw
    assert "Retraction Watch database" in raw and '"Refresh database"' in raw
    assert "onRetractionRan={refreshRetractionChip}" in raw
    # Dead CSS cleaned up alongside the file (rule #5) — the retired classes don't linger unreferenced.
    assert ".findings-section" not in css and ".retraction-batch" not in css and ".retraction-db" not in css
    assert ".fact-mark.retraction" not in css


def test_qa_retriage_20260702_batch_undismiss_and_scan_recovery_fixes():
    """QA re-triage (2026-07-21) against the post-write-lock-fix fixture confirmed the Critical/High findings from
    the 20260703_073208 run (routes 24/27/30/32) were either already fixed (route 30's 500s, via the SQLite
    write-lock arc), not real bugs (route 27's PDF-import expectation and the outside-path scan tradeoff are both
    by design; the console-error findings across routes 24/27/30 are Chromium's own network-layer logging for
    intentionally-triggered 4xx/5xx during adversarial checks, not app errors), or a QA-harness fixture limitation
    (route 32's unreachable exact-precision citation). Two real, still-open bugs were found + fixed here."""
    raw = assemble_jsx()
    # Route 24: un-dismissing a pair previously only refreshed the "previously dismissed" list, leaving the main
    # scan's `state.groups` stale until the whole modal was closed + reopened. `runScan` is now a reusable
    # function called both on mount and after a successful undismiss.
    assert "const runScan = useCallback(() => {" in raw
    assert 'onClick={() => apiPost("/papers/duplicates/undismiss"' in raw
    assert "if (r.ok) { refreshDismissed(); runScan(); }" in raw
    # Route 27: a running scan's {url, jobId} is now persisted so closing + reopening the Watched-folders modal
    # resumes polling instead of silently forgetting an in-flight job (the job itself always completed correctly
    # server-side; only the UI's visibility into it was lost).
    assert 'const SCAN_JOB_KEY = "callosum.scanJob";' in raw
    assert "const _clearScanJob = () => { try { localStorage.removeItem(SCAN_JOB_KEY); }" in raw
    assert 'job = JSON.parse(localStorage.getItem(SCAN_JOB_KEY) || "null");' in raw


def test_retraction_watch_cadence_auto_refresh_is_opt_in_and_staleness_gated():
    """Backlog #31: an automatic cadence refresh for the Retraction Watch mirror, following the established
    client-driven/opt-in/staleness-gated pattern (Feed's own auto-refresh precedent, 30e_feed.jsx) rather than a
    backend scheduler (none exists). Default off; the Settings checkbox and 03_library.jsx's launch/focus trigger
    are decoupled via one shared localStorage key, not prop/ctx threading."""
    raw = assemble_jsx()
    # 03_library.jsx: the trigger reads the same key the Settings checkbox writes, gates on read-only + healthLoaded
    # + an in-flight ref, checks GET .../database first and only proceeds to the full re-check batch when stale
    # (or never downloaded). A 1-hour attempt throttle is a safety net alongside the 30-day staleness gate: a
    # mirror that can never become fresh (e.g. no contact email set, so every refresh attempt fails) would
    # otherwise re-run the full per-paper check batch on every single window focus, indefinitely.
    assert "const triggerRetractionAutoRefresh = useCallback(() => {" in raw
    assert 'localStorage.getItem("callosum.retractionAutoRefresh") === "1"' in raw
    assert "if (Date.now() - lastRetractionAttempt.current < 3600000) return;" in raw
    assert 'api("/methods/retraction/database").then(r => {' in raw
    assert "if (ageDays != null && ageDays <= 30) { retractionRefreshInFlight.current = false; return; }" in raw
    assert 'apiPost("/methods/retraction/run", {}).then(rr => {' in raw
    # fired alongside the existing watched-folder rescan on launch + window focus, not a separate effect
    assert "triggerWatchedRescan();  // on launch\n    triggerRetractionAutoRefresh();" in raw
    assert "onFocus = () => { triggerWatchedRescan(); triggerRetractionAutoRefresh(); };" in raw
    # on completion it refreshes the header chip, same as the manual "Retractions ↻" button's onDone
    assert (
        'if (rp.data.status === "done") { retractionRefreshInFlight.current = false; refreshRetractionChip(); }' in raw
    )
    # 35_settings.jsx: the opt-in checkbox, default off, writing the same key
    assert 'localStorage.getItem("callosum.retractionAutoRefresh") === "1"; } catch (e) { return false; }' in raw
    assert '"callosum.retractionAutoRefresh", next ? "1" : "0"' in raw
    assert "Auto-refresh when stale (checked on launch)" in raw


def test_selected_paper_stays_in_sync_with_the_focused_pdf_tab():
    """Small UX fix (2026-07-21): opening or switching to any PDF tab must keep the library-visible "selected"
    paper (Details pane, row highlight) in one-to-one correspondence with it. Previously `openPdf` never called
    `setSelected`, so opening a paper via a citation, the Files list, or any other non-library-row path left the
    Details pane / row highlight showing a stale paper. Fixed with a single effect derived from `activeTab`
    (covers every path that focuses a PDF tab -- opening a new one, clicking an already-open tab, the
    selected-paper cue's activatePaperTab -- rather than patching each call site)."""
    raw = assemble_jsx()
    assert 'useEffect(() => {\n    if (activeTab === "library") return;' in raw
    assert "const tab = tabs.find(t => t.key === activeTab);" in raw
    assert "if (tab && tab.paperId != null) setSelected(tab.paperId);" in raw
    assert "}, [activeTab, tabs]);" in raw


def test_library_reveals_selected_paper_via_position_endpoint():
    """inc 319: whenever `selected` changes, the library should auto-locate + scroll to that paper -- but only
    within whatever filter is currently active, and never by clearing/overriding it. `buildFilterQs` is shared
    between the main fetch and this reveal effect so they can never ask the backend two different questions; a
    404 from GET /papers/{id}/position (doesn't match the active filter) is a silent no-op, never a filter
    override. The two LOCAL-only filters (Text-Health/Reference) are deliberately out of scope for the
    cross-page jump (rare, modal-triggered secondary views)."""
    raw = assemble_jsx()
    assert "const buildFilterQs = useCallback(() => {" in raw
    assert 'if (trashView) qs.set("deleted", "true");' in raw
    assert "useEffect(() => {\n    if (selected == null) return;" in raw
    assert "if (listState.papers.some(p => p.id === selected)) return;" in raw
    assert "if (libraryTextHealthFilter || libraryReferenceFilter) return;" in raw
    assert "api(`/papers/${selected}/position?${qs.toString()}`).then(r => {" in raw
    assert "const target = Math.floor(r.data.index / PAGE_SIZE);" in raw
    assert "setPage(p => (p === target ? p : target));" in raw
    assert "}, [selected]);" in raw


def test_paper_card_scrolls_and_flashes_when_selected():
    """inc 319: the scroll-into-view + flash for a newly-revealed selected paper lives on PaperCard itself (not
    centrally in PaperList/10_pdf_layer.jsx, which sits at 589/600 lines) -- it's the one place guaranteed to
    exist in the DOM exactly when its paper is part of the current page, so it self-reveals via its own
    isSelected-keyed effect whether it was already on-screen or just mounted after a page jump."""
    raw = assemble_jsx()
    assert "const cardRef = useRef(null);" in raw
    assert "if (!isSelected || !cardRef.current) return;" in raw
    assert 'cardRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });' in raw
    assert 'cardRef.current.classList.add("flash");' in raw
    assert "}, [isSelected]);" in raw
    assert "data-paper-id={p.id}" in raw
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert ".paper.flash { animation: cardflash 1.2s ease; }" in css


def test_open_paper_deep_link():
    """P0 phase 6 (backlog #33/#34): a `?open_paper=<id>` URL param opens that paper's PDF tab on load -- the
    LibreOffice adapter's "Open in Callosum" action launches exactly this URL. One-shot: the param is stripped
    from the address bar right after use so a page refresh doesn't reopen it.

    inc 460 (roadmap #17): also reads "page"/"precision" so the Suggest-citation Details dialog's "Open in PDF"
    button can jump straight to the matched passage's page, mirroring armCapture's own minimal-target shape."""
    raw = assemble_jsx()
    assert 'const raw = params.get("open_paper");' in raw
    assert "const paperId = parseInt(raw, 10);" in raw
    assert "if (!Number.isFinite(paperId)) return;" in raw
    assert 'const rawPage = params.get("page");' in raw
    assert "openPdf({ id: paperId }, target);" in raw
    assert 'params.delete("open_paper");' in raw
    assert 'params.delete("page");' in raw
    assert 'params.delete("precision");' in raw
    assert "window.history.replaceState(null," in raw


def test_citation_style_manager_surface_and_deep_link():
    raw = assemble_jsx()
    assert "function CitationStylesSettings()" in raw
    assert "function CitationStyleEditorModal(" in raw
    assert 'api("/citations/styles")' in raw
    assert 'apiPost("/citations/styles/preview"' in raw
    assert 'apiPut("/citations/styles/preferences"' in raw
    assert '"/citations/styles/validate"' in raw
    assert '"/citations/styles/install"' in raw
    assert "/export`" in raw
    assert 'method: "DELETE"' in raw
    assert "Download .csl" in raw
    assert "/source/validate`" in raw
    assert "expected_revision: loaded.revision" in raw
    assert "Validate & preview" in raw
    assert "Edit source" in raw and "Duplicate to edit" in raw
    assert "Discard unsaved citation-style changes?" in raw
    assert "locally_modified_at" in raw
    assert "Existing documents that use it will not render" in raw
    assert "Choose another application default before removing this style." in raw
    assert 'placeholder="Journal, discipline, acronym, or style name"' in raw
    assert 'accept=".csl,application/xml,text/xml"' in raw
    assert "window.confirm(" in raw
    assert "Personal style" in raw
    assert '["installed", "Installed"]' in raw
    assert "Use as application default" in raw
    assert "Existing documents keep their embedded style and locale." in raw
    assert 'window.location.hash === "#citation-styles" ? "settings"' in raw
    assert '<SettingsCard title="Citation styles" id="citation-styles">' in raw
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    assert ".citation-style-manager {" in css
    assert ".citation-style-install-row {" in css
    assert ".axis-modal.citation-style-editor-modal {" in css
    assert ".app.mobile .citation-style-editor-grid { grid-template-columns: 1fr;" in css
    assert ".app.mobile .citation-style-manager { grid-template-columns: 1fr; }" in css


def test_onboarding_wizard_orchestrates_existing_settings_never_defaults_egress_on():
    raw = assemble_jsx()
    css = Path("app/frontend/styles.css").read_text(encoding="utf-8")
    # The wizard itself exists, is skippable at every step, and persists completion through the existing
    # PUT /settings endpoint (no dedicated onboarding endpoint invented).
    assert "function OnboardingWizard(" in raw
    assert "Skip setup" in raw
    assert 'apiPut("/settings", { onboarding_completed: true })' in raw
    # It reuses the existing settings components verbatim — never a re-implementation of them.
    assert "<MyPubsSettings onRefreshed={onMyPubsRefreshed} />" in raw
    assert "<AiSettings />" in raw
    # inc 416: each of the five step-source components was split into a bare *Body + a thin wrapper that
    # still adds the .axis-modal-overlay chrome — both halves must survive, so every existing standalone
    # entry point (Settings, the library "+Add" menu, the axis editor/suggester) keeps working unchanged.
    for name in ("ScanModal", "ImportModal", "BundleImportModal", "AxisEditModal", "SuggestAxesModal"):
        assert f"function {name}(" in raw, name
        assert f"function {name}Body(" in raw, name
    # Honesty check (invariant #3 / APPROACH-AVOIDANCE A5): the wizard's own source never pre-checks or
    # forces the egress toggle — it only ever renders the existing, already-defaults-off AiSettings.
    assert "data_egress_enabled: true" not in raw
    assert "data_egress_enabled=true" not in raw
    assert ".onboarding-card {" in css
    assert ".onboarding-dot.active {" in css and ".onboarding-dot.done {" in css


def test_my_pubs_settings_gates_actions_until_profile_loads():
    # inc 416: a real pre-existing bug — Save/Add/Refresh were enabled before the initial GET resolved, so a
    # fast click (or Enter in the variant-draft field) before it completed would PUT blank values and wipe an
    # existing profile. Guards against a regression of the fix, not just the wizard's new usage of it.
    src = (FRONTEND_DIR / "js" / "35a_mypubs.jsx").read_text(encoding="utf-8")
    assert "const [loading, setLoading] = useState(true);" in src
    for guarded in ("persistProfile", "save", "addVariant", "removeVariant", "runRefresh"):
        fn_body = src.split(f"const {guarded} = async", 1)[1].split("\n", 3)[0:3]
        assert any("if (loading) return" in line for line in fn_body), guarded


def test_connection_tooltip_shows_app_version_not_verification_version():
    # Follow-up to v0.3.2: the brand-logo tooltip's version suffix used to fall back to
    # verification_version (the local NLI/quote-verification pipeline's own internal version
    # constant, unrelated to the app's release number) because /health had no real app-version
    # field at all. Now it reads the new app_version field exclusively.
    raw = assemble_jsx()
    assert "version: (r.data && r.data.app_version) || null" in raw
    assert "r.data.verification_version" not in raw


def test_desktop_update_progress_surfaces_in_status_popover_and_settings():
    # Follow-up to v0.3.2: the auto-updater (updater.rs) lives entirely in the Tauri/Rust process — never a
    # backend JobStore — so its download-in-progress state can only ever reach the Status popover as a
    # frontend-only synthetic row built from the shared useDesktopUpdate hook (also read by the toast).
    raw = assemble_jsx()
    assert "function useDesktopUpdate()" in raw
    for event in ("update-downloading", "update-progress", "update-ready"):
        assert f'"{event}"' in raw

    # Status popover: the synthetic row is built from live desktopUpdate state, never registered as
    # navigable (the toast already owns the restart action — no second, driftable trigger).
    assert "function desktopUpdateStatusJob(update)" in raw
    assert 'const DESKTOP_UPDATE_STORE = "desktop_update";' in raw
    assert "const STATUS_NAVIGABLE_STORES" not in raw
    assert "const navigable = !!job.nav" in raw
    assert "desktopUpdate" in raw.split("function StatusMenu(", 1)[1].split("\n", 1)[0]

    # Settings: an on-demand "Check for updates" button, desktop-shell-only (returns null without Tauri).
    # inc 420: lives as a subsection inside "Account & sync" (beneath Appearance), not its own standalone
    # card — a plain browser/dev-server render still shows nothing there (DesktopUpdateSettings itself
    # returns null outside Tauri), so no orphaned "Desktop app" label with nothing under it.
    assert "function DesktopUpdateSettings(" in raw
    assert '!("__TAURI__" in window)) return null' in raw
    assert "Check for updates" in raw


def test_status_tracks_every_progress_bar_and_synchronous_ai_request_with_navigation():
    raw = assemble_jsx()
    status = (PROJECT_ROOT / "app/frontend/js/04c_status.jsx").read_text(encoding="utf-8")
    progress = (PROJECT_ROOT / "app/frontend/js/10_pdf_layer.jsx").read_text(encoding="utf-8")
    assert "useProgressStatus({ label, progress, managedBy })" in progress
    assert "StatusScope nav={{ workspace: ws.id, tab: t.id" in raw
    assert "StatusScope nav={{ pane: paneId, section: s.id" in raw
    assert "Completion and ETA are not measurable yet." in status
    assert "compute_kind" in status and "const navigable = !!job.nav" in status
    assert (
        "<StatusMenu onNavigate={onStatusNavigate} desktopUpdate={desktopUpdate} />"
        in raw.split('className="menubar menubar-mobile"', 1)[1]
    )
    for route_fragment in (
        "axes\\/suggest-terms",
        "suggested-tags",
        "citations\\/suggest",
        "critical-read\\/candidates\\/generate",
        "discovery\\/relevance",
        "funding-discovery\\/llm-triage",
        "help\\/ask",
        "my-publications\\/summary\\/generate",
        "registration-comparisons",
        "settings\\/test-key",
        "summaries",
        "workbench\\/rows",
    ):
        assert route_fragment in status
    assert "setPaneTabRequest" in raw
    for modal in ("duplicates", "wanted", "text-health", "gaps", "overlooked", "scan", "import", "bundle-import"):
        assert f'nav.modal === "{modal}"' in raw
    assert 'invoke("check_for_updates_now")' in raw
    assert '<SettingsCard title="Desktop app">' not in raw
    assert "<DesktopUpdateSettings desktopUpdate={desktopUpdate} />" in raw


def test_static_demo_orients_external_and_first_run_surfaces_without_forking_live_ui():
    raw = assemble_jsx()
    assert "function DemoExternalInterfaces()" in raw
    assert "if (!isDemoMode()) return null;" in raw.split("function DemoExternalInterfaces()", 1)[1].split("}", 1)[0]
    assert 'title="Other interfaces & first run"' in raw
    for label in ("First-run onboarding", "Terminal client", "MCP agent interface"):
        assert label in raw


def test_static_demo_exposes_library_scope_and_locks_personal_reader_mutations_precisely():
    raw = assemble_jsx()
    runtime = (PROJECT_ROOT / "demo/demo-runtime.js").read_text(encoding="utf-8")
    assert "const libraryActionsVisible = !readOnly || demoMode;" in raw
    for label in ("Watched folders", "Import file", "Duplicates", "Text Health", "Trash"):
        assert label in raw
    assert "The saved searches below can be recalled in the demo" in raw
    assert "The curated three-paper demo has no duplicate candidate to fabricate" in raw
    assert "The saved demo note is inspectable but immutable" in raw
    assert "Read state and priority are saved personal library markers" in raw
    assert "if (/^\\/annotations\\//.test(path)" in runtime
    assert "if (/^\\/papers\\/\\d+\\/(read|priority)$/.test(path))" in runtime


def test_built_artifact_is_in_sync():
    """callosum-app.html must equal the live assembly — i.e. it was rebuilt after the last source
    edit (CLAUDE.md: re-run tools/build_frontend.py after editing app/frontend/)."""
    assert BUILT_ARTIFACT.is_file(), "callosum-app.html missing — run python tools/build_frontend.py"
    assert BUILT_ARTIFACT.read_text(encoding="utf-8") == build_frontend_document(), (
        "callosum-app.html is stale — re-run python tools/build_frontend.py"
    )
