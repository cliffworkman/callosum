# Increment 127 — GRIM + GRIMMER data-consistency calculator

The second GRIM/p-curve "data-detective" METHODS feature (after p-curve, inc 126). **GRIM** (Brown & Heathers,
2017) checks whether a reported mean of integer data is mathematically possible for the sample size; **GRIMMER**
(Anaya 2016 / Allard 2018) extends the check to the SD. Brainstorming chose an **assisted per-value calculator**
(not an auto-scanner): the user enters a specific reported value to check — reliable, honest, and how researchers
actually use GRIM. No extraction, no false flags, inherently non-accusatory.

## Implemented

- **`app/backend/methods/grim.py`** (new; pure stdlib, no scipy/LLM/egress): `grim_test(mean, n, items=1)` and
  `grimmer_test(mean, sd, n, items=1)`.
  - GRIM: reads the decimals from the reported mean string; the achievable means are `K/(N*items)`; consistent iff
    a candidate integer total (floor/ceil/round of `mean*N*items`) rounds (half-up) back to the reported mean.
    Returns the **nearest** achievable means + granularity + a `no_power` flag (`N*items >= 10**decimals`).
  - GRIMMER (**items=1**): GRIM-check the mean, then test whether an **integer sum of squares** lies in the
    SD-implied interval `[s_lo²(n-1)+T²/n, s_hi²(n-1)+T²/n]` **with the parity refinement** `SS ≡ T (mod 2)` (the
    Allard correction over Anaya). Multi-item GRIMMER returns `supported=False` (deferred); GRIM handles items>1.
  - Input bounds (n/items > 0 and capped) → `ValueError`.
- **`POST /methods/grim`** (`routers/methods.py`) — sync, stateless, no DB/egress; `{mean, sd?, n, items}` →
  `{grim, grimmer?}`; bad inputs → **422**.
- **Frontend `app/frontend/js/07_methods_grim.jsx`** — a self-registering METHODS section "Data consistency
  (GRIM)" (order 30, after STATISTICS CHECK): a mean/SD/N/items form → GRIM (✓/✗ + nearest possible) + GRIMMER
  (✓/✗) + the no-power + integer-scale caveats + a credit block with one-click **add to library**. Tokens-only
  CSS. **No `40_app.jsx` change** (self-registered → avoids the 590/600 cap there).

## Key technical detail

- **The parity refinement is what makes GRIMMER correct** — I hand-traced and unit-tested the two `scrutiny`
  reference cases: (5.23, 2.55, **31**) → consistent and (5.23, 2.55, **35**) → inconsistent. For N=35 the only
  integer SS in the SD interval (1178) is even while the total (183) is odd, so the parity check correctly flips
  it to inconsistent (a naive "integer-in-interval" GRIMMER would wrongly pass it).
- **Round-half-up via `Decimal`** (not Python's banker's rounding or float `==`) so the achievability comparison
  matches how researchers round.
- **Assisted/per-value → non-accusatory by construction**: the user picks the value; the tool never scans, ranks,
  or labels a paper or author. Principles gate aligned; A-A no-accusation veto held. Audit `2026-06-25_grim.md`
  PASS. Credit-the-lineage: in-context + add-to-library + THIRD-PARTY-NOTICES (GRIM + GRIMMER + the `scrutiny`
  reference + the Lakens catalog).

## Manual verification

- Hermetic (`tests/test_grim.py`, no egress): GRIM impossible/consistent/decimals/items/no-power/bad-input;
  GRIMMER consistent + the parity-inconsistent N=35 case + GRIM-fail short-circuit + multi-item-unsupported; the
  endpoint (200 + 422). Route-surface updated (`test_health.py`).
- **Headed (no egress)** `.local/visual/drive_inc127_grim.py`: METHODS → Data consistency (GRIM); mean 3.48/N 20
  → GRIM **impossible**, nearest **3.45 / 3.50**; mean 5.23/SD 2.55/N 31 → GRIM + GRIMMER **consistent**;
  add-to-library → "✓ added"; **0 console/page errors, 0 genai requests**.

## Pytest

471 passed, 1 skipped (+12 `test_grim.py`). `ruff` clean; QA surface check 0 uncovered (91 API / 484 FE).
