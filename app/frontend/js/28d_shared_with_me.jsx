// "Shared with me" modal (SP4c, backlog #15) — the recipient side of live sharing. Lists shares addressed to
// you (sender + when, no content — no passphrase needed to see this list). Per row: Import (passphrase-gated,
// decrypts + merges via the same background-job path POST /library/bundle/import already uses), Dismiss
// (local-only, no passphrase, never touches ciphertext), or Block sender (SP4d — local-only; filters this and
// every future share from that sender, shown with a brief in-place confirmation rather than silent removal). A
// row whose sender revoked it (SP4d) shows "· Withdrawn by sender" and hides Import (Dismiss + Block sender
// remain). Mirrors 28b_bundle.jsx's BundleImportModal structurally.

function SharedWithMeModal({ onClose, onImported, onOpenSettings }) {
  return (
    <div className="axis-modal-overlay" onClick={onClose}>
      <div className="axis-modal" onClick={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Shared with me</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Papers a collaborator end-to-end encrypted and sent you — metadata + tags + annotations, <b>no PDFs</b>.
          Only you can decrypt one, with your own sync passphrase. Before importing, confirm the sender's identity
          if you haven't already — a share's sender id alone isn't fingerprint-verified to you the way SP4a's
          lookup verifies a recipient to a sender.{" "}
          {onOpenSettings && <button className="btn-link" onClick={onOpenSettings}>Verify identities in Sync settings →</button>}
        </div>
        <SharedWithMeList onImported={onImported} />
        <div className="axis-form-actions">
          <button className="axis-link" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function SharedWithMeList({ onImported }) {
  const [state, setState] = useState({ status: "loading" });  // loading | ready | error
  const [rows, setRows] = useState([]);

  const load = () => {
    setState({ status: "loading" });
    api("/sync/shares").then(r => {
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setRows(r.data);
      setState({ status: "ready" });
    });
  };
  useEffect(load, []);

  const dismiss = async (id) => {
    const r = await apiPost(`/sync/shares/${id}/dismiss`, {});
    if (r.ok) setRows(prev => prev.map(row => row.id === id ? { ...row, status: "dismissed" } : row));
  };

  const block = async (sub) => {
    const r = await apiPost("/sync/blocked-senders", { sub });
    // Keep the row(s) visible with a brief in-place confirmation rather than vanishing silently — blocking a
    // sender affects every one of their pending shares, not just the one clicked.
    if (r.ok) setRows(prev => prev.map(row => row.sender_sub === sub ? { ...row, blockedNow: true } : row));
  };

  if (state.status === "loading") return <div className="axis-hint">Checking for shares…</div>;
  if (state.status === "error") return <div className="axis-err">Couldn't check for shares: {state.error}</div>;

  const blocked = rows.filter(r => !r.status && r.blockedNow);
  const pending = rows.filter(r => !r.status && !r.blockedNow);
  const handled = rows.filter(r => r.status);

  return (
    <>
      {pending.length === 0 && handled.length === 0 && blocked.length === 0 &&
        <div className="axis-hint">No one has shared anything with you yet.</div>}
      {blocked.map(row => (
        <div className="gap-row" key={row.id}>
          <div className="gap-row-info">
            <div className="gap-row-title">from {row.sender_sub}</div>
            <div className="gap-row-meta">Blocked. Manage blocked senders in Sync settings.</div>
          </div>
        </div>
      ))}
      {pending.map(row => (
        <SharedRow key={row.id} row={row} onDismiss={() => dismiss(row.id)} onBlock={() => block(row.sender_sub)}
          onImported={() => { setRows(prev => prev.map(r => r.id === row.id ? { ...r, status: "imported" } : r)); onImported && onImported(); }} />
      ))}
      {handled.length > 0 &&
        <div className="axis-hint">{handled.length} already handled (imported or dismissed).</div>}
    </>
  );
}

function SharedRow({ row, onDismiss, onImported, onBlock }) {
  const [importing, setImporting] = useState(false);   // reveal the passphrase field
  const [passphrase, setPassphrase] = useState("");
  const [imp, setImp] = useState({ status: "idle" });   // idle | running | done | error

  const poll = (jobId) => api(`/sync/shares/${row.id}/import/${jobId}`).then(r => {
    if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
    const d = r.data;
    if (d.status === "done") { setImp({ status: "done", summary: d.summary }); onImported(); }
    else if (d.status === "error") setImp({ status: "error", error: d.detail || "Import failed." });
    else { setImp({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
  });

  const run = () => {
    if (!passphrase) return;
    setImp({ status: "running" });
    apiPost(`/sync/shares/${row.id}/import`, { passphrase }).then(r => {
      setPassphrase("");
      if (!r.ok) { setImp({ status: "error", error: r.error }); return; }
      poll(r.data.job_id);
    });
  };

  const s = imp.summary;
  const done = imp.status === "done" && s;
  return (
    <div className="gap-row">
      <div className="gap-row-info">
        <div className="gap-row-title">from {row.sender_sub}</div>
        <div className="gap-row-meta">
          {fmtDateTime(new Date(row.created_at))}{row.revoked ? " · Withdrawn by sender" : ""}
        </div>
        {done &&
          <div className="gap-row-meta">
            <b>{s.papers_created}</b> new · {s.papers_merged} merged
            {s.tags_applied ? ` · ${s.tags_applied} tags` : ""}
            {s.annotations_added ? ` · ${s.annotations_added} highlights` : ""}
            {s.syntheses_imported ? ` · ${s.syntheses_imported} syntheses` : ""}
            {s.skipped ? ` · ${s.skipped} skipped` : ""}
          </div>}
        {importing && imp.status !== "running" && !done &&
          <div className="settings-keyrow">
            <input className="settings-input" type="password" autoComplete="off" placeholder="Your sync passphrase"
              value={passphrase} onChange={e => setPassphrase(e.target.value)} />
            <button className="btn btn-primary" disabled={!passphrase} onClick={run}>Decrypt &amp; import</button>
          </div>}
        {imp.status === "running" && <ProgressBar label="Decrypting + merging…" progress={imp.progress} managedBy="backend-job" />}
        {imp.status === "error" && <div className="axis-err">Couldn't import: {imp.error}</div>}
      </div>
      {!done &&
        <div className="gap-row-actions">
          {!importing && imp.status !== "running" &&
            <>
              {!row.revoked && <button className="axis-link" onClick={() => setImporting(true)}>Import</button>}
              <button className="axis-link" onClick={onDismiss}>Dismiss</button>
              <button className="axis-link axis-danger" onClick={onBlock}>Block Sender</button>
            </>}
        </div>}
    </div>
  );
}
