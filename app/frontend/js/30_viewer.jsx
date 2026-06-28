// buildAnnotationDigest (the highlights/notes Markdown digest) lives in 00_lib.jsx (a pure util; relocated inc 175).

function PdfViewer({ paperId, title, target, annoRefresh }) {
  const [state, setState] = useState({ status: "loading" });
  const [scale, setScale] = useState(1.15);
  const [page, setPage] = useState(1);
  const [annotations, setAnnotations] = useState([]);
  const [picker, setPicker] = useState(null);   // { left, top, page, bboxes, anchorText, prefix, suffix }
  const [editor, setEditor] = useState(null);   // { id, left, top, note, color, anchorText, page }
  const [panelOpen, setPanelOpen] = useState(false);
  const [notice, setNotice] = useState(null);   // transient error/info toast
  const [dpr, setDpr] = useState(() => (typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1));
  const [pageView, setPageView] = useState(() => {
    const v = _loadLayout("callosum.pageView", "page");   // "page" (manual zoom) | "width" (fit) | "two" (two-up)
    return v === "width" || v === "two" ? v : "page";
  });
  const docRef = useRef(null);
  const baseWidthRef = useRef(0);   // page-1 unscaled width (pdf points) — the basis for fit-width / two-up scale
  const scrollRef = useRef(null);
  const pagesRef = useRef(null);
  const tokenRef = useRef(0);
  const annotationsRef = useRef([]);
  const noticeTimer = useRef(null);
  const restoredPaperRef = useRef(null);  // inc 175: which paperId's remembered scroll has been restored (once per open)
  const lastScrollSaveRef = useRef(0);     // inc 175: throttle the per-paper scroll-position write

  // Surface a transient message (e.g. a failed save) so API errors aren't silent.
  const flashNotice = useCallback((msg) => {
    setNotice(msg);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), 5000);
  }, []);

  // Re-render when devicePixelRatio changes (HiDPI / browser-level Ctrl+- zoom) so the
  // canvas backing store and text layer stay in sync. matchMedia('(resolution: Ndppx)')
  // fires when the DPR leaves N, so we re-arm for the new value each time.
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    let mq = null;
    const onChange = () => { setDpr(window.devicePixelRatio || 1); arm(); };
    const arm = () => {
      if (mq) (mq.removeEventListener ? mq.removeEventListener("change", onChange) : mq.removeListener(onChange));
      mq = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      mq.addEventListener ? mq.addEventListener("change", onChange) : mq.addListener(onChange);
    };
    arm();
    return () => { if (mq) (mq.removeEventListener ? mq.removeEventListener("change", onChange) : mq.removeListener(onChange)); };
  }, []);

  // Fetch the PDF bytes (honest 404 handling) and parse the document once.
  useEffect(() => {
    let cancelled = false;
    const token = ++tokenRef.current;
    setState({ status: "loading" });
    setPage(1);
    (async () => {
      let pdfjsLib;
      try {
        pdfjsLib = await loadPdfJs();
      } catch (e) {
        if (!cancelled) setState({ status: "error", error: "Could not load the PDF renderer (PDF.js) from the CDN." });
        return;
      }
      let res;
      try {
        res = await fetch(API_BASE + `/papers/${paperId}/pdf`, { headers: { "Accept": "application/pdf" } });
      } catch (e) {
        if (!cancelled) setState({ status: "error", error: `Could not reach the ${API_LABEL}. Is uvicorn running?` });
        return;
      }
      if (res.status === 404) { if (!cancelled) setState({ status: "unavailable" }); return; }
      if (!res.ok) { if (!cancelled) setState({ status: "error", error: `HTTP ${res.status} fetching the PDF.` }); return; }
      try {
        const buf = await res.arrayBuffer();
        const doc = await pdfjsLib.getDocument({ data: buf }).promise;
        if (cancelled || token !== tokenRef.current) return;
        docRef.current = doc;
        try {
          baseWidthRef.current = (await doc.getPage(1)).getViewport({ scale: 1 }).width;
        } catch (e) { baseWidthRef.current = 0; }
        if (cancelled || token !== tokenRef.current) return;
        setState({ status: "ready", numPages: doc.numPages });
      } catch (e) {
        if (!cancelled && token === tokenRef.current) setState({ status: "error", error: "This file could not be rendered as a PDF." });
      }
    })();
    return () => { cancelled = true; };
  }, [paperId]);

  // Load this paper's user highlights once per paper. Reset any transient UI.
  useEffect(() => {
    let cancelled = false;
    setAnnotations([]);
    setPicker(null);
    setEditor(null);
    (async () => {
      const r = await api(`/papers/${paperId}/annotations`);
      if (!cancelled && r.ok && Array.isArray(r.data)) setAnnotations(r.data);
    })();
    return () => { cancelled = true; };
  }, [paperId]);

  // Refetch when an external action (e.g. saving a highlight from the synthesis pane)
  // bumps annoRefresh, so an already-open viewer shows the new highlight without a reload.
  // No clear-then-fetch here — the list is replaced on success → no flicker. The mount run
  // is skipped (the [paperId] effect above already did the initial load).
  const annoRefreshMounted = useRef(false);
  useEffect(() => {
    if (!annoRefreshMounted.current) { annoRefreshMounted.current = true; return; }
    let cancelled = false;
    (async () => {
      const r = await api(`/papers/${paperId}/annotations`);
      if (!cancelled && r.ok && Array.isArray(r.data)) setAnnotations(r.data);
    })();
    return () => { cancelled = true; };
  }, [annoRefresh]);

  // Keep the imperative-DOM handlers' view of annotations fresh, and (re)draw the
  // overlays whenever the set changes or pages re-render (zoom).
  useEffect(() => {
    annotationsRef.current = annotations;
    if (state.status === "ready") renderUserAnnotations(pagesRef.current, annotations);
  }, [annotations, state.status, scale]);

  // (Re)render every page to a canvas whenever the document or zoom changes.
  useEffect(() => {
    if (state.status !== "ready") return;
    const doc = docRef.current;
    const host = pagesRef.current;
    if (!doc || !host) return;
    let cancelled = false;
    host.innerHTML = "";
    (async () => {
      for (let n = 1; n <= doc.numPages; n++) {
        if (cancelled) return;
        let pdfPage;
        try { pdfPage = await doc.getPage(n); } catch (e) { return; }
        if (cancelled) return;
        const viewport = pdfPage.getViewport({ scale });
        const dpr = window.devicePixelRatio || 1;
        const cssW = viewport.width;   // exact, un-floored — the shared CSS box for every layer
        const cssH = viewport.height;
        const pageWrap = document.createElement("div");
        pageWrap.className = "pdf-page-wrap";
        pageWrap.dataset.page = String(n);
        pageWrap.dataset.sourceWidth = String(viewport.width / scale);
        pageWrap.dataset.sourceHeight = String(viewport.height / scale);
        pageWrap.dataset.rotation = String(viewport.rotation || 0);
        pageWrap.style.width = `${cssW}px`;
        pageWrap.style.height = `${cssH}px`;
        const canvas = document.createElement("canvas");
        canvas.className = "pdf-page";
        // Backing store at device resolution (crisp on HiDPI / browser zoom); CSS box at the
        // exact viewport size so it matches the text layer + overlays pixel-for-pixel.
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(cssH * dpr);
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
        pageWrap.appendChild(canvas);
        // Layer order (bottom→top): canvas, user-highlight layer, citation layer,
        // text layer. The text layer sits on top so native selection works; user
        // highlights are pointer-events:none and removed via click hit-testing.
        const annotationLayer = document.createElement("div");
        annotationLayer.className = "pdf-annotation-layer";
        pageWrap.appendChild(annotationLayer);
        const highlightLayer = document.createElement("div");
        highlightLayer.className = "pdf-highlight-layer";
        pageWrap.appendChild(highlightLayer);
        const textLayerDiv = document.createElement("div");
        textLayerDiv.className = "textLayer";
        textLayerDiv.style.width = `${cssW}px`;
        textLayerDiv.style.height = `${cssH}px`;
        textLayerDiv.style.setProperty("--scale-factor", String(scale));
        pageWrap.appendChild(textLayerDiv);
        host.appendChild(pageWrap);
        try {
          await pdfPage.render({
            canvasContext: canvas.getContext("2d"),
            viewport,
            transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
          }).promise;
        } catch (e) {
          if (cancelled) return;
        }
        if (cancelled) return;
        // Render the invisible, selectable text layer. Failure here only costs
        // selection on that page; the canvas + overlays still work.
        try {
          const textContent = await pdfPage.getTextContent();
          if (cancelled) return;
          const task = pdfjsLib.renderTextLayer({
            textContentSource: textContent,
            textContent,
            container: textLayerDiv,
            viewport,
            textDivs: [],
          });
          if (task && task.promise) await task.promise;
        } catch (e) {
          if (cancelled) return;
        }
      }
      if (!cancelled) {
        applyPdfCitationTarget(scrollRef.current, host, target);
        renderUserAnnotations(host, annotationsRef.current);
        // inc 175: restore remembered scroll once per paper-open (a citation target wins; not on zoom re-renders).
        if (restoredPaperRef.current !== paperId) {
          restoredPaperRef.current = paperId;
          const saved = !target && scrollRef.current ? Number(localStorage.getItem("callosum.pdfScroll." + paperId)) : 0;
          if (saved > 0) scrollRef.current.scrollTop = saved;
        }
      }
    })();
    return () => { cancelled = true; };
  }, [state.status, state.numPages, scale, target, dpr]);

  useEffect(() => {
    if (state.status !== "ready") return;
    applyPdfCitationTarget(scrollRef.current, pagesRef.current, target);
  }, [state.status, target]);

  // Keep the page indicator in sync with scrolling (topmost visible page).
  const onScroll = useCallback(() => {
    const scroller = scrollRef.current;
    const host = pagesRef.current;
    if (!scroller || !host || host.children.length === 0) return;
    const top = scroller.getBoundingClientRect().top;
    let current = 1;
    for (let i = 0; i < host.children.length; i++) {
      if (host.children[i].getBoundingClientRect().top - top <= 64) current = Number(host.children[i].dataset.page || i + 1);
    }
    setPage(p => (p === current ? p : current));
    if (paperId != null && Date.now() - lastScrollSaveRef.current > 500) {  // inc 175: remember scroll per paper
      lastScrollSaveRef.current = Date.now();
      try { localStorage.setItem("callosum.pdfScroll." + paperId, String(scroller.scrollTop)); } catch (e) {}
    }
  }, [paperId]);

  // Manual zoom drops out of any fit mode (fit-width / two-up auto-compute the scale).
  const zoom = useCallback((delta) => {
    setPageView("page");
    _saveLayout("callosum.pageView", "page");
    setScale(s => Math.min(3, Math.max(0.5, Math.round((s + delta) * 100) / 100)));
  }, []);

  const changePageView = useCallback((next) => {
    setPageView(next);
    _saveLayout("callosum.pageView", next);
  }, []);

  // Fit-to-width / two-up: derive `scale` from the scroller's width so one (or two) pages fill it, re-fitting on
  // resize. This feeds the SAME single-scale render pipeline below (the inc-34 alignment invariant is intact — it
  // only chooses the scale value). Manual ("page") mode leaves `scale` to the zoom buttons. `floor` keeps two
  // pages from overflowing the row by a rounding hair.
  useEffect(() => {
    if (state.status !== "ready" || pageView === "page") return;
    const PAD = 16, GAP = 12;   // matches the .pdf-pages padding + gap
    const cols = pageView === "two" ? 2 : 1;
    const fit = () => {
      const el = scrollRef.current, base = baseWidthRef.current;
      if (!el || !base) return;
      const avail = el.clientWidth - 2 * PAD - (cols - 1) * GAP;
      if (avail <= 0) return;
      const s = Math.min(3, Math.max(0.2, Math.floor((avail / (cols * base)) * 100) / 100));
      setScale(prev => (prev === s ? prev : s));
    };
    fit();
    let ro = null;
    if (typeof ResizeObserver !== "undefined" && scrollRef.current) {
      ro = new ResizeObserver(fit);
      ro.observe(scrollRef.current);
    }
    return () => { if (ro) ro.disconnect(); };
  }, [pageView, state.status]);

  // On text selection, map the selection's per-line client rects into the
  // increment-29 coordinate basis (page-relative PDF points) and offer a color.
  const onPagesMouseUp = useCallback(() => {
    const host = pagesRef.current;
    if (!host) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) { setPicker(null); return; }
    const range = sel.getRangeAt(0);
    const startEl = range.startContainer.nodeType === 3 ? range.startContainer.parentElement : range.startContainer;
    const pageWrap = startEl && startEl.closest ? startEl.closest(".pdf-page-wrap") : null;
    if (!pageWrap || !host.contains(pageWrap)) { setPicker(null); return; }
    const textLayer = pageWrap.querySelector(".textLayer");
    if (!textLayer || !textLayer.contains(range.startContainer)) { setPicker(null); return; }
    const anchorText = sel.toString().trim();
    if (!anchorText) { setPicker(null); return; }

    const pageNum = Number(pageWrap.dataset.page);
    const sourceWidth = Number(pageWrap.dataset.sourceWidth);
    const sourceHeight = Number(pageWrap.dataset.sourceHeight);
    const wrapRect = pageWrap.getBoundingClientRect();
    if (!(wrapRect.width > 0 && wrapRect.height > 0 && sourceWidth > 0 && sourceHeight > 0)) { setPicker(null); return; }
    // points-per-displayed-px (robust to CSS down-scaling, not just `scale`).
    const sx = sourceWidth / wrapRect.width;
    const sy = sourceHeight / wrapRect.height;

    const bboxes = [];
    const clientRects = Array.from(range.getClientRects());
    clientRects.forEach(r => {
      if (r.width < 1 || r.height < 1) return;
      const x0 = (r.left - wrapRect.left) * sx;
      const y0 = (r.top - wrapRect.top) * sy;
      const x1 = (r.right - wrapRect.left) * sx;
      const y1 = (r.bottom - wrapRect.top) * sy;
      if (x1 <= x0 || y1 <= y0) return;
      bboxes.push({ page: pageNum, x0, y0, x1, y1 });
    });
    if (bboxes.length === 0) { setPicker(null); return; }

    const ctx = selectionContext(textLayer, range);
    const last = clientRects[clientRects.length - 1];
    setPicker({
      left: Math.max(8, Math.min(window.innerWidth - 190, last.left)),
      top: Math.max(8, Math.min(window.innerHeight - 44, last.bottom + 6)),
      page: pageNum, bboxes, anchorText, prefix: ctx.prefix, suffix: ctx.suffix,
    });
  }, []);

  const createHighlight = useCallback(async (color) => {
    if (!picker) return;
    const body = {
      page: picker.page,
      color,
      bboxes: picker.bboxes,
      anchor_text: picker.anchorText,
      prefix: picker.prefix || null,
      suffix: picker.suffix || null,
    };
    setPicker(null);
    const sel = window.getSelection();
    if (sel) sel.removeAllRanges();
    const r = await apiPost(`/papers/${paperId}/annotations`, body);
    if (r.ok && r.data) setAnnotations(prev => [...prev, r.data]);
    else flashNotice("Couldn't save highlight — " + (r.error || "unknown error"));
  }, [picker, paperId, flashNotice]);

  // Open the note/color editor for an annotation, anchored near (x, y).
  const openEditor = useCallback((ann, x, y) => {
    setEditor({
      id: ann.id,
      note: ann.note || "",
      color: ann.color || HIGHLIGHT_COLORS[0],
      anchorText: ann.anchor_text || "",
      page: ann.page,
      left: Math.max(8, Math.min(window.innerWidth - 268, x)),
      top: Math.max(8, Math.min(window.innerHeight - 210, y)),
    });
  }, []);

  // From the create picker: make the highlight (default color), then immediately open
  // the note editor on it so the user can type a comment + adjust the color.
  const createHighlightWithNote = useCallback(async () => {
    if (!picker) return;
    const pos = { left: picker.left, top: picker.top };
    const body = {
      page: picker.page,
      color: HIGHLIGHT_COLORS[0],
      bboxes: picker.bboxes,
      anchor_text: picker.anchorText,
      prefix: picker.prefix || null,
      suffix: picker.suffix || null,
    };
    setPicker(null);
    const sel = window.getSelection();
    if (sel) sel.removeAllRanges();
    const r = await apiPost(`/papers/${paperId}/annotations`, body);
    if (r.ok && r.data) {
      setAnnotations(prev => [...prev, r.data]);
      openEditor(r.data, pos.left, pos.top);
    } else {
      flashNotice("Couldn't save highlight — " + (r.error || "unknown error"));
    }
  }, [picker, paperId, openEditor, flashNotice]);

  // Plain click (not a selection drag) inside a highlight → open its note/color editor.
  const onPagesClick = useCallback((e) => {
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) return;
    const host = pagesRef.current;
    if (!host || !e.target || !e.target.closest) return;
    const pageWrap = e.target.closest(".pdf-page-wrap");
    if (!pageWrap || !host.contains(pageWrap)) { setEditor(null); return; }
    const pageNum = Number(pageWrap.dataset.page);
    const sourceWidth = Number(pageWrap.dataset.sourceWidth);
    const sourceHeight = Number(pageWrap.dataset.sourceHeight);
    const wrapRect = pageWrap.getBoundingClientRect();
    if (!(wrapRect.width > 0 && wrapRect.height > 0)) return;
    const px = (e.clientX - wrapRect.left) * (sourceWidth / wrapRect.width);
    const py = (e.clientY - wrapRect.top) * (sourceHeight / wrapRect.height);
    const hit = [...annotationsRef.current].reverse().find(ann =>
      Number(ann.page) === pageNum &&
      normalizeBboxes(ann.bboxes_json).some(rect =>
        (rect.page == null || rect.page === pageNum) &&
        px >= rect.x0 && px <= rect.x1 && py >= rect.y0 && py <= rect.y1
      )
    );
    if (!hit) { setEditor(null); return; }
    openEditor(hit, e.clientX, e.clientY + 6);
  }, [openEditor]);

  const saveEdit = useCallback(async () => {
    if (!editor) return;
    const { id, note, color } = editor;
    setEditor(null);
    const r = await apiPatch(`/annotations/${id}`, { note: note && note.trim() ? note : null, color });
    if (r.ok && r.data) setAnnotations(prev => prev.map(a => (a.id === id ? r.data : a)));
    else flashNotice("Couldn't save note — " + (r.error || "unknown error"));
  }, [editor, flashNotice]);

  const deleteAnnotation = useCallback(async (id) => {
    setEditor(null);
    const r = await apiDelete(`/annotations/${id}`);
    if (r.ok) setAnnotations(prev => prev.filter(a => a.id !== id));
    else flashNotice("Couldn't delete highlight — " + (r.error || "unknown error"));
  }, [flashNotice]);

  // inc-144: copy / download the paper's highlights + notes as a Markdown digest (the close reader's "get my
  // marks out"). navigator.clipboard is fine on the 127.0.0.1 secure context (cf. the inc-70 citation copy).
  const copyDigest = useCallback(() => {
    navigator.clipboard.writeText(buildAnnotationDigest(title, annotations))
      .then(() => flashNotice("Highlights + notes copied"))
      .catch(() => flashNotice("Couldn't copy — try Export .md"));
  }, [title, annotations, flashNotice]);
  const exportDigest = useCallback(() => {
    const blob = new Blob([buildAnnotationDigest(title, annotations)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const el = document.createElement("a");
    el.href = url;
    el.download = (title || "highlights").replace(/[^\w.-]+/g, "_").slice(0, 60) + "-notes.md";
    document.body.appendChild(el);
    el.click();
    el.remove();
    URL.revokeObjectURL(url);
  }, [title, annotations]);

  // Scroll the viewer to an annotation's page and briefly flash its highlight.
  const jumpToAnnotation = useCallback((ann) => {
    const host = pagesRef.current;
    if (!host) return;
    const pageEl = host.querySelector(`[data-page="${ann.page}"]`);
    if (pageEl) pageEl.scrollIntoView({ block: "center", behavior: "smooth" });
    host.querySelectorAll(`.pdf-user-highlight[data-annotation-id="${ann.id}"]`).forEach(b => {
      b.classList.remove("flash");
      void b.offsetWidth;  // reflow to restart the animation
      b.classList.add("flash");
      setTimeout(() => b.classList.remove("flash"), 1300);
    });
  }, []);

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <span className="pdf-title" title={title}>{title}</span>
        <span className="pdf-spacer"></span>
        {state.status === "ready" &&
          <>
            <span className="pdf-zoom">
              <button onClick={() => zoom(-0.2)} title="Zoom out">−</button>
              <span className="pdf-zoom-val">{Math.round(scale * 100)}%</span>
              <button onClick={() => zoom(0.2)} title="Zoom in">+</button>
            </span>
            <button className={"pdf-annot-toggle" + (pageView === "width" ? " active" : "")}
                    onClick={() => changePageView(pageView === "width" ? "page" : "width")}
                    title="Fit the page width to the window">Fit width</button>
            <button className={"pdf-annot-toggle" + (pageView === "two" ? " active" : "")}
                    onClick={() => changePageView(pageView === "two" ? "page" : "two")}
                    title="Two pages side by side">Two-up</button>
            <span className="pdf-pageind">Page {page} / {state.numPages}</span>
            <button className={"pdf-annot-toggle" + (panelOpen ? " active" : "")}
                    onClick={() => setPanelOpen(o => !o)} title="Show annotations for this paper">
              Notes ({annotations.length})
            </button>
          </>}
      </div>
      <div className="pdf-body">
        <div className="pdf-scroll" ref={scrollRef} onScroll={onScroll} onMouseUp={onPagesMouseUp} onClick={onPagesClick}>
          {state.status === "loading" &&
            <div className="state"><div className="big">Opening PDF…</div>Streaming and rendering the document.</div>}
          {state.status === "unavailable" &&
            <div className="state">
              <div className="big">PDF not available locally</div>
              This paper has no local PDF file — it may be a URL-only or metadata-only entry.
            </div>}
          {state.status === "error" &&
            <div className="errbox" style={{ margin: "18px" }}>
              <b>Couldn't open this PDF.</b><br />{state.error}
            </div>}
          <div className={"pdf-pages" + (pageView === "two" ? " pdf-two-up" : "")} ref={pagesRef}
               style={{ display: state.status === "ready" ? "flex" : "none" }}></div>
        </div>
        {panelOpen && state.status === "ready" &&
          <div className="pdf-annot-panel">
            <div className="pdf-annot-head">Annotations <span>· {annotations.length}</span>
              {annotations.length > 0 &&
                <span className="pdf-annot-export">
                  <button className="btn-link" onClick={copyDigest} title="Copy all highlights + notes as text">Copy</button>
                  <button className="btn-link" onClick={exportDigest} title="Download highlights + notes as a Markdown file">Export .md</button>
                </span>}
            </div>
            {annotations.length === 0 &&
              <div className="pdf-annot-empty">No highlights yet. Select text in the PDF to add one, then click it to add a note.</div>}
            {annotations.map(a =>
              <div key={a.id} className="pdf-annot-item">
                <div className="pdf-annot-row" onClick={() => jumpToAnnotation(a)} title="Jump to this highlight">
                  <span className="pdf-annot-chip" style={{ background: a.color }}></span>
                  <span className="pdf-annot-page">p.{a.page}</span>
                  <span className="pdf-annot-snip">{(a.anchor_text || "").slice(0, 90) || "(no text)"}</span>
                </div>
                {a.note && <div className="pdf-annot-note">{a.note}</div>}
                <div className="pdf-annot-actions">
                  <button onClick={(e) => openEditor(a, e.clientX - 250, e.clientY + 6)}>{a.note ? "Edit note" : "Add note"}</button>
                  <button className="danger" onClick={() => deleteAnnotation(a.id)}>Delete</button>
                </div>
              </div>)}
          </div>}
      </div>
      {picker &&
        <div className="hl-picker" style={{ left: picker.left, top: picker.top }} onMouseDown={e => e.preventDefault()}>
          {HIGHLIGHT_COLORS.map(c =>
            <span key={c} className="hl-swatch" style={{ background: c }} title="Highlight with this color"
                  onClick={() => createHighlight(c)} />)}
          <button className="hl-note-add" title="Highlight and add a note" onClick={createHighlightWithNote}>✎ note</button>
        </div>}
      {editor &&
        <div className="hl-editor" style={{ left: editor.left, top: editor.top }}>
          <textarea className="hl-note" placeholder="Add a note…" value={editor.note} autoFocus
                    maxLength={4000}
                    onChange={e => setEditor(ed => ({ ...ed, note: e.target.value }))} />
          <div className="hl-editor-swatches">
            {HIGHLIGHT_COLORS.map(c =>
              <span key={c} className={"hl-swatch" + (editor.color === c ? " sel" : "")} style={{ background: c }}
                    title={`Color ${c}`} onClick={() => setEditor(ed => ({ ...ed, color: c }))} />)}
          </div>
          <div className="hl-editor-actions">
            <button className="btn btn-ghost danger" onClick={() => deleteAnnotation(editor.id)}>Delete</button>
            <span style={{ flex: 1 }}></span>
            <button className="btn btn-ghost" onClick={() => setEditor(null)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveEdit}>Save</button>
          </div>
        </div>}
      {notice &&
        <div className="pdf-toast" role="alert" onClick={() => setNotice(null)}>{notice}</div>}
    </div>
  );
}

// The middle column: a persistent Library tab plus one tab per open PDF.
// PDF tabs stay mounted (hidden) so switching back doesn't re-stream them.
function LibraryFrame({ libraryProps, tabs, activeTab, onActivate, onClose, onOpenPdf, onSummarizePapers, onSelectPaper, annoRefresh, readingMode, onToggleReading }) {
  return (
    <div className="lib-frame">
      <div className="frame-tabs">
        <button
          className={"frame-tab" + (activeTab === "library" ? " active" : "")}
          onClick={() => onActivate("library")}
        >Library</button>
        {tabs.map(t => (
          <span
            key={t.key}
            className={"frame-tab" + (activeTab === t.key ? " active" : "")}
            onClick={() => onActivate(t.key)}
          >
            <span className="frame-tab-label" title={t.title}>{t.title}</span>
            <button
              className="frame-tab-close"
              title="Close tab"
              onClick={(e) => { e.stopPropagation(); onClose(t.key); }}
            >×</button>
          </span>
        ))}
        {onToggleReading &&
          <button
            className={"frame-reading" + (readingMode ? " active" : "")}
            title={readingMode ? "Exit reading mode (Esc)" : "Reading mode — hide the side panels and focus the center pane"}
            onClick={onToggleReading}
          >{readingMode ? "⤢ Exit" : "⛶ Read"}</button>}
      </div>
      <div className="frame-pane" style={{ display: activeTab === "library" ? "flex" : "none" }}>
        <PaperList {...libraryProps} onOpenPdf={onOpenPdf} />
      </div>
      {tabs.map(t => (
        <div key={t.key} className="frame-pane" style={{ display: activeTab === t.key ? "flex" : "none" }}>
          {t.type === "dashboard"
            ? <MyPubsDashboard axisId={t.axisId} onSummarize={onSummarizePapers} onSelectPaper={onSelectPaper} onOpenPdf={onOpenPdf} />
            : <PdfViewer paperId={t.paperId} title={t.title} target={t.target || null} annoRefresh={annoRefresh} />}
        </div>
      ))}
    </div>
  );
}

