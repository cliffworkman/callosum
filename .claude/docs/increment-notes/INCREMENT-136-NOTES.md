# Increment 136 — Watched folders rescan on focus (live-ish pickup)

## Implemented

A user dropped a PDF into their library folder and expected it to appear (and be retraction-tagged); nothing
happened. Root cause (diagnosed, no code bug): watched-folder rescans only ran **on app launch** (`40_app.jsx`'s
auto-rescan effect had `[]` deps → mount only), so a PDF added **mid-session** wasn't picked up until a restart
or a manual "Re-scan all". A reasonable user expects a watched folder to feel live.

- **Fix (`40_app.jsx`, frontend-only):** the watched-folder rescan now also fires **when the window regains
  focus** (`window` `focus` event), in addition to launch — so dropping a PDF in the folder and switching back
  to Callosum picks it up on its own. **Throttled** (at most once per 20s) + an **in-flight guard** so rapid
  focus changes don't hammer the disk or overlap scans. Gated by the existing `callosum.autoScanWatched` toggle
  (Settings → Library). The rescan poll + `libRefresh`/`tagRefresh` bumping are unchanged.

## Key technical detail

**The rest of the chain already worked** — the only gap was the trigger. Once a rescan runs, `scan_library_folder`
creates a `pdf-scaffold` for the new file, `_process_scan_result` enriches it
(`enrich_paper_metadata_from_crossref` → `find_doi_in_pdf` **reads the DOI from the PDF text**, `enrichment.py:160`
→ Crossref → real metadata), embeds it, and the inc-134 `auto_check_retractions` checks it (now that it has a
DOI). So a dropped retracted PDF, once picked up, is imported → DOI-resolved → enriched → **retraction-tagged**
automatically. (Two prerequisites the user still owns: the folder must be **registered as watched** — a one-time
"Scan folder" via the UI; and a retraction check must have run / will run on-import.)

## Manual verification script

1. Watch a folder (+ Add ▾ → Watched folders… / Scan folder → its path → Add + scan).
2. With Callosum open, drop a PDF (ideally one with a DOI) into that folder, then click back into the Callosum
   window → within ~a moment it appears in the library with its metadata; a retracted paper shows the ⚠ Retracted
   mark.

## Pytest

**514** unchanged (frontend-only; the rescan endpoint + scan chain are already tested in `test_watched_folders.py`
+ `test_retraction.py`). `ruff` clean; build + assembly + the e2e suite green. No backend / API / migration change.

## Next (queued)

- **Gap-finder v2** (user-chosen scope): forward gap (works that cite many of your papers) + axis-scoped ranking +
  a persistent `gap_candidates` cache.
- Auto-select the top library paper on load (Details populated).
- The accordion-tabs design rule (tabs within a section for like-with-like; Axes+Tags tabs; order Data-consistency
  before Statistics-check) + codify in `DESIGN.md`.
- A true live OS file-watcher (vs focus-triggered) remains a later option if focus-rescan isn't enough.
