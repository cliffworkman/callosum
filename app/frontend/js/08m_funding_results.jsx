// Funding Discovery result rendering: cards, evidence details, and display-only controls.

function FundingSignalTrail({ signal }) {
  const facets = signal.matched_profile_facets || [];
  const evidence = signal.matched_evidence || [];
  return (
    <details className="funding-signal-trail">
      <summary>Signal trail</summary>
      <div className="funding-signal-trail-grid">
        <span><b>Signal type</b>{fundingSignalLabel(signal.signal_type)}</span>
        <span><b>Strength</b>{signal.strength || "unresolved"} - categorical, not a probability.</span>
        <span><b>Matched facets</b>{facets.length ? facets.map(f => f.facet + ": " + f.value).join("; ") : "No profile facets recorded."}</span>
        <span><b>Evidence rows</b>{evidence.length} attached - {fundingSignalSourceSummary(evidence)}</span>
        <span><b>Boundary</b>{fundingSignalBoundary(signal.signal_type)}</span>
      </div>
    </details>
  );
}

function FundingSignalList({ signals, limit = 3 }) {
  return (
    <div className="funding-signals">
      {(signals || []).slice(0, limit).map((s, i) => (
        <div key={i} className={"funding-signal " + s.strength}>
          <b>{fundingSignalLabel(s.signal_type)}</b>
          <span>{s.explanation}</span>
          {s.matched_profile_facets && s.matched_profile_facets.length > 0 &&
            <small>Facets: {s.matched_profile_facets.map(f => f.facet + ": " + f.value).join("; ")}</small>}
          <FundingSignalTrail signal={s} />
        </div>
      ))}
    </div>
  );
}

function FundingLlmEvaluation({ evaluation }) {
  if (!evaluation) return null;
  return (
    <div className="funding-llm-eval">
      <b>{(evaluation.label || "uncertain").replaceAll("_", " ")}</b>
      {evaluation.status === "stale" &&
        <small>AI-fit label based on earlier run evidence; current evidence has changed.</small>}
      {evaluation.rationale && <span>{evaluation.rationale}</span>}
      {evaluation.fit_dimensions && evaluation.fit_dimensions.length > 0 &&
        <small>Fit dimensions: {evaluation.fit_dimensions.join(", ")}</small>}
      {evaluation.concerns && evaluation.concerns.length > 0 &&
        <small>Uncertainty: {evaluation.concerns.join("; ")}</small>}
    </div>
  );
}

function FundingFitTriagePanel({ item, kind, surfaces }) {
  const reasons = fundingTriageReasons(item, kind, surfaces);
  const reviewNotes = fundingTriageReviewNotes(item, kind, surfaces);
  return (
    <div className="funding-fit-triage" aria-label="Funding fit triage evidence">
      <div className="funding-fit-triage-grid">
        <div className="funding-fit-triage-section">
          <b>Why this surfaced</b>
          {reasons.map((reason, i) => <small key={i}>{reason}</small>)}
        </div>
        <div className="funding-fit-triage-section">
          <b>What may need review</b>
          {reviewNotes.map((note, i) => <small key={i}>{note}</small>)}
        </div>
      </div>
      <small className="funding-fit-triage-note">
        Evidence class: {fundingEvidenceClassLabel(kind)} This summary is display-only; it does not alter ranking,
        eligibility, saved state, or opportunity status.
      </small>
    </div>
  );
}

function FundingApplicationRoute({ surfaces }) {
  if (!surfaces || !surfaces.length) return null;
  return (
    <div className="funding-route">
      <b>Application route</b>
      {surfaces.slice(0, 2).map((s, i) => (
        <span key={i}>
          {(s.actionability || "unknown").replaceAll("_", " ")}
          {s.access_mode ? " - " + s.access_mode.replaceAll("_", " ") : ""}
          {s.details ? " - " + s.details : ""}
          {s.url && <> - <a href={s.url} target="_blank" rel="noopener noreferrer">source</a></>}
        </span>
      ))}
    </div>
  );
}

function FundingGroupSummary({ item, label = "funder" }) {
  const group = item && item._fundingGroup;
  if (!group || group.count < 2) return null;
  return (
    <div className="funding-group-summary">
      Same {label} surfaced through {group.evidencePaths} evidence path{group.evidencePaths === 1 ? "" : "s"}
      across {group.count} records. Grouped for display; run and export records stay separate.
      <details>
        <summary>Why grouped?</summary>
        {(group.records || []).map(record => (
          <small key={record.id || record.title}>
            {record.kind}: record {record.id} - {record.title}
            {record.signals && record.signals.length ? ` - signals: ${record.signals.join(", ")}` : ""}
          </small>
        ))}
        <small>Grouping uses exact provider opportunity, funder+scheme, or funder identity keys; distinct routes and evidence classes stay separate.</small>
      </details>
    </div>
  );
}

function FundingEvidenceRow({ evidence }) {
  const title = evidence.purpose_text || evidence.title || evidence.source_record_id || "Historical award evidence";
  const source = evidence.provider_id || evidence.source_kind || "source";
  const amount = fundingAmountText(evidence.amount);
  return (
    <div className="funding-evidence-row">
      <span>{evidence.tax_year ? evidence.tax_year + " - " : ""}{title}</span>
      <div className="funding-evidence-meta">
        <small>Source: {source}{evidence.source_field ? " - " + evidence.source_field : ""}</small>
        {evidence.source_record_id && <small>Record: {evidence.source_record_id}</small>}
        {evidence.award_number && <small>Award: {evidence.award_number}</small>}
        {amount && <small>Amount: {amount}</small>}
        {evidence.scheme_name && <small>Scheme cue: {evidence.scheme_name}</small>}
        {evidence.recipient_withheld && <small>Individual recipient details withheld.</small>}
        {evidence.recipient_name && <small>Recipient: {evidence.recipient_name}</small>}
        {evidence.extraction_method && <small>Basis: {evidence.extraction_method.replaceAll("_", " ")}</small>}
        {evidence.source_url && <a href={evidence.source_url} target="_blank" rel="noopener noreferrer">Open source record</a>}
      </div>
    </div>
  );
}

function FundingDetails({ item, kind }) {
  const evidence = (item.signals || []).flatMap(s => s.matched_evidence || []);
  return (
    <details className="funding-details">
      <summary>Evidence details</summary>
      <div className="funding-detail-block">
        <b>Why this surfaced</b>
        <FundingSignalList signals={item.signals} limit={Math.max((item.signals || []).length, 3)} />
      </div>
      <div className="funding-detail-block">
        <b>Historical evidence</b>
        {evidence.slice(0, 6).map((e, i) => <FundingEvidenceRow key={i} evidence={e} />)}
        {evidence.length === 0 && <div className="settings-sub">No historical award row is attached to this item.</div>}
      </div>
      <div className="funding-detail-block">
        <b>Interpretation boundary</b>
        {kind === "scheme"
          ? <span>Repetition was detected from prior cycles. A current funding window has not been verified.</span>
          : kind === "opportunity"
            ? <span>Current opportunity status is provider-backed. Eligibility still requires review.</span>
            : <span>Portfolio alignment is inferred from observed historical funding records. It is not an explicit statement of current funder priorities.</span>}
      </div>
    </details>
  );
}

function FundingOpportunityCard({ item, surfaces, savedItem, onSaved }) {
  const nextDeadline = item.deadlines && item.deadlines.length ? item.deadlines[0].date : null;
  return (
    <div className="funding-card opportunity">
      <div className="funding-card-head">
        <div>
          <div className="funding-card-title">{item.title || "Untitled opportunity"}</div>
          <div className="funding-card-meta">{item.organization_name} - {item.status || "unknown"}</div>
        </div>
        <FundingSaveButton kind="opportunity" id={item.id} savedItem={savedItem} onSaved={onSaved} />
      </div>
      {nextDeadline && <div className="funding-fact">Next deadline: {nextDeadline}</div>}
      <div className="funding-fact">Eligibility: {(item.eligibility && item.eligibility.label) || "Not assessed"}</div>
      <FundingGroupSummary item={item} label="opportunity" />
      <FundingLlmEvaluation evaluation={item.llm_evaluation} />
      <FundingFitTriagePanel item={item} kind="opportunity" surfaces={surfaces} />
      <FundingApplicationRoute surfaces={surfaces} />
      {item.source_url && <a href={item.source_url} target="_blank" rel="noopener noreferrer">Source</a>}
      <FundingDetails item={item} kind="opportunity" />
    </div>
  );
}

function FundingSchemeCard({ item, surfaces, savedItem, onSaved }) {
  const recurrence = (item.signals || []).find(s => s.signal_type === "scheme_recurrence");
  const years = recurrence ? [...new Set((recurrence.matched_evidence || []).map(e => e.tax_year).filter(Boolean))] : [];
  return (
    <div className="funding-card scheme">
      <div className="funding-card-head">
        <div>
          <div className="funding-card-title">{item.scheme_name || "Recurring scheme"}</div>
          <div className="funding-card-meta">{item.organization_name} - current window not verified</div>
        </div>
        <FundingSaveButton kind="scheme" id={item.id} savedItem={savedItem} onSaved={onSaved} />
      </div>
      {years.length > 0 && <div className="funding-fact">Observed in {years.join(", ")}.</div>}
      <div className="funding-fact">No current application window verified.</div>
      <FundingGroupSummary item={item} label="scheme" />
      <FundingLlmEvaluation evaluation={item.llm_evaluation} />
      <FundingFitTriagePanel item={item} kind="scheme" surfaces={surfaces} />
      <FundingApplicationRoute surfaces={surfaces} />
      <FundingSignalList signals={item.signals} />
      <FundingDetails item={item} kind="scheme" />
    </div>
  );
}

function FundingProspectCard({ item, surfaces, savedItem, onSaved }) {
  return (
    <div className="funding-card prospect">
      <div className="funding-card-head">
        <div>
          <div className="funding-card-title">{item.organization_name || "Funding prospect"}</div>
          <div className="funding-card-meta">
            Historical grantmaking prospect - identity {item.identity_resolution_quality || "unknown"}
          </div>
        </div>
        <FundingSaveButton kind="prospect" id={item.id} savedItem={savedItem} onSaved={onSaved} />
      </div>
      <FundingGroupSummary item={item} label="funder" />
      <FundingLlmEvaluation evaluation={item.llm_evaluation} />
      <FundingFitTriagePanel item={item} kind="prospect" surfaces={surfaces} />
      <FundingSignalList signals={item.signals} />
      {surfaces && surfaces.length
        ? <FundingApplicationRoute surfaces={surfaces} />
        : <div className="funding-fact">No current application surface verified in this run.</div>}
      <FundingDetails item={item} kind="prospect" />
    </div>
  );
}

function FundingSection({ title, items, empty, render }) {
  return (
    <div className="funding-section">
      <div className="funding-subhead">{title}</div>
      {items && items.length ? items.map(render) : <div className="tag-suggest-empty">{empty}</div>}
    </div>
  );
}

function FundingRunActions({ report }) {
  if (!report || !report.run_id) return null;
  return (
    <div className="funding-actions">
      <a className="btn btn-sm" href={`/funding-discovery/runs/${report.run_id}/export.csv`} download>
        Export CSV
      </a>
    </div>
  );
}

function FundingViewToggle({ triageOnly, setTriageOnly, enabled }) {
  if (!enabled) return null;
  return (
    <div className="tags-srcfilter funding-mode" role="group" aria-label="Funding Discovery result view">
      <button type="button" className={"tags-srcfilter-btn" + (!triageOnly ? " on" : "")}
        onClick={() => setTriageOnly(false)}>All surfaced</button>
      <button type="button" className={"tags-srcfilter-btn" + (triageOnly ? " on" : "")}
        onClick={() => setTriageOnly(true)}>LLM-triaged</button>
    </div>
  );
}

function FundingResultFilters({ filter, setFilter, counts, hiddenCount }) {
  return (
    <div className="funding-result-filter-block">
      <div className="funding-subhead">Display filters</div>
      <div className="funding-result-filters" role="group" aria-label="Funding Discovery display filters">
        {FUNDING_RESULT_FILTERS.map(f => (
          <button key={f.key} type="button" className={"tags-srcfilter-btn" + (filter === f.key ? " on" : "")}
            onClick={() => setFilter(f.key)} aria-pressed={filter === f.key}>
            {f.label} <span>{counts[f.key] || 0}</span>
          </button>
        ))}
      </div>
      <div className="funding-result-filter-note">
        Display filters narrow the visible pool only; run evidence, exports, and saved records remain intact.
        {filter !== "all" && ` ${hiddenCount} item${hiddenCount === 1 ? "" : "s"} hidden by the current display filter.`}
      </div>
    </div>
  );
}

function FundingResultSort({ sort, setSort }) {
  return (
    <label className="funding-result-sort">
      <span>Sort visible results</span>
      <select value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort Funding Discovery results">
        {FUNDING_RESULT_SORTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
      </select>
      <small>Sorting changes display order only; result lanes and evidence records are unchanged.</small>
    </label>
  );
}

function FundingResultSummary({ visible, displayPool, surfacedTotal, hiddenLower, filter, sort }) {
  const filterLabel = fundingOptionLabel(FUNDING_RESULT_FILTERS, filter);
  const sortLabel = fundingOptionLabel(FUNDING_RESULT_SORTS, sort);
  return (
    <div className="funding-result-summary" aria-live="polite">
      <div className="funding-result-stat">
        <b>{visible}</b>
        <span>visible of {displayPool} in the current display pool</span>
      </div>
      <div className="funding-result-stat">
        <b>{surfacedTotal}</b>
        <span>surfaced before display-only hiding and filters</span>
      </div>
      <div className="funding-result-stat">
        <b>{hiddenLower}</b>
        <span>lower-signal prospects hidden</span>
      </div>
      <small>Filter: {filterLabel}. Sort: {sortLabel}. These controls change display only.</small>
    </div>
  );
}
