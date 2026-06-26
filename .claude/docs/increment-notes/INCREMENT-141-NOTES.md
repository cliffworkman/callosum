# Increment 141 — statcheck: connect "this paper is flagged" → the specific result (experience-pass fix)

## Implemented

The first **fix** produced by the inc-140 end-user experience pass. The dogfood (the deadline-citer persona vs
statcheck) found that "this paper is flagged" and "here is the specific result that doesn't recompute" were two
good halves that **didn't link**: the METHODS pane defaults to **Details**, and the "⚠ N flagged" chip → filter
left you on Details, not Statistics check, with whatever paper was already selected. This increment connects them
(backlog sub-findings **(a) + (c)**), frontend-only:

- **`40_app.jsx` — the flagged chip now lands you on a flagged paper's check.** `showStatcheckFlagged` (the
  "⚠ N flagged" chip + "Show flagged papers") now also `setMethodsOpen("statcheck")` (opens the Statistics check
  section) and sets a **`pendingSelectTopRef`** instead of clearing the selection. The `/papers` effect, when the
  *filtered* (flagged) list loads, selects that list's **top** paper — so the section lands on a **flagged** paper,
  not the stale pre-filter selection. (`methodsOpen` was added to `paneCtx` so a section can tell when it's open.)
- **`06_methods_statcheck.jsx` — the per-paper check auto-runs when its section is open.** `StatcheckPaper` takes
  an `active` prop (`ctx.methodsOpen === "statcheck"`) and an effect auto-runs the check when
  `active && hasText && idle` — so a (flagged) paper's per-test rows (reported vs recomputed *p*, page link) appear
  with **no manual "Check statistics" click**. Gated on `active`, so the mounted-but-hidden section never runs;
  re-runs per paper.

Net: the deadline citer clicks "⚠ N flagged" → the flagged paper's specific inconsistent result is right there.

## Key technical detail

**The stale-list race (the bug behind the first failed headed run).** Clearing the selection (`setSelected(null)`)
and changing the filter in the same handler let the inc-138 auto-select fire on the **old** (pre-filter) list and
re-pick the clean top paper before the flagged list loaded. The fix is a **deferred-select ref** resolved inside
the `/papers` fetch callback, so the top-of-list selection always uses the freshly-loaded (flagged) list. inc-138's
"only when `selected == null`" rule is untouched (no general "re-select on filter" behavior change).

## Manual verification script

`python .local/visual/drive_inc141_statcheck_path.py` (free port + own-process-alive; seeds a clean top paper +
a flagged paper — an inconsistent `t(28)=2.10, p=.001` in a chunk + the statcheck signal). On load the clean paper
is auto-selected; clicking the "⚠ 1 flagged" chip → the **Statistics check** section opens, **THE FLAGGED STATS
PAPER** is auto-selected, and its inconsistent row **auto-shows** (`computed p = 0.0449` vs reported `.001`) with no
manual click. **PASS** — 0 console errors, 0 page errors, 0 genai hits.

## Gates

- **Experience pass (#11):** this *is* the deliverable of a pass — the persona-agent finding, fixed. Re-walked the
  citer path: chip → flagged paper's specific result, no hunting. Remaining sub-findings (b/d/e) stay in the backlog.
- **No Principles trigger** — UX wiring; the counts/rows are unchanged (still a list to review, never a verdict;
  per-row page-open at region precision — coordinate honesty intact).
- **Rule #10** — no new API/FE surface (reuses the existing chip, section, and per-paper endpoint); surface map
  unchanged (106/106 API + 530/530 FE, 0 uncovered). `route_33_methods_statcheck.md` notes the new flagged→detail path.

## Pytest

**519 passed, 1 skipped** — unchanged (frontend-only). `ruff` clean; build + assembly green.

## Next (queued)

- Remaining statcheck sub-findings (b) on-paper entry point [design], (d) deep-link to the specific test, (e) the
  flagged-vs-to-review duality [design].
- Gap-finder followed-authors / similarity ranking; a cadence auto-refresh.
- **Watch (rule #1):** `clustering/my_publications.py` at **594/600**.
