# Increment 142 — Determinate import/scan progress (Migrator ↔ backlog #4)

## Experience pass (rule #11)

**Persona:** the **Migrator** (new user bringing their whole library in, deciding if Callosum can replace
Zotero/Mendeley). A dispatched persona agent drove the import/scan onboarding flow. **Found:** the after-counts are
honest and the Unsorted safety net is real, but the **biggest gap is no *determinate* progress** — for a
few-hundred-item import the bar is an indeterminate pulse that "looks identical at item 3 and item 380," so the
operation feels like a black box ("stuck? crashed? how far?") right up until it finishes; and the path to "review
the questionable ones" is soft (a hint, not a door). Verdict: *trusts the result, anxious during the wait.* (This
re-validated the QA tool — the agent found a real gap the backlog item, "add a progress bar," had already partly
met with the indeterminate bar.)

## Implemented

- **Determinate "X / N" progress** for the long scan + import jobs. `JobStore` gained a `JobProgress {current,
  total, label}` + `mark_progress` (inc 142). `embed_papers` / `embed_chunks` (the slow phase) + `scan_library_folder`
  (per-file) take an optional `on_progress(current, total)` callback; the scan/import jobs wire it through
  (`_process_scan_result` reports "Fetching metadata" → "Embedding text/papers"; scan reports "Reading PDFs"). The
  `ScanJobResponse` / `ImportJobResponse` expose `progress`; the modals read it from the poll and pass it to a
  `ProgressBar` that now renders a **real fill + "label — X / N"** when `progress` is present (else the old pulse).
- **A "Review unsorted →" door** in the scan done-summary (when `added > 0`) → the inc-80 Unsorted view +
  closes the modal (new `showNeedsReview` handler + `onShowUnsorted` prop), so the migrator goes straight to the
  papers whose DOI didn't resolve instead of hunting the header toggle.

## Key technical detail

Progress is **opt-in + additive**: every other async job (and every direct `embed_*` caller) passes no callback
and stays indeterminate, so the shared `JobStore` change is zero-blast-radius. `mark_progress` is called per item
(cheap, in-memory under the existing lock); the UI polls every 1.5s, so it samples the latest — no need to throttle.
The fill is an inline `width:%` with a `.progress-fill-det` modifier that turns off the indeterminate sweep.

## Manual verification script

`python .local/visual/drive_inc142_progress.py` — starts a server with a **slowed fake** embedding model
(0.4s/paper, deterministic, no real-model download) and imports an 8-record `.bib`. **PASS:** the bar goes
determinate (**"Embedding papers — 4 / 8"** caught mid-run, with a real fill) and finishes "8 imported"; 0
console/page/genai. (A live few-hundred-item import with the real model is the user-confirmable visual.)

## Triage of the remaining migrator findings (filed to backlog #4)

Shipped: determinate progress + the Unsorted door. **Remaining (backlog):** a "which entries were skipped/failed,
and why" list in the done-summary (not just a count); per-item filename in the progress label ("…Smith 2019");
stage labels are partly there (the phase label) but no ETA; a **cancel** button. (The "import is metadata-only"
note already exists in the import modal.)

## Pytest

**+3** (`test_job_store.py` ×2: `mark_progress` / done-clears-progress; `test_embeddings.py`:
`embed_papers` reports progress per paper). `ruff` clean; build + assembly green; surface **106/106 API + 532/532
FE, 0 uncovered**. No new endpoint/migration/egress.

## Next (the build-and-test slate)

- **Librarian ↔ Protect imported/system tags from clobber (#3)** — next (inc 143).
- Then **Close reader ↔ dogfood the reading flow** (inc 144) and **Skeptical synthesizer ↔ multi-paper focus
  query** (inc 145).
- **After the slate: BYOK** (Gemini API key in Settings) — user-prioritized to the top of the pile.
