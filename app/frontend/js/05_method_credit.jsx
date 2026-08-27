// Shared credit-the-lineage affordance (inc 293): checks which DOI-bearing source items are already in the
// library, imports only missing items, and keeps the button label honest for single and multi-source credits.

function creditItems(items) {
  return Array.isArray(items) ? items : [items];
}

function creditDoi(item) {
  return String((item && (item.DOI || item.doi)) || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\/doi\.org\//, "")
    .replace(/^doi:/, "")
    .trim();
}

function missingCreditItems(items, presentDoiSet) {
  return creditItems(items).filter(item => {
    const doi = creditDoi(item);
    return !doi || !presentDoiSet.has(doi);
  });
}

function MethodCreditButton({ items, onChanged }) {
  const readOnly = React.useContext(AppReadOnly);  // inc 308: tri-state; only check/import when confirmed read-write
  const [state, setState] = useState({ status: "checking", present: new Set(), importedAll: false });
  const allItems = creditItems(items);
  const refresh = useCallback(() => {
    const dois = allItems.map(creditDoi).filter(Boolean);
    if (dois.length === 0) { setState({ status: "ready", present: new Set(), importedAll: false }); return; }
    apiPost("/library/credit/status", { dois }).then(r => {
      if (!r.ok) { setState({ status: "ready", present: new Set(), importedAll: false }); return; }
      const present = new Set((r.data.items || []).filter(it => it.present).map(it => it.doi));
      setState({ status: "ready", present, importedAll: false });
    });
  }, [JSON.stringify(allItems.map(creditDoi))]);
  // Fire the read-implemented-as-POST /library/credit/status only once /health confirms a read-WRITE instance —
  // a read-only companion never issues the doomed POST (which would 403 + log a console error).
  useEffect(() => { if (readOnly === false) refresh(); }, [refresh, readOnly]);

  // Importing is a write, so the whole affordance is hidden on a read-only companion (and until /health resolves).
  if (readOnly !== false) return null;

  const inFlight = state.status === "adding" || state.status === "checking";
  const missing = !inFlight ? (state.importedAll ? [] : missingCreditItems(allItems, state.present)) : allItems;
  const done = !inFlight && state.status !== "error" && missing.length === 0;

  // inc 466: POST /library/import is an async job (202 + job_id, GET /library/import/{id} to poll) -- found live
  // while verifying this increment's own new credit blocks: the button previously trusted the 202 response alone
  // and showed "added" even when the job later failed (concrete repro: a concurrent background retraction batch
  // held the write lock, the import's create_paper hit "database is locked", and the job finished with
  // summary.failed > 0 while the button already said done). Poll to the real outcome instead, mirroring
  // GapsModal's own job-polling pattern (`36_gaps.jsx`).
  const pollImport = (jobId) => {
    api(`/library/import/${jobId}`).then(r => {
      if (!r.ok) { setState(prev => ({ ...prev, status: "error" })); return; }
      const d = r.data;
      if (d.status === "done") {
        if (d.summary && d.summary.failed > 0) { setState(prev => ({ ...prev, status: "error" })); return; }
        setState({ status: "ready", present: new Set(allItems.map(creditDoi).filter(Boolean)), importedAll: true });
        onChanged && onChanged();
      } else if (d.status === "error") {
        setState(prev => ({ ...prev, status: "error" }));
      } else {
        setTimeout(() => pollImport(jobId), 2000);
      }
    });
  };
  const addMissing = async () => {
    if (inFlight || done) return;
    setState(prev => ({ ...prev, status: "adding" }));
    const r = await apiPost("/library/import", { content: JSON.stringify(missing), format: "csl-json" });
    if (r && r.ok && r.data && r.data.job_id) {
      pollImport(r.data.job_id);
    } else {
      refresh();
    }
  };
  const label = done
    ? "✓ Added to Library"
    : state.status === "adding"
      ? "Adding…"
      : state.status === "error"
        ? "Add Failed — Retry"
        : "＋ Add Missing to Library";
  return (
    <button className="btn-link" disabled={done || inFlight} onClick={addMissing} title={state.status === "error" ? "The import didn't complete — click to try again." : undefined}>
      {label}
    </button>
  );
}

// inc 466 (credit-the-lineage backfill): a shared credit block for Daniël Lakens' automated-review catalog,
// which surfaced the whole family of METHODS reading aids below (statcheck, GRIM, Bayesian, LMM, meta-analysis,
// transparency, p-curve) but was only ever a passing italic mention in each panel, never an actual clickable,
// library-addable credit. The catalog itself is a living GitHub Pages site, not a paper -- only Crone & Green
// (2025), the real peer-reviewed review of it, is offered via MethodCreditButton; the catalog is linked as
// plain text. One shared component (not 7 copies of the same citation data), rendered once per panel.
const CRONE_GREEN_2025_CSL = {
  id: "crone-green-2025-tools-of-the-data-detective",
  type: "article-journal",
  title:
    "Tools of the data detective: A review of statistical methods to detect data and result anomalies in psychology",
  author: [
    { family: "Crone", given: "Gabriel" },
    { family: "Green", given: "Christopher D." },
  ],
  "container-title": "Personality and Social Psychology Review",
  issued: { "date-parts": [[2025]] },
  DOI: "10.1177/09593543241311861",
};

function LakensCredit() {
  return (
    <div className="method-credit-sub">
      Surfaced via Daniël Lakens'{" "}
      <a href="https://lakens.github.io/automated_review_daily_build/" target="_blank" rel="noopener noreferrer">
        automated-review catalog
      </a>{" "}
      of meta-research tools, reviewed in Crone &amp; Green (2025). <MethodCreditButton items={[CRONE_GREEN_2025_CSL]} />
    </div>
  );
}
