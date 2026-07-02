# Security audit — Effect-size converter (inc 252, meta-analysis workbench SP1)

**Date:** 2026-07-02
**Feature:** the deterministic effect-size converter — `app/backend/methods/effectsize.py` (pure conversions +
`Conversion` dataclass) + `POST /methods/effect-size` (`routers/methods.py`) + the `08i_methods_effectsize.jsx`
METHODS panel. Hand-enter one study's reported statistics → a common meta-analytic metric (Hedges' g, Fisher's z,
log OR/RR, risk difference) + variance + a 95% CI, via standard cited formulas, with the path shown and every
derivation choice recorded.

**Audit-gate trigger:** #1 (a new API endpoint) + #5 (a net-new feature spanning 3 files). Light review — the feature
is local, stateless (no DB read/write), no external fetch / egress / LLM / migration / new dependency.

## The load-bearing boundary — convert, never synthesize (test-pinned)

This is the reason the feature needed design scrutiny, and it is enforced **structurally**:

- The module converts a **single study at a time** — it defines **no** pooling / heterogeneity / meta-regression /
  bias-inference function, and imports no meta-analysis / stats-aggregation library. Pinned by
  `test_no_aggregation_code_path` (an AST scan: no import of numpy/pandas/statsmodels/sklearn/pymare/metafor; no
  `pool`/`combine`/`aggregate`/`heterogeneity`/`meta_regress`/`funnel`/`eggers` def; `NO_AGGREGATION is True`).
- The endpoint request is one study's inputs. There is no code path that combines two `Conversion`s. Aggregation
  (I²/τ², random-effects pooling, publication-bias inference) is metafor/JASP/RevMan's job — the panel says so and
  hands off.

## Threat review

- **Input validation / boundary (rule #4):** the endpoint body is a Pydantic `EffectSizeRequest` — `family` is a
  strict `Literal` (unknown → 422), `inputs` is a dict of numbers (the module coerces via `_fnum`/`_int_n` and raises
  on non-finite / out-of-range / degenerate values). `MAX_N = 10_000_000` bounds n. The router wraps `convert(...)` in
  `try/except (ValueError, KeyError, TypeError, ArithmeticError)` → **422** (never a 500). No user-supplied pattern /
  path / URL reaches any sink.
- **Injection / SQL (rule #3):** NONE — the endpoint touches no database (stateless, ephemeral). No string-built SQL.
- **Output encoding:** the response is a Pydantic `EffectSizeResponse` (JSON floats + string lists). The panel renders
  `metric`/`value`/`path`/`formula_source`/`caveats`/`choices` as React text nodes (no `dangerouslySetInnerHTML`) —
  no XSS surface.
- **SSRF / external calls:** NONE. The converter makes no network call; it is pure arithmetic over scipy primitives
  (`scipy.stats.norm.ppf` for the CI multiplier). Not the Gemini egress gate (no library text leaves the machine).
- **Data egress:** NONE. Fully local — no LLM, no external fetch, no DB. The egress invariant (#3) is untouched.
- **Resource caps:** each `convert` call is O(1) arithmetic on a fixed field set; no loop over user-sized data, no
  recompute. Degenerate inputs raise immediately (negative variance / non-finite / n<2 / r∉(−1,1) / empty 2×2).
- **Numerical safety:** a zero 2×2 cell triggers the Haldane–Anscombe +0.5 continuity correction (recorded); an
  odds/risk ratio with a genuine zero denominator raises → 422 (no `inf`/`nan` in the response — `_result` asserts a
  finite value + non-negative variance).
- **Supply chain:** no new dependency (scipy already an explicit dep).

## Negative-path checks (from `tests/test_effectsize.py`, hermetic)

- Degenerate inputs raise: zero SD, n<2, r∉(−1,1), an empty 2×2, an OR with a zero cross-product denominator.
- The endpoint returns 422 for a degenerate correlation (r=2.0) and for an unknown family.
- Every result carries `path` + `formula_source` + a finite variance; the no-aggregation AST assert holds.

## Verdict

**Security Audit: PASS.** Local, stateless, deterministic arithmetic; bounded/validated inputs; fail-closed 422; no
external fetch / egress / LLM / migration / new dependency; the never-synthesize boundary is structural + test-pinned.
