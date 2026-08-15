// Detail-pane action widgets split from 25_detail.jsx to keep the main editable metadata surface under the
// application-source line budget. These stay behavior-only siblings: citation export, OA acquisition, OCR,
// GROBID structure parsing, and adding arbitrary CSL fields.

// inc-70: export this paper's citation (BibTeX/RIS/CSL-JSON). inc-106: render a FORMATTED citation (APA/MLA/
// Chicago/IEEE/Nature/Harvard) via the citeproc engine + show/copy it. `apiPost` is fine for /citations/render
// (JSON); the export links use a raw fetch (apiPost forces .json()). Clipboard works on the 127.0.0.1 secure
// context. reference_html is server-sanitized (allowlisted inline tags) — safe to render.
function CiteRow({ paperId }) {
  // B5 SP2: the cite/export controls POST to /citations/* + /papers/export (not forwarded / method-gated on a
  // read-only companion), so hide them there rather than fire doomed requests.
  const ro = React.useContext(DetailReadOnly);
  const [copied, setCopied] = useState(null);
  const [styles, setStyles] = useState([]);
  const [style, setStyle] = useState("apa");
  const [rendered, setRendered] = useState(null);   // { in_text, reference_text, reference_html }
  const [fmtCopied, setFmtCopied] = useState(false);

  // Only fetch once read-write is CONFIRMED (ro === false) — undefined = health not yet resolved, true = read-only.
  useEffect(() => { if (ro !== false) return; api("/citations/styles").then(r => { if (r.ok) setStyles(r.data.styles || []); }); }, [ro]);
  useEffect(() => {
    if (ro !== false) return;
    let alive = true;
    setRendered(null);
    apiPost("/citations/render", { paper_ids: [paperId], style }).then(r => {
      if (alive) setRendered(r.ok && r.data.items && r.data.items[0] ? r.data.items[0] : null);
    });
    return () => { alive = false; };
  }, [paperId, style, ro]);
  if (ro === true) return null;

  const copyExport = async (format) => {
    try {
      const res = await fetch(API_BASE + "/papers/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper_ids: [paperId], format }),
      });
      if (!res.ok) { console.warn("[callosum] copy citation failed:", res.status); return; }
      await navigator.clipboard.writeText(await res.text());
      setCopied(format);
      setTimeout(() => setCopied(null), 1500);
    } catch (e) { console.warn("[callosum] copy citation error:", e); }
  };
  const copyFormatted = async () => {
    if (!rendered || !rendered.reference_text) return;
    try {
      await navigator.clipboard.writeText(rendered.reference_text);
      setFmtCopied(true);
      setTimeout(() => setFmtCopied(false), 1500);
    } catch (e) { console.warn("[callosum] copy formatted citation error:", e); }
  };

  return (
    <div className="detail-cite">
      <div className="detail-cite-row">
        <span className="detail-cite-label">Cite as</span>
        <select className="detail-cite-style" value={style} onChange={e => setStyle(e.target.value)} title="Citation style">
          {styles.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <button className="btn-link" onClick={copyFormatted} disabled={!rendered} title="Copy the formatted citation">
          {fmtCopied ? "Copied ✓" : "Copy"}
        </button>
      </div>
      {rendered && rendered.reference_html &&
        <div className="detail-cite-preview" dangerouslySetInnerHTML={{ __html: rendered.reference_html }} />}
      <div className="detail-cite-row">
        <span className="detail-cite-label">Export</span>
        {[["bibtex", "BibTeX"], ["ris", "RIS"], ["csl-json", "CSL-JSON"]].map(([f, lbl]) => (
          <button key={f} className="btn-link" onClick={() => copyExport(f)} title={`Copy ${lbl} to clipboard`}>
            {copied === f ? "Copied ✓" : lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

// Acquisition clean lane (Increment A): fetch a free, rights-holder-authorized open-access copy via OpenAlex
// and import it into the local library. Shown only when a paper has no available PDF. Async job → poll →
// refresh the detail on success (or an honest "no authorized open-access copy found").
function AcquireOaRow({ paperId, onAcquired }) {
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [msg, setMsg] = useState(null);
  const [missed, setMissed] = useState(false); // OA cascade found nothing → offer the library hand-off
  const [libMsg, setLibMsg] = useState(null);
  // inc 263: the free-and-legal hand-off. callosum builds an OpenURL and opens the user's OWN institution's
  // official link resolver in the user's OWN browser (their SSO does the auth); it never fetches the paper and
  // never touches credentials. Opt-in — dormant until a resolver base is set in Settings.
  const getViaLibrary = async () => {
    setLibMsg(null);
    const r = await api(`/papers/${paperId}/library-link`);
    if (!r.ok) { setLibMsg(r.error || "Couldn't build a library link."); return; }
    if (!r.data.configured) { setLibMsg("Add your library's link resolver in Settings to use this."); return; }
    if (!r.data.url) { setLibMsg(r.data.detail || "This record can't be resolved by a library link."); return; }
    window.open(r.data.url, "_blank", "noopener");
    setLibMsg("Opened your library's resolver — sign in there, download the PDF, then attach it here or drop it in your library folder.");
  };
  const poll = async (jobId) => {
    const r = await api(`/papers/acquire-oa/${jobId}`);
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Acquisition status check failed."); return; }
    const j = r.data;
    if (j.status === "done") {
      setStatus("done");
      if (j.found) {
        setMsg("Imported a " + j.oa_color + (j.bronze_unstable ? " (unstable)" : "") + " open-access copy.");
        onAcquired && onAcquired();
      } else {
        setMsg(j.detail || "No authorized open-access copy found.");
        setMissed(true);
      }
      return;
    }
    if (j.status === "error") { setStatus("error"); setMsg(j.detail || "Acquisition failed."); return; }
    setTimeout(() => poll(jobId), 1200); // pending / running → keep polling
  };
  const start = async () => {
    setStatus("running"); setMsg(null); setMissed(false); setLibMsg(null);
    const r = await apiPost(`/papers/${paperId}/acquire-oa`, {});
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Couldn't start acquisition."); return; }
    poll(r.data.job_id);
  };
  return (
    <div className="detail-acquire">
      <button className="btn btn-primary" disabled={status === "running"} onClick={start}
        title="Fetch a free, rights-holder-authorized open-access copy via OpenAlex and import it locally">
        {status === "running" ? "Acquiring…" : "Acquire OA copy"}
      </button>
      {status === "running" && <ProgressBar label="Searching open-access sources…" managedBy="backend-job" />}
      {msg && <span className={"detail-acquire-msg" + (status === "error" ? " detail-acquire-err" : "")}>{msg}</span>}
      {missed && (
        <button className="btn" onClick={getViaLibrary}
          title="Open your institution's official link resolver in your browser — a free, legal route to a copy you're entitled to. callosum never fetches the paper or handles your login.">
          Get via my library →
        </button>
      )}
      {libMsg && <span className="detail-acquire-msg">{libMsg}</span>}
    </div>
  );
}

// inc-231 (B3): OCR a scanned / image-only PDF. Shown only when the paper HAS a PDF but no text layer
// (chunk_count === 0). Async job → poll (with determinate progress) → refresh the detail on success. Fully local
// (Tesseract + local embeddings); nothing leaves the machine. Reuses the .detail-acquire* recipe (DESIGN rule #8).
function OcrRow({ paperId, onOcred }) {
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [msg, setMsg] = useState(null);
  const [prog, setProg] = useState(null);
  const poll = async (jobId) => {
    const r = await api(`/papers/ocr/run/${jobId}`);
    if (!r.ok) { setStatus("error"); setMsg(r.error || "OCR status check failed."); return; }
    const j = r.data;
    if (j.status === "done") {
      setStatus("done"); setProg(null);
      const pages = j.result ? j.result.pages : 0;
      setMsg(`OCR complete — ${pages} page${pages === 1 ? "" : "s"}; this paper is now searchable.`);
      onOcred && onOcred();
      return;
    }
    if (j.status === "error") { setStatus("error"); setProg(null); setMsg(j.detail || "OCR failed."); return; }
    setProg(j.progress || null);
    setTimeout(() => poll(jobId), 1000); // pending / running → keep polling
  };
  const start = async () => {
    setStatus("running"); setMsg(null); setProg(null);
    const r = await apiPost("/papers/ocr/run", { paper_id: paperId });
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Couldn't start OCR."); return; }
    poll(r.data.job_id);
  };
  return (
    <div className="detail-acquire">
      <button className="btn btn-primary" disabled={status === "running"} onClick={start}
        title="This PDF has no text layer (it looks scanned). Run local OCR to make it searchable + citable — nothing leaves your machine.">
        {status === "running" ? "Running OCR…" : "OCR this paper (scanned)"}
      </button>
      {status === "running" && <ProgressBar label="Reading pages…" progress={prog} managedBy="backend-job" />}
      {msg && <span className={"detail-acquire-msg" + (status === "error" ? " detail-acquire-err" : "")}>{msg}</span>}
    </div>
  );
}

// backlog #30 Stage 2 (task 11): parse this paper's document structure with GROBID -- an opt-in, separately-run
// service the user configures + tests in Settings (GrobidSettings, js/35e_maintenance.jsx). GROBID maps its own
// section boundaries onto this paper's already-extracted PyMuPDF chunk bboxes (task 10 already prefers that
// mapped data over the local heuristic once present) -- server-side precondition is just a local PDF (422
// otherwise), so this is shown alongside "Reprocess PDF text" whenever one exists. Async job -> poll, mirroring
// OcrRow's poll shape below; unlike OcrRow's library-wide sibling (POST /grobid/library/parse), a single paper's
// job reports no determinate progress, so the bar stays indeterminate like AcquireOaRow's above.
function GrobidParseRow({ paperId, onParsed }) {
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [msg, setMsg] = useState(null);
  const poll = async (jobId) => {
    const r = await api(`/grobid/papers/${paperId}/parse/${jobId}`);
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Parse status check failed."); return; }
    const j = r.data;
    if (j.status === "done") {
      setStatus("done");
      const res = j.result;
      setMsg(res
        ? `Parsed ${res.sections_found} section${res.sections_found === 1 ? "" : "s"}; mapped ${res.chunks_mapped} chunk${res.chunks_mapped === 1 ? "" : "s"}.`
        : "Parse complete.");
      onParsed && onParsed();
      return;
    }
    if (j.status === "error") { setStatus("error"); setMsg(j.detail || "Parse failed."); return; }
    setTimeout(() => poll(jobId), 1500); // pending / running -> keep polling
  };
  const start = async () => {
    setStatus("running"); setMsg(null);
    const r = await apiPost(`/grobid/papers/${paperId}/parse`, {});
    if (!r.ok) { setStatus("error"); setMsg(r.error || "Couldn't start parsing."); return; }
    poll(r.data.job_id);
  };
  return (
    <div className="detail-acquire">
      <button className="btn btn-ghost" disabled={status === "running"} onClick={start}
        title="Parse this paper's document structure with GROBID (configured in Settings) -- maps its section detection onto this paper's already-extracted text.">
        {status === "running" ? "Parsing structure…" : "Parse document structure…"}
      </button>
      {status === "running" && <ProgressBar label="Parsing document structure…" managedBy="backend-job" />}
      {msg && <span className={"detail-acquire-msg" + (status === "error" ? " detail-acquire-err" : "")}>{msg}</span>}
    </div>
  );
}

// inc-97: add an arbitrary CSL bibliographic field by hand (completes the inc-49 "More" deferral). Reuses the
// validated generic `csl` patch — the backend allows letter-led [A-Za-z0-9_-] keys, rejecting reserved/core
// ones (those have their own fields) with a 422 that surfaces as the pane's save note.
function AddFieldRow({ onSave }) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const add = async () => {
    const key = name.trim();
    if (!key || !value.trim() || busy) return;
    setBusy(true);
    const r = await onSave("csl", { [key]: value.trim() });
    setBusy(false);
    if (r && r.ok) { setName(""); setValue(""); }
  };
  return (
    <div className="detail-addfield">
      <input className="detail-addfield-key" placeholder="field name" value={name} spellCheck={false}
        onChange={(e) => setName(e.target.value)} />
      <input className="detail-addfield-val" placeholder="value" value={value} spellCheck={false}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") add(); }} />
      <button className="btn-link" disabled={busy || !name.trim() || !value.trim()} onClick={add}>+ add</button>
    </div>
  );
}
