// Settings → Local maintenance (split from 35_settings.jsx, backlog #40 -- adding the TOP Factor mirror row
// pushed that file over the 600-line cap; extracted whole, matching the inc-256 35b_providers.jsx precedent).
// Hoists across the shared IIFE, so SettingsModal (35_settings.jsx) calls it directly, unchanged.
// GrobidSettings (backlog #30 Stage 2, task 11) lives in this same file -- a self-hosted opt-in service, the
// same "local maintenance" territory as the mirrors above -- and is called separately from 35_settings.jsx.

function LocalMaintenanceSettings({ onRetractionRan }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const repairSummaryCache = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/settings/repair-summary-cache", {});
    setBusy(false);
    if (r.ok) setMsg(`Scanned ${r.data.scanned} summary cache row${r.data.scanned === 1 ? "" : "s"}; removed ${r.data.removed} malformed row${r.data.removed === 1 ? "" : "s"}.`);
    else setMsg("Couldn't repair summary cache: " + (r.error || "error"));
  };

  // Retraction Watch DB mirror (inc 132; moved from the old left-pane Review accordion — the library-wide
  // retraction check itself lives as a header button now, `10b_libmenus.jsx`'s RetractionCheckButton; this is
  // just the "how fresh is the local mirror" admin view + a refresh-only action).
  const [db, setDb] = useState(null);  // { count, retrieved_at } | null
  const [dbRun, setDbRun] = useState({ status: "idle" });
  const loadDb = () => api("/methods/retraction/database").then(r => { if (r.ok) setDb(r.data); });
  useEffect(() => { loadDb(); }, []);
  const refreshDb = async () => {
    setDbRun({ status: "running" });
    const poll = (jobId) => api(`/methods/retraction/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setDbRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setDbRun({ status: "done" }); loadDb(); if (onRetractionRan) onRetractionRan(); }
      else if (d.status === "error") setDbRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/retraction/database/refresh", {});
    if (!r.ok) { setDbRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const ageDays = db && db.retrieved_at ? Math.floor((Date.now() - new Date(db.retrieved_at).getTime()) / 86400000) : null;
  const stale = ageDays != null && ageDays > 30;

  // Opt-in cadence auto-refresh (backlog #31): default off, decoupled via localStorage — 03_library.jsx's
  // triggerRetractionAutoRefresh reads the same key on launch/focus. Mirrors Feed's own opt-in auto-refresh
  // toggle (30e_feed.jsx) — visible + inspectable, never a silent standing timer (Principles gate, rule #9).
  const [autoRefresh, setAutoRefresh] = useState(() => {
    try { return localStorage.getItem("callosum.retractionAutoRefresh") === "1"; } catch (e) { return false; }
  });
  const toggleAutoRefresh = () => {
    setAutoRefresh(v => {
      const next = !v;
      try { localStorage.setItem("callosum.retractionAutoRefresh", next ? "1" : "0"); } catch (e) { /* ignore */ }
      return next;
    });
  };

  // TOP Factor mirror (backlog #40) — a periodically-updated public snapshot (no live query API exists) that
  // feeds Where-to-submit's TOP Factor fact once downloaded. Mirrors the Retraction Watch block above exactly,
  // minus the contact-email requirement (no auth needed).
  const [tf, setTf] = useState(null);  // { count, retrieved_at } | null
  const [tfRun, setTfRun] = useState({ status: "idle" });
  const loadTf = () => api("/methods/top-factor/database").then(r => { if (r.ok) setTf(r.data); });
  useEffect(() => { loadTf(); }, []);
  const refreshTf = async () => {
    setTfRun({ status: "running" });
    const poll = (jobId) => api(`/methods/top-factor/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setTfRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setTfRun({ status: "done" }); loadTf(); }
      else if (d.status === "error") setTfRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/top-factor/database/refresh", {});
    if (!r.ok) { setTfRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  // AJOL mirror (backlog #40, inc 451) — a THIRD-PARTY compiled snapshot (not an AJOL-official feed), dated
  // to a fixed vintage (snapshot_date) that a re-download can never change -- "Download database" (never
  // "Refresh") is the honest verb here; TOP Factor/Retraction Watch are periodically republished by their own
  // source org, this is a one-time academic dataset with no such guarantee.
  const [ajol, setAjol] = useState(null);  // { count, retrieved_at, snapshot_date } | null
  const [ajolRun, setAjolRun] = useState({ status: "idle" });
  const loadAjol = () => api("/methods/ajol/database").then(r => { if (r.ok) setAjol(r.data); });
  useEffect(() => { loadAjol(); }, []);
  const downloadAjol = async () => {
    setAjolRun({ status: "running" });
    const poll = (jobId) => api(`/methods/ajol/database/refresh/${jobId}`).then(r => {
      if (!r.ok) { setAjolRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setAjolRun({ status: "done" }); loadAjol(); }
      else if (d.status === "error") setAjolRun({ status: "error", error: d.detail || "Download failed." });
      else setTimeout(() => poll(jobId), 2000);
    });
    const r = await apiPost("/methods/ajol/database/refresh", {});
    if (!r.ok) { setAjolRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };

  return (
    <>
      <p className="eyebrow">Local maintenance</p>
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">Retraction Watch database</span>
          <button className="btn btn-ghost" disabled={dbRun.status === "running"} onClick={refreshDb}>
            {dbRun.status === "running" ? "Downloading…" : "Refresh database"}
          </button>
        </div>
        <span className="settings-sub">
          The local mirror of the Retraction Watch database (Crossref-hosted, CC0) — the richest source
          (reason/date/notice) the library's retraction check can draw on.
        </span>
        <span className="method-credit-sub">
          Courtesy of <a href="https://retractionwatch.com/" target="_blank" rel="noopener noreferrer">Retraction
          Watch</a>, a project of The Center for Scientific Integrity (Ivan Oransky &amp; Adam Marcus), mirrored via
          Crossref's <a href="https://api.labs.crossref.org/data/retractionwatch" target="_blank" rel="noopener noreferrer">public
          CC0 dataset</a>. No single canonical paper describes the database itself — credited by acknowledgment, not
          fabricated as a citation.
        </span>
        <div className={"settings-note" + (stale ? " settings-note-err" : "")}>
          {db && db.count > 0
            ? `${db.count.toLocaleString()} records${db.retrieved_at ? " · as of " + db.retrieved_at.slice(0, 10) : ""}`
            : "Not downloaded — refresh to enable the richest source"}
          {stale && ` · ${ageDays} days old — refresh recommended`}
        </div>
        <label className="auto-refresh-toggle" title="When enabled, refreshes the mirror and re-checks your library automatically on launch (and when you switch back to Callosum) if the mirror is more than 30 days old.">
          <input type="checkbox" checked={autoRefresh} onChange={toggleAutoRefresh} /> Auto-refresh when stale (checked on launch)
        </label>
      </div>
      {dbRun.status === "error" && <div className="settings-note settings-note-err">{dbRun.error}</div>}
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">TOP Factor database</span>
          <button className="btn btn-ghost" disabled={tfRun.status === "running"} onClick={refreshTf}>
            {tfRun.status === "running" ? "Downloading…" : "Refresh database"}
          </button>
        </div>
        <span className="settings-sub">
          The Center for Open Science's per-journal transparency/openness rubric — a periodically-updated public
          snapshot (no live query API exists) that feeds Discover → Journals' TOP Factor fact once downloaded.
        </span>
        <div className="settings-note">
          {tf && tf.count > 0
            ? `${tf.count.toLocaleString()} journals${tf.retrieved_at ? " · as of " + tf.retrieved_at.slice(0, 10) : ""}`
            : "Not downloaded — refresh to include TOP Factor in Where-to-submit results"}
        </div>
      </div>
      {tfRun.status === "error" && <div className="settings-note settings-note-err">{tfRun.error}</div>}
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">AJOL database</span>
          <button className="btn btn-ghost" disabled={ajolRun.status === "running"} onClick={downloadAjol}>
            {ajolRun.status === "running" ? "Downloading…" : "Download database"}
          </button>
        </div>
        <span className="settings-sub">
          A third-party, CC-BY-4.0 compiled snapshot of African Journals Online (AJOL) journal metadata — not an
          AJOL-official feed. A one-time academic dataset, not a periodically-updated source: downloading again
          will not fetch newer data than the {ajol ? ajol.snapshot_date : "dataset's"} snapshot, and it may not
          reflect journals AJOL has added, removed, or reclassified since.
        </span>
        <div className="settings-note">
          {ajol && ajol.count > 0
            ? `${ajol.count.toLocaleString()} journals · ${ajol.snapshot_date} snapshot, downloaded ${ajol.retrieved_at ? ajol.retrieved_at.slice(0, 10) : "?"}`
            : "Not downloaded — download to include AJOL in Where-to-submit results"}
        </div>
      </div>
      {ajolRun.status === "error" && <div className="settings-note settings-note-err">{ajolRun.error}</div>}
      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">Synthesis cache</span>
          <button className="btn btn-ghost" disabled={busy} onClick={repairSummaryCache}>
            {busy ? "Scanning…" : "Repair synthesis cache"}
          </button>
        </div>
        <span className="settings-sub">
          Scans cached AI draft summaries and removes only malformed cache rows. Saved syntheses, verified citations, chunks, and evidence records are not changed.
        </span>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </>
  );
}

// GROBID document structure (backlog #30 Stage 2, task 11) -- mirrors 35b_providers.jsx's own Local-provider
// endpoint field exactly (fetch GET /grobid/status on mount, a plain URL text input + Save via POST
// /grobid/settings, then a Test connection button against POST /grobid/test-connection with the same inline
// settings-note/settings-note-err result convention SharingIdentityPanel and ProviderRow both already use).
// GROBID is a separately-run, opt-in Docker service (never bundled) that extracts a paper's real document
// structure (sections/headings) more accurately than callosum's own local heuristic; task 10 already prefers
// GROBID's mapped data over that heuristic once present. Sending a PDF to a non-loopback GROBID URL is
// egress-gated exactly like a custom AI provider endpoint (invariant #3) -- a refused parse surfaces that 403
// detail verbatim through the shared apiPost error path, nothing new to build here.
function GrobidSettings() {
  const [url, setUrl] = useState("");       // the STORED url, from GET /grobid/status
  const [urlInput, setUrlInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgErr, setMsgErr] = useState(false);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState(null);   // { ok, detail } | null
  // backlog #58: a silent, automatic reachability check (distinct from the manual "Test" button's own `test`
  // state above) -- decides which Docker-lifecycle UI branch to show, without rendering its own message.
  const [autoReachable, setAutoReachable] = useState(null);
  const [dockerStatus, setDockerStatus] = useState(null);  // { docker_installed, docker_daemon_running, container_state, managed_url } | null
  const [install, setInstall] = useState({ status: "idle" });  // idle | running | done | error
  const [stopping, setStopping] = useState(false);

  const load = () => api("/grobid/status").then(r => {
    if (r.ok) {
      setUrl(r.data.url || "");
      setUrlInput(r.data.url || "");
      setAutoReachable(null);
      if (r.data.url) apiPost("/grobid/test-connection", {}).then(t => setAutoReachable(t.ok && t.data.ok));
    }
  });
  const loadDockerStatus = () => api("/grobid/docker/status").then(r => { if (r.ok) setDockerStatus(r.data); });
  useEffect(() => { load(); loadDockerStatus(); }, []);

  const startInstall = async () => {
    setInstall({ status: "running" });
    const poll = (jobId) => api(`/grobid/docker/install/${jobId}`).then(r => {
      if (!r.ok) { setInstall({ status: "error", detail: r.error }); return; }
      const d = r.data;
      if (d.status === "done") { setInstall({ status: "done" }); load(); loadDockerStatus(); }
      else if (d.status === "error") setInstall({ status: "error", detail: d.detail || "Install failed." });
      else setTimeout(() => poll(jobId), 1500);
    });
    const r = await apiPost("/grobid/docker/install", {});
    if (!r.ok) { setInstall({ status: "error", detail: r.error }); return; }
    poll(r.data.job_id);
  };

  const stopManaged = async () => {
    setStopping(true);
    const r = await apiPost("/grobid/docker/stop", {});
    setStopping(false);
    // Re-check reachability too (not just Docker's own container_state) -- the stopped/removed container was
    // very likely the thing `autoReachable` last verified was working; leaving it stale here would keep
    // showing the quiet "already configured" branch for a URL that's now genuinely unreachable (caught live).
    if (r.ok) { setInstall({ status: "idle" }); load(); loadDockerStatus(); }
  };

  const save = async () => {
    setBusy(true); setMsg(""); setTest(null);
    const r = await apiPost("/grobid/settings", { url: urlInput.trim() || null });
    setBusy(false);
    if (r.ok) { setUrl(r.data.url || ""); setMsgErr(false); setMsg(r.data.url ? "Saved." : "Cleared."); }
    else { setMsgErr(true); setMsg("Couldn't save: " + (r.error || "error")); }
  };

  const testConnection = async () => {
    setTesting(true); setTest(null);
    const r = await apiPost("/grobid/test-connection", {});
    setTesting(false);
    setTest(r.ok ? r.data : { ok: false, detail: r.error || "Test failed." });
  };

  // Bulk "Parse structure for library" -- POST /grobid/library/parse, a real backend JobStore (grobid_parse_jobs,
  // already registered in JOB_NAV_DEFAULTS/JOB_LABELS/JOB_COMPUTE_KINDS by task 9, status.py) -- managedBy=
  // "backend-job" so this ProgressBar doesn't ALSO register a duplicate client-side Status row (invariant #5 --
  // the backend job is already the one source of truth for this operation's Status entry).
  const [run, setRun] = useState({ status: "idle" });  // idle | running | done | error
  const runLibrary = async (onlyUnparsed) => {
    setRun({ status: "running" });
    const poll = (jobId) => api(`/grobid/library/parse/${jobId}`).then(r => {
      if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
      const d = r.data;
      if (d.status === "done") setRun({ status: "done", summary: d.summary });
      else if (d.status === "error") setRun({ status: "error", error: d.detail || "Parse failed." });
      else { setRun({ status: "running", progress: d.progress }); setTimeout(() => poll(jobId), 1500); }
    });
    const r = await apiPost("/grobid/library/parse", onlyUnparsed ? { only_unparsed: true } : {});
    if (!r.ok) { setRun({ status: "error", error: r.error }); return; }
    poll(r.data.job_id);
  };
  const s = run.summary;

  return (
    <>
      <p className="eyebrow">GROBID document structure</p>
      <div className="settings-field">
        <label className="settings-field-label">GROBID server URL
          <span className="settings-sub">
            A separately-run, opt-in GROBID Docker service — parses a PDF's real document structure
            (sections/headings) more accurately than callosum's own local heuristic. Not bundled; run your own
            (e.g. <code>docker run --rm -p 8070:8070 lfoppiano/grobid:latest</code>) and point callosum at it. A
            loopback URL needs no consent; a remote one is gated by the same "Allow AI features" egress toggle
            as a custom AI provider.
          </span>
        </label>
        <div className="settings-keyrow">
          <input className="settings-input" placeholder="http://127.0.0.1:8070" value={urlInput}
            onChange={e => setUrlInput(e.target.value)} />
          <button className="btn btn-ghost" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</button>
          {url &&
            <button className="btn btn-ghost" disabled={testing} onClick={testConnection}>{testing ? "Testing…" : "Test"}</button>}
        </div>
        {test && <div className={"settings-note" + (test.ok ? "" : " settings-note-err")}>{test.detail}</div>}
        {msg && <div className={"settings-note" + (msgErr ? " settings-note-err" : "")}>{msg}</div>}
      </div>

      {/* backlog #58: let callosum drive Docker directly instead of requiring the reader to already know
          Docker CLI commands. Not bundled -- Docker Desktop itself remains a one-time external prerequisite;
          this only detects it and orchestrates the container. */}
      <GrobidDockerLifecycle
        url={url} autoReachable={autoReachable} dockerStatus={dockerStatus}
        install={install} stopping={stopping} onInstall={startInstall} onStop={stopManaged}
      />

      <div className="settings-field">
        <div className="settings-row settings-maintenance-action">
          <span className="settings-field-label">Parse structure for library</span>
          <div className="settings-keyrow">
            <button className="btn btn-ghost" disabled={!url || run.status === "running"} onClick={() => runLibrary(false)}>
              {run.status === "running" ? "Parsing…" : "Parse all papers"}
            </button>
            <button className="btn btn-ghost" disabled={!url || run.status === "running"} onClick={() => runLibrary(true)}
              title="Skip papers that already have a GROBID-mapped section from a prior run.">
              {run.status === "running" ? "Parsing…" : "Parse unparsed only"}
            </button>
          </div>
        </div>
        <span className="settings-sub">
          Runs GROBID structure parsing across every paper with a local PDF — the same per-paper action as the
          "Parse document structure…" button in a paper's Details, just for the whole library at once.
          "Parse unparsed only" skips papers a prior run already mapped.
        </span>
      </div>
      {run.status === "running" && <ProgressBar label="Parsing document structure…" progress={run.progress} managedBy="backend-job" />}
      {run.status === "error" && <div className="settings-note settings-note-err">{run.error}</div>}
      {run.status === "done" && s &&
        <div className="settings-note">
          {s.papers_parsed} paper{s.papers_parsed === 1 ? "" : "s"} parsed
          {s.papers_skipped ? ` · ${s.papers_skipped} skipped` : ""} · {s.sections_found} section{s.sections_found === 1 ? "" : "s"} found · {s.chunks_mapped} chunk{s.chunks_mapped === 1 ? "" : "s"} mapped.
        </div>}
    </>
  );
}

const GROBID_DOWNLOAD_LABEL = "~500MB download";

// backlog #58: don't require the reader to already know Docker. `dockerStatus` (GET /grobid/docker/status)
// decides the branch: not installed -> guide to Docker's own installer (never auto-installed, a deliberate
// scope boundary); installed + no callosum-managed container -> a primary Install action, explicit about the
// download before the click (transparency, not an egress-gate dialog -- pulling callosum's own tooling
// dependency from Docker Hub sends no library content anywhere, unlike the AI-egress gate above, which is why
// this reuses none of that consent machinery); already running -> Stop. A working, already-configured GROBID
// (the common case once this has been used once) stays the quiet, secondary path -- never nags to replace a
// setup that already works.
function GrobidDockerLifecycle({ url, autoReachable, dockerStatus, install, stopping, onInstall, onStop }) {
  if (!dockerStatus) return null;
  const { docker_installed, docker_daemon_running, container_state } = dockerStatus;
  const hasWorkingUrl = !!url && autoReachable === true;
  const weManageIt = container_state === "running";

  if (hasWorkingUrl && !weManageIt) {
    // A working GROBID is already configured (today's existing state) -- don't push a replacement.
    return docker_installed && docker_daemon_running
      ? <div className="settings-note">
          Or let callosum manage a local GROBID instance for you instead —{" "}
          <button className="btn-link" disabled={install.status === "running"} onClick={onInstall}>
            {install.status === "running" ? "Installing…" : `install & start (${GROBID_DOWNLOAD_LABEL})`}
          </button>
        </div>
      : null;
  }

  return (
    <div className="settings-field">
      <span className="settings-field-label">Run GROBID for me</span>
      {!docker_installed &&
        <div className="settings-note">
          This needs Docker, which isn't installed on this machine.{" "}
          <a href="https://www.docker.com/products/docker-desktop/" target="_blank" rel="noopener noreferrer">
            Install Docker Desktop
          </a>, then reopen this page. Callosum never installs Docker itself.
        </div>}
      {docker_installed && !docker_daemon_running &&
        <div className="settings-note">Docker is installed but not running. Start Docker Desktop, then reopen this page.</div>}
      {docker_installed && docker_daemon_running && !weManageIt &&
        <>
          <span className="settings-sub">
            Downloads and runs GROBID's own lightweight, CPU-only Docker image ({GROBID_DOWNLOAD_LABEL}) and points
            callosum at it — no Docker commands to type. Docker Desktop must already be installed (above).
          </span>
          <button className="btn btn-ghost" disabled={install.status === "running"} onClick={onInstall}>
            {install.status === "running" ? "Installing…" : `Install & Start GROBID (${GROBID_DOWNLOAD_LABEL})`}
          </button>
        </>}
      {weManageIt &&
        <div className="settings-keyrow">
          <span className="settings-note">Running (managed by callosum).</span>
          <button className="btn btn-ghost" disabled={stopping} onClick={onStop}>{stopping ? "Stopping…" : "Stop"}</button>
        </div>}
      {install.status === "running" && <ProgressBar label="Installing GROBID (this can take a few minutes)…" managedBy="backend-job" />}
      {install.status === "error" && <div className="settings-note settings-note-err">{install.detail}</div>}
    </div>
  );
}

// LibreOffice plugin settings (split from 35_settings.jsx, backlog #33/#34 phase 1 — the "Point LibreOffice at
// this instance" button pushed that file over the 600-line cap; moved whole, matching this file's own existing
// split precedent). Hoists across the shared IIFE, so 35_settings.jsx calls it directly, unchanged.
function LibreOfficeSettings() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [urlBusy, setUrlBusy] = useState(false);
  const [urlMsg, setUrlMsg] = useState("");
  const install = async () => {
    setBusy(true); setMsg("");
    const r = await apiPost("/integrations/libreoffice/install", {});
    setBusy(false);
    setMsg(r.ok ? (r.data.detail || "Opening LibreOffice…") : ("Couldn't install: " + (r.error || "error")));
  };
  // backlog #33/#34 phase 1: closes the loop instead of asking the user to copy a port into Writer's own
  // Callosum → Server URL… dialog — the packaged app's port isn't fixed across launches.
  const pointAtThisInstance = async () => {
    setUrlBusy(true); setUrlMsg("");
    const r = await apiPost("/integrations/libreoffice/set-server-url", {});
    setUrlBusy(false);
    setUrlMsg(r.ok ? r.data.detail : ("Couldn't set it: " + (r.error || "error")));
  };
  return (
    <>
      <p className="eyebrow">LibreOffice plugin</p>
      <button className="btn btn-ghost settings-integration-action" disabled={busy} onClick={install}>{busy ? "Installing…" : "Install Plugin"}</button>
      <div className="settings-sub">
        Installs the Callosum extension — a <b>Callosum</b> menu + toolbar in Writer (Add citation, Suggest, Refresh, Style, Flatten). Click Install, confirm in LibreOffice's Extension Manager, then restart Writer. The app must be running for the plugin to reach it. <button className="btn-link" onClick={() => downloadAsset("/integrations/libreoffice/plugin.oxt", "callosum.oxt")}>Download .oxt.</button>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
      <button className="btn btn-ghost settings-integration-action" disabled={urlBusy} onClick={pointAtThisInstance}>{urlBusy ? "Setting…" : "Point LibreOffice at This Instance"}</button>
      <div className="settings-sub">Only needed if the plugin can't reach Callosum (e.g. after a restart picked a different port).</div>
      {urlMsg && <div className="settings-note">{urlMsg}</div>}
    </>
  );
}

// Server address (backlog #33/#34, packaged-desktop-app phase 1) — the packaged app spawns its backend on a
// per-launch port (stable across ordinary restarts once persisted, but not guaranteed), which external tools
// have no other way to discover: LibreOffice's own sidecar config (Server URL… dialog), a Word HTTPS companion,
// or a Google Docs tunnel's local target all need this number. `window.location.origin` is exactly it, for
// free, since this page is served from that same origin. Shown once above the Integrations grid.
function ServerAddressSettings() {
  const [copied, setCopied] = useState(false);
  const base = window.location.origin;
  const copy = () => {
    navigator.clipboard.writeText(base).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
  };
  return (
    <div className="settings-keyrow">
      <span className="settings-note">Server address: <code>{base}</code></span>
      <button className="btn btn-ghost" onClick={copy}>{copied ? "Copied!" : "Copy"}</button>
    </div>
  );
}
