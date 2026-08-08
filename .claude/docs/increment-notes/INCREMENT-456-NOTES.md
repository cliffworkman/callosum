# Increment 456 — Empirically calibrate the self-citation field-baseline N (backlog #25/#37)

## Implemented

Citation Concentration's self-citation signal (`app/backend/methods/citation_equity.py::_self_citation`) has
always hardcoded `field_pct=None` — "there is no field baseline for self-citation" — while the other 3 signals
(Matthew effect, venue concentration, institutional concentration) all show the paper's value next to a field
comparison. The backlog carried this as "needs per-field-paper reference fetches — a cost/design call" for a
long time.

Investigating directly overturned part of that framing: a field-sample paper's own `referenced_works` and its
authors' real OpenAlex **ids** (not just display names) are already present in the same, already-cached
`fetch_field_sample` response — `_meta_from_work` just never extracted them. The real, uneliminable cost is one
level deeper: determining whether a field-sample paper cites itself needs to know who wrote *its* references,
and a cheap version of that check exists (a filtered, count-only OpenAlex query) but doing it for all 200 papers
in the field sample is real added cost that scales with how many field papers get checked.

Rather than guess a "small enough" N, this increment builds the reusable primitive plus a calibration tool and
runs a real empirical study (mirroring stimulus-norming methodology: gather a larger pilot, bootstrap-resample
smaller subsets to find where the estimate stabilizes) to pick N from real data. **Wiring the chosen N into the
shipped `_self_citation()` signal is a deliberate, separate follow-up** — not done in this increment.

### New reusable primitive

`OpenAlexClient.fetch_self_citation_hit_count(conn, *, ref_ids, author_ids)` — "of these reference ids, how many
were authored by any of these author ids" — one count-only `filter=openalex_id:{chunk},authorships.author.id:
{author_ids}` request per chunk of ≤50 ref ids (`meta.count` only, no metadata payload), summed, cached,
fail-closed to `None` (never a silently-wrong partial zero). This is the exact mechanism the eventual production
signal will call — the study is a real dry-run of it, not throwaway code.

### The proactive split (a real, necessary side effect)

`integrations/openalex/adapter.py` was already at 599/600 lines with zero headroom. Rather than grow past the
cap, it was split into three modules:
- **`integrations/openalex/work_meta.py`** — the pure OpenAlex-work → meta-dict mapping layer (`_meta_from_work`,
  `_meta_with_abstract`, `_reconstruct_abstract`, `_csl_from_work`), plus `OPENALEX_PROVIDER` and the tiny
  `_cached_response` helper. No I/O beyond a cache read; no dependency on `adapter.py` or `field_sample.py`.
- **`integrations/openalex/field_sample.py`** — a `FieldSampleMixin` class (`fetch_field_sample`,
  `fetch_topic_candidates`, `fetch_works_by_ids`, and the new `fetch_self_citation_hit_count`). A **mixin**, not
  free functions: these methods rely on `OpenAlexClient`'s own instance state
  (`self.fetcher`/`self.mailto`/`self.timeout`/`self.cache_engine`) and private helpers (`self._store`,
  `self._polite_params`, `self._headers`) via ordinary Python method resolution — `OpenAlexClient(
  FieldSampleMixin)` keeps every existing call site (`client.fetch_field_sample(...)` etc.) completely
  unchanged. Imports only from `work_meta.py`, never from `adapter.py` — no circular import.
- **`adapter.py`** itself — now ~330 lines — re-exports everything external callers previously imported directly
  (`_meta_from_work`, `_meta_with_abstract`, `_csl_from_work`, `OPENALEX_PROVIDER`) so `beyond_library.py` and 3
  test files needed zero changes.

### The calibration tool + study

`tools/citation_concentration_study.py` (a `validation_harness.py`-shaped dev script, not a shipped feature):
resolves each of 6 field names to a real OpenAlex Topic id via a live `/topics?search=` call, fetches a 200-paper
field sample per field against a throwaway scratch SQLite DB (never the real app DB), computes each field
paper's own self-citation rate via the new primitive, persists raw per-paper results to a resumable JSONL file,
then bootstrap-resamples (1,000 reps, without replacement) across a grid of candidate N to show how the SE/95%-CI
width of the field-average estimate shrinks as N grows. Self-paced (~3 req/s) since `OpenAlexClient` has no
built-in throttle. The report **does not itself declare a single "correct" N** — signal, not verdict, applied to
our own tooling decisions too.

## Key technical detail

**The real study surfaced two genuine findings the backlog's framing didn't anticipate:**

1. **Population self-citation rates vary ~3x by field** — Cognitive Neuroscience 5.0%, Public Health 5.6%,
   Social Psychology 7.0%, Machine Learning 7.9% (at N=62), Astrophysics 12.6%, Genetics 16.0%. This confirms
   per-field baselines (already the design) are the right call — a flat constant baseline would have been wrong
   for most fields.
2. **"Computable" coverage varies hugely by field** — not every field-sample paper has both a usable reference
   list and author ids. Cognitive Neuroscience yielded only 36/200 computable papers (18%); Genetics and Social
   Psychology yielded ~148/200 (74%). This is a load-bearing implementation constraint for the eventual
   production wiring: N must be a **target computable count**, and the code has to keep checking raw field-sample
   papers (up to the 200 cap) until it reaches N or runs out — not simply "check the first N papers," which
   would silently starve a low-coverage field like Cognitive Neuroscience.

**Stabilization did not generalize to one clean N across fields.** Using a ±5-percentage-point 95% CI width as a
reasonable bar for a descriptive comparison value (not a precision scientific estimate — the sibling signals
carry no CI treatment at all), the N needed to cross that bar ranged from ~25 (Cognitive Neuroscience, Public
Health) to ~75 (Genetics) — Genetics needs roughly 3x the sample of the easiest fields for the same absolute
precision. **N=40 was chosen deliberately** — it crosses Social Psychology's own stabilization point (CI width
0.0443 at N=40) — a disclosed, reasoned judgment call, not a hidden default; Genetics stays wider at this N
(~CI width 0.075) and that's an accepted, honest limitation for a descriptive field-baseline bar.

**The frontend needs zero changes for the eventual production wiring** — confirmed by reading
`08b_methods_citation_equity.jsx`: `field_pct` is already rendered generically for any signal where it's
non-`None` (`s.field_pct != null && <CiteEquityBar label="Field" pct={s.field_pct} kind="field" />`). Wiring N=40
into `_self_citation()` is a pure backend change.

## Housekeeping / gates

- **No dedicated security-audit file** — a one-off dev-tooling script in `tools/` (the `validation_harness.py`
  precedent), not a new shipped API/UI surface; egress is the same already-audited public OpenAlex metadata class
  every other citation-equity signal already uses, never the Gemini gate.
- `.claude/docs/INCREMENT-BACKLOG.md`: #25/#37 updated with the calibration finding and N=40 — **not closed**;
  closes when the production signal actually ships.
- `.claude/CLAUDE.md`: counter bumped to 456.

## Manual verification script

1. `python -m tools.citation_concentration_study --fields "Cognitive Neuroscience" --sample-size 20 --reps 50`
   (a small, cheap live run) — confirm it resolves a real topic id, fetches a real field sample, computes a
   handful of real self-citation rates, and writes `.local/citation-concentration-study/report.md`.
2. Read the report — confirm the population mean + the SE/CI-width table render sensibly.
3. Confirm `.local/citation-concentration-study/` never appears in `git status` (gitignored).

## Verification

- `pytest tests/test_citation_equity.py tests/test_openalex_adapter.py tests/test_overlooked_work.py tests/test_gapfinder.py -q`
  → **68 passed** (4 new: `fetch_self_citation_hit_count` counting/validation, chunking-and-summing, fail-closed
  on a partial chunk failure, and caching).
- `python tools/check_line_budget.py`: clean (498 files; `adapter.py` 333, `work_meta.py` 208,
  `field_sample.py` 192 — all comfortably under the cap, with headroom).
- `ruff format` + `ruff check`: clean.
- Real live run: 6 fields, up to 200 raw field-sample papers each, real OpenAlex data — see `report.md`
  (gitignored, not committed) and the summary above.

## Rollback

Revert `adapter.py`/`work_meta.py`/`field_sample.py` to the pre-split single file (git history has the exact
prior state); remove `tools/citation_concentration_study.py` and its 4 new tests in `test_citation_equity.py`.
No schema/migration, no production behavior change — `_self_citation()`'s `field_pct` is still `None` after this
increment; nothing about the shipped citation-equity signal changed.
