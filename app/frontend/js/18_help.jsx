// In-app help viewer — renders the served help corpus (GET /help/corpus) as a navigable two-column
// modal: a section table-of-contents + the section bodies, each with a stable anchor id. Above the docs
// sits the AI help assistant (POST /help/ask): ask a question, get an answer + reference chips that scroll
// to and highlight the matching section — recapitulating the synthesis "probe → route to source" workflow
// over the app's own help. The assistant has its own consent toggle (CALLOSUM_HELP_ASSISTANT_ENABLED).

// Scroll to a help section by id and flash it. Mirrors the PDF viewer's jumpToAnnotation flash; reused by
// the TOC and by the help-assistant reference chips. Hoisted top-level so any help chunk can call it.
function flashHelpSection(id) {
  const el = document.getElementById("help-" + id);
  if (!el) return;
  el.scrollIntoView({ block: "start", behavior: "smooth" });
  el.classList.remove("flash");
  void el.offsetWidth;            // reflow to restart the animation
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1300);
}

function HelpChat({ titleById }) {
  const [messages, setMessages] = useState([]);   // [{role:"user"|"assistant", content, references?}]
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);     // disabled/error guidance (e.g. assistant off → how to enable)
  const logRef = useRef(null);

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [messages, busy]);

  const send = () => {
    const message = draft.trim();
    if (!message || busy) return;
    const history = messages.map(m => ({ role: m.role, content: m.content }));
    setMessages(m => [...m, { role: "user", content: message }]);
    setDraft("");
    setBusy(true);
    setNotice(null);
    apiPost("/help/ask", { message, history }).then(r => {
      setBusy(false);
      if (!r.ok) { setNotice(r.error); return; }
      setMessages(m => [...m, { role: "assistant", content: r.data.answer, references: r.data.references || [] }]);
    });
  };

  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  return (
    <div className="help-chat">
      <div className="help-chat-log" ref={logRef}>
        {messages.length === 0 && !busy &&
          <p className="help-chat-hint">Ask a question about using Callosum — answers link to the relevant help below.</p>}
        {messages.map((m, i) =>
          <div key={i} className={"help-msg help-msg-" + m.role}>
            <div className="help-msg-text">{m.content}</div>
            {m.references && m.references.length > 0 &&
              <div className="help-refs">
                {m.references.map((ref, j) =>
                  <button key={j} className="help-ref-chip" title={ref.reason}
                    onClick={() => flashHelpSection(ref.section_id)}>
                    {titleById[ref.section_id] || ref.section_id}
                  </button>)}
              </div>}
          </div>)}
        {busy && <div className="help-msg help-msg-assistant"><div className="help-msg-text help-msg-thinking">Thinking…</div></div>}
        {busy && <ProgressBar label="Drafting a Help answer…" managedBy="tracked-request" />}
      </div>
      {notice && <p className="help-chat-notice">{notice}</p>}
      <div className="help-ask-row">
        <input className="help-ask-input" placeholder="Ask the help assistant…" value={draft}
          onChange={e => setDraft(e.target.value)} onKeyDown={onKey} disabled={busy} />
        <button className="help-ask-send" onClick={send} disabled={busy || !draft.trim()}>Ask</button>
      </div>
    </div>
  );
}

// inc 280 (stage 3): the Help center view (the menu-bar "Help" utility workspace) — formerly a modal.
function HelpView() {
  const [state, setState] = useState({ status: "loading" });

  useEffect(() => {
    let live = true;
    api("/help/corpus").then(r => {
      if (!live) return;
      if (!r.ok) { setState({ status: "error", error: r.error }); return; }
      setState({ status: "ready", sections: (r.data && r.data.sections) || [] });
    });
    return () => { live = false; };
  }, []);

  const ready = state.status === "ready" && state.sections.length > 0;
  const titleById = {};
  if (ready) state.sections.forEach(s => { titleById[s.id] = s.title; });

  return (
    <div className="workspace-view scroll help-view">
        <p className="eyebrow">Help &amp; tips</p>

        {state.status === "loading" && <p className="help-empty">Loading help…</p>}
        {state.status === "error" && <p className="help-empty">Couldn't load help: {state.error}</p>}
        {state.status === "ready" && state.sections.length === 0 && <p className="help-empty">No help content yet.</p>}

        {ready &&
          <>
            <HelpChat titleById={titleById} />
            <div className="help-layout">
              <nav className="help-toc">
                {state.sections.map(s =>
                  <button key={s.id} className="help-toc-item" onClick={() => flashHelpSection(s.id)}>{s.title}</button>)}
              </nav>
              <div className="help-content">
                {state.sections.map(s =>
                  <section key={s.id} id={"help-" + s.id} className="help-section">
                    <h4 className="help-section-title">{s.title}</h4>
                    <div className="help-body" dangerouslySetInnerHTML={{ __html: s.html }} />
                  </section>)}
              </div>
            </div>
          </>}
    </div>
  );
}
