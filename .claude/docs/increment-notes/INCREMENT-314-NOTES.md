# Increment 314 — retire the left-pane "Review" accordion into Synthesize → Critique

## Context
The user asked whether Review's contents could move into Critique and Review could go away entirely, then
self-corrected: the library-wide retraction check already lives in the Library header, so what's really left is
whether the *paper-level* retraction/findings summary is already part of Critique. Verified at the code level
(not just by inspection) before touching anything: it mostly already was, with one real gap and one real
regression risk, both fixed as part of the move.

## Implemented

**Confirmed redundant, deleted:** `FindingsSection`'s `RetractionBatch` ("Check all papers for retractions") in
`08_methods_findings.jsx` called the exact same `POST /methods/retraction/run` as the Library header's
`RetractionCheckButton` (`10b_libmenus.jsx`) — a live, already-shipped duplicate.

**Confirmed already covered by Critique, kept as-is:** `critical_review.py::_stored_method_signals` (Critique's
Tier-1 backbone) already reads `get_paper_findings(conn, paper_id)["facts"]` — the same FACT rows Review
rendered, including the retraction fact (labeled "Retraction status") — plus `open_science_signals` status rows
Review never even surfaced. Critique's backbone was already a superset of Review's FACT display.

**The one real gap, filled:** `get_paper_findings` also returns `candidates` — reviewable items (e.g. a statcheck
batch flagging N inconsistencies as a `kind:"candidate"` row) driving the library-wide "N to review" badge. Only
`FindingsSection`'s `FindingCard` (Confirmed / Accepted [+reason] / Noted) could act on these. Moved `findingText`/
`FindingCard` verbatim into `08x_methods_critical.jsx`; `CriticalReadPaper` now also fetches
`GET /papers/{id}/findings` and renders a **"Needs your review"** block wired to `onReviewed` →
`ctx.onFindingsChanged()` — already in scope for free, since `40_app.jsx`'s `workspaceCtx = { ...paneCtx, ... }`
spreads every pane callback into every workspace tab's ctx.

**The one real regression, caught and fixed before it shipped:** writing the QA route for this move surfaced
that Critique's generic `method_signals` rendering (`{kind, label, detail}`) drops the retraction fact's
clickable **notice** link (a doi.org registry URL) — `FactMark` used to render it, the generic Tier-1 list
didn't. Since "every claim carries its evidence" is a PRINCIPLES-level commitment, not a nice-to-have, fixed at
the source rather than accepted as a silent loss: `_stored_method_signals` now threads a `notice_url` field
through (`None` for non-fact signals, the fact's own `payload.get("notice_url")` otherwise — never re-derived),
`MethodSignalResponse` (the Pydantic response model) gained the field, and `ScrutinyBackboneView` renders a
**notice** link exactly where a signal carries one.

**Relocated, not deleted:** `RetractionDatabasePanel` (the RW-mirror "N records · as of DATE · Refresh database"
admin view) has no equivalent anywhere else — the Library header button's tooltip only shows last-run info on
hover, not a standing staleness view. Moved into `35_settings.jsx`'s existing **Local maintenance** section,
beside the established "Repair synthesis cache" action (same status-line-+-button recipe); `MetadataSettings`
right below it already said "Setting it here enables the Retraction Watch database download," so this completes
a connection Settings already anticipated. `onRetractionRan` threads from `40_app.jsx` (`refreshRetractionChip`,
already destructured from `useLibrary()`) through `SettingsView` into `LocalMaintenanceSettings`.

**Deliberately not preserved, documented as a trade-off:** `RetractionStatusLine`'s granular per-paper wording
("checked — none found" / "unchecked — no DOI" / "not yet checked") is superseded by two other things: (1) a
"none"/"unchecked" status *does* still surface as its own Tier-1 signal row (the `open_science_signals` table's
status row, independent of whether a FACT exists), just with terser text ("none" vs. "checked — none found"); (2)
Tier-1's one honest-null message ("Nothing surfaced by these checks... read on your own judgment") already covers
the whole-backbone case. A redundant retraction-specific line would have partially duplicated that framing.

**Deliberately left as a minimal, documented leftover, not deleted:** `GET /papers/{id}/retraction` (the endpoint
`RetractionStatusLine` called) has no frontend caller left post-merge. Not deleted — the approved plan was scoped
to "no backend changes," and while the `notice_url` fix was a necessary regression fix, deleting a whole working
endpoint (model + router function + its own tests) was optional cleanup, not required by the user's request.
Flagged here and in `route_39_retraction.md` rather than silently left to be rediscovered as a mystery later.

**Deleted:** `08_methods_findings.jsx` in full, its `registerPaneSection({id:"findings", label:"Review",
paneId:"theory", order:40})` call, and the CSS that only it used (`.findings-section`, `.findings-facts`,
`.fact-mark.retraction*`, `.retraction-status`, `.retraction-batch`, `.retraction-db*`) — `.fact-mark`/
`.fact-mark-card`/`.finding-badge`/`.finding-card` etc. stay (still used by the Library card badge and the moved
`FindingCard`).

## Key technical detail
The `ctx` spread in `40_app.jsx` (`workspaceCtx = { ...paneCtx, ... }`) meant every side-pane-accordion callback
was already reachable from every workspace tab before this increment — the entire candidate-review move needed
zero prop-threading beyond passing `onFindingsChanged` one level down from `CriticalReadSection` into
`CriticalReadPaper`. This is also why the notice-link regression was easy to *find*: writing the QA route forced
a side-by-side comparison of what `FactMark` used to render vs. what the generic signal list renders, surfacing
the gap that a code-only review would likely have missed (the two renderers look superficially equivalent — a
label + a status string — until you check for the one non-textual thing, a link).

## Manual verification (Playwright, this session, against the real ~250-paper testing DB)
1. Restarted the dev uvicorn process (it lacked `--reload`; the backend `notice_url` change needed a fresh
   process to take effect) — confirmed via `GET /health` before continuing.
2. Confirmed 0 console errors and the left-pane accordion headers are exactly `[Axes, Details, Data consistency
   (GRIM), Statistics check, Bayesian statistics, Mixed-model reporting, Meta-analysis reporting, Transparency
   signals]` — no "Review".
3. Selected a real retracted paper (id 114, "RETRACTED ARTICLE: Complex societies precede moralizing gods...").
   Opened Synthesize → Critique: confirmed a "Retraction status" signal row renders with the reason detail *and*
   a working **notice** link (`https://doi.org/10.1038/s41586-021-03656-3`, opens in a new tab) — the exact
   regression fix, confirmed live, not just via the API response shape.
4. Selected a paper with a real unreviewed statcheck candidate (id 6, "Believing is Seeing..."). Opened Critique:
   confirmed a "Needs your review" block rendered the candidate with `show in paper · p.7` + Confirmed/Accepted…/
   Noted. Clicked **Confirmed** → the card flipped to "✓ confirmed" (0 console errors); confirmed via
   `GET /findings/overview` that `unreviewed_count` dropped from 1 to 0 immediately (the library "N to review"
   badge's data updates live, not just on next reload).
5. Opened Settings → Local maintenance: confirmed the "Retraction Watch database" status line + Refresh action
   render correctly beside "Repair synthesis cache" — the real testing DB already had a mirror downloaded
   ("68,318 records · as of 2026-07-20"), rendering the populated state, not just the empty one.

## Pytest
Full suite **1294 passed, 1 skipped** (up from 1293). `tests/test_critical_review.py` extended (the
`{kind,label,detail,notice_url}` shape + a positive `notice_url` passthrough assertion for a retraction fact, and
a negative one confirming statcheck's own signal never carries one). `tests/test_frontend_assembly.py` gained
`test_review_accordion_retired_into_critique` (the file's gone, the moved pieces exist in their new homes, the
dead CSS is gone) and two existing tests updated for the new `CriticalReadPaper` call signature + a stale
assertion removed (it was checking `RetractionBatch`'s own detail-rendering under a misleadingly-named "library
header polish" test — a pre-existing test-labeling issue this session's investigation surfaced, not caused by it).
`ruff check .` / `ruff format --check .` clean; `python tools/check_line_budget.py` clean (348 files, down from
349 — one fewer file). `python tools/qa/build_surface_map.py check`: API 250/250 (hard gate clean); FE
1166/1181 covered, the same pre-existing 15-surface `35a_mypubs.jsx` gap (unrelated).

## Gates
- **QA (#10):** `route_38_findings.md` retired, its assertions folded into `route_67_critical_review.md` (now the
  single home for Tier-1 facts + the findings queue + Tier-2 AI candidates, with explicit assertions that the
  three item kinds stay visually/functionally distinct). `route_39_retraction.md` and `route_74_retraction_watch.md`
  repointed to the new homes (`08x_methods_critical.jsx`, `10_pdf_layer.jsx`/`10b_libmenus.jsx`, `35_settings.jsx`)
  and rewritten to describe the real current flow rather than the retired one. `route_73_workspaces.md`'s
  left-pane description and `fe:` coverage list updated (the dangling `08_methods_findings.jsx` reference
  removed).
- **DESIGN.md (#8):** §5's workspace/pane map corrected (it had also drifted stale on the earlier Work/Extract
  reorg — "Extract" was still listed as a workspace, a pre-existing gap from that increment, fixed here too since
  the same section needed editing anyway); the "AI-usage and findings contracts" paragraph rewritten to describe
  the FACT/CANDIDATE contract as it now actually works, including a stale "METHODS 'Review'" mislabel (Review was
  always `paneId:"theory"`, the left pane, never the right) that predates this increment.
- **Principles (#9):** the notice-link fix is directly a principle-fidelity fix ("every claim carries its
  evidence") — named explicitly rather than treated as an incidental UI polish item.

## Next
None outstanding from this move. `GET /papers/{id}/retraction` is a known, documented, low-priority cleanup
candidate (unused by the frontend, still tested, still correct) — not urgent enough to action without being
asked, per the approved plan's "no backend changes" scoping.
