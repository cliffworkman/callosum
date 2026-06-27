# Increment 155 — Scan done-summary surfaces which files couldn't be read (#4)

The autonomous part of backlog #4 (Migrator experience-pass remainder). The folder scan already isolated per-file
failures (`scan_library_folder` → `errors:[{path,error}]` via per-file savepoints) but only reported a **count** —
now the done-summary shows **which files failed and why**.

## Implemented

- **`app/backend/api/routers/library.py`** — a `ScanError{path, error}` model; `ScanSummary` gains
  `error_details: list[ScanError]` (capped at `_SCAN_ERROR_DETAIL_CAP = 25`); `_scan_summary` maps the scan's
  `errors`; the **watched-rescan** aggregation collects `error_details` across all folders (incl. a
  "watched folder no longer exists" entry). No new endpoint (additive field on the existing `ScanJobResponse`).
- **`app/frontend/js/27_scan.jsx`** — a collapsible `<details className="scan-errors">` in the scan done-summary:
  *"N file(s) couldn't be read"* → a list of `<basename> — <reason>` (full path on hover), with an "…and K more"
  line when capped. CSS: a `.scan-errors` recipe (flag-amber; tokens only, rule #8).

## Scope note (honest)

This covers the **scan** path (the data was already collected — pure surfacing). The **import** path's "skipped"
records are dropped *at parse* (both the BibTeX and CSL-JSON parsers silently drop title-less/malformed entries
before the import loop, so they never reach a `failed` count) — surfacing those needs a **parser-level** change
(have `parse_records` report dropped entries). That's deferred (noted on backlog #4), not folded in here, to keep
the increment honest rather than ship a rarely-populated import detail list. The other #4 remainders — per-item
**ETA** + a **cancel** button — need timing/cooperative-cancellation infra and stay deferred too.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc155_scan_errors.py`): a fake-embedding app over a temp folder with
a valid PDF + a broken one → scan from the UI → the summary reads "1 added · 1 error" and the collapsible lists
*"broken.pdf — FileDataError: Failed to open file…"*. 0 console/page/genai.

## Pytest

**557** (+1 `test_library_scan.py::test_scan_surfaces_per_file_errors`: a broken file → `summary.errors >= 1` +
`error_details` carries the path + a non-empty reason). `ruff` clean; build + assembly green; QA surface **109/109
API + 561/561 FE, 0 uncovered** (additive field; route_27 covers the scan modal). No migration.

## This completes the autonomous-work pass

inc 153 (synthesis coverage) · 154 (statcheck deep-link) · 155 (scan error detail). The remaining open items are
all design-gated / destructive-security / future-track / non-code — none autonomous-cheap (see the reconciled
`INCREMENT-BACKLOG.md`).
