# Increment 357 — LibreOffice refresh citation at cursor

## Context

P1 roadmap item #13 already had full, citation-only, bibliography-only, and dirty-surface refreshes. The smallest
remaining bounded control was refreshing one citation during large-manuscript editing without rewriting every
ReferenceMark or the managed bibliography.

## Implemented

- Added **Refresh citation at cursor** to the Writer Callosum menu and macro exports.
- The command resolves only an existing, supported Callosum ReferenceMark at the caret. Outside a live citation,
  it explains where to place the cursor and performs no render or mutation.
- `refresh` accepts an optional set of target mark names. Citeproc still receives the full ordered document, so
  numeric position, disambiguation, and subsequent-citation state remain correct; transactional write-back is
  narrowed to the requested mark.
- Other citation fields and the managed bibliography remain untouched.
- A targeted refresh does not clear the document-wide citation-dirty flag. Without per-mark dirty state,
  repairing one citation cannot prove all others are current.
- Extension version bumped 0.6.0 → 0.7.0 and the `.oxt` rebuilt.

## Gates

- **Principles / governance:** non-triggering. This is deterministic document formatting and makes no scholarly
  claim, ranking, quality judgment, or worker assessment.
- **Security:** audit `2026-07-23_libreoffice-selected-refresh.md` is **PASS**. The action is fixed, local, bounded,
  plain-text, and reuses the existing render endpoint and transactional mutation path.
- **QA:** no web-app surface changed. Unit coverage checks exact target routing and the no-target path; the
  required real-UNO harness checks actual Writer selection and ReferenceMark mutation.

## Verification

- `pytest -n auto -q` — **1458 passed, 1 skipped**.
- Targeted LibreOffice adapter/install/OXT tests — **73 passed**.
- Ruff check/format and OXT build — clean.
- `python adapters/libreoffice/run_roundtrip.py` — real headless LibreOffice, isolated `.oxt` profile, and real
  seeded Callosum server printed **`SELFTEST OK`**. Two deliberately stale citations proved that only the mark at
  the caret changed, the bibliography stayed byte-for-byte stable, and global citation-pending state remained.

## Manual verification debt

Cliff should install 0.7.0 and click **Refresh citation at cursor** in headed Writer, both inside and outside a
live citation. The real-UNO harness proves the behavior but not the rendered menu appearance. The existing
citations-panel and bibliography-editing click-through debt remains open.

## Next

Current-section refresh is the next explicit #13 control, but it needs a robust Writer section-boundary contract.
The document-event listener for native citation moves and immediate reopen state is a separate lifecycle slice.
