# Increment 513 — Word diagnostics' orphan detection wasn't trash-aware (real bug, found live-testing inc 512)

## Implemented

Cliff live-tested inc 512's Document diagnostics exactly the way it was meant to be tested: moved a cited
paper's row to trash in the library, re-ran diagnostics, and it was still reported clean. Real bug, not a
misunderstanding — traced to a genuine design mistake in how orphan detection was wired.

**Root cause**: orphan detection reused `POST /methods/retraction/check-selected`'s `not_found` field (real
requested ids that raised `NoResultFound`). But that endpoint's `_check_and_persist` calls
`get_paper(conn, paper_id)` (`app/backend/persistence/repository.py:99-100`) — confirmed by reading it —
`select(papers).where(papers.c.id == paper_id)`, **no `deleted_at` filter at all**. "Trash" in callosum is a
soft delete (`deleted_at` set, row still present), so a trashed paper's row is still found by `get_paper`,
never raises `NoResultFound`, and never lands in `not_found`. This is exactly the case a real user is most
likely to test first (trash a cited paper, expect diagnostics to flag it) — inc 512's own increment notes even
said the manual verification script *was* "delete a cited paper from the library... confirm diagnostics reports
it orphaned," but that verification was never actually run live before shipping (documented as "not yet run
live — hand off for a real-Word check" in `INCREMENT-512-NOTES.md`) — this is exactly the class of gap that
step would have caught, and did, once Cliff ran it.

**The fix**: don't infer existence from the retraction-check endpoint at all. `get_papers_for_export`
(`paper_query_repo.py:399-409`, confirmed by re-reading) *does* filter `papers.c.deleted_at.is_(None)` — so
`/papers/export` is trash-aware where `check-selected` isn't. But its response can't be correlated back to
which requested id it answers by trusting the record's own `.id` field (the exact problem inc 512 already fixed
for citation tags — stored `csl_json.id` isn't guaranteed to match the real database id). The fix uses
`/papers/export` **per distinct id, in parallel** (`Promise.all`), keying existence off presence/count of the
response (`rows.length > 0`) rather than any id value in it — sidesteps the correlation problem entirely while
staying trash-aware. `/methods/retraction/check-selected` is still called, but now only for ids already
confirmed to exist (retraction status is a separate concern from existence, and it's still the right endpoint
for that half).

### Files

- `adapters/word/taskpane.js` — `runDiagnostics()`: replaced the single `check-selected` call's `not_found`
  usage with a parallel per-id `/papers/export` existence loop (`missingIds`), then calls `check-selected` only
  over the confirmed-existing ids for retraction status.
- `adapters/word/taskpane_core.js` — `summarizeDiagnostics`'s doc comment corrected (the `missingPaperIds`
  param is no longer sourced from `check-selected`'s `not_found`); no logic change — the pure function's
  contract (a "missing ids" list in, an orphan list out) was already source-agnostic, so nothing internal
  needed to change once the caller started feeding it the right data.
- `adapters/word/taskpane_core.test.js` — comments/test names updated to match (no assertion changes needed —
  the pure function's behavior was already correct once given the right input).

**No backend changes** — both endpoints behave exactly as designed; this was purely a client-side wiring
mistake (using the wrong signal for "does this paper still exist").

## Key technical detail

Two backend paper-lookup paths have different trash semantics and neither is wrong for its own purpose:
`get_paper` (used by retraction status/check, paper detail, and several other read paths) intentionally has no
trash filter, since checking or displaying a trashed paper's own retraction status is still meaningful — a
trashed paper isn't purged, just hidden from ordinary library views. `get_papers_for_export`/`list_papers`
intentionally DO filter trash, since export/listing should reflect the user's live library. A caller needing
"is this real, resolvable paper still one I'd consider part of my library" (this diagnostic's actual question)
must use the trash-aware path — using the wrong one silently gives the wrong answer for exactly the trash case.

## Manual verification script

Not yet re-run live (session's established pattern: build, verify with `node --test`, hand off). In real Word:
re-run **Document diagnostics…** on the same document from inc 512's testing (the paper already in trash) —
should now report it orphaned. Restore that paper from trash and re-run — should report clean again. Confirm
retraction flagging (if a retracted paper is cited) is unaffected by this change.

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 27/27 passed (unchanged count — no new pure-logic behavior,
just corrected wiring in the untested Office.js glue layer plus doc-comment/test-name corrections for accuracy).
