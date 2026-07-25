# Increment 383 - Writer grouped-citation navigation

## Context

Increment 375 deliberately kept a grouped citation's rendered text plain because one ReferenceMark has several
possible bibliography destinations. The remaining P1 item #11 slice was an explicit, deterministic way to choose
which source to open or navigate to without inferring fragile per-item spans from citeproc's final cluster text.

## Implemented

- **Open cited work in callosum…** now opens a bounded source chooser for grouped citations and deep-links the
  selected numeric paper id. Single-work citations still open immediately.
- **Go to bibliography entry…** jumps single-work citations directly and lets grouped citations choose among
  sources with stable targets in the full bibliography.
- Choices accept only `callosum-<digits>` ids, de-duplicate by source, reuse the existing bounded citation-row
  formatter, and cap the displayed set at 50.
- Excluded works and documents without a built full bibliography fail honestly. Explicit navigation is
  independent of the opt-in visible citation-link preference; section bibliographies create no duplicate target.
- The extension version is `0.28.0`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic navigation over user-created citation
  structure and produces no claim, score, ranking, recommendation, or new egress.
- **Security:** `2026-07-25_writer-grouped-citation-navigation.md` - **PASS**.
- **QA:** route 34 step 16 covers second-source selection, exclusion/missing-bibliography behavior, link-toggle
  independence, local open, and save/reopen persistence.
- **Experience:** a code/help-grounded deadline-author walkthrough found the two action names explicit, the
  source list recognizable, and cancel/default-first behavior conventional. Keeping the grouped mark plain avoids
  a misleading one-destination affordance. A persona subagent was not used because delegation was disabled. The
  existing checked-state follow-up remains.

## Manual verification

1. In Writer, insert a grouped citation containing two sources and build the full bibliography.
2. Put the caret inside the group, choose **Go to bibliography entry…**, select the second source, and confirm the
   view cursor lands at that source's full-bibliography entry.
3. Turn visible citation links off and repeat; the explicit jump still works.
4. Exclude the second source and confirm it is no longer offered. Remove the full bibliography and confirm the
   command explains that a full entry must be built or refreshed.
5. Save/reopen and repeat the second-source jump. Choose **Open cited work in callosum…**, select the second
   source, and confirm that paper opens in the local app.

## Verification

- Focused adapter/OXT/install/help tests: **158 passed**.
- Installed Writer focused grouped-navigation/bibliography-link spike: **SELFTEST OK** (108.5 seconds).
- Installed Writer full matrix: **SELFTEST OK** (535.3 seconds).
- Full project suite: **1585 passed, 1 skipped** (823.70 seconds).
- Ruff check/format: **pass**.
- Line budget: **pass** (386 app-source files).
- QA surface map: **pass** (309/309 gated API; 1370/1391 frontend with 21 existing report-only findings).
- OXT packaging: **pass** (74,000 bytes).
- Diff hygiene: **pass**.

## Remaining item #11 scope

Long-manuscript section-bibliography list/jump/remove-all polish remains.
