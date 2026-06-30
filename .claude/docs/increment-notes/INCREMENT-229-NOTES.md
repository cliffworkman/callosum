# Increment 229 — Citation equity → "Citation concentration" (drop the people-categorizing geography signal + gender framing; rename) + low-coverage flag

A **values rework** of the inc-227/228 citation-equity panel, prompted by the maintainer — and CC reached the same
conclusion independently while looking at the methods. The core point, in the maintainer's words: *"pushing people
into categories to make them easy to see has the same problem as pushing categories onto people to make them more
difficult to be seen."* A citation tool cannot measure who is under-cited by sorting cited authors into a group,
because that re-inscribes the very category the bias runs on. Visibility-by-category (an equity metric) and
erasure-by-category (the bias) are the same machinery pointed in different directions.

The SP1 (inc 227) design had congratulated itself on **rejecting name→gender inference** — then shipped the
**structurally identical move on a different axis**: the **geography ("Global South spread") signal** classified every
cited author's country-of-affiliation into a hardcoded `GLOBAL_NORTH` binary to produce a "Global South share." (And
country-of-affiliation isn't even origin — a Nigerian scholar at MIT is coded "US.") So it had to go too.

## The decision (with the maintainer)

- **Removed** the geography signal + the gender framing. The gender module was never code; it was described as
  "deferred," which kept the rejected idea alive — reframed to **dropped, rejected on principle**.
- **Kept** the 4 signals that measure the *shape of what is cited*, never who wrote it: **self-citation**,
  **reliance on highly-cited work** (Matthew), **venue concentration**, **institutional concentration**.
- **Institutional concentration stays** — the maintainer's explicit call: surfacing Ivory-Tower over-emphasis is
  measuring deference to a power *structure*, not the identity of a person. That's the through-line for the whole
  surviving set: *deference to concentrated power/prestige*.
- **Renamed** the panel **"Citation concentration"** (the surviving signals don't measure "equity").
- **SP2 Find overlooked work is untouched** — it categorizes no one (a local topical embedding cosine).
- **Folded in** the inc-227 experience-pass **low-coverage flag** (a signal computed over <50% of references is shown
  but flagged), since it touches the same files.

## Implemented

- **`app/backend/methods/citation_equity.py`** — removed `_geography` + the `GLOBAL_NORTH` frozenset; `audit_reference_list`
  now builds 4 signals; the module docstring + `audit_reference_list` docstring reframed around concentration + the
  no-people-categorization principle. The **low-coverage flag**: a frozen **`Coverage{text, fraction}`** with a `.low`
  property (`< LOW_COVERAGE = 0.5`); `_coverage(...)` returns it (the human sentence + the *effective* coverage
  fraction — `with_data/total` when a signal needs richer data than a bare record, else `resolved/total`);
  `SignalView.coverage: Coverage` is a **type** change → **zero call-site churn** (all `SignalView(..., _coverage(...))`
  constructions unchanged); `to_dict` emits additive `coverage_fraction` + `low_coverage`.
- **`integrations/openalex/adapter.py`** — `_meta_from_work` **no longer extracts `country_codes`** (the geography
  signal was its only consumer; rule #5 + making the "we don't look at nationality" stance real at the data layer).
  `institutions` (for the institutional signal) is kept.
- **`app/backend/api/routers/citation_equity.py`** — docstring reframed; `SignalModel` += `coverage_fraction`/`low_coverage`
  (built `EquityReportModel(**report.to_dict())`, so the keys flow once declared). **The API path keeps the historical
  `/methods/citation-equity/*` slug** — it's internal, not user-visible; renaming it would churn the frontend/QA/tests
  for no user benefit.
- **`app/frontend/js/08b_methods_citation_equity.jsx`** — section label "Citation equity" → **"Citation concentration"**;
  the header comment, intro, how-to, and the (renamed-in-meaning) note all reframed: *this tool never infers or shows
  the identity of the people you cite — rejected on principle, not deferred*. A **⚠ low coverage (N%)** badge +
  `.low-coverage` class. (The CSS class `.cite-equity-*` names are kept — internal, renaming churns CSS/QA.)
- **`app/frontend/styles.css`** — `.cite-equity-lowcov` (amber `--flag-*` pill — the uncertain/low-confidence STATUS
  color, rule #8) + the bar de-emphasis. Tokens only.

## Key technical detail

**The no-people-categorization stance is now enforced at three layers, not just by docs:** (1) the data layer doesn't
even *extract* nationality (`country_codes` gone from `_meta_from_work`); (2) a behavioral test
(`test_no_people_categorization_in_core`) injects `gender`/`race`/`sex`/`country_codes` into the inputs and asserts
the output is byte-identical (they're never read); (3) a **static guard** (`test_analyzer_source_has_no_people_categorization`)
greps the analyzer source and fails if it ever keys on `gender`/`sex`/`race`/`country_code`/`GLOBAL_NORTH`/`global_south`.
A future contributor cannot re-introduce people-categorization without a test going red.

## Manual verification script

1. `HF_HUB_OFFLINE=1 python .local/visual/drive_inc229_concentration.py` — seeds a paper whose OpenAlex record lists
   10 `referenced_works` but only 3 resolve (the rest 404) ⇒ every surviving signal is computed over 3 of 10 = 30%.
   Headed: METHODS → **Citation concentration** (asserts the old "Citation equity" label is gone) → **Run audit** →
   asserts **exactly 4 signals**, **0 "geography"/"Global South"/"high-income" mentions anywhere on the page**, a
   **⚠ low coverage (30%)** badge with the number still rendered, and the never-categorize-people principle note.
   Expect `PASS`, 0 console/page/genai.

## Pytest

`HF_HUB_OFFLINE=1 python -m pytest tests/test_citation_equity.py tests/test_overlooked_work.py -q` → **24 passed** (14
citation-concentration + 10 overlooked). Full suite **819 passed, 1 skipped** (net 0 vs inc 228: −the geography test,
+the low-coverage test). QA surface **165/165 API + 727/727 FE, 0 uncovered** (`route_51` rewritten — 4 signals, the
no-people-categorization veto incl. geography). No migration, no new dependency; the egress posture is unchanged and
*narrowed* (country/nationality is no longer extracted at all).
