// inc 261: CRediTer — the CRediT contribution-statement builder (THEORY authoring cluster). An authoring AID: it
// formats the contributions the author *asserts* (an authors × 14-NISO-role grid) into a human-readable
// contributorship statement, in two layouts (by author / by role). It is a BUILDER, not a verifier — it never
// infers or judges who did what; the human is the source of truth. Local, deterministic, no AI, no egress.

// The 14 NISO CRediT roles (mirrors app/backend/methods/credit.py — a fixed open standard, duplicated like ES_FIELD).
const CREDIT_ROLES = [
  { key: "conceptualization", label: "Conceptualization" },
  { key: "data_curation", label: "Data curation" },
  { key: "formal_analysis", label: "Formal analysis" },
  { key: "funding_acquisition", label: "Funding acquisition" },
  { key: "investigation", label: "Investigation" },
  { key: "methodology", label: "Methodology" },
  { key: "project_administration", label: "Project administration" },
  { key: "resources", label: "Resources" },
  { key: "software", label: "Software" },
  { key: "supervision", label: "Supervision" },
  { key: "validation", label: "Validation" },
  { key: "visualization", label: "Visualization" },
  { key: "writing_original_draft", label: "Writing – original draft" },
  { key: "writing_review_editing", label: "Writing – review & editing" },
];
const CREDIT_DEGREES = ["lead", "equal", "supporting"];

// credit-the-lineage: the taxonomy this operationalizes + the prior tool (tenzing). Added via the inc-93 import path.
const CREDIT_TAXONOMY_CSL = {
  type: "article-journal",
  title: "Beyond authorship: attribution, contribution, collaboration, and credit",
  author: [
    { family: "Brand", given: "Amy" },
    { family: "Allen", given: "Liz" },
    { family: "Altman", given: "Micah" },
    { family: "Hlava", given: "Marjorie" },
    { family: "Scott", given: "Jo" },
  ],
  "container-title": "Learned Publishing",
  volume: "28",
  issue: "2",
  page: "151-155",
  issued: { "date-parts": [[2015]] },
  DOI: "10.1087/20150211",
};
const CREDIT_TENZING_CSL = {
  type: "article-journal",
  title: "Documenting contributions to scholarly articles using CRediT and tenzing",
  author: [
    { family: "Holcombe", given: "Alex O." },
    { family: "Kovacs", given: "Marton" },
    { family: "Aust", given: "Frederik" },
    { family: "Aczel", given: "Balazs" },
  ],
  "container-title": "PLOS ONE",
  volume: "15",
  issue: "12",
  page: "e0244611",
  issued: { "date-parts": [[2020]] },
  DOI: "10.1371/journal.pone.0244611",
};

function _blankAuthor() {
  return { name: "", roles: {} };  // roles: { roleKey: degree|"" } — key present = assigned
}

function CreditSection({ ctx }) {
  const readOnly = React.useContext(AppReadOnly);  // inc 308: only format via the backend when confirmed read-write
  const paperKey = "callosum.credit." + (ctx && ctx.selectedPaper != null ? ctx.selectedPaper : "_");
  const [authors, setAuthors] = useState([_blankAuthor()]);
  const [result, setResult] = useState(null);       // { by_author, by_role, roles }
  const [view, setView] = useState("by_author");    // by_author | by_role
  const [copied, setCopied] = useState(false);
  const [staged, setStaged] = useState(false);
  const [pulled, setPulled] = useState("idle");     // idle | pulling | none
  const loadedKeyRef = useRef(null);

  // Load the saved grid on mount + whenever the selected paper changes (per-paper scratchpad).
  useEffect(() => {
    const saved = _loadLayout(paperKey, null);
    let next = [_blankAuthor()];
    if (saved) { try { const p = JSON.parse(saved); if (Array.isArray(p) && p.length) next = p; } catch (e) { /* ignore */ } }
    loadedKeyRef.current = paperKey;
    setAuthors(next);
    setStaged(false); setCopied(false);
  }, [paperKey]);

  // Save on edit — but skip the render right after a paper switch (authors still belong to the old key), so we
  // never clobber the new paper's saved grid with the outgoing paper's rows.
  useEffect(() => {
    if (loadedKeyRef.current !== paperKey) return;
    _saveLayout(paperKey, JSON.stringify(authors));
  }, [authors, paperKey]);

  // Debounced format via the deterministic backend (the source of truth for the statement text). Gated on a
  // confirmed read-WRITE instance (inc 308) so the mount-time POST never fires + 403s during the brief window
  // before /health resolves on a read-only companion (the CRediT tab is `hideInReadOnly`, but it can mount first).
  useEffect(() => {
    if (readOnly !== false) return;
    const body = { authors: authors.map((a) => ({
      name: a.name,
      roles: Object.keys(a.roles).map((role) => ({ role, degree: a.roles[role] || null })),
    })) };
    setStaged(false);  // the staged copy in /credit/pending is now stale — the user must re-send after editing
    const t = setTimeout(async () => {
      const r = await apiPost("/credit/statement", body);
      if (r.ok) setResult(r.data);
    }, 250);
    return () => clearTimeout(t);
  }, [authors, readOnly]);

  const setName = (i) => (e) => setAuthors(authors.map((a, ai) => ai === i ? { ...a, name: e.target.value } : a));
  const addAuthor = () => setAuthors([...authors, _blankAuthor()]);
  const removeAuthor = (i) => setAuthors(authors.length > 1 ? authors.filter((_, ai) => ai !== i) : [_blankAuthor()]);
  const toggleRole = (i, key) => setAuthors(authors.map((a, ai) => {
    if (ai !== i) return a;
    const roles = { ...a.roles };
    if (key in roles) delete roles[key]; else roles[key] = "";
    return { ...a, roles };
  }));
  const setDegree = (i, key, deg) => setAuthors(authors.map((a, ai) =>
    ai === i ? { ...a, roles: { ...a.roles, [key]: deg } } : a));

  const pullAuthors = async () => {
    if (!ctx || ctx.selectedPaper == null) return;
    setPulled("pulling");
    const r = await api("/papers/" + ctx.selectedPaper);
    const names = r.ok && Array.isArray(r.data.authors) ? r.data.authors : [];
    if (!names.length) { setPulled("none"); return; }
    // Non-destructive: append names not already in the grid; keep any existing rows + their roles.
    const have = new Set(authors.map((a) => a.name.trim()).filter(Boolean));
    const fresh = names.filter((n) => !have.has(String(n).trim())).map((n) => ({ name: String(n), roles: {} }));
    const base = authors.filter((a) => a.name.trim() || Object.keys(a.roles).length);  // drop the empty seed row
    setAuthors([...base, ...fresh].length ? [...base, ...fresh] : [_blankAuthor()]);
    setPulled("idle");
  };

  const lines = result ? (view === "by_role" ? result.by_role : result.by_author) : [];
  const text = lines.join("\n");

  const copy = () => navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
  const sendToManuscript = async () => {
    const r = await apiPost("/credit/pending", { text });
    if (r.ok) setStaged(true);  // persistent — cleared when the grid changes (the staged text would be stale) or on re-stage
  };

  return (
    <div className="grim-section">
      <div className="settings-sub">Build a <b>CRediT contribution statement</b> — assign each author their <a href="https://credit.niso.org/" target="_blank" rel="noopener noreferrer">NISO CRediT</a> roles (optionally lead / equal / supporting), and Callosum formats it. It formats the contributions <b>you assert</b>; it does not verify who did what — you are the source of truth.</div>

      {ctx && ctx.selectedPaper != null &&
        <button className="btn-link credit-pull" onClick={pullAuthors} disabled={pulled === "pulling"}>
          {pulled === "pulling" ? "pulling…" : pulled === "none" ? "no authors on this paper" : "⤵ pull authors from this paper"}
        </button>}

      <div className="credit-grid">
        {authors.map((a, i) => (
          <div className="credit-author" key={i}>
            <div className="credit-author-head">
              <input className="es-in credit-name" value={a.name} onChange={setName(i)} placeholder="Author name" spellCheck={false} />
              <button className="btn-icon credit-remove" title="Remove author" onClick={() => removeAuthor(i)}>✕</button>
            </div>
            <div className="credit-roles">
              {CREDIT_ROLES.map((role) => {
                const assigned = role.key in a.roles;
                return (
                  <span key={role.key} className={"credit-role" + (assigned ? " on" : "")}>
                    <button type="button" className="credit-role-label" onClick={() => toggleRole(i, role.key)}>{role.label}</button>
                    {assigned &&
                      <select className="credit-degree" value={a.roles[role.key] || ""} onChange={(e) => setDegree(i, role.key, e.target.value)} title="Degree of contribution (optional)">
                        <option value="">—</option>
                        {CREDIT_DEGREES.map((d) => <option key={d} value={d}>{d}</option>)}
                      </select>}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
        <button className="btn-link credit-add" onClick={addAuthor}>＋ add author</button>
      </div>

      <div className="tags-srcfilter credit-view" role="tablist" aria-label="Statement layout">
        <button className={"tags-srcfilter-btn" + (view === "by_author" ? " on" : "")} onClick={() => setView("by_author")}>By author</button>
        <button className={"tags-srcfilter-btn" + (view === "by_role" ? " on" : "")} onClick={() => setView("by_role")}>By role</button>
      </div>
      <div className="settings-sub credit-view-hint">Most journals ask for the <b>by-author</b> layout — check your target journal's instructions for authors.</div>

      {lines.length > 0
        ? <div className="credit-output" aria-label="Contribution statement">{lines.map((ln, i) => <div key={i} className="credit-line">{ln}</div>)}</div>
        : <div className="credit-output credit-output-empty">Assign at least one role to generate a statement.</div>}

      <div className="credit-actions">
        <button className="btn btn-primary" disabled={!lines.length} onClick={copy}>{copied ? "✓ copied" : "Copy"}</button>
        <button className="btn btn-ghost" disabled={!lines.length} onClick={sendToManuscript} title="Stage the statement for the LibreOffice Callosum add-on to insert at the cursor (requires the add-on)">Send to LibreOffice</button>
      </div>
      {staged && <div className="credit-staged">Staged — switch to LibreOffice and run <b>Callosum → Insert CRediT statement</b> to place it at the cursor. (Editing the grid clears this — re-send after changes.)</div>}

      <div className="statcheck-caveat">Callosum formats the contributions you assert — it does not infer or verify who did what. The 14 roles are the fixed open <b>NISO CRediT</b> taxonomy; degree of contribution (lead / equal / supporting) is optional.</div>
      <div className="method-credit">
        <b>About this tool:</b> CRediTer formats the <b>CRediT / NISO</b> taxonomy (Brand, Allen, Altman, Hlava &amp; Scott 2015, <i>Learned Publishing</i>) and follows the <i>tenzing</i> workflow (Holcombe, Kovacs, Aust &amp; Aczel 2020, <i>PLOS ONE</i>) — these credit the standard behind this feature, not citations for your manuscript.{" "}
        <MethodCreditButton items={[CREDIT_TENZING_CSL, CREDIT_TAXONOMY_CSL]} />
      </div>
    </div>
  );
}

registerWorkspaceTab(
  { id: "work", label: "Work", order: 50 },
  { id: "credit", label: "CRediT statement", order: 20, hideInReadOnly: true, render: (ctx) => <CreditSection ctx={ctx} /> },
);
