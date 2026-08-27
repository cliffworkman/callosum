// Explicit, inspectable feedback egress. The browser talks only to the local API; the Slack destination and
// credential exist exclusively in the separately deployed relay.

const FEEDBACK_COMPONENTS = [
  ["library", "Library"], ["pdf_viewer", "PDF viewer"], ["synthesis", "Synthesis"],
  ["discovery", "Discovery"], ["work", "Work"], ["settings", "Settings"],
  ["desktop_app", "Desktop app"], ["integrations", "Integrations"], ["other", "Other"],
];

function _feedbackId() {
  const bytes = new Uint8Array(16); window.crypto.getRandomValues(bytes);
  return "fb_" + [...bytes].map(value => value.toString(16).padStart(2, "0")).join("");
}
function _feedbackLine(value) { return String(value || "").trim().split(/\s+/).filter(Boolean).join(" "); }
function _feedbackText(value) {
  const lines = String(value || "").replace(/\r\n?/g, "\n").split("\n").map(_feedbackLine);
  const output = [];
  lines.forEach(line => { if (line || (output.length && output[output.length - 1])) output.push(line); });
  return output.join("\n").trim();
}
function _feedbackInitial() {
  return {
    report_type: "bug", title: "", description: "", component: "desktop_app", app_version: "",
    operating_system: "", installation_type: "browser", contact: "", contact_permitted: false,
    actual_behavior: "", expected_behavior: "", reproduction_steps_text: "", reproducibility: "sometimes",
    reporter_assessed_impact: "normal", requested_capability: "", problem_or_workflow: "",
    current_workaround: "", why_it_matters: "",
  };
}
function _feedbackPayload(draft, reportId, submittedAt) {
  const shared = {
    schema_version: 1, report_id: reportId, report_type: draft.report_type,
    title: _feedbackLine(draft.title), description: _feedbackText(draft.description), component: draft.component,
    app_version: _feedbackLine(draft.app_version), operating_system: _feedbackLine(draft.operating_system),
    installation_type: draft.installation_type,
    contact: draft.contact_permitted && _feedbackLine(draft.contact) ? _feedbackLine(draft.contact) : null,
    contact_permitted: !!draft.contact_permitted, submitted_at: submittedAt,
  };
  if (draft.report_type === "bug") return {
    ...shared, actual_behavior: _feedbackText(draft.actual_behavior), expected_behavior: _feedbackText(draft.expected_behavior),
    reproduction_steps: String(draft.reproduction_steps_text || "").split(/\r?\n/).map(_feedbackLine).filter(Boolean).slice(0, 12),
    reproducibility: draft.reproducibility, reporter_assessed_impact: draft.reporter_assessed_impact,
  };
  return {
    ...shared, requested_capability: _feedbackText(draft.requested_capability),
    problem_or_workflow: _feedbackText(draft.problem_or_workflow),
    current_workaround: _feedbackText(draft.current_workaround) || null,
    why_it_matters: _feedbackText(draft.why_it_matters),
  };
}
function _feedbackValidation(payload) {
  const missing = [];
  if (payload.title.length < 5) missing.push("a title of at least 5 characters");
  if (payload.description.length < 10) missing.push("a description of at least 10 characters");
  if (!payload.app_version) missing.push("the Callosum version");
  if (!payload.operating_system) missing.push("the operating system");
  if (payload.contact && !payload.contact_permitted) missing.push("permission to use the contact information");
  if (payload.report_type === "bug") {
    if (payload.actual_behavior.length < 10) missing.push("what happened (at least 10 characters)");
    if (payload.expected_behavior.length < 10) missing.push("what you expected (at least 10 characters)");
    if (!payload.reproduction_steps.length) missing.push("at least one reproduction step");
  } else {
    if (payload.requested_capability.length < 10) missing.push("the requested capability (at least 10 characters)");
    if (payload.problem_or_workflow.length < 10) missing.push("the problem or workflow (at least 10 characters)");
    if (payload.why_it_matters.length < 10) missing.push("why the request matters (at least 10 characters)");
  }
  return missing;
}

function FeedbackLauncher({ compact = false }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener("callosum:open-feedback", show);
    return () => window.removeEventListener("callosum:open-feedback", show);
  }, []);
  return (
    <>
      <button type="button" className="menubar-item feedback-menu-toggle" aria-haspopup="dialog"
        onClick={() => setOpen(true)} title="Report a bug or request a feature">
        {compact ? "Feedback" : "Feedback"}
      </button>
      {open && <FeedbackDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function FeedbackDialog({ onClose }) {
  const [draft, setDraft] = useState(_feedbackInitial);
  const [reportId, setReportId] = useState(_feedbackId);
  const [submittedAt] = useState(() => new Date().toISOString());
  const [capability, setCapability] = useState({ loading: true, enabled: false });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [copyMessage, setCopyMessage] = useState("");
  const dialogRef = useRef(null);
  const titleRef = useRef(null);
  const openerRef = useRef(document.activeElement);
  const submittingRef = useRef(false);

  useEffect(() => {
    let active = true;
    api("/feedback/capability").then(response => {
      if (!active) return;
      if (!response.ok) { setCapability({ loading: false, enabled: false }); return; }
      const data = response.data;
      setCapability({ loading: false, enabled: !!data.enabled });
      setReportId(data.report_id || _feedbackId());
      setDraft(previous => ({
        ...previous, app_version: previous.app_version || data.app_version || "unknown",
        operating_system: previous.operating_system || data.operating_system || navigator.platform || "Unknown",
        installation_type: data.installation_type || previous.installation_type,
      }));
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    titleRef.current?.focus();
    const onKey = event => {
      if (event.key === "Escape") {
        event.preventDefault(); event.stopImmediatePropagation();
        if (!submittingRef.current) onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll("button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, [tabindex]:not([tabindex='-1'])")];
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey, true);
    return () => { window.removeEventListener("keydown", onKey, true); openerRef.current?.focus?.(); };
  }, []);
  useEffect(() => { submittingRef.current = submitting; }, [submitting]);

  const change = (field, value) => {
    setDraft(previous => ({ ...previous, [field]: value }));
    setResult(null); setCopyMessage("");
  };
  const payload = _feedbackPayload(draft, reportId, submittedAt);
  const preview = JSON.stringify(payload, null, 2);
  const submit = async event => {
    event.preventDefault();
    const missing = _feedbackValidation(payload);
    if (missing.length) { setResult({ ok: false, message: "Please add " + missing.join(", ") + ".", validation: true }); return; }
    setSubmitting(true); setResult(null); setCopyMessage("");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    try {
      const response = await callosumFetch(API_BASE + "/feedback/reports", {
        method: "POST", headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: preview, signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (response.ok && data?.ok) setResult({ ok: true, reportId: data.report_id });
      else setResult({ ok: false, message: data?.error?.message || "The report was not submitted. Please retry or copy it." });
    } catch (error) {
      setResult({ ok: false, message: error?.name === "AbortError"
        ? "The feedback service did not respond in time. Nothing has been confirmed as submitted."
        : "The feedback service could not be reached. Nothing was submitted." });
    } finally {
      window.clearTimeout(timeout); setSubmitting(false);
    }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(preview); setCopyMessage("Exact report copied."); }
    catch (error) { setCopyMessage("Copy failed. Select the preview text and copy it manually."); }
  };
  const field = (name, label, options = {}) => (
    <label className="settings-field">
      <span className="settings-field-label">{label}{options.required ? " *" : ""}</span>
      {options.multiline
        ? <textarea className="settings-input feedback-textarea" value={draft[name]} maxLength={options.maxLength}
            rows={options.rows || 3} required={options.required} onChange={event => change(name, event.target.value)} />
        : <input ref={name === "title" ? titleRef : null} className="settings-input" value={draft[name]}
            maxLength={options.maxLength} required={options.required} disabled={options.disabled}
            onChange={event => change(name, event.target.value)} />}
    </label>
  );

  return ReactDOM.createPortal(
    <div className="axis-modal-overlay feedback-overlay" onMouseDown={event => { if (event.target === event.currentTarget && !submitting) onClose(); }}>
      <section ref={dialogRef} className="axis-modal feedback-modal" role="dialog" aria-modal="true"
        aria-labelledby="feedback-title" aria-describedby="feedback-privacy" aria-busy={submitting}>
        <div className="axis-modal-head feedback-head">
          <div><h2 id="feedback-title">Report a bug or request a feature</h2><p>Send an inspectable report to the Callosum team.</p></div>
          <button type="button" className="btn btn-icon" aria-label="Close feedback dialog" disabled={submitting} onClick={onClose}>×</button>
        </div>
        <p id="feedback-privacy" className="feedback-privacy">
          Submitting sends only the JSON preview below outside this device. Callosum does not attach PDFs, library or
          manuscript data, file paths, logs, prompts, clipboard contents, or machine identifiers.
        </p>
        <form onSubmit={submit} noValidate>
          <fieldset className="feedback-type-tabs">
            <legend>Report type</legend>
            <label><input type="radio" name="feedback-type" value="bug" checked={draft.report_type === "bug"}
              onChange={() => change("report_type", "bug")} /> Bug Report</label>
            <label><input type="radio" name="feedback-type" value="feature" checked={draft.report_type === "feature"}
              onChange={() => change("report_type", "feature")} /> Feature Request</label>
          </fieldset>
          <div className="feedback-grid">
            {field("title", "Title", { required: true, maxLength: 160 })}
            <label className="settings-field"><span className="settings-field-label">Relevant component or area *</span>
              <select className="settings-input" value={draft.component} onChange={event => change("component", event.target.value)}>
                {FEEDBACK_COMPONENTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          </div>
          {field("description", "Brief description", { required: true, multiline: true, maxLength: 4000 })}
          {draft.report_type === "bug" ? <>
            <div className="feedback-grid">
              {field("actual_behavior", "What happened", { required: true, multiline: true, maxLength: 4000 })}
              {field("expected_behavior", "What you expected", { required: true, multiline: true, maxLength: 4000 })}
            </div>
            {field("reproduction_steps_text", "Reproduction steps — one per line", { required: true, multiline: true, maxLength: 6011, rows: 4 })}
            <div className="feedback-grid">
              <label className="settings-field"><span className="settings-field-label">Is it reproducible?</span>
                <select className="settings-input" value={draft.reproducibility} onChange={event => change("reproducibility", event.target.value)}>
                  <option value="always">Always</option><option value="sometimes">Sometimes</option>
                  <option value="once">Happened Once</option><option value="not_yet">Not Tried Again</option>
                </select>
              </label>
              <label className="settings-field"><span className="settings-field-label">Reporter-assessed impact</span>
                <select className="settings-input" value={draft.reporter_assessed_impact} onChange={event => change("reporter_assessed_impact", event.target.value)}>
                  <option value="blocking">Blocking My Work</option><option value="major">Major Impact</option>
                  <option value="normal">Normal Impact</option><option value="minor">Minor Impact</option>
                </select>
              </label>
            </div>
          </> : <>
            {field("requested_capability", "Requested capability", { required: true, multiline: true, maxLength: 3000 })}
            {field("problem_or_workflow", "Problem or workflow it would address", { required: true, multiline: true, maxLength: 3000 })}
            <div className="feedback-grid">
              {field("current_workaround", "Current workaround (optional)", { multiline: true, maxLength: 2000 })}
              {field("why_it_matters", "Why this matters to your work", { required: true, multiline: true, maxLength: 3000 })}
            </div>
          </>}
          <details className="feedback-metadata" open>
            <summary>System information included in the report</summary>
            <div className="feedback-grid">
              {field("app_version", "Callosum version", { required: true, maxLength: 64 })}
              {field("operating_system", "Operating system", { required: true, maxLength: 128 })}
              <label className="settings-field"><span className="settings-field-label">Installation or packaging type</span>
                <select className="settings-input" value={draft.installation_type} onChange={event => change("installation_type", event.target.value)}>
                  <option value="tauri">Tauri Desktop</option><option value="browser">Browser</option>
                  <option value="source">Source Checkout</option><option value="other">Other</option>
                </select>
              </label>
            </div>
            <div className="feedback-readonly-meta">Report ID: <code>{reportId}</code> · Created: <code>{submittedAt}</code></div>
          </details>
          <div className="feedback-contact">
            <label><input type="checkbox" checked={draft.contact_permitted}
              onChange={event => change("contact_permitted", event.target.checked)} /> The Callosum team may contact me about this report</label>
            {field("contact", "Optional email or other contact information", { maxLength: 320, disabled: !draft.contact_permitted })}
          </div>
          <details className="feedback-preview" open>
            <summary>Exact transmission preview</summary>
            <pre tabIndex="0">{preview}</pre>
          </details>
          {capability.loading && <p className="feedback-state" role="status">Checking feedback availability…</p>}
          {!capability.loading && !capability.enabled && <p className="feedback-state unavailable" role="status">
            Feedback submission is unavailable in this installation. Your report has not left this device; you can still copy it.
          </p>}
          {submitting && <StatusScope nav={{ modal: "feedback" }}><ProgressBar label="Submitting feedback…" /></StatusScope>}
          {result && <p className={"feedback-state " + (result.ok ? "success" : "error")} role="status">
            {result.ok ? <>Submitted successfully. Report ID: <code>{result.reportId}</code></> : result.message}
          </p>}
          {copyMessage && <p className="feedback-state" role="status">{copyMessage}</p>}
          <div className="settings-actions feedback-actions">
            <button type="button" className="btn btn-ghost" onClick={copy}>Copy Exact Report</button>
            <span className="feedback-action-spacer" />
            <button type="button" className="btn btn-ghost" disabled={submitting} onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting || !capability.enabled || result?.ok}>
              {submitting ? "Submitting…" : result?.ok ? "Submitted" : result && !result.ok ? "Retry submission" : "Submit report"}
            </button>
          </div>
        </form>
      </section>
    </div>, document.body
  );
}
