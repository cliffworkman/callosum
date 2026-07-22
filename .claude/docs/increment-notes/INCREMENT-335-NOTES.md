# Increment 335 — Backlog #19: tags ↔ findings/system-facts (retraction-surfacing)

## Context
Next in the 12-item decision queue. Cliff's answer was "yes, build a filter for this." Research before touching
anything found the backlog's own framing ("still not filterable") was **already stale**: retraction has been
filterable since inc 131 via `GET /papers?signal=retraction-retracted`, with a working header chip
(`showRetractionFlagged`), a "Filtered to retracted papers" banner, and even documented help text ("click it to
filter to just those papers"). So the real gap #19 closes isn't "no filter exists" — it's that retraction's
filterability lives in a **bespoke, hardcoded facet** (a `SIGNAL_FILTERS` allowlist entry + a purpose-built chip
+ a purpose-built banner branch) instead of the **generic, reusable tag mechanism** every other label in the
app already goes through (the sidebar Tags browser, a paper's Tags row, saved searches). That reuse/consistency
argument — not "add a missing filter" — is what this increment actually delivers.

## Implemented
- `app/backend/methods/retraction.py`: `RETRACTION_TAG_NAME = "system:retraction:retracted"` /
  `RETRACTION_TAG_SOURCE = "system:retraction"`. `apply_retraction()` — the single call site both the batch job
  and the on-import hook (`auto_check_retractions`) use — now links the tag when `outcome.merged.status ==
  "retracted"` and unlinks it (by name) otherwise, in the same function that already writes the FACT/signal.
  Scoped to `"retracted"` only, matching `signals_repo.count_retraction_flagged`'s existing "flagged" definition
  (not correction/concern) — no scope creep on what counts as "flagged."
- `app/backend/persistence/tags_repo.py`: `get_tag(conn, tag_id)` (a single-row lookup, needed by the new router
  guards) and `remove_tag_from_paper_by_name(conn, paper_id, name)` (un-retraction never holds a tag id).
- `app/backend/api/routers/tags.py`: three guards protect the fact from user mutation —
  `POST /tags/{id}/color`, `POST /papers/{pid}/tags/{id}/lock`, and `DELETE /papers/{pid}/tags/{id}` all 409
  ("System-generated fact tags aren't user-editable") when the target tag's `import_source` namespace is
  `system`; `POST /papers/{pid}/tags` 422s a user-typed name starting with `system:` (case-insensitive) so the
  reserved namespace can't be squatted with the wrong provenance.
- Frontend: `tagIsSystemFact(source)` + `tagDisplayName(t)` (`00_lib.jsx`) — the former hides the color-dot/
  lock/remove affordances in `TagsRow` (`25b_tags.jsx`) and drops system tags from the add-tag autocomplete
  list; the latter renders `"Retracted"` instead of the raw reserved tag name, used in both `TagsRow` and the
  sidebar `TagsPanel` (`10e_tagspanel.jsx`) — including the "Filtered to tag …" banner text (passed through
  `onFilterToTag`'s `name` field). `tagSourceLabel`/`tagSourceGroupLabel` gained a `system:retraction` case.

## Key technical detail
The backlog's own open design question — global `tags.import_source` is set once at tag *creation* and can't
say "THIS paper is retracted" if the same tag name is later linked to a non-retracted paper — turned out to be
a non-issue for retraction specifically. Only ONE global tag row (`system:retraction:retracted`) ever exists;
"which papers are retracted" is entirely a property of the **link** (`paper_tags`), not the tag row, exactly
like any other tag. The naming-only path #9 sketched (no schema change, no per-link provenance column) is
sufficient — the earlier worry was solved by not needing a *value-bearing* tag at all, just a boolean
membership tag, the same shape every other tag in the app already is.

## Principles/A-A gate (rule #9)
Directly on-point: this is a findings-subsystem FACT gaining a new *presentation* surface. The design keeps the
fact-vs-candidate distinction and provenance intact by construction — the tag is non-editable (three router
guards + hidden frontend affordances) precisely so it reads as a registry fact, never a label a user could
casually mistake for their own organizational tag or silently delete. The **coexist, don't replace** choice
(leaving `SIGNAL_FILTERS["retraction-retracted"]`, the header chip, and the RETRACTED badge untouched) matches
the backlog's own explicit build directive and the precedent already set for statcheck's signal chip (#31: kept
separate from any unified facet "on purpose... revisit only if it starts reading as redundant"). The reserved-
namespace guard (422 on a user typing `system:...`) is a small but real integrity protection: without it, a
user could pre-create a `system:retraction:retracted`-named tag with `import_source="user"`, and the FIRST time
`apply_retraction` ran its get-or-create, it would silently inherit the wrong (user) provenance for what should
be an authoritative fact — the guard closes that hole before it could ever occur, not after.

## Tests
- `tests/test_retraction.py` (+4): the tag is created on `status="retracted"`, removed on un-retraction,
  NOT created for `"correction"`/`"concern"`, and re-applying is idempotent (no duplicate link on a repeat run).
- `tests/test_tags.py` (+2): a `system:`-sourced tag 409s on color/lock/delete (while an ordinary tag on the
  same paper is unaffected — the guard is scoped correctly); a user-submitted `system:...` name 422s
  (case-insensitive).
- `tests/test_frontend_assembly.py`: one pre-existing literal-substring assertion
  (`test_tag_lock_controls_are_per_paper_and_accessible`) needed updating for the new `!tagIsSystemFact(...)`
  gate inserted into the remove-button JSX condition — a legitimate staleness from the code change, not a
  weakened check (updated to match the new, still-correct source line verbatim).
- Full suite: **1360 passed, 1 skipped** (`pytest -n auto -q`, ~9 min) — up from 1354 (+6).

## Manual verification script
1. Start the app against a library with at least one paper carrying a DOI known to Retraction Watch (or inject
   a fake checker in a scratch script, as the tests do).
2. Run **Retractions ↻** in the library header (unchanged UI). Confirm the existing chip/badge/banner behavior
   is untouched.
3. Open the sidebar Tags tab. Confirm a **"System facts"** group now appears with a single **"Retracted"** tag
   (count = however many papers are flagged). Click it — confirms the same library filter as the header chip.
4. Open a retracted paper's Details pane. Confirm its **Tags** row shows a "Retracted" chip with no color dot,
   no lock button, and no **×** remove button (hover shows the tooltip explaining why it's automatic).
5. Attempt `POST /papers/{id}/tags` with `{"name": "system:test"}` → expect 422. Attempt
   `DELETE /papers/{id}/tags/{retraction_tag_id}` → expect 409.
6. Re-run **Retractions ↻** after the registry stops flagging a paper (or manually clear the record) → confirm
   the "Retracted" tag disappears from that paper and the sidebar count decrements.

## Documentation
- `.claude/docs/data-contracts.md` / `.claude/docs/glossary.md`: `system:{fact}` moved from "reserved, not yet
  produced" to "produced, retraction is the first case."
- `.claude/docs/INCREMENT-BACKLOG.md`: #19 removed (closed → `INCREMENT-BACKLOG-DONE.md`).
- `app/backend/help/help_content.md`: one bullet added to "Checking for retractions" describing the new Tags-tab
  discovery path; `HELP-DOCS-SYNCED` marker moved forward.

## Next
statcheck has an equally-queryable "flagged" fact (`open_science_signals`, same shape) and would be a trivial
second system-fact producer — explicitly left out of this pass since the backlog's #19 entry was retraction-
specific and Cliff hasn't been asked about generalizing. Flagged as a natural, cheap follow-on, not actioned.
