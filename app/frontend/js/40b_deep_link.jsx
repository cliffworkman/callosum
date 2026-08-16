// App's "?open_paper=<id>" deep-link handling, split from 40_app.jsx (rule #1 -- the demo-mode init additions
// pushed it over the 600-line cap). useOpenPaperDeepLink (a hook) hoists in the shared IIFE, so App (in 40_app,
// textually before) references it regardless of chunk load order.

// A URL deep link ("?open_paper=<id>") opens that paper's PDF tab on load -- the LibreOffice adapter's
// "Open in Callosum" action (P0 phase 6, backlog #33/#34) launches exactly this URL against the local server.
// inc 460 (roadmap #17): the Suggest-citation Details dialog's "Open in PDF" button also passes "page"/
// "precision", jumping straight to the matched passage's page -- mirrors armCapture's own minimal-target
// shape (id/paperId/page/precision; no bboxJson needed since these matches are always "region" precision,
// never a fabricated exact rect per invariant #2, and applyPdfCitationTarget only needs bboxJson for "exact").
// One-shot: the params are stripped from the address bar right after use so a page refresh doesn't reopen it.
function useOpenPaperDeepLink(openPdf) {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("open_paper");
    if (!raw) return;
    const paperId = parseInt(raw, 10);
    if (!Number.isFinite(paperId)) return;
    const rawPage = params.get("page");
    const page = rawPage ? parseInt(rawPage, 10) : null;
    const target = Number.isFinite(page)
      ? { id: `open_paper:${paperId}:${page}`, paperId, page, precision: params.get("precision") || null }
      : undefined;
    openPdf({ id: paperId }, target);
    params.delete("open_paper");
    params.delete("page");
    params.delete("precision");
    const qs = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : ""));
  }, [openPdf]);
}
