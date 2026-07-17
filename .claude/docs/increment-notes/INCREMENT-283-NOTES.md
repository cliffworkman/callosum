# Increment 283 — PDF text-health: fix "missing section labels" (per-line detection + honest staleness)

Text Health reported **"102 local PDFs · 101 missing section labels · 0 stale extraction"** — nearly every
paper flagged, which read as a broken feature. It was two compounding defects, not a metric bug.

## Root cause (diagnosed read-only against both live DBs)

1. **Every stored chunk predated section detection.** Section labeling (`pdf_processing/sections.py` +
   the `section_tracker` call in `extraction.py`) was added in commit `91ed1ae`; the whole library was
   extracted before that, so **100% of chunks had `section = NULL`** (14,352/14,352 and 24,938/24,938 in
   the two DBs). The `missing_section_labels` flag fires when a paper has chunks but *zero* labeled → every
   paper flagged.
2. **The staleness signal was blind to it.** `stale_chunk_version` compares each chunk's
   `chunking_strategy`/`extraction_tool` to the current constants. `91ed1ae` added detection **without
   bumping** `DEFAULT_CHUNKING_STRATEGY` (`"pymupdf-block-v1"`), so pre-section chunks read as *current* →
   misleading **"0 stale extraction"** → nothing signaled that 100+ papers needed re-extraction.

Also found: detection under-performed even on fresh extraction, because `SectionTracker.observe` was fed the
**whole PyMuPDF block**. PyMuPDF routinely merges a heading with its following body into one block
("Methods\n<body>"), which fails `_has_heading_shape` (too long / trailing period) — so the heading was
never seen, though its **first line** matched.

## Implemented

- **`app/backend/pdf_processing/sections.py`** — new `SectionTracker.observe_block(block_text) -> bool`:
  scans a block **line-by-line** with the existing `detect_section_heading`, sets `current_section` from the
  first heading line found, and returns `True` only when the block is a *single* heading line (so the caller
  skips a pure heading but still labels merged heading+body blocks). `observe`/`detect_section_heading`
  unchanged.
- **`app/backend/pdf_processing/extraction.py`** — the chunk loop now calls `observe_block(block.text)`
  instead of `observe(...) is not None`; the emitted chunk keeps `section=section_tracker.current_section`,
  so a merged block is emitted **and** labeled. Bumped `DEFAULT_CHUNKING_STRATEGY` → **`"pymupdf-block-v2"`**
  (chunk output changed materially) so pre-section chunks now honestly read as `stale_chunk_version`.
- **`tests/test_pdf_processing.py`** — `test_observe_block_labels_merged_heading_and_body` (merged block
  labels + emits body; pure heading skipped; no-heading unchanged; heading after a running-header line still
  caught; a trailing-period sentence is not a heading) + `test_default_chunking_strategy_bumped_for_section_detection`.
  Fixed `test_changed_chunking_strategy_changes_chunk_version` (its arbitrary "alternate" was `pymupdf-block-v2`,
  now the default) → `pymupdf-block-alt`.

## Key technical detail

The fix is *where* the heading scan looks: a PyMuPDF block's text is `"\n".join(lines)`. Observing the whole
block only ever matches when a heading is its own isolated block; observing each line catches the far more
common merged case while `_has_heading_shape` (≤90 chars, ≤9 words, no trailing period/comma) still rejects
prose lines, so false positives stay out. The block is skipped **only** when it is exactly one heading line —
preserving the old "don't emit a pure heading as a chunk" behavior (proven by the unchanged
`test_section_headings_are_attached_to_following_chunks`).

## Measured impact (read-only, full `library/*.pdf`)

- Papers with **zero** section labels: **13/108 (12%) → 0/107**.
- Mean fraction of chunks labeled: **82.4%**; mean distinct sections/paper: **5.0**.
- Payoff beyond the health panel: `chunks.section` feeds **section-scoped summarization**
  (`summarization/pipeline.py:219`), **statcheck finding context** (`methods/statcheck.py`), and
  chunk/citation metadata — all silently degraded while the library was 100% NULL.

## Manual verification script

1. App on :8888 → Library header → **Text health**. With the v2 bump, the overview now honestly shows a
   non-zero **stale extraction** count (the old chunks are v1) instead of "0 stale."
2. Click **Reprocess missing section labels** → job runs (`reprocess_pdf_attachment` re-extracts + re-embeds
   + persists `section`). Re-open Text health → `missing_section_labels` and stale counts fall to ≈ the
   handful of no-heading / no-local-PDF papers; `ok` rises.
3. Open a reprocessed paper's statcheck / summary → section context now appears.
4. Papers with no local PDF (83) stay honestly flagged `no_local_pdf`; a rare heading-less scan stays flagged
   (silence-is-not-a-certificate).

## Gates

- **Principles (#9):** section labels are a deterministic-local extraction attribute (no LLM/egress) — this
  improves a local signal's accuracy (deterministic-substrate-is-source-of-truth); no provenance/egress
  posture change; kept best-effort (never authoritative).
- **QA (#10):** no new endpoint/control/view-state — only existing counts change value; `build_surface_map.py
  check` unchanged.
- **Security:** audit gate not triggered (no new endpoint/fetch/ingestion/dep).
- **Help:** `help_content.md` already describes "reprocess … missing section labels / stale extraction" — the
  fix makes reality match the docs; no corpus edit.

## Pytest

`tests/test_pdf_processing.py` 22 passed (2 new). Full suite: **1239 passed, 1 skipped** (was 1237 + 2 new).
