# Increment 384 - Writer section-bibliography manager

## Context

Heading-scoped bibliographies were safe and live, but a long manuscript could remove one only by first finding
its owning section. The last active P1 item #11 follow-up was a document-wide list/jump/remove-all surface with
useful heading/count feedback.

## Implemented

- **Section bibliographies…** lists every complete block in document order as `Heading — N cited works`.
  Heading-free and pre-heading scopes use honest Document/Preamble labels.
- **Go to** moves Writer to the selected managed block. **Remove selected** deletes only that block and reopens the
  manager. **Remove all** names the count, defaults confirmation to No, and removes every complete block.
- Selected and bulk removal each use one named Writer Undo context. Citations, heading prose, other blocks, and the
  full bibliography are outside the selected mutation ranges.
- Real fault injection found Writer could restore a removed bookmark pair but leave its content empty. A bounded
  runtime Undo listener now restores the correct state after Undo/Redo and mid-transaction rollback. A current
  local render plan preserves managed DOI/title links; offline/stale recovery restores exact plain text and marks
  bibliography formatting pending rather than pretending links are current.
- Recovery payloads are interned by strict id/exact contents and cleared with Undo history/document disposal.
  Damaged triples are counted but not listed, and remove-all refuses until diagnostics are resolved.
- Insert/remove confirmations now name the owning heading and cited-work count. The extension version is `0.29.0`.
- This closes the recorded section-manager follow-up and completes P1 item #11 / the active LibreOffice phase.

## Gates

- **Principles / governance:** non-triggering. This is deterministic document navigation/removal and produces no
  claim, score, recommendation, ranking, or new egress.
- **Security:** `2026-07-25_writer-section-bibliography-manager.md` - **PASS**.
- **QA:** route 34 step 20 covers list order/counts, jump, selected/bulk removal, confirmation cancellation,
  one-step Undo/Redo, injected rollback, link preservation, and damaged-block refusal.
- **Experience:** a code/help-grounded deadline-author walkthrough found heading/count recognition materially
  better than bookmark identities, and one manager removes the need to hunt through a long manuscript. Remove-all
  is explicit, count-specific, and safely defaulted. A persona subagent was not used because delegation was
  disabled. The optional checked-toggle polish remains separate future UX work.

## Manual verification

1. Create two heading-scoped bibliographies with distinct cited works.
2. Open **Section bibliographies…** and confirm document-order `Heading — N cited work(s)` rows.
3. Select the second row and **Go to**; confirm Writer lands at that block.
4. Remove the first row; confirm the second, all citations, and the full bibliography remain unchanged.
5. Choose **Remove all**, first cancel, then confirm. Confirm one Writer Undo restores both blocks with links and
   Redo removes them again.
6. Damage one strict triple and confirm the manager reports it while bulk removal refuses.

## Verification

- Focused adapter/OXT/install/help tests: **159 passed**.
- Installed Writer focused section-bibliography spike: **SELFTEST OK** (105.0 seconds).
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1586 passed, 1 skipped** in 782.71 seconds.
- Ruff check and format: pass (**517 files already formatted**).
- Line budget: pass (**386** application-source files within the 600-line cap).
- QA surface map: pass (**309/309** API; **1370/1391** frontend, 21 report-only).
- OXT packaging: pass (`0.29.0`, **78,417 bytes**).
- Diff hygiene: pass.

## Remaining LibreOffice scope

The active core adapter phase is complete. Traveling-library collaboration, journal abbreviations, comprehensive
keyboard/screen-reader accessibility, and P2 manuscript-analysis features remain future roadmap projects, not
unfinished close-out work.
