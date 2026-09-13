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
  const [outcome, setOutcome] = useState(null);  // {kind, created, paperId, acquiring, fulltextReady, noAccess} | {kind:'error', message}
  const [critique, setCritique] = useState({ phase: "idle" });  // idle | running | ready | error (#79)
  const reqRef = useRef(0);
  const mountedRef = useRef(true);
  const acqPollRef = useRef(null);   // cancel fn for the OA-acquisition poll
  const critPollRef = useRef(null);  // cancel fn for the critique poll
  useEffect(() => () => {
    mountedRef.current = false;
    if (acqPollRef.current) acqPollRef.current();
    if (critPollRef.current) critPollRef.current();
  }, []);

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

  // "Usable full text" = the paper actually has chunks. A downloaded-but-unparsed PDF (attachment_count>0,
  // chunk_count==0) is NOT usable — Critique needs real full text, never metadata/abstract (#79 boundary).
  const _fulltextReady = async (paperId) => {
    const r = await api("/papers/" + paperId);
    return !!(r.ok && r.data && (r.data.chunk_count || 0) > 0);
  };

  const add = useCallback(async (c) => {
    setPhase("adding"); setOutcome(null); setCritique({ phase: "idle" });
    const save = await apiPost("/discovery/save", {
      title: c.title || c.doi || "Untitled",
      doi: c.doi || null, authors: c.authors || [], journal: c.venue || null,
      year: c.year || null, url: c.url || null,
    });
    if (!save.ok || !save.data) {
      if (mountedRef.current) setOutcome({ kind: "error", message: "Couldn't add the paper — " + (save.error || "unknown error") });
      setPhase("done"); return;
    }
    const paperId = save.data.paper_id;
    const created = !!save.data.created;
    setPhase("done");
    // Already have usable full text (an existing chunked paper, or a re-run)? Critique can proceed directly.
    if (await _fulltextReady(paperId)) {
      if (mountedRef.current) setOutcome({ kind: "added", created, paperId, fulltextReady: true });
      return;
    }
    // Otherwise attempt the canonical OA acquisition, then RE-CHECK for usable full text. This resolves
    // synchronously to ready or a clear no-access state — nothing is queued or retained for later (#79 scope).
    if (mountedRef.current) setOutcome({ kind: "added", created, paperId, acquiring: true, fulltextReady: false });
    const acq = await apiPost("/papers/" + paperId + "/acquire-oa", {});
    if (!acq.ok || !acq.data || !acq.data.job_id) {
      if (mountedRef.current) setOutcome({ kind: "added", created, paperId, fulltextReady: false, noAccess: "acquire-error" });
      return;
    }
    acqPollRef.current = observeJobUntilTerminal("/papers/acquire-oa/" + acq.data.job_id, {
      onDone: async (data) => {
        acqPollRef.current = null;
        if (!data.found) {
          if (mountedRef.current) setOutcome({ kind: "added", created, paperId, fulltextReady: false, noAccess: "no-oa" });
          return;
        }
        const ready = await _fulltextReady(paperId);   // downloaded, but did it ingest into usable chunks?
        if (mountedRef.current) setOutcome({ kind: "added", created, paperId, fulltextReady: ready, noAccess: ready ? null : "no-fulltext" });
      },
      onError: () => {
        acqPollRef.current = null;
        if (mountedRef.current) setOutcome({ kind: "added", created, paperId, fulltextReady: false, noAccess: "acquire-error" });
      },
    });
  }, []);

  // Critique the (full-text-ready) paper via the canonical single-paper Critical Read — the ONLY Critique
  // implementation. The run persists, so it's reviewable later in that paper's Synthesize → Critique.
  const startCritique = useCallback((paperId) => {
    setCritique({ phase: "running", paperId });
    apiPost("/papers/" + paperId + "/critical-read", {}).then(r => {
      if (!r.ok || !r.data || !r.data.job_id) {
        if (mountedRef.current) setCritique({ phase: "error", paperId, error: r.error || "Couldn't start the critique." });
        return;
      }
      critPollRef.current = observeJobUntilTerminal("/critical-read/" + r.data.job_id, {
        onDone: () => { critPollRef.current = null; if (mountedRef.current) setCritique({ phase: "ready", paperId }); },
        onError: (err) => { critPollRef.current = null; if (mountedRef.current) setCritique({ phase: "error", paperId, error: err || "Critique failed." }); },
      });
    });
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
            <div>{outcome.created ? "Added to your library." : "This paper was already in your library."}</div>
            {outcome.acquiring &&
              <div className="axis-hint" style={{ marginTop: 6 }}>Finding an open-access copy and preparing the full text…</div>}
            {!outcome.acquiring && outcome.fulltextReady &&
              <div className="reffind-critique" style={{ marginTop: 8 }}>
                {critique.phase === "idle" &&
                  <>
                    <button className="btn btn-primary" onClick={() => startCritique(outcome.paperId)}>Critique this paper</button>
                    <div className="axis-hint" style={{ marginTop: 4 }}>
                      Runs Callosum's ordinary Critique on this paper's full text — is its evidence strong enough to lean on?
                    </div>
                  </>}
                {critique.phase === "running" &&
                  <div className="axis-hint">Critiquing… you can keep reading — it runs in the background.</div>}
                {critique.phase === "ready" &&
                  <div>
                    Critique ready — review it in this paper's <b>Synthesize → Critique</b>.
                    {onOpenPaper &&
                      <button className="btn btn-ghost" style={{ marginLeft: 8 }}
                        onClick={() => { onOpenPaper({ id: outcome.paperId, title: null }); onClose(); }}>Open paper</button>}
                  </div>}
                {critique.phase === "error" &&
                  <div className="reffind-outcome err" style={{ marginTop: 0 }}>{critique.error}</div>}
              </div>}
            {!outcome.acquiring && !outcome.fulltextReady && outcome.noAccess &&
              <div style={{ marginTop: 6 }}>
                Critique needs the full paper.{" "}
                {outcome.noAccess === "no-oa"
                  ? "No open-access copy was available, so it can't be critiqued from here yet."
                  : outcome.noAccess === "no-fulltext"
                    ? "The copy that was found couldn't be turned into usable full text, so it can't be critiqued yet."
                    : "The open-access lookup didn't complete, so it can't be critiqued yet."}{" "}
                You can attach a PDF to this paper later and critique it from <b>Synthesize → Critique</b>.
              </div>}
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
