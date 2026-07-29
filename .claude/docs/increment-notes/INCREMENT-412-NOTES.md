# Increment 412 — axis-review list no longer jumps to the top on ✓/✕

## Implemented

A third bug report (same colleague, Isabella Bobrow): reviewing candidate papers in an axis and clicking ✓
(confirm) or ✕ (remove) "shoots me back up to the top of the list, which is a little disorienting." Cliff had
independently noticed the same thing already. Low priority per the reporter ("literally not a big deal but
since this is beta"), but cheap to fix once traced.

Root cause: `AxesPanel`'s `loadDetail(id)` (`app/frontend/js/15_axes.jsx`) unconditionally reset
`details[id]` to `{status: "loading", papers: []}` at the *start* of every fetch — including the tiny refetch
that `confirmPaper`/`removePaper` trigger after a single row's decision. `AxisItem` (`js/15b_axis_card.jsx`)
renders a one-line "Loading…" placeholder while `status === "loading"`, so the whole (possibly long) paper
list would momentarily collapse to one line, then reflow back to full height once the refetch resolved. That
collapse-then-reflow is what reset the scroll position — the browser has no reason to preserve a scroll offset
into content that briefly didn't exist.

Fix: `loadDetail` now only shows the "Loading…" placeholder on a genuine first load. When a detail is already
`"ready"` (i.e. this is a refresh, not an initial fetch), it flips to a new `"refreshing"` status and *keeps
the existing papers array* rather than clearing it — so the already-rendered list stays exactly as it is,
in place, until the new data arrives and React patches only what changed (one row's status/removal), instead
of unmounting and remounting the whole list. `AxisItem`'s render condition and its `readyPapers`/
`uncertainCount` derivation were both updated to treat `"refreshing"` the same as `"ready"` (show the list;
count it), so nothing visually blanks during a refresh.

This also quietly improves the collapse→reopen case: reopening an axis you'd already expanded earlier in the
session now shows the previously-loaded list instantly while silently revalidating in the background, instead
of flashing "Loading…" again every time (the same code path, no separate change needed).

## Key technical detail

`loadDetail` decides "first load" vs. "refresh" purely from whether `details[id]` already exists with
`status === "ready"` — it does not track *why* it was called (confirm, reject, re-score, editor save all funnel
through the same function). A full re-score can change the paper list substantially; the brief window where the
pre-rescore list is still showing while the new one is in flight is an acceptable, honest trade for scroll
stability — the data is never wrong, just up to one round-trip stale for a moment, exactly as it always was
during the old "Loading…" placeholder window too.

## Manual verification

- Traced directly from the reporter's screenshot (the axis "uncertain" candidate list with ✓/✕ per row) to the
  exact `loadDetail`/`AxisItem` code path — not a guess at a plausible-sounding cause.
- `python tools/build_frontend.py` — rebuilt `callosum-app.html` from the two changed chunks.
- `pytest tests/test_frontend_assembly.py tests/test_axes.py -q` → **85 passed** (no `.status` string is
  asserted directly in the existing suite, so correctness here rests on tracing every consumer of
  `details[id].status`, not on a test asserting the fix's behavior — a gap worth a future frontend test if
  this codebase adds any JS-level test harness).
- This is a JS-only change (no Python touched), so it doesn't shift the full-suite Python count; the full
  `pytest -n auto -q` run for this session (from the sibling inc-411 fix) was **1683 passed, 1 skipped**.
- Manual UI check (start the app, expand an axis with uncertain candidates, click ✓/✕, confirm the list stays
  in place — not scripted, but recommended before considering this fully closed per CLAUDE.md's UI-change
  verification protocol) is still owed; flagging as the one open item for this fix.

## Pytest

`tests/test_frontend_assembly.py` + `tests/test_axes.py`: 85 passed.
