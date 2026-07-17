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
  useEffect(() => { refresh(); }, [refresh]);

  const missing = state.status === "ready" ? (state.importedAll ? [] : missingCreditItems(allItems, state.present)) : allItems;
  const done = state.status === "ready" && missing.length === 0;
  const addMissing = async () => {
    if (state.status !== "ready" || done) return;
    setState(prev => ({ ...prev, status: "adding" }));
    const r = await apiPost("/library/import", { content: JSON.stringify(missing), format: "csl-json" });
    if (r && r.ok) {
      setState({ status: "ready", present: new Set(allItems.map(creditDoi).filter(Boolean)), importedAll: true });
      onChanged && onChanged();
    } else {
      refresh();
    }
  };
  const label = done ? "✓ added to library" : state.status === "adding" ? "adding…" : "＋ add missing to library";
  return (
    <button className="btn-link" disabled={done || state.status === "adding" || state.status === "checking"} onClick={addMissing}>
      {label}
    </button>
  );
}
