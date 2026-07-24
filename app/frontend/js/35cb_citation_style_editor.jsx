// Revision-safe source editor for independent personal CSL styles.
function CitationStyleEditorPreview({ preview, family }) {
  if (!preview) return <div className="citation-style-empty">Validate to render this draft.</div>;
  return (
    <div className="citation-style-editor-preview">
      <div className="citation-style-preview-block">
        <span className="settings-field-label">{family === "note" ? "First note" : "Citation"}</span>
        <div>{preview.citations[0]}</div>
      </div>
      {family === "note" && preview.citations[1] &&
        <div className="citation-style-preview-block">
          <span className="settings-field-label">Subsequent note</span>
          <div>{preview.citations[1]}</div>
        </div>}
      <div className="citation-style-preview-block">
        <span className="settings-field-label">Bibliography</span>
        <div className="citation-style-bibliography">
          {preview.bibliography_text || "This style does not produce a bibliography."}
        </div>
      </div>
    </div>
  );
}

function CitationStyleEditorModal({ style, locale, onClose, onSaved }) {
  const [loaded, setLoaded] = useState(null);
  const [source, setSource] = useState("");
  const [preview, setPreview] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const dirty = !!loaded && source !== loaded.csl;

  useEffect(() => {
    let live = true;
    setStatus("loading"); setError("");
    api(`/citations/styles/${encodeURIComponent(style.id)}/source`).then(result => {
      if (!live) return;
      if (!result.ok) {
        setStatus("error");
        setError("Couldn't open citation style source: " + (result.error || "error"));
        return;
      }
      setLoaded(result.data);
      setSource(result.data.csl);
      setStatus("ready");
    });
    return () => { live = false; };
  }, [style.id]);

  const close = () => {
    if (dirty && !window.confirm("Discard unsaved citation-style changes?")) return;
    onClose();
  };

  const validate = async () => {
    setStatus("validating"); setError("");
    const result = await apiPost(
      `/citations/styles/${encodeURIComponent(style.id)}/source/validate`,
      { csl: source, locale },
    );
    if (!result.ok) {
      setStatus("error");
      setError("Couldn't validate citation style: " + (result.error || "error"));
      return;
    }
    setSource(result.data.normalized_csl);
    setPreview(result.data.preview);
    setStatus("validated");
  };

  const save = async () => {
    if (!loaded) return;
    setStatus("saving"); setError("");
    const result = await apiPut(
      `/citations/styles/${encodeURIComponent(style.id)}/source`,
      { csl: source, expected_revision: loaded.revision, locale },
    );
    if (!result.ok) {
      setStatus("error");
      setError("Couldn't save citation style: " + (result.error || "error"));
      return;
    }
    onSaved(result.data);
  };

  return (
    <div className="axis-modal-overlay" role="dialog" aria-modal="true"
      aria-labelledby="citation-style-editor-title" onClick={close}>
      <div className="axis-modal citation-style-editor-modal" onClick={event => event.stopPropagation()}>
        <div className="axis-modal-head">
          <span id="citation-style-editor-title">Edit citation style</span>
          <button type="button" className="axis-link" aria-label="Close citation style editor" onClick={close}>×</button>
        </div>
        <div className="citation-style-editor-title">{style.full_title || style.title}</div>
        <div className="citation-style-editor-grid">
          <label className="settings-field-label citation-style-editor-source">
            CSL source
            <textarea className="settings-input" aria-label="CSL source" spellCheck={false}
              value={source} maxLength={1000000} disabled={!loaded || status === "saving"}
              onChange={event => { setSource(event.target.value); setPreview(null); setStatus("ready"); setError(""); }} />
          </label>
          <section className="citation-style-editor-output" aria-label="Draft preview">
            <span className="settings-field-label">Draft preview</span>
            <CitationStyleEditorPreview preview={preview} family={style.family} />
          </section>
        </div>
        {error && <div className="settings-note settings-note-err">{error}</div>}
        {!error && status === "validated" &&
          <div className="settings-note">Draft is valid and previewed.</div>}
        <div className="axis-form-actions citation-style-editor-actions">
          <button type="button" className="btn" onClick={close}>Cancel</button>
          <button type="button" className="btn" disabled={!loaded || status === "validating" || status === "saving"}
            onClick={validate}>{status === "validating" ? "Validating…" : "Validate & preview"}</button>
          <button type="button" className="btn btn-primary"
            disabled={!loaded || !dirty || status === "validating" || status === "saving"}
            onClick={save}>{status === "saving" ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>
  );
}
