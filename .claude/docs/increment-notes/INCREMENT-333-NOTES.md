# Increment 333 — Backlog #27: statcheck reads test statistics reported as a bound

## Context
Continuing through the backlog after #30 and #45. #27 ("more statcheck test forms — test-stat `<`/`>`
comparisons, results reported in tables") was framed in the backlog as a "regex-extension, low effort"
item. Reading the existing implementation first showed the comparator extension is genuinely low-effort to
*wire up*, but getting the **consistency math right** for an inequality-reported statistic needed real care —
this is exactly the kind of place a careless implementation could produce a false "inconsistent" flag on a
legitimately-reported null result (e.g. `F(1,44) < 1, p > .05`, a very common way authors report a clearly
non-significant effect without giving an exact F), which would be a real honesty violation (PRINCIPLES: never
an accusation; a signal, not a verdict), not just a bug.

## Implemented
`app/backend/methods/statcheck.py`:
- The test-statistic comparator is no longer hardcoded to `=` — a new `_STAT_COMP` group (mirroring the
  existing `_P` pattern's comparator) accepts `<`/`>`/`=`/`≤`/`≥` before the reported statistic, for all five
  test-type patterns (t/F/r/chi2/z).
- **`_classify`** now branches: the `=` case is completely unchanged (byte-for-byte the same code path as
  before); a `<`/`>` case delegates to new **`_classify_stat_bound`**.
- **`_classify_stat_bound(test_type, a, stat_comp, p_comp, p_value, p_dec, df1, df2)`**: since every test
  statistic here has p monotonically decreasing in |stat|, a reported bound implies a **p-value interval**
  rather than a point — `<` (true |stat| smaller) → true p is LARGER than p(bound), interval `(p(bound), 1]`;
  `>` → true p is smaller, interval `[0, p(bound))`. Consistency reuses the **existing** `_p_consistent`
  helper unchanged — the same "does at least one valid true value exist consistent with the reported claim"
  philosophy the `=` path already applies via its rounding interval, just fed a differently-derived interval.
  Never produces `"decision-error"` (that classification needs a point estimate this input doesn't have) —
  only `"consistent"` or `"inconsistent"`, and only the latter when **no** valid value in the reported bound's
  range could produce the reported p (an ambiguous case — some values would, some wouldn't — is left
  unflagged, matching the codebase's existing conservative stance elsewhere, e.g. `_reported_significant`'s
  explicit "ambiguous → None" handling).

## Verifying the math (not guessed)
Reference p-values were computed directly via scipy before writing any test assertion:
- `F(1,44)` at `F=1` → `p ≈ 0.3228` (one-sided, matching `recompute_p`'s existing F convention).
- `t(28)` at `t=1` (two-tailed) → `p ≈ 0.3259`.
- `t(28)` critical value for `p=.05` (two-tailed) → `t ≈ 2.048`.
- `t(28)` at `t=3` (two-tailed) → `p ≈ 0.00562`.

These grounded six new test cases: an unambiguously-consistent bound (`F(1,44) < 1, p > .05`), an
unambiguously-inconsistent one (`t(28) < 1, p < .01` — impossible for ANY value under the bound, not just
improbable), a genuinely **ambiguous** one deliberately left unflagged (`t(28) < 3, p > .05` — since
`t_crit(.05, df=28) ≈ 2.048 < 3`, some values in `(0,3)` give `p ≤ .05` and others don't — the reported claim
isn't provably wrong), a `>`-bound consistent case, a confirmation that this path never emits
`decision-error`, and a regression check that the pre-existing `=` path is byte-for-byte unaffected.

## Tests
- `tests/test_statcheck.py` (+6, all using the exact reference values above): see "Verifying the math."
- 34 passed (`test_statcheck.py` + `test_pcurve.py`, which shares `StatResult`) — confirmed no regression in
  the pcurve module, which reuses the statcheck extractor for significant p-values.
- Full suite re-run pending (background) for the final count.

## Documentation
- `app/backend/help/help_content.md`'s "Checking statistics (statcheck)" section gained one sentence describing
  the new bound-form coverage and its ambiguous-case handling — honest about what gets flagged and what doesn't.
- **Deliberately NOT moved**: the `HELP-DOCS-SYNCED` marker in `.claude/changes.md`. Reviewing the help corpus
  for this fix surfaced that the "Citing in LibreOffice Writer" section is now substantially stale relative to
  this session's LibreOffice adapter work (the composer, beyond-library suggest, Edit Citation, document
  diagnostics — none of it reflected there). That's a much bigger rewrite than this narrow fix and is flagged
  as its own follow-up rather than silently folded in or silently ignored by moving the marker past it.

## Gates
- **Security audit:** not triggered — no new endpoint, no egress, no file-write path; a pure local computation
  change to an already-audited, deterministic Methods producer.
- **Principles/A-A (rule #9):** directly on-point — the whole design of `_classify_stat_bound` (existence-based
  consistency, never guessing at ambiguous cases, no new `decision-error` claim without a point estimate) is an
  application of "signal not verdict" and "never an accusation." Explicitly considered and rejected: any design
  that would flag "inconsistent" merely because a bound doesn't pin down an exact p — that would be exactly the
  kind of overclaiming rule #9 exists to catch.

## Next
"Results reported in tables" (the other half of #27) remains open — a structurally different problem
(table-aware PDF text extraction, not a regex extension) and out of scope for this pass. The LibreOffice
help-doc staleness flagged above is a real, larger follow-up item, not yet actioned.
