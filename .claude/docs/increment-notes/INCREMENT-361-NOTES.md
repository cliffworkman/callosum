# Increment 361 — LibreOffice incremental write-back

## Context

The last open part of P1 roadmap item #13 was incremental rendering. Cropping the citeproc request to only
apparently changed citations would be incorrect: citation numbering, author-date disambiguation, and bibliography
membership all depend on the complete ordered manuscript. The safe optimization boundary is therefore Writer
write-back, after a full render.

## Implemented

- Citeproc still receives every live citation in document order on each requested refresh.
- A pure citation delta planner compares rendered output with each targeted ReferenceMark's visible text and
  schedules only changed, nonempty results.
- The managed bibliography has one canonical rendered string. It is considered current only when both bounding
  bookmarks are intact and the exact text between them matches that string.
- An explicit bibliography cursor move always rebuilds/repositions the range. Missing/damaged bookmark pairs and
  manual edits also compare unequal and force a rebuild.
- A fully current refresh returns before opening an UndoManager context, so it creates no empty Writer undo entry.
- Requested dirty flags clear when the exact comparison proves that surface current, including a zero-mutation
  refresh.
- Extension version bumped 0.10.0 → 0.11.0.

## Verification

- Targeted adapter/OXT/install suite: **89 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** with the installed OXT and real Writer.
  Instrumented Writer mutations measured:
  - identical full refresh: **0 citation writes, 0 bibliography writes**
  - one deliberately stale citation: **1 citation write, 0 bibliography writes**
  - deliberately stale bibliography with bibliography-only refresh: **0 citation writes, 1 bibliography write**
- The real fixture also confirmed that the exact managed bookmark-range comparison recognizes text written by
  Writer, including its newline behavior, and completed every pre-existing LibreOffice spike.
- Full project suite: `1474 passed, 1 skipped in 683.56s (0:11:23)`.

## Gates

- **Principles / governance:** non-triggering. This changes deterministic local document formatting only and
  creates no literature claim, signal, ranking, recommendation, or worker assessment.
- **Security:** `2026-07-23_libreoffice-incremental-writeback.md` is **PASS**.
- **QA:** no web API or frontend surface changed. Pure tests cover citation planning, exact bibliography
  comparison, damaged bounds, and the empty-delta UndoManager path; real UNO proves actual mutation counts.

## Manual verification debt

Cliff should install 0.11.0, refresh an already-current Writer document, and confirm no new refresh entry appears
in Writer's Undo menu. Making one citation visibly stale should rewrite only that field. Prior menu/panel
appearance click-through debt remains open.

## Next

P1 roadmap item #13 is complete. Remaining LibreOffice P1 candidates include the real CSL style manager,
note/footnote styles, and further bibliography controls; the next slice should be selected from the roadmap rather
than extending the now-complete refresh/performance track.
