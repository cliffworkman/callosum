// First-class extra URL editor for Details. The primary CSL URL remains its own row; this manages additional links.
function PaperUrlsEditor({ paper, readOnly, onChanged }) {
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const urls = paper.urls || [];
  const add = async () => {
    const trimmed = url.trim();
    if (!trimmed || busy) return;
    setBusy(true); setError("");
    const r = await apiPost(`/papers/${paper.id}/urls`, { url: trimmed, label: label.trim() || null });
    setBusy(false);
    if (r.ok) {
      setUrl(""); setLabel("");
      onChanged && onChanged();
    } else {
      setError(r.error || "Couldn't add that URL.");
    }
  };
  const remove = async (item) => {
    if (!item || item.id == null || busy) return;
    setBusy(true); setError("");
    const r = await apiDelete(`/papers/${paper.id}/urls/${item.id}`);
    setBusy(false);
    if (r.ok) onChanged && onChanged();
    else setError(r.error || "Couldn't remove that URL.");
  };
  return (
    <div className="paper-urls">
      <div className="paper-urls-label">More URLs</div>
      {urls.length > 0
        ? <div className="paper-url-list">
            {urls.map((item, i) => (
              <div className="paper-url-row" key={(item.id || "legacy") + ":" + item.url + ":" + i}>
                <a href={item.url} target="_blank" rel="noreferrer" title={item.url}>
                  {item.label || item.url}
                </a>
                {item.label && <span className="paper-url-full" title={item.url}>{item.url}</span>}
                {!readOnly && item.id != null &&
                  <button className="btn-link danger" onClick={() => remove(item)} disabled={busy}
                    title="Remove this URL from the paper record">Remove</button>}
              </div>
            ))}
          </div>
        : <div className="axis-hint">No additional URLs.</div>}
      {!readOnly &&
        <div className="paper-url-add">
          <input value={label} placeholder="label (optional)" onChange={e => setLabel(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") add(); }} />
          <input value={url} placeholder="https://…" onChange={e => setUrl(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") add(); }} />
          <button className="btn-link" disabled={busy || !url.trim()} onClick={add}>+ add</button>
        </div>}
      {error && <div className="axis-err paper-url-error">{error}</div>}
    </div>
  );
}
