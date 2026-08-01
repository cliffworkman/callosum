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

function RegistrationComparisonWorkspace({ paperId, paperTitle, versions, onOpenPaper, invalidLinkIds = [] }) {
  const [versionId, setVersionId] = useState(versions[0] ? versions[0].id : "");
  const [includeSupplements, setIncludeSupplements] = useState(false);
  const [expandSearch, setExpandSearch] = useState(true);
  const [runs, setRuns] = useState([]);
  const [detail, setDetail] = useState(null);
  const [rawVersion, setRawVersion] = useState(null);
  const [showRaw, setShowRaw] = useState(false);
  const [state, setState] = useState({ status: "idle" });
  const pollTimer = useRef(null);
  const selectedVersion = versions.find(version => String(version.id) === String(versionId)) || versions[0];
  const incorrectMatch = !!selectedVersion && invalidLinkIds.includes(selectedVersion.link_id);

  const load = useCallback(async (requestedVersion = versionId) => {
    const result = await api(`/papers/${paperId}/registration-comparisons`);
    if (!result.ok) return setState({ status: "error", error: result.error });
    const allRuns = result.data || [];
    setRuns(allRuns);
    const latest = allRuns.find(run => String(run.registration_version_id) === String(requestedVersion));
    if (!latest) { setDetail(null); return; }
    const full = await api(`/papers/${paperId}/registration-comparisons/${latest.id}`);
    if (full.ok) setDetail(full.data);
  }, [paperId, versionId]);

  useEffect(() => {
    if (!versions.some(version => String(version.id) === String(versionId))) setVersionId(versions[0]?.id || "");
  }, [versions, versionId]);
  useEffect(() => {
    setDetail(null); setRawVersion(null); setShowRaw(false); setState({ status: "idle" });
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
    rows: current.rows.map(row => row.id === updated.id ? updated : row),
    unreviewed_count: current.rows.filter(row => row.id !== updated.id && row.review_state === "unreviewed").length
      + (updated.review_state === "unreviewed" ? 1 : 0),
  }));
  const surfaced = detail ? detail.rows.filter(row => row.comparison_status !== "aligned" && row.review_state === "unreviewed").length : 0;
  const currentRun = runs.find(run => detail && run.id === detail.id);

  return <div className="registration-comparison-workspace">
    <div className="registration-comparison-toolbar">
      <div>
        <b>Publication crosswalk</b>
        <div className="axis-hint">
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
      {versions.length > 1 && <label>Registration version
        <select value={versionId} onChange={event => setVersionId(event.target.value)}>
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
      <div className="axis-hint">Stored version {selectedVersion?.content_hash} · independently inspectable comparison source</div>
      {rawVersion ? <pre>{rawVersion.rendered_text || JSON.stringify(rawVersion.structured, null, 2)}</pre>
        : <div className="axis-hint">loading stored registration…</div>}
    </div>}
    {detail && detail.status === "stale" && <div className="provider-egress-warn registration-stale-note">
      <b>Comparison stale.</b> Re-run before relying on it. Basis changed: {(detail.stale_reasons || []).map(reason => reason.replaceAll("-", " ")).join("; ")}.
    </div>}
    {detail && <div className="registration-crosswalk">
      <div className="registration-crosswalk-framing">{detail.framing} Each row is a flag to inspect. “Not located” is not proof of absence.</div>
      {detail.rows.map(row => <RegistrationComparisonRow key={row.id} row={row} onUpdated={updateRow}
        onOpenRegistration={() => openSource(row.registration_source_locator, row.registration_evidence_text, `registration:${row.id}`)}
        onOpenPublication={() => openSource(row.publication_source_locator, row.publication_evidence_text, `publication:${row.id}`)} />)}
    </div>}
    {currentRun && <div className="axis-hint registration-comparison-basis">
      Registration {currentRun.registration_content_hash.slice(0, 12)} · commitment {currentRun.commitment_extraction_version} · retrieval {currentRun.retrieval_version} · comparison {currentRun.comparison_version}
    </div>}
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
      {row.review_state !== "unreviewed" && <span className="axis-hint">{row.review_state}</span>}
    </div>
    <div className="registration-evidence-columns">
      <div className="registration-evidence-column">
        <b>Registration</b>
        {row.registration_evidence_text ? <blockquote>{row.registration_evidence_text}</blockquote>
          : <div className="axis-hint">No extracted registration evidence for this canonical field.</div>}
        {canOpenRegistration && <button className="btn-link" onClick={onOpenRegistration}>Open registration evidence</button>}
      </div>
      <div className="registration-evidence-column">
        <b>Publication</b>
        {row.publication_evidence_text ? <blockquote>{row.publication_evidence_text}</blockquote>
          : <div className="axis-hint">Not located in the recorded publication search scope.</div>}
        {canOpenPublication && <button className="btn-link" onClick={onOpenPublication}>Open publication evidence</button>}
      </div>
    </div>
    <div className="registration-comparison-why"><b>Why this was surfaced</b><div>{row.explanation}</div></div>
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
      <textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Add a private review note…" aria-label="Comparison review note" />
      <div className="settings-actions">
        <button className="btn btn-secondary" disabled={busy} onClick={() => save("reviewed")}>Mark reviewed</button>
        <button className="btn-link" disabled={busy} onClick={() => save("dismissed")}>Dismiss flag</button>
        <button className="btn-link" disabled={busy || note === (row.note || "")} onClick={() => save(row.review_state)}>Save note</button>
      </div>
      {error && <div className="axis-err">{error}</div>}
    </div>
  </article>;
}
