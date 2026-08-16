// inc 250 (#44 increment 1): transparency-signals auditor — read a paper's extracted text and detect whether it
// *discloses* 7 open-science artifacts (ODDPub/rtransparent-derived): data availability, code availability,
// conflict-of-interest, funding, protocol/trial registration, preregistration, and an "available upon request"
// weak-signal qualifier. FLAG-not-ADJUDICATE: each present / not-found / n/a — never a verdict, never a score, never
// an accusation. "not found" ≠ "absent" (silence≠certificate). Local, rule-based, no AI, no egress. The deterministic
// sibling of statcheck / the LMM / meta-analysis auditors. See methods/transparency.py.

// inc 250 (credit-the-lineage): the detector lineage, one-click added to the library (statcheck/lmm/meta pattern).
// DOIs are included only where confidently known — a missing DOI over a wrong one (import dedups on title+year+author).
const TRANSPARENCY_CSL = [
  {
    type: "article-journal",
    title: "ODDPub — a text-mining algorithm to detect data sharing in biomedical publications",
    author: [
      { family: "Riedel", given: "Nico" },
      { family: "Kip", given: "Miriam" },
      { family: "Bobrov", given: "Evgeny" },
    ],
    "container-title": "Data Science Journal",
    volume: "19", page: "42",
    issued: { "date-parts": [[2020]] },
    DOI: "10.5334/dsj-2020-042",
  },
  {
    type: "article-journal",
    title: "Assessment of transparency indicators across the biomedical literature: How open is open?",
    author: [
      { family: "Serghiou", given: "Stylianos" },
      { family: "Contopoulos-Ioannidis", given: "Despina G." },
      { family: "Boyack", given: "Kevin W." },
      { family: "Riedel", given: "Nico" },
      { family: "Wallach", given: "Joshua D." },
      { family: "Ioannidis", given: "John P. A." },
    ],
    "container-title": "PLOS Biology",
    volume: "19", issue: "3", page: "e3001107",
    issued: { "date-parts": [[2021]] },
    DOI: "10.1371/journal.pbio.3001107",
  },
  {
    type: "article-journal",
    title: "The preregistration revolution",
    author: [
      { family: "Nosek", given: "Brian A." },
      { family: "Ebersole", given: "Charles R." },
      { family: "DeHaven", given: "Alexander C." },
      { family: "Mellor", given: "David T." },
    ],
    "container-title": "Proceedings of the National Academy of Sciences",
    volume: "115", issue: "11", page: "2600-2606",
    issued: { "date-parts": [[2018]] },
    DOI: "10.1073/pnas.1708274114",
  },
];

// Per-paper audit. The section gets only the paper id via ctx, so it self-fetches title + chunk_count. Auto-runs
// when its section is the open one (like statcheck / the LMM / meta auditors).
function TransparencyPaper({ paperId, onOpenPaper, onOpenMetaPreregistration, active }) {
  const [meta, setMeta] = useState(null); // { title, hasText } | null
  const [state, setState] = useState({ status: "idle" });
  useEffect(() => {
    setState({ status: "idle" }); setMeta(null);
    if (paperId == null) return;
    let live = true;
    api(`/papers/${paperId}`).then(r => {
      if (!live || !r.ok) return;
      setMeta({ title: r.data.title, hasText: (r.data.chunk_count || 0) > 0, attachments: r.data.attachments || [] });
    });
    return () => { live = false; };
  }, [paperId]);
  const run = async () => {
    setState({ status: "running" });
    const r = await api(`/papers/${paperId}/transparency`);
    setState(r.ok ? { status: "done", data: r.data } : { status: "error", error: r.error });
  };
  useEffect(() => {
    if (active && meta && meta.hasText && state.status === "idle") run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, meta]);
  const open = (evidence, key) => {
    if (!onOpenPaper) return;
    const title = meta ? meta.title : "";
    const target = methodEvidenceTarget(paperId, title, evidence, key);
    if (target) onOpenPaper({ id: paperId, title }, target);
  };
  if (paperId == null) return <div className="tag-suggest-empty">Select a paper to check its transparency disclosures.</div>;
  const hasText = meta ? meta.hasText : false;
  const d = state.data;
  return (
    <div className="detail-statcheck">
      <span className="detail-cite-label">{meta ? meta.title : "This paper"}</span>
      <DemoMethodAction label="Check disclosures" />
      {!meta
        ? <span className="tag-suggest-empty">loading…</span>
        : !hasText
          ? <span className="tag-suggest-empty">Process a PDF first — the auditor reads the paper's extracted text.</span>
          : state.status === "idle" && !isDemoMode()
            ? <button className="btn-link" title="Detect this paper's open-science disclosures — local, no AI" onClick={run}>Check disclosures</button>
            : null}
      {state.status === "running" && <span className="tag-suggest-empty">checking…</span>}
      {state.status === "error" && <div className="axis-err">Couldn't check: {state.error}</div>}
      {state.status === "done" && d && <TransparencyChecklist checks={d.checks} onOpen={open}
        references={d.registration_references} referenceState={d.registration_reference_state} />}
      {meta && onOpenMetaPreregistration && <div className="settings-note registration-workspace-cue">
        <span>Find, attach, and compare registrations in the full Synthesize workspace.</span>
        <button className="btn btn-ghost" onClick={onOpenMetaPreregistration}>Open Meta-Preregistration</button>
      </div>}
    </div>
  );
}

function TransparencyChecklist({ checks, onOpen, references, referenceState, showRegistrationReferences = true }) {
  if (!checks || !checks.length) return null;
  const present = checks.filter(c => c.status === "present").length;
  const notFound = checks.filter(c => c.status === "not-found").length;
  const na = checks.filter(c => c.status === "not-applicable").length;
  return (
    <div className="bayes-checklist">
      <p className="eyebrow">Open-science disclosures</p>
      {/* A factual tally of the statuses below — not a score or a grade. */}
      <div className="lmm-summary">{present} disclosed · {notFound} not detected · {na} not applicable · {checks.length} checks</div>
      {checks.map((c) => (
        <div key={c.key} className={"bayes-check-item" + (c.status === "not-applicable" ? " lmm-na" : "")}>
          <div className="bayes-check-head">
            <span className="bayes-check-label">{c.label}</span>
            {c.status === "present"
              ? <span className="cite-status verified">✓ detected</span>
              : <span className="bayes-check-muted">{c.status === "not-applicable" ? "n/a" : "not detected"}</span>}
          </div>
          {c.note && <div className="bayes-check-note">{c.note}</div>}
          {c.explainer && <div className="lmm-explainer">{c.explainer}</div>}
          {c.basis && <div className="lmm-basis">basis: {c.basis}</div>}
          {c.evidence &&
            <EvidenceQuote text={c.evidence} match={c.evidence} label="Evidence" className="bayes-check-ev"
              precision={c.coordinate_precision} hasSourcePage={c.page != null}
              onOpen={c.page != null ? () => onOpen(c, `transparency-check:${c.key}`) : null}
              openLabel={c.coordinate_precision === "exact" ? "Open and highlight this disclosure evidence" : "Open source page for this disclosure evidence"} />}
          {c.evidence && <EvidenceTrail detector="Transparency signals" matched={c.evidence}
            precision={c.coordinate_precision} hasSourcePage={c.page != null} page={c.page}
            caveat="Disclosure signals are text detections only; not detected does not mean absent." />}
          {showRegistrationReferences && c.key === "preregistration" &&
            <RegistrationReferences references={references || []} state={referenceState} onOpen={onOpen} />}
        </div>
      ))}
      <div className="statcheck-caveat">
        Detects <b>reported disclosures</b> in the extracted text — it does not judge a paper's openness. <b>“Not detected” means not found in the text, NOT that the artifact is absent</b> — a data-availability statement can live in an appendix, a footnote, or the journal's structured metadata this reader doesn't fully see. It's a prompt to look, never a score, and never an accusation of the authors. “Available upon request” is shown as a weaker signal than an open link, not a concern in itself.
      </div>
    </div>
  );
}

function RegistrationReferences({ references, state, onOpen }) {
  const stateLabel = state === "multiple-references-detected" ? "Multiple registration references detected"
    : state === "reference-detected" ? "Registration reference detected"
      : state === "language-detected" ? "Preregistration language detected; no actionable reference located"
        : "No registration reference detected";
  return (
    <div className="registration-reference-list">
      <div className="lmm-summary">{stateLabel}</div>
      {references.map((ref, index) => <div className="bayes-check-ev" key={`${ref.provider}:${ref.external_id}:${index}`}>
        <div><b>{ref.provider}</b> · <code>{ref.external_id}</code></div>
        {ref.evidence_snippet && <EvidenceQuote text={ref.evidence_snippet} match={ref.evidence_snippet}
          label={ref.extraction_method === "pdf-hyperlink" ? `Linked from “${ref.visible_text || "link"}”` : "Reference evidence"}
          className="bayes-check-ev" precision={ref.coordinate_precision} hasSourcePage={ref.page != null}
          onOpen={ref.page != null ? () => onOpen(ref, `registration-reference:${index}`) : null}
          openLabel="Open source page for this registration reference" />}
        <div className="settings-actions">
          {ref.canonical_url && <button className="axis-link" onClick={() => window.open(ref.canonical_url, "_blank", "noopener")}>Open externally</button>}
          <span className="axis-hint">{ref.explicitly_printed ? "printed in document" : ref.extraction_method === "manual" ? "supplied by you" : "PDF link target"}</span>
        </div>
      </div>)}
      {!references.length && <div className="axis-hint">“Not located” is not equivalent to absent; the reference may be in unextracted metadata, a supplement, or visible only outside the document.</div>}
    </div>
  );
}

function RegistrationReferenceActions({ paperId, attachments, onChanged }) {
  const [value, setValue] = useState("");
  const [selectedAttachment, setSelectedAttachment] = useState("");
  const [status, setStatus] = useState({ state: "idle" });
  const fileInput = useRef(null);
  if (isDemoMode()) return <section className="settings-card registration-reference-actions">
    <h2 className="settings-card-title">Add or correct a source</h2>
    <div className="settings-note">Source edits and local-file attachment are unavailable in this immutable online demo.</div>
  </section>;
  const addReference = async () => {
    if (!value.trim()) return;
    setStatus({ state: "working" });
    const r = await apiPost(`/papers/${paperId}/registration-references`, { value: value.trim() });
    if (!r.ok) return setStatus({ state: "error", error: r.error });
    setValue(""); setStatus({ state: "done", message: "Registration reference saved locally." }); onChanged();
  };
  const markAttachment = async () => {
    if (!selectedAttachment) return;
    setStatus({ state: "working" });
    const r = await apiPatch(`/papers/${paperId}/attachments/${selectedAttachment}/document-role`, { role: "preregistration" });
    if (!r.ok) return setStatus({ state: "error", error: r.error });
    setStatus({ state: "done", message: "Attachment marked as a preregistration." }); onChanged();
  };
  const attachFile = async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    setStatus({ state: "working" });
    const r = await apiUpload(`/papers/${paperId}/registration-attachments?filename=${encodeURIComponent(file.name || "registration.pdf")}`, file);
    event.target.value = "";
    if (!r.ok) return setStatus({ state: "error", error: r.error });
    setStatus({ state: "done", message: "Local registration PDF attached and processed." }); onChanged();
  };
  return <section className="settings-card registration-reference-actions">
    <h2 className="settings-card-title">Add or correct a source</h2>
    <div className="settings-sub">These actions are local. Saving a reference does not fetch it or confirm that it belongs to this paper.</div>
    <div className="settings-field">
      <label className="settings-field-label" htmlFor={`registration-reference-${paperId}`}>Registration URL, DOI, or identifier</label>
      <div className="settings-actions registration-source-row">
        <input id={`registration-reference-${paperId}`} className="settings-input" value={value} onChange={e => setValue(e.target.value)} placeholder="https://osf.io/… or 10.17605/OSF.IO/…" />
        <button className="btn btn-ghost" disabled={status.state === "working" || !value.trim()} onClick={addReference}>Save reference</button>
      </div>
    </div>
    <div className="settings-actions">
      <input ref={fileInput} type="file" accept="application/pdf,.pdf" onChange={attachFile} style={{display: "none"}} />
      <button className="btn btn-ghost" disabled={status.state === "working"} onClick={() => fileInput.current && fileInput.current.click()}>Attach local preregistration PDF</button>
    </div>
    {!!attachments.length && <div className="settings-field">
      <label className="settings-field-label" htmlFor={`registration-attachment-${paperId}`}>Existing attachment</label>
      <div className="settings-actions registration-source-row">
        <select id={`registration-attachment-${paperId}`} className="settings-input" value={selectedAttachment} onChange={e => setSelectedAttachment(e.target.value)}>
          <option value="">Choose an existing attachment…</option>
          {attachments.filter(a => a.role !== "preregistration").map(a => <option value={a.id} key={a.id}>{a.filename || `Attachment ${a.id}`} · {a.role || "legacy role"}</option>)}
        </select>
        <button className="btn btn-ghost" disabled={status.state === "working" || !selectedAttachment} onClick={markAttachment}>Mark as preregistration</button>
      </div>
    </div>}
    {status.state === "error" && <div className="settings-note settings-note-err">{status.error}</div>}
    {status.state === "done" && <div className="settings-note">{status.message}</div>}
  </section>;
}

// inc 427 / 434: registry discovery is an explicit metadata-egress action. Opening Meta-Preregistration fetches
// already-local candidate state only. Confirmation records a link; acquisition remains a separate user action.
function RegistrationDiscovery({ paperId, paperTitle, onOpenPaper, refreshKey = 0 }) {
  const [links, setLinks] = useState([]);
  const [versions, setVersions] = useState([]);
  const [state, setState] = useState({ status: "idle" });
  const pollTimer = useRef(null);
  const loadLocalState = useCallback(async () => {
    const [linkResult, versionResult] = await Promise.all([
      api(`/papers/${paperId}/registration-links?include_rejected=true`),
      api(`/papers/${paperId}/registration-versions`),
    ]);
    if (linkResult.ok) setLinks(linkResult.data || []);
    if (versionResult.ok) setVersions(versionResult.data || []);
  }, [paperId]);
  useEffect(() => {
    setState({ status: "idle" }); setLinks([]); setVersions([]); loadLocalState();
    return () => { if (pollTimer.current) clearTimeout(pollTimer.current); };
  }, [loadLocalState, refreshKey]);
  const showDisclosure = async () => {
    const r = await api(`/papers/${paperId}/registration-discovery/preview`);
    setState(r.ok ? { status: "consent", preview: r.data } : { status: "error", error: r.error });
  };
  const search = async (fresh = false) => {
    setState({ status: "running" });
    const started = await apiPost(`/papers/${paperId}/registration-discovery`, { metadata_consent: true, fresh });
    if (!started.ok) return setState({ status: "error", error: started.error });
    const poll = async () => {
      const r = await api(`/registration-discovery/${started.data.job_id}`);
      if (!r.ok) return setState({ status: "error", error: r.error });
      if (r.data.status === "done") {
        setLinks(r.data.candidates || []);
        return setState({ status: "done", providers: r.data.providers || [] });
      }
      if (r.data.status === "error") return setState({ status: "error", error: r.data.detail || "Registry discovery failed." });
      pollTimer.current = setTimeout(poll, 1200);
    };
    poll();
  };
  const change = async (link, action, incorrect = false) => {
    setState({ status: "working", linkId: link.id });
    const r = await apiPost(`/papers/${paperId}/registration-links/${link.id}/${action}`, {});
    if (!r.ok) return setState({ status: "error", error: r.error });
    await loadLocalState();
    setState({ status: "done", message: action === "confirm"
      ? "Registration link confirmed. No registration content has been downloaded yet."
      : incorrect ? "Registration link marked as an incorrect match. Its saved comparisons will be shown as stale."
      : "Candidate dismissed. It will stay hidden unless you request a fresh search." });
  };
  const acquire = async link => {
    setState({ status: "acquiring", linkId: link.id });
    const started = await apiPost(`/papers/${paperId}/registration-links/${link.id}/acquire`, {});
    if (!started.ok) return setState({ status: "error", error: started.error });
    const poll = async () => {
      const result = await api(`/registration-acquisition/${started.data.job_id}`);
      if (!result.ok) return setState({ status: "error", error: result.error });
      if (result.data.status === "done") {
        await loadLocalState();
        return setState({
          status: "done",
          message: result.data.changed
            ? "Registration acquired as a new local version. It has not been compared yet."
            : "The public registration matches the version already stored locally.",
        });
      }
      if (result.data.status === "error") {
        return setState({ status: "error", error: result.data.detail || "Registration acquisition failed." });
      }
      pollTimer.current = setTimeout(poll, 1200);
    };
    poll();
  };
  const confirmed = links.filter(link => link.link_status === "confirmed");
  const rejected = links.filter(link => link.link_status === "rejected");
  const invalid = links.filter(link => link.link_status !== "confirmed");
  const candidates = links.filter(link => link.link_status === "candidate" || link.link_status === "withdrawn" || link.link_status === "unavailable");
  const statusLabel = rejected.length && !confirmed.length ? "Incorrect registration match"
    : versions.length ? "Registration source saved"
    : confirmed.length ? "Registration linked, not acquired"
    : candidates.length ? "Candidates found, choose"
      : "No registration linked";
  return <div className="registration-workflow">
    <section className="settings-card registration-discovery">
      <div className="settings-row registration-discovery-head">
        <div><h2 className="settings-card-title">Registration source</h2><div className="settings-sub">{statusLabel}</div></div>
        <button className="btn btn-ghost" disabled={isDemoMode() || state.status === "running" || state.status === "working"} onClick={showDisclosure}
          title={isDemoMode() ? "Registry search is unavailable in the static online demo." : undefined}>
          {links.length ? "Search again" : "Find registration"}
        </button>
      </div>
      {state.status === "consent" && <div className="provider-egress-warn registration-discovery-consent">
        <b>Search public registry metadata?</b>
        <div>{state.preview.notice}</div>
        <div>Sends: <b>{(state.preview.metadata_fields || []).join(", ") || "no paper metadata"}</b>.</div>
        {!!(state.preview.local_match_fields || []).length && <div>Used only on this machine for matching: {state.preview.local_match_fields.join(", ")}.</div>}
        <div className="settings-actions">
          <button className="btn btn-primary" onClick={() => search(false)}>Search OSF and DataCite</button>
          <button className="btn btn-ghost" onClick={() => setState({ status: "idle" })}>Cancel</button>
        </div>
      </div>}
      {state.status === "running" && <ProgressBar label="Searching public registration metadata…" managedBy="backend-job" />}
      {state.status === "acquiring" && <ProgressBar label="Acquiring the confirmed public registration…" managedBy="backend-job" />}
      {state.status === "error" && <div className="settings-note settings-note-err">Registration workflow failed: {state.error}</div>}
      {state.message && <div className="settings-note">{state.message}</div>}
      {(state.providers || []).map(report => report.status !== "ok" && <div className="settings-note" key={report.provider}>
        {report.provider}: {report.detail || report.status}
      </div>)}
      {!!rejected.length && !confirmed.length && <div className="provider-egress-warn">
        <b>Incorrect registration match.</b> Choose another candidate or run a fresh search. Saved comparisons remain inspectable and are marked stale.
      </div>}
      {confirmed.map(link => <RegistrationCandidateCard key={link.id} link={link} confirmed
        versions={versions.filter(version => version.link_id === link.id)}
        busy={(state.status === "acquiring" || state.status === "working") && state.linkId === link.id}
        onAcquire={() => acquire(link)} onIncorrect={() => change(link, "reject", true)} />)}
      {candidates.map(link => <RegistrationCandidateCard key={link.id} link={link}
        busy={state.status === "working" && state.linkId === link.id}
        onConfirm={() => change(link, "confirm")} onReject={() => change(link, "reject")} />)}
      {state.status === "done" && !links.length && <div className="settings-note">
        No candidate was located through the searched metadata routes. This is not evidence that no registration exists.
        You can add a known reference or local PDF below.
      </div>}
      {state.status === "done" && <button className="btn-link" onClick={() => search(true)}>Fresh search, including dismissed candidates</button>}
    </section>
    {!!versions.length && <RegistrationComparisonWorkspace paperId={paperId} paperTitle={paperTitle}
      versions={versions} onOpenPaper={onOpenPaper} invalidLinkIds={invalid.map(link => link.id)} />}
  </div>;
}

function RegistrationCandidateCard({ link, confirmed, versions = [], busy, onConfirm, onReject, onAcquire, onIncorrect }) {
  const evidence = link.match_evidence || [];
  const evidenceLabel = item => item.kind === "datacite-related-identifier"
    ? `DataCite relation: ${item.relation_type || "typed relation"} · ${item.doi || ""}`
    : item.kind === "osf-papers-resource" ? `OSF papers resource names publication DOI ${item.doi || ""}`
      : item.kind === "paper-reference" ? `Reference surfaced from the paper${item.printed ? "" : " (link target or supplied reference)"}`
        : item.kind === "contributor-overlap" ? `Contributor overlap: ${(item.names || []).join(", ")}`
          : item.kind === "title-terms" ? `Shared title terms: ${(item.terms || []).join(", ")}`
            : item.kind === "date-order" ? `Registered ${item.registration_year}; paper published ${item.publication_year}`
              : item.kind.replaceAll("-", " ");
  const canAcquire = ["osf", "aspredicted", "manual-local"].includes(link.provider)
    && !["withdrawn", "unavailable", "embargoed"].includes(link.registration_status);
  const unavailableLink = ["withdrawn", "unavailable"].includes(link.link_status);
  const latestVersion = versions[0];
  return <div className="registration-candidate-card">
    <div className="registration-candidate-top">
      <span className={`registration-linkage ${link.linkage_class}`}>{confirmed ? "Linked by you" : link.linkage_label}</span>
      {link.registration_status && <span className="settings-sub">{link.registration_status}</span>}
    </div>
    <b>{link.title || `${link.provider} registration ${link.external_id}`}</b>
    <div className="settings-sub">{link.provider} · {link.registration_doi || link.external_id}{link.registered_at ? ` · ${link.registered_at.slice(0, 10)}` : ""}</div>
    {!!(link.contributors || []).length && <div className="settings-sub">{link.contributors.join(", ")}</div>}
    {!!evidence.length && <ul className="registration-candidate-evidence">{evidence.map((item, index) => <li key={index}>{evidenceLabel(item)}</li>)}</ul>}
    {["withdrawn", "unavailable", "embargoed"].includes(link.registration_status) && <div className="settings-note settings-note-err">
      The registry reports this registration as {link.registration_status}. Inspect its public metadata; Callosum will not try to download an unavailable artifact.
    </div>}
    {confirmed && latestVersion && <div className="registration-version-summary">
      <b>Stored locally</b>
      <div className="settings-sub">
        Version {latestVersion.content_hash.slice(0, 12)} · retrieved {new Date(latestVersion.retrieved_at).toLocaleDateString()}
        {versions.length > 1 ? ` · ${versions.length} preserved versions` : ""}
      </div>
      <div className="settings-sub">{isDemoMode()
        ? "The saved source version is independently identifiable; inspect its publication crosswalk below."
        : "Registration content is attached and can be inspected independently. No comparison has run yet."}</div>
    </div>}
    <div className="settings-actions">
      {link.canonical_url && <button className="axis-link" onClick={() => window.open(link.canonical_url, "_blank", "noopener")}>Open externally</button>}
      {!confirmed && <button className="btn btn-ghost" disabled={isDemoMode() || busy || unavailableLink || ["withdrawn", "unavailable", "embargoed"].includes(link.registration_status)} onClick={onConfirm}>Confirm link</button>}
      {!confirmed && <button className="btn-link" disabled={isDemoMode() || busy} onClick={onReject}>Dismiss</button>}
      {confirmed && canAcquire && <button className="btn btn-ghost" disabled={isDemoMode() || busy} onClick={onAcquire}>
        {latestVersion ? "Check for an updated version" : "Acquire registration"}
      </button>}
      {confirmed && <button className="btn-link" disabled={isDemoMode() || busy} onClick={onIncorrect}>Incorrect registration match</button>}
    </div>
    {confirmed && !latestVersion && !canAcquire && <div className="settings-sub">This provider has no bounded acquisition route. Attach a local registration PDF below.</div>}
    <div className="settings-sub registration-candidate-caveat">Candidate evidence supports inspection, not a claim that this is the paper's correct registration or that the paper followed it.</div>
  </div>;
}

function TransparencyCredit() {
  return (
    <div className="method-credit">
      <b>Detectors:</b> data &amp; code availability — ODDPub (Riedel et al. 2020); conflict-of-interest, funding &amp; registration indicators — rtransparent (Serghiou et al. 2021); preregistration — Nosek et al. (2018).{" "}
      <MethodCreditButton items={TRANSPARENCY_CSL} />
      <div className="method-credit-sub">A reading aid — a rule-based text detector, never a transparency score or a judgment of the authors.</div>
      <LakensCredit />
    </div>
  );
}

// inc 251: batch-detect transparency signals across the whole library, then jump to a review queue. The queues are
// "not detected — go look", never "papers that hide their data" (the A-A no-accusation boundary).
function TransparencyLibrary({ onReview, onRan }) {
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const start = async () => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/methods/transparency/run/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setRun({ status: "done", summary: d.summary }); if (onRan) onRan(); }
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Detection failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/methods/transparency/run", {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;
  return (
    <div className="statcheck-lib">
      <div className="settings-sub">Detect open-science disclosures across your whole library — local, no AI. Present disclosures become evidence-carrying marks in each paper's Review section; the review queues below list papers where the auditor <i>didn't</i> detect a disclosure in the text (it may still share elsewhere — a prompt to look, never a claim it hides anything).</div>
      <div className="settings-actions">
        <button className="btn btn-primary" disabled={run.status === "running" || isDemoMode()} onClick={start}
          title={isDemoMode() ? "Library-wide computation is unavailable in the static online demo." : undefined}>
          {run.status === "running" ? "Detecting…" : "Check all papers"}
        </button>
      </div>
      {isDemoMode() && <div className="settings-note">This saved library snapshot is fully inspectable. Running disclosure detection requires the local Callosum application.</div>}
      {run.status === "running" && <ProgressBar label="Detecting transparency signals…" managedBy="backend-job" />}
      {run.status === "error" && <div className="settings-note settings-note-err">Detection failed: {run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.total} paper{s.total === 1 ? "" : "s"} checked · <b>{s.with_disclosures}</b> with ≥1 disclosure detected.
          {onReview && <div className="transparency-queues">
            Review queues (not detected in the text — go look):{" "}
            {TRANSPARENCY_QUEUES.map((q, i) => (
              <React.Fragment key={q.key}>
                {i > 0 && " · "}
                <button className="btn-link" onClick={() => onReview(q.key)}>{q.label}</button>
              </React.Fragment>
            ))}
          </div>}
        </div>}
    </div>
  );
}

// The 7 review-queue signal keys (repository.SIGNAL_FILTERS). Registration is a `not-detected` queue (n/a papers are
// excluded upstream — precondition scoping); upon-request is the PRESENT case (a weaker-openness prompt, not an absence).
const TRANSPARENCY_QUEUES = [
  { key: "transparency-data-not-detected", label: "data" },
  { key: "transparency-code-not-detected", label: "code" },
  { key: "transparency-coi-not-detected", label: "COI" },
  { key: "transparency-funding-not-detected", label: "funding" },
  { key: "transparency-registration-not-detected", label: "registration" },
  { key: "transparency-preregistration-not-detected", label: "preregistration" },
  { key: "transparency-upon-request", label: "available upon request" },
];

function TransparencySection({ ctx, active }) {
  if (ctx.researchContext.kind === "manuscript") return (
    <div className="statcheck-section">
      <div className="settings-sub">Detect <b>reported open-science disclosures</b> in the current manuscript's
        exact primary-file checkpoint. Local, no AI, rule-based. Detected disclosures retain their evidence as facts;
        “not detected” is only detector coverage, never a score or claim that an artifact is absent.</div>
      <p className="eyebrow">This manuscript</p>
      <WipTransparencySection manuscript={ctx.researchContext.entity} ctx={ctx} />
      <TransparencyCredit />
    </div>
  );
  return (
    <div className="statcheck-section">
      <div className="settings-sub">Detect a paper's <b>open-science disclosures</b> — does it state where the data &amp; code live, declare conflicts of interest &amp; funding, and (for a trial/review) report a registration or preregistration? Local, no AI, rule-based. It surfaces what's <i>reported</i>, with the matched sentence — never a transparency score, and “not detected” never means the artifact is absent.</div>
      <p className="eyebrow">Whole library</p>
      <TransparencyLibrary onReview={ctx.onShowTransparencyReview} onRan={ctx.onTransparencyRan} />
      <p className="eyebrow">This paper</p>
      <TransparencyPaper paperId={ctx.selectedPaper} onOpenPaper={ctx.onOpenPaper}
        onOpenMetaPreregistration={ctx.onOpenMetaPreregistration} active={active} />
      <TransparencyCredit />
    </div>
  );
}

// Part of the Checklists 2x2-grid tab group (order 10 -> top-left) — 05_panes.jsx's registerPaneTab find-or-creates
// the "checklists" host regardless of which of its 4 sibling files loads first, as long as they agree on its
// metadata (label/paneId/order). `active` now arrives as a real prop (section open AND this tab selected) rather
// than derived from ctx.methodsOpen, which only ever reflected the open SECTION id, not the active tab within it.
registerPaneTab(
  { id: "checklists", label: "Checklists", paneId: "methods", order: 40 },
  {
    id: "transparency", label: "Transparency signals", order: 10, hideInReadOnly: true, demoInspectable: true,
    render: (ctx, active) => <TransparencySection ctx={ctx} active={active} />,
  },
);
