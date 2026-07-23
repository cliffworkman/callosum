// Assisted-extraction funnel UI (workbench SP2b, inc 259) — the LLM PROPOSES; the human disposes. Split out of
// 45_workbench.jsx (rule #1) as hoisted function declarations (callable across the shared esbuild IIFE — the
// 10b/35b precedent). Amber (`--flag`) = candidate / uncertain / region (DESIGN #8; no new color semantics). A
// candidate NEVER enters the trusted cell until the human clicks ✓ — facts ≠ candidates (PRINCIPLES).

// The per-row "Draft from PDF →" control: only rendered inside the paper_id != null branch in 45_workbench.jsx.
function WbDraftButton({ row, aiReady, busy, disabled, onDraft }) {
  return (
    <button className="wb-draft" disabled={!aiReady || busy || disabled}
      title={disabled
        ? "Another drafting request is in progress"
        : aiReady
          ? "Ask the AI to propose values from this paper's PDF — you verify each one before it's saved"
        : "Turn on \"Allow AI features\" in Settings to let the AI draft values from this paper's PDF"}
      onClick={onDraft}>{busy ? "Drafting…" : "✨ Draft from PDF →"}</button>
  );
}

// The honest anchor signal — derived locally, never a model score. exact = quote located AND value literal in it.
function WbAnchorBadge({ p }) {
  if (p.anchor_state === "exact")
    return <span className="wb-badge ok" title="Quote located in the PDF; the value is in it">✓ exact · p.{p.page}</span>;
  if (p.anchor_state === "region")
    return <span className="wb-badge flag" title="Quote located, but the value isn't literally in it — verify against the source">region · p.{p.page}</span>;
  return <span className="wb-badge flag" title="Couldn't find the quote in the PDF — verify before accepting">
    p.{p.page == null ? "?" : p.page + "?"} — couldn't verify</span>;
}

// The amber candidate on an empty structured cell: value + anchor badge + Open-at-anchor + accept / edit / reject.
// Unanchored proposals get the `.unanchored` dashed treatment (DESIGN §5 `.speculative` precedent — invariant #2).
// The verbatim quote is shown below the controls in BOTH view and edit modes (invariant #4: evidence always
// shown — you keep the source in view while correcting a misread number).
function WbCandidate({ proposal, onAccept, onReject, onOpen }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(proposal.value || "");
  const isUnanchored = proposal.anchor_state === "unanchored";
  return (
    <div className={"wb-cand" + (isUnanchored ? " unanchored" : "")}
      title="AI candidate — verify against the source, then accept, edit, or reject">
      {editing
        ? <input className="wb-cellin wb-cand-in" autoFocus value={val}
            onChange={e => setVal(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter") onAccept(val);
              else if (e.key === "Escape") { setVal(proposal.value || ""); setEditing(false); }
            }} />
        : <span className="wb-cand-val">✎ {proposal.value}</span>}
      <WbAnchorBadge p={proposal} />
      <span className="wb-cand-acts">
        <button className="wb-cand-open" title="Open the PDF at this anchor — verify against the source" onClick={onOpen}>📎</button>
        {editing
          ? <button className="wb-cand-ok" title="Accept the edited value" onClick={() => onAccept(val)}>✓</button>
          : (<>
              <button className="wb-cand-ok" title="Accept into the cell" onClick={() => onAccept(undefined)}>✓</button>
              <button className="wb-cand-edit" title="Edit before accepting" onClick={() => setEditing(true)}>✎</button>
            </>)}
        <button className="wb-cand-x" title="Reject this candidate" onClick={onReject}>✗</button>
      </span>
      {proposal.quote && <span className="wb-cand-quote">"{proposal.quote}"</span>}
    </div>
  );
}
