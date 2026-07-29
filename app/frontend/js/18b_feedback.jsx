// In-app bug report / feature request (inc 413) — the "Feedback" item in the menu bar's right-aligned
// utilities, beside Help / Settings / Status.
//
// It is a MODAL, not a utility workspace like Help and Settings, and that is deliberate: a bug report is about
// the screen you are looking at. Navigating to a Feedback *workspace* would replace that screen — discarding
// the context being reported and putting the reporter itself in any screenshot taken afterwards. So it rides
// the same MenuBar exception StatusMenu does (04b_workspaces.jsx / 04c_status.jsx, inc 406) and overlays.
//
// The report is assembled ON THIS MACHINE: the backend writes report.md (+ screenshot) under
// ~/.callosum/feedback/ and hands back a prefilled mailto: draft. callosum never transmits it — the user's
// own mail client does, with the full text visible in the draft first. The diagnostics block is fetched
// BEFORE submitting and rendered in the form, so nothing is attached that the user hasn't read (the
// inspectability commitment, applied to the app's own telemetry surface).
//
// Screenshots come from getDisplayMedia (the browser's own picker — no CDN library, and it captures the
// pdf.js CANVAS correctly, which a DOM-to-image renderer would not) or from paste / drag-drop of a file
// the user grabbed with the OS screenshot tool.

const FEEDBACK_MAX_IMAGE_EDGE = 1600;     // downscale before encoding — the API caps a decoded image at 5 MB
const FEEDBACK_MAX_IMAGE_BYTES = 5 * 1024 * 1024;

// Browser-side half of the diagnostics table. Deliberately narrow: environment, not content.
function feedbackClientDiagnostics(extra) {
  const d = {
    user_agent: navigator.userAgent || "",
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    screen: `${window.screen ? window.screen.width : "?"}x${window.screen ? window.screen.height : "?"} @${window.devicePixelRatio || 1}x`,
    language: navigator.language || "",
    theme: document.documentElement.getAttribute("data-theme") || "light",
    page: window.location.pathname + window.location.search,
  };
  return Object.assign(d, extra || {});
}

// Draw an <img>/<video> frame to a canvas, downscaled to FEEDBACK_MAX_IMAGE_EDGE, and encode. PNG keeps
// text crisp; if the result is over the API's cap we fall back to JPEG rather than failing the submit.
function _encodeFrame(source, width, height) {
  const scale = Math.min(1, FEEDBACK_MAX_IMAGE_EDGE / Math.max(width || 1, height || 1));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
  const png = canvas.toDataURL("image/png");
  if (png.length * 0.75 <= FEEDBACK_MAX_IMAGE_BYTES) return png;
  return canvas.toDataURL("image/jpeg", 0.82);
}

// Capture the screen/tab the user picks. Rejects with a human-readable message the modal shows as-is.
async function captureFeedbackScreenshot() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
    throw new Error("This browser can't capture a screenshot. Take one with your usual key combination, then paste or drop it here.");
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { displaySurface: "browser" }, audio: false, preferCurrentTab: true,
    });
  } catch (e) {
    if (e && e.name === "NotAllowedError") throw new Error("Screen capture was dismissed. You can also paste or drop an image here.");
    throw new Error("Couldn't start screen capture: " + ((e && e.message) || "unknown error"));
  }
  try {
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    await video.play();
    await new Promise(r => setTimeout(r, 250));   // let a real frame arrive before we read it
    if (!video.videoWidth) throw new Error("The capture produced no frame. Try again, or paste an image.");
    return _encodeFrame(video, video.videoWidth, video.videoHeight);
  } finally {
    stream.getTracks().forEach(t => t.stop());   // always release the capture indicator
  }
}

// Paste / drag-drop path: an image File → the same downscaled data URL.
function readFeedbackImageFile(file) {
  return new Promise((resolve, reject) => {
    if (!file || !/^image\//.test(file.type || "")) { reject(new Error("That isn't an image file.")); return; }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Couldn't read that image."));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Couldn't decode that image."));
      img.onload = () => { try { resolve(_encodeFrame(img, img.naturalWidth, img.naturalHeight)); } catch (e) { reject(e); } };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

// The destination address — blank by default, so a report is never pre-addressed to someone the user
// didn't choose. Rendered inline in the modal AND in Settings (one component, one source of truth); the
// shared IIFE lets 35_settings.jsx call it directly (the inc-208/222 hoist precedent).
function FeedbackDestinationRow({ config, onSaved }) {
  const [email, setEmail] = useState((config && config.destination_email) || "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { setEmail((config && config.destination_email) || ""); }, [config && config.destination_email]);
  const save = async () => {
    setBusy(true); setMsg("");
    const r = await apiPut("/feedback/config", { set_destination_email: true, destination_email: email.trim() });
    setBusy(false);
    if (!r.ok) { setMsg("Couldn't save: " + (r.error || "error")); return; }
    setMsg(email.trim() ? "Saved." : "Cleared.");
    if (onSaved) onSaved(r.data);
  };
  const fromEnv = config && config.destination_source === "env";
  return (
    <div className="settings-field">
      <label className="settings-field-label">Send feedback to
        <span className="settings-sub">
          The address your bug reports and feature requests are addressed to. callosum ships with none set — it
          only ever opens a draft in your mail client, so nothing is sent until you press send.
          {fromEnv ? " Currently set by the CALLOSUM_FEEDBACK_EMAIL environment variable." : ""}
        </span>
      </label>
      <div className="settings-keyrow">
        <input className="settings-input" type="email" autoComplete="off" placeholder="maintainer@example.com"
          value={email} onChange={e => setEmail(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") save(); }} />
        <button className="btn btn-ghost" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</button>
      </div>
      {msg && <div className="settings-note">{msg}</div>}
    </div>
  );
}

// The Settings block (rendered by SettingsView's "Feedback" card), so the address is configurable from the
// place the user looks for settings — the same component, so the two entry points can't drift.
function FeedbackSettings() {
  const [config, setConfig] = useState(null);
  useEffect(() => { api("/feedback/config").then(r => { if (r.ok) setConfig(r.data); }); }, []);
  return (
    <>
      <p className="eyebrow">Feedback</p>
      <FeedbackDestinationRow config={config} onSaved={setConfig} />
      {config && <div className="settings-note">Reports are written to <code>{config.feedback_dir}</code>.</div>}
    </>
  );
}

// The menu-bar entry point. Self-contained (it owns the open state), so the shell needs no new plumbing —
// MenuBar just renders it, exactly as it renders StatusMenu.
function FeedbackMenuItem({ workspace }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="menubar-item" onClick={() => setOpen(true)}
        title="Report a bug or request a feature">Feedback</button>
      {open && <FeedbackModal onClose={() => setOpen(false)} viewContext={{ workspace: workspace || "" }} />}
    </>
  );
}

function FeedbackModal({ onClose, viewContext }) {
  const [kind, setKind] = useState("bug");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [steps, setSteps] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [shot, setShot] = useState(null);            // data URL of the attached image
  const [config, setConfig] = useState(null);        // {destination_email, diagnostics, feedback_dir}
  const [includeDiag, setIncludeDiag] = useState(true);
  const [showDiag, setShowDiag] = useState(false);
  const [capturing, setCapturing] = useState(false); // hide the modal so it isn't in its own screenshot
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);        // the written bundle
  const [copied, setCopied] = useState("");

  useEffect(() => { api("/feedback/config").then(r => { if (r.ok) setConfig(r.data); }); }, []);
  // Prefill the reply-to from the polite-pool contact the user already gave us, rather than asking twice.
  useEffect(() => { api("/settings").then(r => { if (r.ok && r.data.contact_email) setReplyTo(r.data.contact_email); }); }, []);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const capture = async () => {
    setErr(""); setCapturing(true);
    try {
      await new Promise(r => setTimeout(r, 60));      // let the hide paint before the picker opens
      setShot(await captureFeedbackScreenshot());
    } catch (e) { setErr((e && e.message) || "Screenshot failed."); }
    finally { setCapturing(false); }
  };

  const takeFile = async (file) => {
    setErr("");
    try { setShot(await readFeedbackImageFile(file)); }
    catch (e) { setErr((e && e.message) || "Couldn't read that image."); }
  };
  const onPaste = (e) => {
    const item = Array.from((e.clipboardData && e.clipboardData.items) || []).find(i => /^image\//.test(i.type));
    if (item) { e.preventDefault(); takeFile(item.getAsFile()); }
  };
  const onDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) takeFile(file);
  };

  const submit = async () => {
    if (!title.trim() || !body.trim()) { setErr("A title and a description are both required."); return; }
    setBusy(true); setErr("");
    const r = await apiPost("/feedback", {
      kind, title: title.trim(), body: body.trim(),
      steps: kind === "bug" && steps.trim() ? steps.trim() : null,
      reply_to: replyTo.trim() || null,
      include_diagnostics: includeDiag,
      client_diagnostics: includeDiag ? feedbackClientDiagnostics(viewContext) : {},
      screenshot: shot,
    });
    setBusy(false);
    if (!r.ok) { setErr(r.error || "Couldn't save the report."); return; }
    setResult(r.data);
  };

  const copy = (text, what) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(what); setTimeout(() => setCopied(""), 1600); });
  };

  const diag = (config && config.diagnostics) || {};
  const destination = (config && config.destination_email) || "";

  return (
    <div className={"axis-modal-overlay" + (capturing ? " fb-hidden" : "")} onClick={onClose}>
      <div className="axis-modal fb-modal" onClick={e => e.stopPropagation()} onPaste={onPaste}
        onDragOver={e => e.preventDefault()} onDrop={onDrop} role="dialog" aria-modal="true" aria-label="Send feedback">
        <div className="axis-modal-head">
          <span>{result ? "Report saved" : "Report a bug or request a feature"}</span>
          <button className="axis-link" onClick={onClose} aria-label="Close">×</button>
        </div>

        {result ? (
          <div className="fb-done">
            <p className="fb-done-lead">Your report was written to this machine. Nothing has been sent yet —
              opening the draft below hands it to your mail client, where you can read it before sending.</p>
            <div className="fb-path">{result.report_path}</div>
            {result.screenshot_path &&
              <p className="fb-note">The screenshot is saved beside it as <b>{result.screenshot_path.split(/[\\/]/).pop()}</b> —
                mail clients can't be handed an attachment from a link, so attach it to the draft yourself.</p>}
            <div className="fb-actions">
              {result.mailto_url
                ? <a className="btn btn-primary" href={result.mailto_url}>Open email draft</a>
                : <span className="fb-note">No destination address is set, so there's no draft to open — set one
                    below (or in Settings) and the next report will offer it. Your report is safe on disk either way.</span>}
              <button className="btn btn-ghost" onClick={() => copy(result.report_markdown, "report")}>
                {copied === "report" ? "Copied" : "Copy report"}</button>
              <button className="btn btn-ghost" onClick={() => copy(result.directory, "path")}>
                {copied === "path" ? "Copied" : "Copy folder path"}</button>
            </div>
            {!result.mailto_url && <FeedbackDestinationRow config={config} onSaved={setConfig} />}
            <details className="fb-details">
              <summary>What was written</summary>
              <pre className="fb-pre">{result.report_markdown}</pre>
            </details>
            <div className="fb-actions">
              <button className="btn btn-ghost" onClick={onClose}>Done</button>
            </div>
          </div>
        ) : (
          <div className="fb-form">
            <div className="fb-kinds" role="radiogroup" aria-label="Report type">
              <button className={"fb-kind" + (kind === "bug" ? " active" : "")} role="radio" aria-checked={kind === "bug"}
                onClick={() => setKind("bug")}>Something's broken</button>
              <button className={"fb-kind" + (kind === "feature" ? " active" : "")} role="radio" aria-checked={kind === "feature"}
                onClick={() => setKind("feature")}>I'd like a feature</button>
            </div>

            <label className="fb-label">Title
              <input className="settings-input" value={title} autoFocus maxLength={200}
                placeholder={kind === "bug" ? "The PDF renders blank in two-up view" : "Let me sort the library by date added"}
                onChange={e => setTitle(e.target.value)} />
            </label>

            <label className="fb-label">{kind === "bug" ? "What happened" : "What you'd like"}
              <textarea className="settings-input fb-textarea" value={body} maxLength={20000}
                placeholder={kind === "bug" ? "What you expected, and what you got instead." : "What you're trying to do, and where it gets in your way."}
                onChange={e => setBody(e.target.value)} />
            </label>

            {kind === "bug" &&
              <label className="fb-label"><span className="fb-label-text">Steps to reproduce <span className="fb-optional">optional</span></span>
                <textarea className="settings-input fb-textarea fb-textarea-sm" value={steps} maxLength={8000}
                  placeholder={"1. Open a paper\n2. Switch to two-up\n3. …"}
                  onChange={e => setSteps(e.target.value)} />
              </label>}

            <div className="fb-shot">
              <div className="fb-shot-head">
                <span className="fb-label-text">Screenshot <span className="fb-optional">optional</span></span>
                <div className="fb-shot-actions">
                  <button className="btn btn-ghost" onClick={capture}>{shot ? "Retake" : "Take screenshot"}</button>
                  {shot && <button className="btn btn-ghost danger" onClick={() => setShot(null)}>Remove</button>}
                </div>
              </div>
              {shot
                ? <img className="fb-shot-preview" src={shot} alt="Attached screenshot preview" />
                : <p className="fb-note">Your browser will ask which window or tab to capture. You can also paste
                    (⌘/Ctrl-V) or drag an image straight into this panel.</p>}
            </div>

            <label className="fb-label"><span className="fb-label-text">Your email <span className="fb-optional">optional — so a reply can reach you</span></span>
              <input className="settings-input" type="email" value={replyTo} autoComplete="off"
                placeholder="you@example.com" onChange={e => setReplyTo(e.target.value)} />
            </label>

            <div className="fb-diag">
              <label className="fb-check">
                <input type="checkbox" checked={includeDiag} onChange={e => setIncludeDiag(e.target.checked)} />
                <span>Attach diagnostics — versions and settings only. No library content, no file paths, no API key.</span>
              </label>
              <button className="btn-link fb-diag-toggle" onClick={() => setShowDiag(v => !v)}>
                {showDiag ? "Hide" : "Show"} what's attached</button>
              {showDiag &&
                <table className="fb-diag-table">
                  <tbody>
                    {Object.keys(diag).map(k => <tr key={k}><td>{k}</td><td>{diag[k]}</td></tr>)}
                    {Object.entries(feedbackClientDiagnostics(viewContext)).map(([k, v]) =>
                      <tr key={"c" + k}><td>client.{k}</td><td className="fb-diag-wrap">{v}</td></tr>)}
                  </tbody>
                </table>}
            </div>

            {err && <div className="fb-error">{err}</div>}

            <p className="fb-note">
              {destination
                ? <>This is saved to your machine, then opened as a draft to <b>{destination}</b> in your mail client. callosum sends nothing itself.</>
                : <>No destination address is set yet. Your report will still be saved to this machine, and you can set an address in Settings → Feedback.</>}
            </p>

            <div className="fb-actions">
              <button className="btn btn-primary" disabled={busy || !title.trim() || !body.trim()} onClick={submit}>
                {busy ? "Saving…" : "Save report"}</button>
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
