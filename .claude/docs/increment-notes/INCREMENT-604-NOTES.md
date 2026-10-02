# Increment 604 — restore the paper index after provisional PDF admission

Local follow-up to Windows candidate `2a80b734`; not a release or hardware acceptance rerun.

## Implemented

- `app/backend/capture/provisional.py`: call the existing `ensure_paper_indexed` helper once at
  `attempt_attach_to_paper`, after canonical admission commits and before PDF eligibility checks.
  Confirmation, automatic promotion and retry all reach this seam. No new embedding implementation.
- `tests/test_admission_indexing.py`: extend the existing admission matrix with real Ioannidis PDF
  confirmation and synthetic front-matter automatic promotion. Exercise actual routes, extraction,
  chunking and vector persistence; deterministic model and injected resolver keep the tests offline.
- Extend QA route 27 and document cause, chronology, evidence and the remaining targeted acceptance
  check in `../research/2026-10-02_capture-paper-index.md`.

## Key technical detail

`attach_pdf_to_paper` indexes chunks only. Its caller must honor the separate canonical metadata
admission invariant. `ensure_paper_indexed` already owns text construction, current-model/version
checks, vector writes, one-paper transactions and logged nonfatal failures. Reusing it for both new
and existing papers repairs missing indexes while leaving a valid index untouched. PDF attachment
conflicts cannot exempt an already-admitted paper from metadata indexing. Unresolved capture and
preview never reach this seam. No migration, protocol, UI, identity or runtime change.

## Manual verification script

Not executed against the accepted QA session. After approval, use a fresh isolated database/Library
and the exact corrected source with the unchanged packaged Windows runtime. Stage the checksum-pinned
Ioannidis fixture provisionally, record preconfirmation state, then exercise the actual confirmation
route. Require one paper, one byte-identical PDF, 122 current chunk vectors plus one current paper
metadata vector, retained confirmation provenance, no duplicates on replay and persistence on reopen.
Measure confirmation latency separately. Full Chrome setup/capture acceptance need not be repeated
because the source change is downstream of that established boundary. See the linked research note.

## Pytest and gates

The failing-before-fix receipt proves successful confirmation/PDF/chunk indexing followed by zero
paper embeddings. Focused **88 passed**; broader **180 passed, 2 POSIX-only skips on Windows**;
total **268 passed, 2 skipped**. Ruff, pre-commit/Bandit/line budget/Tach and API coverage passed.
The website gate passes with the existing explicit marketing deferral extended to increment 604,
not a fresh visual review. Detailed commands, timings and limits are recorded in the research note.
No production model or new packaged candidate is claimed from deterministic-model tests.

## Experience, latency and lineage

Corpus-builder walkthrough: a confirmed paper must participate in metadata-based retrieval as well
as passage retrieval. No control or review flow changes; this backend-only correction has a trivial
experience pass. Model failure remains nonfatal under the existing shared contract and is logged.
The app-owned model/store are reused; a current paper adds no inference, a missing index adds one
metadata input. Chunk batching and worker ownership are unchanged. No new performance claim.

Cliff supplied physical Windows acceptance and follow-up authorization; Cody diagnosed and implemented
the invariant repair and regression coverage; Lucien scoped the repair to shared admission behavior.
The original Windows PARTIAL evidence remains unchanged. No source push or release action.
