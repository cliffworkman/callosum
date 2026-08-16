// Text-selection -> highlight-picker mapping split from 30_viewer.jsx (rule #1 -- the demo-mode annotation guards
// pushed it over the 600-line cap). usePagesMouseUpHandler (a hook) hoists in the shared IIFE, so PdfViewer (in
// 30_viewer, textually before) references it regardless of chunk load order.

// On text selection, map the selection's per-line client rects into the increment-29 coordinate basis
// (page-relative PDF points) and offer a color -- or, if a workbench cell has armed "select in PDF" (inc 255
// SP2a-2), capture the selection as that cell's exact anchor instead and skip the highlight picker entirely.
function usePagesMouseUpHandler({ pagesRef, armedRef, setPicker }) {
  return useCallback(() => {
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

    // inc 255 (workbench SP2a-2): if a cell has armed "select in PDF", capture THIS selection as the cell's exact
    // anchor -- its verbatim text (the value the human vets + edits) + a single union bbox -- and skip the highlight
    // picker entirely. Nothing is parsed or inferred; the coordinate is a real drawn rectangle -> exact precision.
    const armed = armedRef.current;
    if (armed) {
      armed.cb({ page: pageNum, bbox: wbUnionRect(bboxes), quote: anchorText });
      const sel2 = window.getSelection();
      if (sel2) sel2.removeAllRanges();
      setPicker(null);
      return;
    }

    const ctx = selectionContext(textLayer, range);
    const last = clientRects[clientRects.length - 1];
    setPicker({
      left: Math.max(8, Math.min(window.innerWidth - 190, last.left)),
      top: Math.max(8, Math.min(window.innerHeight - 44, last.bottom + 6)),
      page: pageNum, bboxes, anchorText, prefix: ctx.prefix, suffix: ctx.suffix,
    });
  }, []);
}
