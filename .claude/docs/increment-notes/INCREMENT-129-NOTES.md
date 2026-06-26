# Increment 129 — multi-item GRIMMER

Completes inc 127's GRIMMER: it now supports **multi-item scales** (`items > 1`), not just single-item. Small,
focused extension of `grimmer_test`.

## Implemented

- **`app/backend/methods/grim.py` — `grimmer_test` generalized to `items > 1`.** The multi-item math: each
  person's score is the mean of `items` integer items, so over all `N*items` item responses the total `T` is an
  integer and the variance of the N person-scores is `(Σc_i² − T²/N) / (items² · (N−1))` (where `c_i` is person
  i's integer item-sum). So the achievable integer `Σc_i² = SD² · (N−1) · items² + T²/N`, checked for an integer
  in the SD-rounding interval **with the same parity refinement** `Σc_i² ≡ Σc_i = T (mod 2)`. `items=1` is the
  special case (`items²=1`) — the single-item code is unchanged in effect. The `items != 1 → supported=False`
  guard is removed; `supported` is now always `True`.
- **Frontend `07_methods_grim.jsx`:** removed the now-dead `!d.grimmer.supported` caveat branch (rule #5); the
  GRIMMER row renders for any `items`.
- **Help corpus:** the GRIMMER line now reads "single- or multi-item scales (set items)".

## Key technical detail

- **The same parity refinement carries to multi-item** — `c_i` integer ⇒ `c_i² ≡ c_i (mod 2)` ⇒ `Σc_i² ≡ T`.
  The only change from single-item is the **`items²` factor** on the variance term and taking the total over
  `N*items` responses. Derived from first principles and **validated against the scrutiny reference**
  (mean 2.74, SD 0.96, N 63, items 2 → consistent).
- The simplified analytic matches the reference and **errs toward leniency** (it doesn't add the per-item-range
  bound on the minimum sum of squares), so any miss is a *missed* inconsistency, never a false "impossible" — the
  safe, non-accusatory direction.

## Manual verification

- `tests/test_grim.py`: multi-item consistent (the scrutiny reference) + a multi-item GRIM-fail → inconsistent +
  the items=2 endpoint path; the single-item cases unchanged. Full pytest **472 passed, 1 skipped**. `ruff` clean;
  build + assembly green. (The UI render path for a GRIMMER verdict was headed-verified in inc 127 and is
  unchanged — items>1 now reaches the same pill.)

## Pytest

472 passed, 1 skipped (+1 net: replaced the "unsupported" test with two multi-item tests).
