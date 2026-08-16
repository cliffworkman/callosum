// inc 462 (backlog #33/#34 P2 #21): open-science statement staging (THEORY/Work authoring cluster). Extends
// CRediT's own "build in the web UI -> stage -> LibreOffice pulls & inserts" pattern (38_credit.jsx, inc 261)
// to 7 more manuscript-level disclosures. Like CRediT, this is an authoring AID: it offers common starting
// phrasing the author can pick and edit; it never asserts a fact about the user's own study (funding received,
// ethics approval, AI use, etc.) — the human is the source of truth, exactly as CRediT's own framing states.

// (label, full canned sentence) pairs per statement kind — real, common scholarly-publishing boilerplate, not
// tied to any one journal's house style. Clicking a phrase button is a starting point, never silently applied.
const STATEMENT_TYPES = [
  {
    kind: "data_availability", label: "Data availability",
    phrases: [
      { label: "Available on request", text: "The data that support the findings of this study are available from the corresponding author upon reasonable request." },
      { label: "Openly available", text: "The data that support the findings of this study are openly available in [repository name] at [URL/DOI]." },
      { label: "Restricted (third-party)", text: "The data used in this study are third-party data, and restrictions apply to their availability." },
      { label: "No new data", text: "No new data were generated in this study." },
    ],
  },
  {
    kind: "code_availability", label: "Code availability",
    phrases: [
      { label: "Openly available", text: "The code that supports the findings of this study is available at [repository URL]." },
      { label: "Available on request", text: "The code used in this study is available from the corresponding author upon reasonable request." },
      { label: "No custom code", text: "No custom code was used in this study." },
    ],
  },
  {
    kind: "preregistration", label: "Preregistration",
    phrases: [
      { label: "Preregistered", text: "The study design and analysis plan were preregistered at [registry/URL] prior to data collection." },
      { label: "Not preregistered", text: "This study was not preregistered." },
      { label: "Some exploratory analyses", text: "Some analyses reported here were not specified in the preregistration and should be considered exploratory." },
    ],
  },
  {
    kind: "funding", label: "Funding",
    phrases: [
      { label: "Funded", text: "This work was supported by [Funder name] under Grant No. [XXX]." },
      { label: "No specific funding", text: "This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors." },
    ],
  },
  {
    kind: "conflict_of_interest", label: "Conflict of interest",
    phrases: [
      { label: "None declared", text: "The authors declare no competing interests." },
      { label: "Declared", text: "The authors declare the following competing interests: [describe]." },
    ],
  },
  {
    kind: "ethics", label: "Ethics",
    phrases: [
      { label: "IRB approved", text: "This study was approved by [IRB/Ethics Committee name], protocol #[XXX]." },
      { label: "Not required", text: "This study did not require ethical approval because [reason]." },
      { label: "Informed consent", text: "All participants provided informed consent prior to participation." },
    ],
  },
  {
    kind: "ai_use", label: "AI use",
    phrases: [
      { label: "AI used", text: "Generative AI tools were used for [specific purpose]; all AI-assisted content was reviewed and edited by the authors, who take full responsibility for the final manuscript." },
      { label: "No AI used", text: "No generative AI tools were used in the preparation of this manuscript." },
    ],
  },
];

function StatementsSection({ ctx }) {
  const paperKey = "callosum.statements." + (ctx && ctx.selectedPaper != null ? ctx.selectedPaper : "_");
  const [texts, setTexts] = useState({});   // kind -> current textarea value
  const [staged, setStaged] = useState({}); // kind -> true while the current text matches what's staged server-side
  const [copiedKind, setCopiedKind] = useState(null);
  const loadedKeyRef = useRef(null);

  // Load the saved drafts on mount + whenever the selected paper changes (per-paper scratchpad, the exact
  // CRediT scoping convention — keyed on ctx.selectedPaper with a "_" fallback).
  useEffect(() => {
    if (isDemoMode()) {
      api("/demo/saved-artifacts/statements").then(r => {
        if (!r.ok) return;
        loadedKeyRef.current = paperKey;
        setTexts(r.data || {});
      });
      return;
    }
    const saved = _loadLayout(paperKey, null);
    let next = {};
    if (saved) { try { const parsed = JSON.parse(saved); if (parsed && typeof parsed === "object") next = parsed; } catch (e) { /* ignore */ } }
    loadedKeyRef.current = paperKey;
    setTexts(next);
    setStaged({});
  }, [paperKey]);

  useEffect(() => {
    if (loadedKeyRef.current !== paperKey) return;
    _saveLayout(paperKey, JSON.stringify(texts));
  }, [texts, paperKey]);

  const setText = (kind, value) => {
    setTexts((t) => ({ ...t, [kind]: value }));
    setStaged((s) => (s[kind] ? { ...s, [kind]: false } : s));  // editing invalidates the "staged" badge
  };

  const applyPhrase = (kind, phraseText) => {
    const current = (texts[kind] || "").trim();
    if (current && current !== phraseText && !window.confirm("Replace the current text with the selected phrase?")) return;
    setText(kind, phraseText);
  };

  const copy = (kind) => {
    const text = texts[kind] || "";
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => { setCopiedKind(kind); setTimeout(() => setCopiedKind(null), 1500); });
  };

  const sendToLibreOffice = async (kind) => {
    const text = (texts[kind] || "").trim();
    const r = await apiPost("/statements/pending", { kind, text });
    if (r.ok) setStaged((s) => ({ ...s, [kind]: !!text }));
  };

  return (
    <div className="grim-section ws-pad">
      <div className="settings-sub">Build the manuscript-level disclosures many journals require. Callosum offers common starting phrasing for each — you decide what applies and edit freely; it never asserts a fact about your study on your behalf.</div>
      {isDemoMode() && <div className="settings-note">Saved synthetic-manuscript disclosure drafts. Copying and browser-local edits work; persistent storage and LibreOffice handoff require local Callosum.</div>}
      {STATEMENT_TYPES.map((type) => {
        const text = texts[type.kind] || "";
        return (
          <div className="statements-block" key={type.kind}>
            <div className="statements-label">{type.label}</div>
            <div className="statements-phrases">
              {type.phrases.map((p, i) => (
                <button key={i} type="button" className="btn-link statements-phrase" onClick={() => applyPhrase(type.kind, p.text)}>{p.label}</button>
              ))}
            </div>
            <textarea
              className="settings-input statements-textarea"
              rows={3}
              value={text}
              onChange={(e) => setText(type.kind, e.target.value)}
              placeholder={`Type or pick a starting phrase for your ${type.label.toLowerCase()} statement…`}
              spellCheck={true}
            />
            <div className="statements-actions">
              <button className="btn btn-primary" disabled={!text} onClick={() => copy(type.kind)}>{copiedKind === type.kind ? "✓ copied" : "Copy"}</button>
              <button
                className="btn btn-ghost"
                disabled={isDemoMode()}
                onClick={() => sendToLibreOffice(type.kind)}
                title="Stage this statement for the LibreOffice Callosum add-on to insert at the cursor (requires the add-on)"
              >
                Send to LibreOffice
              </button>
            </div>
            {staged[type.kind] &&
              <div className="statements-staged">Staged — switch to LibreOffice and run <b>Callosum → Insert statement…</b> to place it at the cursor. (Editing this box clears this — re-send after changes.)</div>}
          </div>
        );
      })}
    </div>
  );
}

registerWorkspaceTab(
  { id: "work" },
  { id: "statements", label: "Statements", order: 31, hideInReadOnly: true, render: (ctx) => <StatementsSection ctx={ctx} /> },
);
