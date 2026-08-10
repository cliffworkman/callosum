# Increment 469 — Repeated-values checker (item #3 of round 2 — the narrowed #54)

## Implemented

Item #3 of round 2 (memory `callosum-next5-backlog-roadmap-round2`). Backlog #54 was originally framed (by me,
when spinning it off from DEBIT's own scope in inc 467) as "duplicate-publication detection" — comparing a
paper's reported stats against *other* papers/authors. Research before design found that framing was itself an
unverified assumption, and reality splits into two genuinely different things:

- **Duplicate publication / salami-slicing** (redundant publication of overlapping findings across separate
  papers) has **no algorithmic detection method** — the research-integrity literature is explicit that this
  needs expert peer judgment, not software ("There is no software application or algorithm for the detection
  of salami publications... detection... involves expert peer judgment"). **Declined outright** — same
  disposition as #24 (Bayesian ANOVA/regression BF, "declined as a documented finding"), recorded in
  `INCREMENT-BACKLOG.md` §6.
- **`scrutiny`'s actual `duplicate_count`/`duplicate_tally`/`duplicate_count_colpair` functions** (the real
  source of the design doc's "duplication analysis" mention) are something else entirely: within one paper's
  own reported table, counting how often each exact value repeats — a possible data-fabrication smell,
  architecturally in the same single-paper/deterministic family as GRIM/GRIMMER/DEBIT. Unlike those three,
  though, it has **no peer-reviewed method behind it** — confirmed via search: `scrutiny`'s own docs call it
  "a blunt tool... not too informative," and no JOSS/peer-reviewed paper exists for `scrutiny` itself, only a
  standard software citation.

**Confirmed with Cliff:** build the narrow within-paper heuristic, honestly labeled as weaker/more speculative
than GRIM/GRIMMER/DEBIT — no verdict, no pill, no invented threshold, just a transparent frequency breakdown.

### Backend

- `app/backend/methods/duplicate_values.py` (new) — `count_repeated_values(values)`: a bounded (1–500) list of
  entered strings, counted via `collections.Counter`, returning only entries with `count > 1` sorted by count
  descending then value. **No `consistent`/`flagged` field anywhere in the result** — a deliberate omission
  (see Principles note below), unlike `GrimResult`/`GrimmerResult`/`DebitResult`.
- `app/backend/api/routers/methods_duplicate_values.py` (new) — `POST /methods/duplicate-values` (the
  calculator) **and** the paper-aware save/list/delete endpoints, all in one new sibling router. Unlike GRIM/
  DEBIT (whose calculator lives in `methods.py`, with only the *save* endpoints split into a sibling router),
  this one's calculator went straight into its own file: `methods.py` was already at 586/600 lines by the time
  this shipped, so extending it would have repeated the exact line-budget miss CI caught during inc 467/468.
  `app/backend/persistence/schema_duplicate_value_checks.py` (new, table `paper_duplicate_value_checks`,
  migration `0072`) and `duplicate_value_checks_repo.py` (new) mirror `schema_debit_checks.py`/
  `debit_checks_repo.py` exactly.

### Frontend

`app/frontend/js/07_methods_grim.jsx` — a third block in the "Data" section, `DuplicateValuesSection`. A
textarea (not three single-value inputs, since this tool takes a whole column of values) replaces the usual
`.grim-in` fixed-64px input with a new `.duplicate-values-in` (wider, resizable). The result renders as a plain
`<ul>` (`.duplicate-values-list`, monospace, neutral ink color) — **deliberately not** the `.cite-status
verified/flagged` pill GRIM/GRIMMER/DEBIT use, so this tool can't visually borrow their credibility. Credit
line is **text-only** (no `MethodCreditButton` — there is no paper to add to the library, only a software
reference). The section's one shared `<LakensCredit />` moved from `DebitSection` to the end of
`DuplicateValuesSection`, since it now renders once for the whole three-tool "Data" section.

## Key technical detail

The Principles-gate finding that shaped this whole design: GRIM/GRIMMER/DEBIT each rest on a real mathematical
constraint (an achievable mean given N and precision; an achievable SD given a mean; the fully-determined SD of
binary data), so their `consistent`/`impossible` verdict is earned — it's the honest output of comparing a
reported value against what's actually possible. A repeated-value count has no equivalent ground truth: nothing
says how many repeats is "too many" for real data, and the package this is inspired by says so itself ("a blunt
tool"). Giving it the same green/amber pill treatment as the other three would make an unvalidated heuristic
*look* as trustworthy as three validated ones sitting right next to it — the misaligned path named and declined
before writing any frontend code, not caught after the fact.

## Manual verification script

1. Open Methods → Data for any paper — confirm the new "Repeated values" mini-tool below GRIM/GRIMMER and DEBIT,
   with a paste-in textarea (not three small inputs).
2. Paste values with a repeat (`3.45`, `3.45`, `3.45`, `2.10`, `5.00`, one per line) → Check → confirm a plain
   list `3.45 × 3` — no colored pill, no "consistent"/"impossible" wording anywhere.
3. Paste values with no repeats → confirm "No exact value repeats more than once."
4. Confirm the credit line is text-only (no "add to library" button) and the shared Lakens/Crone-&-Green credit
   block now renders once, at the very end of the whole Data section.
5. Save a check, switch papers and back, confirm correct paper-scoping, delete it.

## Verification

Live-verified end-to-end via Playwright against the real 209-paper curated library (server restarted to pick
up the new backend code):
- The three-tool Data section renders correctly; the repeated-values result, credit line, and shared
  `LakensCredit` placement all confirmed via screenshot.
- Check (repeat + no-repeat cases), save, list (via direct `curl` cross-check), and delete all confirmed live,
  zero console errors across every step.
- `pytest tests/test_duplicate_values.py tests/test_duplicate_values_saved.py tests/test_health.py
  tests/test_frontend_assembly.py -q` → **87 passed** (8 + 5 new + 10 + 64 existing, one test-assertion typo of
  my own caught and fixed before this count — "2 values repeat" should have been "3 values repeat" for a
  3-distinct-value test case, a mistake in the test, not the code).
- `python -m ruff check` / `ruff format --check` on every touched file → clean.
- `python tools/check_line_budget.py` (run as the **very last** step before every commit, now the established
  discipline since inc 467/468) → clean; `methods_duplicate_values.py` staying entirely separate from
  `methods.py` was itself the fix that avoided a repeat of that exact miss.
- `python tools/build_frontend.py` → clean build; `07_methods_grim.jsx` 219→303 lines, comfortably under cap.
- `python tools/qa/build_surface_map.py check` → 0 uncovered API/FE surfaces (route 37 extended a third time).
- `alembic upgrade head` against a fresh temp DB and the real library DB (via server restart) both applied
  migration `0072_paper_duplicate_value_checks` cleanly.
- `.claude/security-audits/2026-08-09_repeated-values.md` — PASS, mirrors the DEBIT audit's shape.

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md`: #54 closed — the salami-slicing branch recorded as declined in §6 (no
  algorithmic method exists); the shipped narrow heuristic closed via `INCREMENT-BACKLOG-DONE.md`.
- Memory `callosum-next5-backlog-roadmap-round2`: item 3 closed; item 4 (#55 z-curve) next.
- `.claude/CLAUDE.md`: counter bumped to 469; pytest count updated.
