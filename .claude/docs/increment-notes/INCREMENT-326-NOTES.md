# Increment 326 — LibreOffice adapter rework: Phase 8 (safe flatten — "Prepare submission copy")

## Context
The roadmap's item 7 asked to rename the existing bare, immediate `flatten()` action into something like
"Prepare submission copy," with an explicit irreversible-action warning, save-as-copy by default, and a
post-operation integrity check. This phase ships that as a **new, additional** action rather than replacing
`flatten()` — the existing "Flatten to static text" stays available as the advanced, in-place option for anyone
who genuinely wants to keep editing the flattened document itself.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`verify_flatten_integrity(before_text, after_text, doc)`**: the post-op integrity check. `flatten()` only
  ever removes invisible mark/bookmark structure and re-inserts the SAME rendered text, so a successful flatten
  must leave the document's plain-text content byte-identical, with zero `CALLOSUM_CITATION` marks remaining.
- **`prepare_submission_copy(doc, filename)`**: the core mechanism. Captures the document's text, groups the
  `flatten()` call as one `XUndoManager` context, verifies via the check above, `storeToURL`s the result to a
  new file (same folder as the open document if it's already saved, else the user's home folder), then
  **always** `undo()`s the flatten in the live document — the saved copy on disk is the reversible artifact,
  the same role a `merge_operations` snapshot or a soft-delete husk plays for database rows elsewhere in this
  codebase, adapted to a document that isn't one. If verification fails or the save itself errors, the live
  document is undone regardless, and the failure is surfaced honestly.
- **`prepare_submission_copy_interactive(doc)`**: prompts for a filename (prefilled
  `<docname>-submission-copy.odt`), showing the citation/bibliography counts and an explicit "your open document
  is never changed" statement, then reports where the copy landed.
- New `_ACTIONS` entry (`prepareSubmissionCopy`) + macro wrapper + a new `Addons.xcu` menu node placed right
  next to "Flatten to static text," labeled as the recommended option.

**Known v1 limitation, documented rather than guessed around:** the copy is always saved as ODF (`writer8`
filter), regardless of the original document's format. LibreOffice's per-format filter-name strings are numerous
and format-specific enough that guessing the right one for every possible original type without being able to
verify each is worse than shipping one honestly-documented, verified format. The "retain hyperlinks" / "remove
Callosum document metadata" checkboxes from the original roadmap sketch were also dropped for this pass — this
adapter generates no hyperlinks today (confirmed during the original research), making that checkbox a no-op,
and the document metadata (style/locale/bib-auto preferences) isn't sensitive enough to need a dedicated strip
step yet.

## Tests
Real-UNO spike (`spike_prepare_submission_copy` in `selftest_uno.py`) — this is exactly the kind of mutation
logic this rework has consistently kept out of pytest (real UndoManager grouping + a real file save/reload, no
faithful fake available). Inserts a citation, calls `prepare_submission_copy`, then confirms **both** halves of
the safety guarantee against real UNO: the SAVED copy has zero live marks (loaded fresh via `load_doc` and
scanned) with byte-identical visible text, and the OPEN document still has its live mark intact with
byte-identical text — i.e., it was never actually left flattened. Passed on the first run.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 15 passed (unaffected; no new pytest-testable pure logic).
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all prior
   spikes (Phases 0/2/4/6/7) still pass, plus the new Phase-8 spike.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. `python -c "import xml.dom.minidom; ...parse(...)"` caught a real XML bug before it shipped: an inline XML
   comment used a bare `--` (`"a bare Flatten -- always"`), which is invalid inside an XML comment body (only
   valid at the `<!--`/`-->` delimiters) — fixed by rewording to avoid the double-hyphen. A genuine catch, not a
   false alarm.
5. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count (unchanged from
   Increment 325's — no new pytest cases this phase).

## Gates
- **Security audit:** a new `doc.storeToURL(...)` file-write path is a real audit-relevant surface (a new
  file-ingestion/file-write trigger per the gate). Reviewed inline here rather than a separate stub, given how
  narrow it is: the target path is built from (a) the ALREADY-open document's own folder (or the user's home
  folder) and (b) a filename the user types into a local input box on their own machine — the same trust
  boundary LibreOffice's own native "Save As" already has (no networked/multi-user context, no external input).
  No new dependency, no egress, no secrets. The live document is provably never left mutated (verified by the
  spike). **PASS.**
- **Principles/A-A (rule #9):** unchanged — a safety mechanism for an existing, already-reviewed action; no new
  claim/signal/judgment.
- **README:** the "Use" section's numbering was fully redone (not just appended) after catching that a
  non-numeric list marker (`5a.`) would have broken CommonMark's ordered-list continuation rules — items 5-14
  renumbered cleanly. The "Limitations" paragraph updated to state the ODF-only save format and drop the
  now-stale "bibliography lives at the document end" claim (Phase 7 made it bounded and movable).

## Next
Phase 9 (diagnostics/repair) is the last of the smaller phases before Phase 5 (the composer, the largest
remaining piece).
