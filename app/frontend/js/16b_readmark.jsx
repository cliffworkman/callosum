// inc 220: per-paper reading markers on a library card — a manual read/unread toggle + a user-set priority
// (high/normal/low). Both are personal triage labels the user sets BY HAND, never an AI score (the inc-207
// declined-ratings logic). Optimistic: local state mirrors the paper prop and reverts on a failed write.
// inc 294: priority now ALSO drives the Reading Queue's strata, so a change here must invalidate that other view —
// `onChanged` (fired after a successful priority write) bumps the queue refresh so both panes re-read the one
// source of truth (papers.priority). Function hoists in the shared IIFE → PaperCard (10_pdf_layer.jsx, loads
// earlier) renders it. Kept out of 10_pdf_layer to stay under the 600-line cap (the inc-208 10b_libmenus pattern).

const PRIORITY_LEVELS = ["high", "normal", "low"];
const _cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function ReadPriorityControl({ paper, onChanged, demoLocked }) {
  const [read, setRead] = useState(!!paper.read_at);
  const [priority, setPriority] = useState(paper.priority || "");
  const [pop, setPop] = useState(false);
  useEffect(() => { setRead(!!paper.read_at); setPriority(paper.priority || ""); }, [paper.read_at, paper.priority]);
  useEffect(() => {
    if (!pop) return;
    const close = () => setPop(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [pop]);

  const toggleRead = (e) => {
    e.stopPropagation();
    if (demoLocked) {
      explainDemoLock("Read state and priority are saved personal library markers. Their current demo values remain visible, but changing them requires your local Callosum library.", `/papers/${paper.id}/read`);
      return;
    }
    const next = !read;
    setRead(next);  // optimistic
    apiPost(`/papers/${paper.id}/read`, { read: next }).then((r) => { if (!r.ok) setRead(!next); });
  };
  const setLevel = (e, level) => {
    e.stopPropagation();
    if (demoLocked) {
      setPop(false);
      explainDemoLock("Read state and priority are saved personal library markers. Their current demo values remain visible, but changing them requires your local Callosum library.", `/papers/${paper.id}/priority`);
      return;
    }
    const prev = priority;
    setPriority(level || "");  // optimistic
    setPop(false);
    apiPost(`/papers/${paper.id}/priority`, { priority: level }).then((r) => {
      if (!r.ok) { setPriority(prev); return; }
      if (onChanged) onChanged();  // inc 294: re-read the Queue strata from the persisted value
    });
  };

  return (
    <span className="paper-mark" onClick={(e) => e.stopPropagation()}>
      <button
        className={"paper-read" + (read ? " is-read" : "")}
        title={read ? "Read — click to mark unread" : "Mark as read"}
        onClick={toggleRead}
      >{read ? "✓ Read" : "○ Unread"}</button>
      <span className="paper-priority-wrap">
        <button
          className={"paper-priority pr-" + (priority || "none")}
          title="Set reading priority (your triage label)"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); setPop((v) => !v); }}
        >{priority ? _cap(priority) : "Priority ▾"}</button>
        {pop && (
          <span className="priority-pop" onMouseDown={(e) => e.stopPropagation()}>
            {PRIORITY_LEVELS.map((l) => (
              <button key={l} className={"pr-opt pr-" + l} onClick={(e) => setLevel(e, l)}>{_cap(l)}</button>
            ))}
            <button className="pr-opt pr-clear" onClick={(e) => setLevel(e, null)}>Clear</button>
          </span>
        )}
      </span>
    </span>
  );
}
