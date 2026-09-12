// In-reader PDF find/search (inc 590, backlog #42). Searches the ALREADY-RENDERED text layer rather than
// pulling in pdf.js's FindController — the viewer uses a custom getDocument + renderTextLayer pipeline, not
// pdf.js's PDFViewer/EventBus component stack that FindController requires, so retrofitting that stack would be
// a large, risky change. Every page already renders real selectable text into `.textLayer span` elements, so we
// search that DOM directly: fully local, no new dependency, and it finds exactly what is visually present.
//
// Highlighting draws overlay rectangles (computed from a DOM Range's client rects) into a per-page
// `.pdf-find-layer`, mirroring renderUserAnnotations' percentage-of-page overlay pattern — it never mutates the
// text layer, so native selection + annotations are untouched, and cross-line matches paint one rect per line.

const PDF_FIND_MATCH_CAP = 500;  // bound the work + overlay count on a huge doc; disclosed in the count as "500+"

// Pure, testable: every start index of `needle` in `haystack` (case-insensitive, overlapping not counted).
// Returns [] for an empty needle. Kept free of the DOM so it can be unit-tested from string literals.
function findAllMatchStarts(haystack, needle) {
  if (!haystack || !needle) return [];
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  const starts = [];
  let from = 0;
  while (starts.length < PDF_FIND_MATCH_CAP) {
    const i = h.indexOf(n, from);
    if (i === -1) break;
    starts.push(i);
    from = i + n.length;  // non-overlapping: resume past this match
  }
  return starts;
}

// Pure, testable: build a page's concatenated text + a map of char-range → text node, from an ordered list of
// {textContent, length} segments (the real caller passes DOM text nodes; a test can pass plain objects). Returns
// { text, segments:[{seg, start, end}] } where [start,end) is the segment's char span in `text`.
function buildPageTextIndex(segments) {
  let text = "";
  const spans = [];
  for (const seg of segments) {
    const s = seg.textContent != null ? seg.textContent : "";
    if (!s) continue;
    spans.push({ seg, start: text.length, end: text.length + s.length });
    text += s;
  }
  return { text, spans };
}

// The find bar: a small toolbar-styled control with input, prev/next, count, and close. Pure presentational —
// all state + search logic lives in usePdfFind. Enter = next, Shift+Enter = prev, Escape = close.
function PdfFindBar({ query, onQuery, count, current, onPrev, onNext, onClose, inputRef }) {
  return (
    <div className="pdf-find-bar" role="search">
      <input
        ref={inputRef}
        className="pdf-find-input"
        type="text"
        placeholder="Find in document…"
        aria-label="Find in document"
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); e.shiftKey ? onPrev() : onNext(); }
          else if (e.key === "Escape") { e.preventDefault(); onClose(); }
        }}
      />
      <span className="pdf-find-count">
        {query
          ? (count === 0 ? "No matches" : `${current} / ${count >= PDF_FIND_MATCH_CAP ? PDF_FIND_MATCH_CAP + "+" : count}`)
          : ""}
      </span>
      <button className="pdf-find-btn" onClick={onPrev} disabled={count === 0} title="Previous match (Shift+Enter)" aria-label="Previous match">▴</button>
      <button className="pdf-find-btn" onClick={onNext} disabled={count === 0} title="Next match (Enter)" aria-label="Next match">▾</button>
      <button className="pdf-find-btn pdf-find-close" onClick={onClose} title="Close find (Esc)" aria-label="Close find">✕</button>
    </div>
  );
}

// The find engine hook. Searches every rendered page's text layer for `query`, paints overlay rects for each
// match, tracks a current match (scrolled into view + emphasized), and exposes prev/next. `recompute()` is
// called by the viewer after a (re)render while find is open, so highlights survive zoom / fit-mode changes.
function usePdfFind({ pagesRef, scrollRef }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [count, setCount] = useState(0);
  const [current, setCurrent] = useState(0);   // 1-based index of the emphasized match (0 = none)
  const inputRef = useRef(null);
  const matchesRef = useRef([]);                // ordered [{ box, pageEl }] across all pages, in document order
  const currentRef = useRef(0);                 // 0-based index into matchesRef

  const clearHighlights = useCallback(() => {
    const host = pagesRef.current;
    if (host) host.querySelectorAll(".pdf-find-layer").forEach((l) => l.remove());
    matchesRef.current = [];
    currentRef.current = 0;
    setCount(0);
    setCurrent(0);
  }, [pagesRef]);

  // Emphasize the current match + scroll it into view. `smooth` is off on recompute (avoid a lurch on zoom).
  const focusCurrent = useCallback((smooth) => {
    const matches = matchesRef.current;
    matches.forEach((m, i) => m.box.classList.toggle("current", i === currentRef.current));
    const m = matches[currentRef.current];
    if (m && m.box.scrollIntoView) m.box.scrollIntoView({ block: "center", behavior: smooth ? "smooth" : "auto" });
    setCurrent(matches.length ? currentRef.current + 1 : 0);
  }, []);

  // Walk one page's text nodes → concatenated string + node map; find matches; draw an overlay rect per line
  // fragment of each match into the page's find layer. Returns the page's match boxes in reading order.
  const highlightPage = useCallback((pageEl, needle) => {
    const textLayer = pageEl.querySelector(".textLayer");
    if (!textLayer) return [];
    const wrapRect = pageEl.getBoundingClientRect();
    if (!(wrapRect.width > 0 && wrapRect.height > 0)) return [];
    // Ordered text nodes → index. TreeWalker keeps DOM order, so char offsets map back to (node, localOffset).
    const nodes = [];
    const walker = document.createTreeWalker(textLayer, NodeFilter.SHOW_TEXT, null);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      nodes.push({ textContent: node.textContent, node });
    }
    const { text, spans } = buildPageTextIndex(nodes);
    const starts = findAllMatchStarts(text, needle);
    if (starts.length === 0) return [];
    const layer = document.createElement("div");
    layer.className = "pdf-find-layer";
    pageEl.appendChild(layer);
    const boxes = [];
    for (const start of starts) {
      const end = start + needle.length;
      const from = spans.find((s) => start >= s.start && start < s.end);
      const to = spans.find((s) => end > s.start && end <= s.end);
      if (!from || !to) continue;  // match fell outside mapped nodes (defensive)
      let range;
      try {
        range = document.createRange();
        range.setStart(from.seg.node, start - from.start);
        range.setEnd(to.seg.node, end - to.start);
      } catch (_) { continue; }
      const rects = range.getClientRects();
      let firstBox = null;
      for (const r of rects) {
        if (!(r.width > 0 && r.height > 0)) continue;
        const box = document.createElement("div");
        box.className = "pdf-find-hit";
        box.style.left = `${((r.left - wrapRect.left) / wrapRect.width) * 100}%`;
        box.style.top = `${((r.top - wrapRect.top) / wrapRect.height) * 100}%`;
        box.style.width = `${(r.width / wrapRect.width) * 100}%`;
        box.style.height = `${(r.height / wrapRect.height) * 100}%`;
        layer.appendChild(box);
        if (!firstBox) firstBox = box;
      }
      if (firstBox) boxes.push({ box: firstBox, pageEl });  // one entry per match (its first line fragment)
    }
    return boxes;
  }, []);

  // (Re)run the search across all pages. `preserveIndex` keeps the current match position across a zoom
  // recompute; a fresh query resets to the first match.
  const recompute = useCallback((preserveIndex) => {
    const host = pagesRef.current;
    if (host) host.querySelectorAll(".pdf-find-layer").forEach((l) => l.remove());
    const needle = query.trim();
    if (!host || !needle) { matchesRef.current = []; currentRef.current = 0; setCount(0); setCurrent(0); return; }
    const all = [];
    host.querySelectorAll(".pdf-page-wrap").forEach((pageEl) => {
      for (const m of highlightPage(pageEl, needle)) all.push(m);
    });
    matchesRef.current = all;
    setCount(all.length);
    if (all.length === 0) { currentRef.current = 0; setCurrent(0); return; }
    currentRef.current = preserveIndex ? Math.min(currentRef.current, all.length - 1) : 0;
    focusCurrent(!preserveIndex);
  }, [pagesRef, query, highlightPage, focusCurrent]);

  // Re-search whenever the query changes while open (debounced lightly so typing stays responsive).
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => recompute(false), 120);
    return () => clearTimeout(t);
  }, [query, open, recompute]);

  const step = useCallback((dir) => {
    const n = matchesRef.current.length;
    if (!n) return;
    currentRef.current = (((currentRef.current + dir) % n) + n) % n;  // wraps
    focusCurrent(true);
  }, [focusCurrent]);

  const openFind = useCallback(() => {
    setOpen(true);
    setTimeout(() => { if (inputRef.current) { inputRef.current.focus(); inputRef.current.select(); } }, 0);
  }, []);
  const closeFind = useCallback(() => { setOpen(false); clearHighlights(); }, [clearHighlights]);

  // Ctrl/Cmd+F opens find when THIS viewer is visible (a background viewer never hijacks the shortcut, and we
  // override the browser's own find, which can't usefully see the custom-rendered text layer). Esc-to-close lives
  // on the find input (PdfFindBar). Guarding on scrollRef visibility keeps the listener scoped to the live reader.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "f" || !(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey) return;
      if (!scrollRef.current || scrollRef.current.offsetParent === null) return;
      e.preventDefault();
      openFind();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [scrollRef, openFind]);

  return {
    open, query, count, current, inputRef,
    setQuery, openFind, closeFind,
    next: () => step(1), prev: () => step(-1),
    recompute,  // the viewer calls this after a re-render while find is open
  };
}
