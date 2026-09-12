// Reader "Find referenced paper…" modal (inc 595, rule #1: its own chunk). TRANSIENT: no highlight/annotation
// is ever created. It snapshots the selected text at invocation (props.text -> local state), so a later reader
// selection change never affects an open lookup, and a stale in-flight response is discarded (reqRef token).
// Explicit egress: the /references/resolve request fires only from an explicit click ("Find referenced
// paper…" opens the modal and runs it once; "Look up" re-runs it) — never from selecting/highlighting text.
// It composes EXISTING endpoints only: POST /references/resolve, then POST /discovery/save (canonical, deduped,
// background-enriched add) + POST /papers/{id}/acquire-oa (OA is a separate step; its failure never undoes the
// metadata add). Hoists in the shared IIFE so PdfViewer references it regardless of chunk load order.

function _refAuthorLine(c) {
  const names = (c.authors || []).map(a => String(a).split(",")[0].trim()).filter(Boolean);
  if (names.length === 0) return "";
  return names.length <= 3 ? names.join(", ") : names.slice(0, 3).join(", ") + ", et al.";
}

function ReferenceCandidateRow({ c, onAdd, onOpen, busy }) {
  const meta = [_refAuthorLine(c), c.year, c.venue].filter(Boolean).join(" · ");
  return (
    <div className="gap-row">
      <div className="gap-row-info">
        <div className="gap-row-title" title={c.title || c.doi || ""}>{c.title || c.doi || "Untitled record"}</div>
        {meta && <div className="gap-row-meta">{meta}</div>}
        {c.doi && <div className="reffind-doi">{c.doi}</div>}
      </div>
      <div className="gap-row-actions">
        {c.in_library
          ? <>
              <span className="reffind-inlib">✓ In your library</span>
              {onOpen && c.existing_paper_id != null &&
                <button className="btn btn-ghost" onClick={() => onOpen(c)}>Open</button>}
            </>
          : <button className="btn btn-primary" disabled={busy} onClick={() => onAdd(c)}>Add to library</button>}
      </div>
    </div>
  );
}

function ReferenceFinderModal({ text: initialText, onClose, onOpenPaper }) {
  const [text, setText] = useState(initialText || "");
  const [phase, setPhase] = useState("idle");   // idle | loading | adding | done
  const [result, setResult] = useState(null);   // { classification, candidates, normalized_text, error }
  const [outcome, setOutcome] = useState(null);  // { kind: 'added'|'error', created, oa, ... }
  const reqRef = useRef(0);

  const lookup = useCallback(async () => {
    const q = (text || "").trim();
    if (!q) return;
    const token = ++reqRef.current;   // snapshot: a superseded/stale response is ignored
    setPhase("loading"); setOutcome(null); setResult(null);
    const r = await apiPost("/references/resolve", { text: q });
    if (token !== reqRef.current) return;   // a newer lookup (or a close) won
    setResult(r.ok && r.data ? r.data
      : { classification: "none", candidates: [], error: r.error || "The lookup failed. Please try again." });
    setPhase("done");
  }, [text]);

  // The click that opened this modal IS the explicit egress authorization — run the captured selection once.
  useEffect(() => { if ((initialText || "").trim()) lookup(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  const add = useCallback(async (c) => {
    setPhase("adding"); setOutcome(null);
    const save = await apiPost("/discovery/save", {
      title: c.title || c.doi || "Untitled",
      doi: c.doi || null, authors: c.authors || [], journal: c.venue || null,
      year: c.year || null, url: c.url || null,
    });
    if (!save.ok || !save.data) {
      setOutcome({ kind: "error", message: "Couldn't add the paper — " + (save.error || "unknown error") });
      setPhase("done"); return;
    }
    let oa = "existing";
    if (save.data.created) {
      const acq = await apiPost(`/papers/${save.data.paper_id}/acquire-oa`, {});   // OA failure ≠ add failure
      oa = acq.ok ? "started" : "unavailable";
    }
    setOutcome({ kind: "added", created: !!save.data.created, oa });
    setPhase("done");
  }, []);

  const openExisting = useCallback((c) => {
    if (onOpenPaper && c.existing_paper_id != null) {
      onOpenPaper({ id: c.existing_paper_id, title: c.title });
      onClose();
    }
  }, [onOpenPaper, onClose]);

  const candidates = (result && result.candidates) || [];
  return (
    <div className="axis-modal-overlay" onMouseDown={onClose}>
      <div className="axis-modal" onMouseDown={e => e.stopPropagation()}>
        <div className="axis-modal-head">
          <span>Find referenced paper</span>
          <button className="axis-link" onClick={onClose}>×</button>
        </div>
        <div className="axis-modal-note">
          Looks this reference up in Crossref (a public scholarly index), then adds the paper through your normal
          library import. Edit the text below if the selection was imperfect.
        </div>
        <textarea className="reffind-text" value={text} maxLength={2000} placeholder="Reference text…"
                  onChange={e => setText(e.target.value)} />
        <div className="reffind-actions">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          <button className="btn btn-primary" disabled={phase === "loading" || !text.trim()} onClick={lookup}>
            {phase === "loading" ? "Looking up…" : "Look up"}
          </button>
        </div>

        {phase === "loading" && <div className="axis-hint">Searching Crossref…</div>}

        {outcome && outcome.kind === "added" &&
          <div className="reffind-outcome ok">
            {outcome.created ? "Added to your library." : "This paper was already in your library."}
            {outcome.created && outcome.oa === "started" && " Fetching an open-access copy in the background…"}
            {outcome.created && outcome.oa === "unavailable" &&
              " No open-access copy was available — the record was still added."}
          </div>}
        {outcome && outcome.kind === "error" && <div className="reffind-outcome err">{outcome.message}</div>}

        {phase !== "loading" && result && result.error && !outcome &&
          <div className="reffind-outcome err">{result.error}</div>}
        {phase !== "loading" && result && !result.error && !outcome && result.classification === "none" &&
          <div className="axis-hint">No defensible match. Edit the reference text above and look up again.</div>}
        {phase !== "loading" && candidates.length > 0 && !outcome &&
          <div className="reffind-results">
            {result.classification === "multiple_candidates" &&
              <div className="axis-hint">Several possible matches — choose the right one:</div>}
            {candidates.map((c, i) =>
              <ReferenceCandidateRow key={c.doi || i} c={c} onAdd={add} onOpen={openExisting}
                busy={phase === "adding"} />)}
          </div>}
      </div>
    </div>
  );
}
