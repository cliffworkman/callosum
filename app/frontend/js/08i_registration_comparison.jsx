// inc 432: inspectable registration↔publication crosswalk. Every row keeps both available sources and bounded
// uncertainty; this surface never computes a compliance/integrity/risk score or author-level judgment.

const REGISTRATION_STATUS_LABELS = {
  "aligned": "Aligned",
  "potentially-changed": "Potentially changed",
  "planned-item-not-located-in-publication": "Planned item not located in publication",
  "reported-item-not-located-in-registration": "Reported item not located in registration",
  "disclosed-deviation": "Disclosed deviation",
  "underspecified-in-registration": "Underspecified in registration",
  "underspecified-in-publication": "Underspecified in publication",
  "ambiguous-study-mapping": "Ambiguous study mapping",
  "not-comparable": "Not comparable",
  "extraction-uncertain": "Extraction uncertain",
};

const REGISTRATION_TIMING_LABELS = {
  "prospective-timing-supported": "Prospective timing supported",
  "timing-unclear": "Timing unclear",
  "registration-appears-after-data-collection-began": "Registration appears after data collection began",
  "registration-appears-after-data-collection-ended": "Registration appears after data collection ended",
  "registration-appears-after-analysis": "Registration appears after analysis",
  "insufficient-dates-to-compare": "Insufficient dates to compare",
};

const REGISTRATION_TRIAGE_LABELS = {
  "prioritize": "Prioritize for review",
  "uncertain": "Keep in focused view — uncertain",
  "likely_noise": "Likely lower-yield",
};

function RegistrationComparisonWorkspace({ paperId, paperTitle, versions, onOpenPaper, invalidLinkIds = [] }) {
  const [versionId, setVersionId] = useState(versions[0] ? versions[0].id : "");
  const [includeSupplements, setIncludeSupplements] = useState(false);
  const [expandSearch, setExpandSearch] = useState(true);
  const [runs, setRuns] = useState([]);
  const [detail, setDetail] = useState(null);
  const [rawVersion, setRawVersion] = useState(null);
  const [showRaw, setShowRaw] = useState(false);
  const [state, setState] = useState({ status: "idle" });
  const [triageState, setTriageState] = useState({ status: "idle" });
  const [triageOnly, setTriageOnly] = useState(false);
  const pollTimer = useRef(null);
  const selectedVersion = versions.find(version => String(version.id) === String(versionId)) || versions[0];
  const incorrectMatch = !!selectedVersion && invalidLinkIds.includes(selectedVersion.link_id);

  const load = useCallback(async (requestedVersion = versionId) => {
    const result = await api(`/papers/${paperId}/registration-comparisons`);
    if (!result.ok) return setState({ status: "error", error: result.error });
    const allRuns = result.data || [];
    setRuns(allRuns);
    const latest = allRuns.find(run => String(run.registration_version_id) === String(requestedVersion));
    if (!latest) { setDetail(null); setTriageOnly(false); return; }
    const full = await api(`/papers/${paperId}/registration-comparisons/${latest.id}`);
    if (full.ok) {
      setDetail(full.data);
      setTriageOnly(full.data.llm_triage_status?.status === "success");
    }
  }, [paperId, versionId]);

  useEffect(() => {
    if (!versions.some(version => String(version.id) === String(versionId))) setVersionId(versions[0]?.id || "");
  }, [versions, versionId]);
  useEffect(() => {
    setDetail(null); setRawVersion(null); setShowRaw(false); setState({ status: "idle" });
    setTriageState({ status: "idle" }); setTriageOnly(false);
    if (versionId) load(versionId);
    return () => { if (pollTimer.current) clearTimeout(pollTimer.current); };
  }, [paperId, versionId, load]);

  const compare = async () => {
    if (!selectedVersion) return;
    setState({ status: "running" });
    const started = await apiPost(`/papers/${paperId}/registration-comparisons`, {
      version_id: selectedVersion.id,
      include_supplements: includeSupplements,
      expand_beyond_expected_sections: expandSearch,
      top_k: 3,
    });
    if (!started.ok) return setState({ status: "error", error: started.error });
    const poll = async () => {
      const result = await api(`/registration-comparisons/jobs/${started.data.job_id}`);
      if (!result.ok) return setState({ status: "error", error: result.error });
      if (result.data.status === "done") {
        await load(selectedVersion.id);
        return setState({ status: "done", message: "Comparison saved. Inspect each row against both sources." });
      }
      if (result.data.status === "error") {
        return setState({ status: "error", error: result.data.detail || "Registration comparison failed." });
      }
      pollTimer.current = setTimeout(poll, 1200);
    };
    poll();
  };

  const inspectRaw = async () => {
    if (!selectedVersion) return;
    if (!rawVersion) {
      const result = await api(`/papers/${paperId}/registration-versions/${selectedVersion.id}`);
      if (!result.ok) return setState({ status: "error", error: result.error });
      setRawVersion(result.data);
    }
    setShowRaw(value => !value);
  };

  const triage = async () => {
    if (!detail || detail.status === "stale") return;
    setTriageState({ status: "running" });
    const result = await apiPost(`/papers/${paperId}/registration-comparisons/${detail.id}/llm-triage`, {});
    if (!result.ok) return setTriageState({ status: "error", error: result.error });
    const triageStatus = result.data.llm_triage_status || {};
    if (triageStatus.status !== "success") {
      return setTriageState({ status: "done", triageStatus });
    }
    await load(selectedVersion.id);
    setTriageOnly(true);
    setTriageState({ status: "done", triageStatus });
  };

  const openSource = (locator, quote, key) => {
    if (!locator || !onOpenPaper || locator.attachment_id == null) return;
    const page = locator.page_start || locator.page || null;
    if (page == null) { setShowRaw(true); return; }
    onOpenPaper({ id: paperId, title: paperTitle }, {
      id: key,
      paperId,
      paperTitle,
      page,
      pageEnd: locator.page_end || page,
      section: locator.section || null,
      precision: "region",
      bboxJson: locator.bbox || null,
      quote: quote || "",
      attachmentId: locator.attachment_id,
    });
  };

  const updateRow = updated => setDetail(current => current && ({
    ...current,
    rows: current.rows.map(row => row.id === updated.id ? { ...updated, llm_triage: row.llm_triage } : row),
    unreviewed_count: current.rows.filter(row => row.id !== updated.id && row.review_state === "unreviewed").length
      + (updated.review_state === "unreviewed" ? 1 : 0),
  }));
  const surfaced = detail ? detail.rows.filter(row => row.comparison_status !== "aligned" && row.review_state === "unreviewed").length : 0;
  const currentRun = runs.find(run => detail && run.id === detail.id);
  const triageStatus = triageState.triageStatus || detail?.llm_triage_status || null;
  const triageReady = detail?.llm_triage_status?.status === "success";
  const effectiveTriageOnly = triageOnly && triageReady;
  const visibleRows = detail ? detail.rows.filter(row => !effectiveTriageOnly || !row.llm_triage || row.llm_triage.show_in_triage) : [];
  const triageHidden = detail ? detail.rows.length - visibleRows.length : 0;

  return <section className="settings-card registration-comparison-workspace">
    <div className="settings-row registration-comparison-toolbar">
      <div>
        <h2 className="settings-card-title">Publication crosswalk</h2>
        <div className="settings-sub">
          {detail ? detail.status === "stale" ? "Comparison stale — source or pipeline changed"
            : surfaced ? `Compared · ${surfaced} item${surfaced === 1 ? "" : "s"} to inspect`
              : "Compared · review the crosswalk; no positive certificate is implied"
            : "Registration attached, not compared"}
        </div>
      </div>
      <button className="btn btn-primary" disabled={state.status === "running" || !selectedVersion || incorrectMatch} onClick={compare}>
        {detail ? "Re-run comparison" : "Compare now"}
      </button>
    </div>
    {incorrectMatch && <div className="settings-note settings-note-err">This version belongs to a registration link marked as an incorrect match. Select or confirm another registration before comparing.</div>}
    <div className="registration-comparison-options">
      {versions.length > 1 && <label className="settings-field-label">Registration version
        <select className="settings-input" value={versionId} onChange={event => setVersionId(event.target.value)}>
          {versions.map(version => <option key={version.id} value={version.id}>
            {version.content_hash.slice(0, 12)} · {new Date(version.retrieved_at).toLocaleDateString()}
          </option>)}
        </select>
      </label>}
      <label className="settings-check"><input type="checkbox" checked={includeSupplements}
        onChange={event => setIncludeSupplements(event.target.checked)} /> Include relevant supplements</label>
      <label className="settings-check"><input type="checkbox" checked={expandSearch}
        onChange={event => setExpandSearch(event.target.checked)} /> Expand beyond expected sections when bounded search is weak</label>
      <button className="btn-link" onClick={inspectRaw}>{showRaw ? "Hide stored registration" : "Inspect stored registration"}</button>
      {selectedVersion?.attachment_id && selectedVersion.provider !== "osf" && <button className="btn-link"
        onClick={() => onOpenPaper && onOpenPaper({ id: paperId, title: paperTitle }, {
          id: `file:${selectedVersion.attachment_id}`, paperId, attachmentId: selectedVersion.attachment_id,
        })}>Open registration attachment</button>}
    </div>
    {state.status === "running" && <ProgressBar label="Comparing bounded registration fields with publication passages…" />}
    {state.status === "error" && <div className="settings-note settings-note-err">Comparison failed: {state.error}</div>}
    {state.message && <div className="settings-note">{state.message}</div>}
    {showRaw && <div className="registration-raw-record">
      <div className="settings-sub">Stored version {selectedVersion?.content_hash} · independently inspectable comparison source</div>
      {rawVersion ? <pre>{rawVersion.rendered_text || JSON.stringify(rawVersion.structured, null, 2)}</pre>
        : <div className="settings-sub">loading stored registration…</div>}
    </div>}
    {detail && detail.status === "stale" && <div className="provider-egress-warn registration-stale-note">
      <b>Comparison stale.</b> Re-run before relying on it. Basis changed: {(detail.stale_reasons || []).map(reason => reason.replaceAll("-", " ")).join("; ")}.
    </div>}
    {detail && <RegistrationLlmTriageControls detail={detail} status={triageStatus}
      running={triageState.status === "running"} triageOnly={effectiveTriageOnly}
      hiddenCount={triageHidden} onRun={triage} onView={setTriageOnly} />}
    {triageState.status === "error" && <div className="settings-note settings-note-err">AI triage failed: {triageState.error}</div>}
    {detail && <div className="registration-crosswalk">
      <div className="registration-crosswalk-framing">{detail.framing} Each row is a flag to inspect. “Not located” is not proof of absence.</div>
      {!visibleRows.length && <div className="settings-note">No rows were selected for the focused view. Switch to <b>All rows</b> to inspect the complete crosswalk.</div>}
      {visibleRows.map(row => <RegistrationComparisonRow key={row.id} row={row} onUpdated={updateRow}
        onOpenRegistration={() => openSource(row.registration_source_locator, row.registration_evidence_text, `registration:${row.id}`)}
        onOpenPublication={() => openSource(row.publication_source_locator, row.publication_evidence_text, `publication:${row.id}`)} />)}
    </div>}
    {currentRun && <div className="settings-sub registration-comparison-basis">
      Registration {currentRun.registration_content_hash.slice(0, 12)} · commitment {currentRun.commitment_extraction_version} · retrieval {currentRun.retrieval_version} · comparison {currentRun.comparison_version}
    </div>}
  </section>;
}

function RegistrationLlmTriageControls({ detail, status, running, triageOnly, hiddenCount, onRun, onView }) {
  const ready = detail.llm_triage_status?.status === "success";
  const stale = detail.status === "stale" || detail.llm_triage_status?.status === "stale";
  return <div className="settings-subsection registration-llm-triage">
    <div className="settings-row registration-llm-triage-head">
      <div>
        <p className="eyebrow">AI triage</p>
        <div className="settings-sub">Sends only the saved comparison fields and bounded registration/publication passages to your configured model. The model adds reversible display labels; it cannot alter evidence, statuses, or review state.</div>
      </div>
      <button className="btn btn-ghost" disabled={running || detail.status === "stale"} onClick={onRun}>
        {ready ? "Re-triage rows with AI" : "Triage rows with AI"}
      </button>
    </div>
    {running && <ProgressBar label="Triaging comparison rows from bounded evidence…" />}
    {status && ["unavailable", "failed"].includes(status.status) &&
      <div className="settings-note settings-note-err">{status.warning || "AI triage is unavailable."}</div>}
    {stale && <div className="settings-note">Saved AI triage is stale. Re-run the comparison, then triage the new rows.</div>}
    {ready && !stale && <div className="registration-triage-view">
      <div className="tags-srcfilter" role="group" aria-label="Registration comparison row view">
        <button className={"tags-srcfilter-btn" + (!triageOnly ? " on" : "")} onClick={() => onView(false)}>All rows</button>
        <button className={"tags-srcfilter-btn" + (triageOnly ? " on" : "")} onClick={() => onView(true)}>AI-focused</button>
      </div>
      <span className="settings-sub">{triageOnly ? `${hiddenCount} lower-yield row${hiddenCount === 1 ? "" : "s"} hidden from this display.` : "The complete deterministic crosswalk is visible."}</span>
    </div>}
    {status?.status === "success" && status.warning && <div className="settings-note">{status.warning}</div>}
  </div>;
}

function RegistrationComparisonRow({ row, onUpdated, onOpenRegistration, onOpenPublication }) {
  const [note, setNote] = useState(row.note || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => setNote(row.note || ""), [row.note]);
  const save = async reviewState => {
    setBusy(true); setError(null);
    const result = await apiPost(`/registration-comparison-rows/${row.id}/review`, {
      review_state: reviewState,
      note: note.trim() || null,
    });
    setBusy(false);
    if (result.ok) onUpdated(result.data);
    else setError(result.error || "Could not save this review state.");
  };
  const scope = row.search_scope || {};
  const canOpenRegistration = row.registration_source_locator && row.registration_source_locator.attachment_id != null;
  const canOpenPublication = row.publication_source_locator && row.publication_source_locator.attachment_id != null;
  return <article className={`registration-comparison-row status-${row.comparison_status} review-${row.review_state}`}>
    <div className="registration-comparison-row-head">
      <div><span className="eyebrow">{row.field_type.replaceAll("-", " ")}</span>
        <div className="registration-comparison-status">{REGISTRATION_STATUS_LABELS[row.comparison_status] || row.comparison_status}</div></div>
      {row.timing_status && <span className="registration-timing-status">{REGISTRATION_TIMING_LABELS[row.timing_status] || row.timing_status}</span>}
      {row.review_state !== "unreviewed" && <span className="settings-sub">{row.review_state}</span>}
    </div>
    <div className="registration-evidence-columns">
      <div className="registration-evidence-column">
        <b>Registration</b>
        {row.registration_evidence_text ? <blockquote>{row.registration_evidence_text}</blockquote>
          : <div className="settings-sub">No extracted registration evidence for this canonical field.</div>}
        {canOpenRegistration && <button className="btn-link" onClick={onOpenRegistration}>Open registration evidence</button>}
      </div>
      <div className="registration-evidence-column">
        <b>Publication</b>
        {row.publication_evidence_text ? <blockquote>{row.publication_evidence_text}</blockquote>
          : <div className="settings-sub">Not located in the recorded publication search scope.</div>}
        {canOpenPublication && <button className="btn-link" onClick={onOpenPublication}>Open publication evidence</button>}
      </div>
    </div>
    <div className="registration-comparison-why"><b>Why this was surfaced</b><div>{row.explanation}</div></div>
    {row.llm_triage && <div className={`registration-row-triage triage-${row.llm_triage.label} ${row.llm_triage.status || "current"}`}>
      <b>AI triage · {REGISTRATION_TRIAGE_LABELS[row.llm_triage.label] || row.llm_triage.label}</b>
      {row.llm_triage.rationale && <div>{row.llm_triage.rationale}</div>}
      {!!(row.llm_triage.concerns || []).length && <div className="settings-sub">Review caveat: {row.llm_triage.concerns.join(" · ")}</div>}
      <small>Display aid only — not a revised comparison status or a judgment about the paper or authors.</small>
    </div>}
    <details className="registration-search-scope"><summary>Search scope and uncertainty</summary>
      <div>Expected sections: {(scope.expected_section_families || []).join(", ") || "not applicable"}</div>
      <div>Sections searched: {(scope.sections_searched || []).join(", ") || "none located"}</div>
      <div>{scope.whole_article_expanded ? "Whole-article expansion occurred." : "Search remained bounded to expected sections."}</div>
      <div>{scope.supplements_searched ? "Relevant supplements were searched." : "Supplements were not searched for this field."}</div>
      <div>Study mapping: {scope.study_mapping || "not applicable"}</div>
      <div>Publication sources: {(scope.publication_sources || []).map(source =>
        `attachment ${source.attachment_id}${source.checksum ? ` (${source.checksum.slice(0, 12)})` : ""}`).join(", ") || "none"}</div>
      <div>{row.uncertainty}</div>
    </details>
    <div className="registration-row-review">
      <textarea className="settings-input" value={note} onChange={event => setNote(event.target.value)} placeholder="Add a private review note…" aria-label="Comparison review note" />
      <div className="settings-actions">
        <button className="btn btn-ghost" disabled={busy} onClick={() => save("reviewed")}>Mark reviewed</button>
        <button className="btn-link" disabled={busy} onClick={() => save("dismissed")}>Dismiss flag</button>
        <button className="btn-link" disabled={busy || note === (row.note || "")} onClick={() => save(row.review_state)}>Save note</button>
      </div>
      {error && <div className="axis-err">{error}</div>}
    </div>
  </article>;
}

// inc 434: this comparison is information-dense enough to need a full selected-paper workspace. Transparency
// keeps local disclosure/reference evidence and links here; discovery, acquisition, source correction, and the
// evidence crosswalk live together after Critique under Synthesize.
function MetaPreregistrationPane({ ctx, active }) {
  const paperId = ctx.selectedPaper;
  const [meta, setMeta] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const loadPaper = useCallback(async () => {
    if (paperId == null) return setMeta(null);
    const result = await api(`/papers/${paperId}`);
    setMeta(result.ok ? {
      title: result.data.title,
      attachments: result.data.attachments || [],
    } : { error: result.error, title: `Paper ${paperId}`, attachments: [] });
  }, [paperId]);
  useEffect(() => {
    setMeta(null);
    if (active) loadPaper();
  }, [active, loadPaper]);
  const sourceChanged = async () => {
    await loadPaper();
    setRefreshKey(value => value + 1);
  };
  if (paperId == null) return <div className="meta-preregistration ws-pad">
    <div className="tag-suggest-empty">Select a Library paper to find, attach, or compare a registration.</div>
  </div>;
  return <div className="meta-preregistration ws-pad">
    <div className="meta-preregistration-intro">
      <p className="eyebrow">Meta-Preregistration</p>
      <div className="settings-sub">Compare a publication with a confirmed registration through evidence-bound flags for human inspection. Callosum does not produce a compliance, integrity, or author score, and “not located” never means absent.</div>
    </div>
    {!meta && <div className="settings-note">Loading registration workspace…</div>}
    {meta?.error && <div className="settings-note settings-note-err">Could not load this paper: {meta.error}</div>}
    {meta && !meta.error && <div className="meta-preregistration-grid">
      <RegistrationDiscovery paperId={paperId} paperTitle={meta.title} onOpenPaper={ctx.onOpenPaper}
        refreshKey={refreshKey} />
      <RegistrationReferenceActions paperId={paperId} attachments={meta.attachments} onChanged={sourceChanged} />
    </div>}
  </div>;
}

registerWorkspaceTab(
  { id: "synthesis", label: "Synthesize", order: 30 },
  { id: "meta-preregistration", label: "Meta-Preregistration", order: 30, hideInReadOnly: true,
    render: (ctx, active) => <MetaPreregistrationPane ctx={ctx} active={active} /> },
);
