# Increment 516 — Word "Citations in this document" panel (P1, backlog #33/#34)

## Implemented

First P1 item on the Word/Docs parity roadmap, Cliff's pick over the bigger note-style-placement item and the
accessibility pass (both smaller/lower-risk P1 candidates were offered; this one won). Mirrors the roadmap
doc's item #12 (RefWorks' "My Citations" precedent): a persistent, on-demand panel listing every unique cited
work with occurrence count, orphan/retraction status, and click-to-navigate.

**Scoped narrower than the roadmap's full wishlist, disclosed not silently dropped:**
- **"Metadata conflicts"** (does the same paper's CSL data differ across occurrences) — skipped. A real check,
  but a fuzzy one (cosmetic formatting difference vs. a meaningful conflict) that deserves its own scoping pass.
- **"Most recent citation"** — Word's data model has no insertion timestamp, only document position. "First
  occurrence" is kept (meaningful); "most recent" would have to be faked from position alone, so it's dropped.

**Confirmed via research before building, not assumed:** `Range.select()` (Word JS API) selects a range and,
standard Word UI behavior, brings it into view — no separate scroll call needed for click-to-navigate.

### Files

- `adapters/word/taskpane_core.js` (pure, tested):
  - `buildCitationsPanelEntries(tags)` — walks tags in document order, groups citation items by resolved
    paper id (`extractPaperId`, inc 512) into `{key, paperId, row, occurrenceCount, positions}` entries.
    `positions` indexes into the document-order list of citation-tagged controls (the same "index into
    document order" concept `refreshDocument`/`runDiagnostics` already rely on) — malformed tags still consume
    a position slot (kept in sync with a real re-scan) even though they contribute no entry. Items with no
    resolvable id (pre-inc-512 legacy citations) each get their own singleton entry rather than being guessed
    into a group. Entries ordered by first occurrence.
  - `mergePanelEntryStatus(entries, missingPaperIds, retractionChecked)` — pure augmentation reusing the exact
    input shape `summarizeDiagnostics` already consumes, marking each entry `orphaned`/`retraction`.
- `adapters/word/taskpane_core.test.js` — 6 new tests (33 total, was 27): grouping across a solo + grouped
  citation of the same paper, singleton handling for unresolvable items, malformed-tag position-slot
  consumption, non-citation tags ignored, first-occurrence ordering, and status-merge correctness (including a
  no-mutation check on the input array).
- `adapters/word/taskpane.js`:
  - **Extracted `checkPaperExistence(ids)`** from `runDiagnostics`'s previously-inlined per-id `/papers/export`
    + capped `/methods/retraction/check-selected` orchestration (the inc-513 trash-aware existence fix) — both
    Document diagnostics and the new panel need the identical logic; factoring it out means the fix can't drift
    between two copies. `runDiagnostics` is now a much shorter caller of the shared helper (net simplification,
    not just a move).
  - New `runCitationsPanel()`/`renderCitationsPanelList()`/`onCitationsPanelClick()`/`navigateToCitation()` —
    explicit on-demand trigger (matches diagnostics' UX pattern), client-side search filtering (no extra
    network call per keystroke), and fresh-re-scan navigation (never holds a stale Content Control reference
    across the click, since the document may have changed since the panel was built).
- `adapters/word/taskpane.html`/`.css` — "Citations in this document…" button, a search input (revealed on
  first use), the results list, and a `.badge-warn` style for orphan/retraction flags.

## Key technical detail

`navigateToCitation(position)` deliberately does **not** cache the Content Control objects the panel was built
from — it re-scans `body.contentControls` fresh on every click and re-filters to citation-tagged ones in the
same order `buildCitationsPanelEntries` used. This sidesteps the composer's own `.track()`/`.untrack()`
correlated-objects complexity entirely (nothing to track) at the cost of a possible stale-position mismatch if
the user edits the document between opening the panel and clicking a row — an accepted, disclosed tradeoff
matching the same implicit "index into document order" assumption `refreshDocument` already relies on
elsewhere in this file.

## Manual verification script

Not yet run live (session's established pattern: build, verify with `node --test`, hand off). In real Word:
cite the same paper twice — once solo, once inside a grouped citation — and confirm the panel shows it once
with occurrence count 2; click it and confirm Word selects/scrolls to the first occurrence; type in the search
box and confirm client-side filtering (no network activity); delete a cited paper from the library and re-run
the panel, confirm it's flagged "not in library."

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 33/33 passed (27 existing + 6 new). No Python changes —
this is 100% adapter-side (Word) work reusing the already-adapter-agnostic backend endpoints.
