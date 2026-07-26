# Increment 392 — exact Cite attachment routing and active PDF identity

**Date:** 2026-07-26
**Status:** implemented; local gates complete

## Outcome

Work → Cite suggestions now retain the PDF attachment that supplied their matched chunk. **Open source region**
therefore opens the exact article, supplement, or other local PDF before applying the existing region-level page
navigation. The PDF viewer toolbar also names the active served file beside the paper title, including at phone
width, so a secondary attachment is no longer visually indistinguishable from the primary article.

When a matched chunk belongs to a non-PDF attachment, Callosum does not transfer that attachment's page coordinates
onto a different PDF. The card instead says **Open primary PDF**, opens the paper's ordinary primary PDF, and carries
no page or overlay target. The matched quote remains visible in the suggestion card.

## Architecture and boundaries

- `Suggestion` and `SuggestionResponse` add one optional integer `attachment_id`.
- The citation engine resolves the matched chunk and retains its attachment id only when the database record is
  typed as PDF. The retrieval, ranking, region precision, quote, stance, and caps are unchanged.
- `SuggestionCard` passes that id through the existing `citationTarget` → `openPdf` → `PdfViewer` path.
- Non-PDF fallback deliberately nulls page start/end before opening the primary PDF, preventing cross-file
  coordinate drift.
- `GET /papers/{paper_id}/pdf?attachment_id=` remains the only file-serving route and still scopes the integer id
  to the paper, resolves the path from its database row, and rejects stale, foreign, unavailable, or non-PDF rows.
- `PdfViewer` reads the already-present `Content-Disposition` filename after a successful response. No filesystem
  path, new endpoint, persistence, migration, dependency, write, LLM, provider, or egress surface is added.

## Principles and experience

This strengthens Principles 1 and 8 and the coordinate-honesty invariant: the evidence jump reaches the file that
actually supplied the passage. The tempting misalignment was to pass the page while continuing to open the primary
PDF, producing a plausible but cross-file source location.

The required experience pass was performed directly because this session may not delegate to a persona subagent.
In the **deadline citer** role, the main agent pasted a claim, opened a suggestion backed by a named supplement,
confirmed the actual request carried that attachment id, saw the region-only note with no exact rectangle, and
could read the active filename without overflow at desktop and `375x812`. The first phone pass found the filename
collapsed to a sliver; the same increment moved source identity onto its own mobile toolbar row. The repeat pass
measured a readable ~197px filename, zero toolbar/document overflow, and zero console/page errors.

## Manual verification

1. Use a paper with distinct primary and secondary PDFs and a searchable chunk in the secondary.
2. Open **Work → Cite**, paste text matching that chunk, and click **Suggest**.
3. Click **Open source region** and confirm the PDF request carries the secondary attachment id.
4. Confirm the toolbar names that secondary file, the correct page opens, the region note appears, and no exact
   rectangle is drawn.
5. Resize to `375x812`; confirm the active filename remains readable and no toolbar/document overflow appears.
6. Repeat with a matched non-PDF attachment; confirm **Open primary PDF** applies no source page or overlay.

## Verification

- Affected citation/PDF/summary/frontend suite: **150 passed**.
- Frontend assembly after responsive adjustment: **53 passed**.
- Direct Playwright desktop/mobile walkthrough: exact attachment request, named active file, region-only evidence,
  zero exact highlights, zero overflow, and zero console/page errors.
- Full project suite: **1634 passed, 1 skipped** in 894.26 seconds.
- Ruff check/format, 404-file line budget, frontend build parity, diff hygiene, and QA
  **318/318 API + 1398/1419 FE** (same 21 report-only): pass.
- Required GitHub checks: pending push.
