# Increment 36 Notes — Synthesis → annotation bridge (suite "Increment C")

Let the user save a **verified, exact-coordinate** synthesis citation passage as a durable
annotation with `source="synthesis"`, uniting the ephemeral citation-overlay system with durable
user highlights — without violating the coordinate-precision honesty contract. Backend + frontend;
no migration, no schema change (the `source` column + `create_annotation(source=…)` were already
scaffolded in increment 30/31).

## What changed

**Backend (`app/backend/api/app.py`):**
- `AnnotationCreateRequest` gains an optional `source: str | None = None`.
- `_validate_annotation_request` rejects any non-null `source` outside the allowlist
  `NATIVE_ANNOTATION_SOURCES = ("user","synthesis")` (imported from the repository — one source of
  truth, also used to scope annotation reads) → **422**. No forged sources.
- `create_paper_annotation` passes `source=request.source or "user"` (was hardcoded `"user"`).
- No new endpoint, **no route-surface change** → `test_api_exposes_only_read_only_get_routes`
  unchanged. `_annotation_bboxes_payload` already strips everything but `page/x0/y0/x1/y1`, so a
  citation bbox's `coordinate_precision` sub-key is dropped — stored annotation bboxes are pure
  geometry.

**Frontend (`callosum-app.html`):**
- `CitationCard` gets a **"Save as highlight"** control beside "Open source". Enabled **only** when
  `coordinate_precision === "exact" && status === "verified"` and ≥1 normalized bbox; otherwise
  shown **disabled with a tooltip** ("Only verified, exact-coordinate citations can be saved as a
  precise highlight"). Per-card state: `Save → Saving… → ✓ Saved to highlights` / `Couldn't save —
  retry`; disables re-save after success (client-side dup guard).
- `App.saveCitationHighlight(citation)` POSTs `{page: page_start, color: HIGHLIGHT_COLORS[0],
  bboxes: normalizeBboxes(bbox_json), anchor_text: quote, source: "synthesis"}`, **re-checking the
  honesty gate** before the write. It does **not** force-open the PDF tab.
- Prop threaded `App → RightPane → SynthesisPane → GroupedSummarySentences → SummarySentence →
  CitationCard` as `onSaveHighlight` (mirrors the existing `onOpenCitation` path).
- **Cross-component live refresh:** an App-level `annoRefresh` nonce (bumped on save) is passed to
  every `PdfViewer`; a new effect refetches annotations on nonce change **without** the
  clear-then-fetch (no flicker), skipping its mount run. So a save made while the paper's PDF tab is
  open appears immediately — no reload.
- **Visual provenance marker (user choice: "outline marker only"):** `renderUserAnnotations` keeps
  the increment-35 group model (opaque rects + group multiply — no per-rect borders, which would
  re-seam the union) and, for `ann.source === "synthesis"`, appends **one dashed `.pdf-synthesis-
  outline`** tracing the passage's union bounds, drawn as a layer sibling (crisp, not veiled by the
  group's multiply). Border color `#5c55b0` echoes the citation-overlay accent.
  `clearUserAnnotations` now also removes `.pdf-synthesis-outline`.

## Honesty contract
- Precise saves are offered **only** for exact + verified citations (precision and status are
  independent — an exact-but-flagged citation is correctly not saveable). Region/null/flagged →
  disabled. Enforced in the UI and re-checked server-bound in `saveCitationHighlight`.
- A saved synthesis highlight is geometrically identical to its citation overlay (same `bbox_json`
  via `normalizeBboxes`); the dashed outline keeps its machine origin legible even after a recolor.
- **Multi-page exact citation (rough edge):** `page = page_start`; all bboxes are stored, but only
  rects on `ann.page` render (single-page annotation model). Under-renders the rare cross-page case
  but never misrepresents — the drawn part is exact, no data lost.

## Decisions
- **Extend the create endpoint with `source`** (not a new endpoint).
- **Provenance-link column deferred:** `source="synthesis"` + the saved quote (`anchor_text`)
  already record origin; a back-link column needs a new migration + multi-file plumbing for a
  not-yet-requested feature ("jump back to the synthesis sentence") — not "cheap". Reversible.

## Verification
- **pytest: 129 passed** (126 + 3 new `source` accept/default/forged tests).
- **Headless E2E** (`.local/inc36_e2e/run_e2e.py`, real uvicorn + real `library/*.pdf`, Chromium):
  - precision-gating: exactly 1 enabled + 1 disabled Save control (disabled carries the honesty
    tooltip);
  - save creates a `source="synthesis"` annotation (API confirms `["synthesis"]`);
  - **live refresh:** `.pdf-synthesis-outline` count `0 → 1` while the PDF tab stayed open (no
    reload);
  - **reload-drift = 0.0px** (geometry identical before/after reload);
  - **0 console errors** (the in-browser Babel/JSX edits compile + render cleanly).

## Rough edges
- No server-side dedupe of identical saves (client-side guard only).
- A determined client could POST `source="synthesis"` with arbitrary geometry — local single-user,
  no trust boundary; the allowlist only blocks garbage source strings (see security audit).
- The global `annoRefresh` nonce refetches every open viewer on any save (cheap, flicker-free GET).
- Rotated pages keep the existing no-overlay limitation.
